"""Build the frozen-geometry S3 transport A/B/C diagnostic assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from plyfile import PlyData

from bake_directional_tau_basis import (
    ASSET_AXIS_FROM_UE,
    _axis_tau,
    _grid_coordinates,
)
from grid_to_7drgs import COMPACT_PROPERTIES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_rows(path: Path) -> np.ndarray:
    vertices = PlyData.read(path, mmap="r").elements[0].data
    if tuple(vertices.dtype.names or ()) != COMPACT_PROPERTIES:
        raise ValueError(f"{path} is not the expected 16-float compact layout")
    return np.stack(
        [np.asarray(vertices[name], dtype="<f4") for name in COMPACT_PROPERTIES],
        axis=1,
    )


def _write_rows(
    path: Path,
    rows: np.ndarray,
    source: Path,
    grid: Path,
    variant: str,
    angular_sigma: float,
) -> None:
    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment source_compact {source.as_posix()}",
        f"comment reference_grid {grid.as_posix()}",
        f"comment diagnostic_variant {variant}",
        f"comment spatial_points {len(rows)}",
        "comment light_lobes 6",
        "comment compact_static_transport 1",
        "comment compact_shared_opacity 1",
        f"comment angular_sigma {angular_sigma}",
        "comment direct_transport_ambient 0",
        "comment asset_axis_from_ue 0 1 5 4 3 2",
        f"element vertex {len(rows)}",
        *(f"property float {name}" for name in COMPACT_PROPERTIES),
        "end_header",
        "",
    ]
    with path.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        stream.write(np.asarray(rows, dtype="<f4").tobytes(order="C"))


def _percentiles(values: np.ndarray) -> dict[str, list[float]]:
    result = np.percentile(values, (0, 1, 50, 95, 99, 100), axis=0)
    return {
        name: [float(value) for value in row]
        for name, row in zip(("p0", "p1", "p50", "p95", "p99", "p100"), result)
    }


def build(
    source: Path,
    grid_path: Path,
    output_dir: Path,
    density_scale: float,
    voxel_cm: float,
    angular_sigma: float,
) -> dict:
    if min(density_scale, voxel_cm, angular_sigma) <= 0.0:
        raise ValueError("scale values must be positive")

    source_rows = _read_rows(source)
    if source_rows.shape[1] != 16 or source_rows.strides[0] != 64:
        raise ValueError("source must use the 64-byte compact layout")
    if not np.isfinite(source_rows).all():
        raise ValueError("source contains non-finite values")

    grid = np.load(grid_path, mmap_mode="r")
    if grid.ndim != 3 or grid.dtype != np.float32:
        raise ValueError("reference grid must be a 3D float32 array")
    coordinates = _grid_coordinates(source_rows[:, :3] * 100.0, grid.shape, voxel_cm)
    inside = np.all(
        (coordinates >= 0.0) & (coordinates <= np.asarray(grid.shape) - 1.0),
        axis=1,
    )
    if not np.all(inside):
        raise ValueError(f"only {inside.mean():.3%} of S3 centers lie inside the grid")

    ue_tau = [
        _axis_tau(grid, coordinates, axis, positive, density_scale, voxel_cm)
        for axis in range(3)
        for positive in (True, False)
    ]
    asset_tau = np.stack([ue_tau[index] for index in ASSET_AXIS_FROM_UE], axis=1)
    direct_j = np.exp(-asset_tau).astype("<f4")
    if not np.isfinite(direct_j).all() or np.any((direct_j < 0.0) | (direct_j > 1.0)):
        raise ValueError("direct transport J is invalid")

    output_dir.mkdir(parents=True, exist_ok=False)
    paths = {
        "A_current_4nn_j": output_dir / "S3_A_Current4NNJ.ply",
        "B_vdb_direct_j": output_dir / "S3_B_VDBDirectJ.ply",
        "C_unity_j": output_dir / "S3_C_UnityJ_NoBakedJ_DGSMStillActive.ply",
        "D_sqrt_j": output_dir / "S3_D_SqrtJ.ply",
        "E_fourth_root_j": output_dir / "S3_E_FourthRootJ.ply",
        "F_gamma04_j": output_dir / "S3_F_Gamma04J.ply",
    }
    shutil.copy2(source, paths["A_current_4nn_j"])
    direct_rows = source_rows.copy()
    direct_rows[:, 10:16] = direct_j
    _write_rows(
        paths["B_vdb_direct_j"],
        direct_rows,
        source,
        grid_path,
        "B_vdb_direct_j",
        angular_sigma,
    )
    unity_rows = source_rows.copy()
    unity_rows[:, 10:16] = 1.0
    _write_rows(
        paths["C_unity_j"],
        unity_rows,
        source,
        grid_path,
        "C_unity_j_no_baked_j_dgsm_still_active",
        angular_sigma,
    )
    sqrt_rows = source_rows.copy()
    sqrt_rows[:, 10:16] = np.sqrt(direct_j)
    _write_rows(
        paths["D_sqrt_j"],
        sqrt_rows,
        source,
        grid_path,
        "D_sqrt_j",
        angular_sigma,
    )
    fourth_root_rows = source_rows.copy()
    fourth_root_rows[:, 10:16] = np.sqrt(np.sqrt(direct_j))
    _write_rows(
        paths["E_fourth_root_j"],
        fourth_root_rows,
        source,
        grid_path,
        "E_fourth_root_j",
        angular_sigma,
    )
    gamma04_rows = source_rows.copy()
    gamma04_rows[:, 10:16] = np.power(direct_j, 0.4)
    _write_rows(
        paths["F_gamma04_j"],
        gamma04_rows,
        source,
        grid_path,
        "F_gamma04_j",
        angular_sigma,
    )

    decoded = {name: _read_rows(path) for name, path in paths.items()}
    geometry_bits = source_rows[:, :10].view(np.uint32)
    for name, rows in decoded.items():
        if not np.array_equal(rows[:, :10].view(np.uint32), geometry_bits):
            raise AssertionError(f"{name} changed frozen geometry or opacity")
        if rows.shape != source_rows.shape or rows.strides[0] != 64:
            raise AssertionError(f"{name} changed point count or layout")
    if not np.array_equal(decoded["C_unity_j"][:, 10:16].view(np.uint32), np.ones_like(direct_j).view(np.uint32)):
        raise AssertionError("unity J was not written exactly")
    if not np.allclose(decoded["D_sqrt_j"][:, 10:16], np.sqrt(direct_j)):
        raise AssertionError("sqrt J was not written correctly")
    if not np.allclose(decoded["E_fourth_root_j"][:, 10:16], np.sqrt(np.sqrt(direct_j))):
        raise AssertionError("fourth-root J was not written correctly")
    if not np.allclose(decoded["F_gamma04_j"][:, 10:16], np.power(direct_j, 0.4)):
        raise AssertionError("gamma-0.4 J was not written correctly")

    current_j = source_rows[:, 10:16]
    report = {
        "spec": {
            "frozen_columns": list(COMPACT_PROPERTIES[:10]),
            "variable_columns": list(COMPACT_PROPERTIES[10:16]),
            "A": "current G2 4-NN transferred J",
            "B": "dimensionless VDB direct J = exp(-tau), ambient = 0",
            "C": "J = 1; DGSM and phase remain active in UE",
            "D": "J = sqrt(exp(-tau)); frozen geometry and opacity",
            "E": "J = fourth-root(exp(-tau)); frozen geometry and opacity",
            "F": "J = pow(exp(-tau), 0.4); frozen geometry and opacity",
        },
        "inputs": {
            "source": str(source.resolve()),
            "source_sha256": _sha256(source),
            "reference_grid": str(grid_path.resolve()),
            "reference_grid_sha256": _sha256(grid_path),
            "grid_shape": list(grid.shape),
            "density_scale": density_scale,
            "voxel_cm": voxel_cm,
            "angular_sigma": angular_sigma,
            "asset_axis_from_ue": list(ASSET_AXIS_FROM_UE),
            "inside_fraction": float(inside.mean()),
        },
        "layout": {
            "points": len(source_rows),
            "floats_per_point": source_rows.shape[1],
            "bytes_per_point": source_rows.strides[0],
            "payload_bytes": int(source_rows.nbytes),
            "frozen_columns_bit_identical": True,
        },
        "transport": {
            "A_current": _percentiles(current_j),
            "B_direct": _percentiles(direct_j),
            "A_B_rmse": float(np.sqrt(np.mean((current_j - direct_j) ** 2))),
            "A_B_max_abs": float(np.max(np.abs(current_j - direct_j))),
        },
        "outputs": {
            name: {"path": str(path.resolve()), "sha256": _sha256(path)}
            for name, path in paths.items()
        },
    }
    (output_dir / "diagnostic_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("reference_grid", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--density-scale", type=float, default=0.04)
    parser.add_argument("--voxel-cm", type=float, default=0.8163265306122449)
    parser.add_argument("--angular-sigma", type=float, default=0.5)
    args = parser.parse_args()
    report = build(
        args.source,
        args.reference_grid,
        args.output_dir,
        args.density_scale,
        args.voxel_cm,
        args.angular_sigma,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
