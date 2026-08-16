"""Lift a fitted GaussianVolume JSON asset into the 7DRGS PLY layout."""

from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path


SH_C0 = 0.28209479177387814
PLY_PROPERTIES = [
    "x", "y", "z", "nx", "ny", "nz",
    "f_dc_j", *(f"f_rest_j_{i}" for i in range(15)),
    "opacity", "scale_0", "scale_1", "scale_2",
    "rot_0", "rot_1", "rot_2", "rot_3",
    "mu_t", "mu_d_0", "mu_d_1", "mu_d_2",
    *(f"chol_diag_{i}" for i in range(7)),
    *(f"chol_offdiag_{i}" for i in range(21)),
    "lambda_t", "lambda_d",
    "f_dc_t", *(f"f_rest_t_{i}" for i in range(15)),
]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def _transpose(m: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*m)]


def _rotation_matrix(quaternion: list[float]) -> list[list[float]]:
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm <= 1e-12:
        raise ValueError("zero-length quaternion")
    x, y, z, w = (value / norm for value in (x, y, z, w))
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def _spatial_cholesky_gl(
    scales_cm: list[float], quaternion: list[float]
) -> list[list[float]]:
    if len(scales_cm) != 3 or min(scales_cm) <= 0.0:
        raise ValueError("scale must contain three positive values")
    rotation = _rotation_matrix(quaternion)
    covariance_ue = _matmul(
        _matmul(rotation, [[(s / 100.0) ** 2 if i == j else 0.0
                            for j, s in enumerate(scales_cm)] for i in range(3)]),
        _transpose(rotation),
    )
    # UE = P * GL, P is symmetric and orthogonal: GL = P * UE * P.
    p = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, -1.0, 0.0]]
    covariance_gl = _matmul(_matmul(p, covariance_ue), p)

    l = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(i + 1):
            value = covariance_gl[i][j] - sum(l[i][k] * l[j][k] for k in range(j))
            if i == j:
                l[i][j] = math.sqrt(max(value, 1e-12))
            else:
                l[i][j] = value / l[j][j]
    return l


def _inverse_softplus(value: float) -> float:
    return math.log(math.expm1(max(value, 1e-8)))


def _logit(value: float) -> float:
    value = min(max(value, 1e-6), 1.0 - 1e-6)
    return math.log(value / (1.0 - value))


def _make_row(
    gaussian: dict,
    opacity_scale: float,
    j_value: float,
    tview_value: float,
    condition_strength: float,
) -> tuple[float, ...]:
    center = gaussian["center"]
    scale = gaussian["scale"]
    rotation = gaussian["rotation"]
    sigma_t = float(gaussian["sigma_t"])
    if (
        len(center) != 3
        or len(rotation) != 4
        or not all(math.isfinite(float(v)) for v in (*center, *scale, *rotation, sigma_t))
    ):
        raise ValueError("invalid Gaussian record")

    # Inverse of the runtime's PLY GL-metres -> UE-centimetres conversion.
    xyz_gl = [center[0] / 100.0, -center[2] / 100.0, -center[1] / 100.0]
    l = _spatial_cholesky_gl(scale, rotation)
    spatial_diag = [l[i][i] for i in range(3)]
    chol_diag = [*spatial_diag, 0.1, 1.0, 1.0, 1.0]
    chol_offdiag = [0.0] * 21
    chol_offdiag[0] = l[1][0] / spatial_diag[1]
    chol_offdiag[1] = l[2][0] / spatial_diag[2]
    chol_offdiag[2] = l[2][1] / spatial_diag[2]

    # Match the central optical depth of the volumetric Gaussian along a
    # representative (geometric-mean) path through its covariance.
    path_sigma_cm = math.prod(scale) ** (1.0 / 3.0)
    tau = max(sigma_t, 0.0) * math.sqrt(2.0 * math.pi) * path_sigma_cm
    alpha = 1.0 - math.exp(-opacity_scale * tau)

    row = [
        *xyz_gl, 0.0, 0.0, 0.0,
        (j_value - 0.5) / SH_C0, *([0.0] * 15),
        _logit(alpha),
        *(math.log(max(value / 100.0, 1e-6)) for value in scale),
        1.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
        *(math.log(value) for value in chol_diag),
        *chol_offdiag,
        _inverse_softplus(condition_strength),
        _inverse_softplus(condition_strength),
        (tview_value - 0.5) / SH_C0, *([0.0] * 15),
    ]
    if len(row) != len(PLY_PROPERTIES):
        raise AssertionError(f"PLY row/property mismatch: {len(row)} != {len(PLY_PROPERTIES)}")
    return tuple(float(value) for value in row)


def convert(
    source: Path,
    output: Path,
    opacity_scale: float = 1.0,
    j_value: float = 1.0,
    tview_value: float = 0.0,
    condition_strength: float = 1e-6,
) -> dict:
    if opacity_scale <= 0.0:
        raise ValueError("opacity scale must be positive")
    if not 0.0 <= tview_value <= 1.0 or j_value < 0.0:
        raise ValueError("J must be non-negative and TView must be in [0,1]")
    if condition_strength <= 0.0:
        raise ValueError("condition strength must be positive")

    payload = json.loads(source.read_text(encoding="utf-8"))
    gaussians = payload.get("gaussians")
    if not isinstance(gaussians, list) or not gaussians:
        raise ValueError("source JSON has no gaussians")
    rows = [
        _make_row(g, opacity_scale, j_value, tview_value, condition_strength)
        for g in gaussians
        if math.isclose(float(g.get("omega", 0.0)), 0.0, abs_tol=1e-6)
    ]
    if not rows:
        raise ValueError("source JSON has no Gaussian base primitives")

    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment lifted_from {source.as_posix()}",
        f"comment opacity_scale {opacity_scale}",
        "element vertex " + str(len(rows)),
        *(f"property float {name}" for name in PLY_PROPERTIES),
        "end_header",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    record = struct.Struct("<" + "f" * len(PLY_PROPERTIES))
    with output.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        for row in rows:
            stream.write(record.pack(*row))
    return {
        "source": str(source),
        "output": str(output),
        "point_count": len(rows),
        "opacity_scale": opacity_scale,
        "j_value": j_value,
        "tview_value": tview_value,
        "condition_strength": condition_strength,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--opacity-scale", type=float, default=1.0)
    parser.add_argument("--j", type=float, default=1.0)
    parser.add_argument("--tview", type=float, default=0.0)
    parser.add_argument("--condition-strength", type=float, default=1e-6)
    args = parser.parse_args()
    print(json.dumps(convert(
        args.source,
        args.output,
        args.opacity_scale,
        args.j,
        args.tview,
        args.condition_strength,
    ), indent=2))


if __name__ == "__main__":
    main()
