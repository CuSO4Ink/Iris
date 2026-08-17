"""Soften only S3 Gaussians whose support reaches a low-frequency VDB shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

from bake_directional_tau_basis import _grid_coordinates
from build_s3_transport_diagnostic import _read_rows, _sha256, _write_rows


def _smoothstep01(value: np.ndarray) -> np.ndarray:
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def build(
    source: Path,
    grid_path: Path,
    output_dir: Path,
    voxel_cm: float,
    blur_sigma: float,
    envelope_threshold: float,
    boundary_sigma: float,
    spreads: tuple[float, ...],
) -> dict:
    if min(voxel_cm, blur_sigma, envelope_threshold, boundary_sigma) <= 0.0:
        raise ValueError("shell parameters must be positive")
    if not spreads or min(spreads) <= 0.0:
        raise ValueError("at least one positive spread is required")

    rows = _read_rows(source)
    grid = np.load(grid_path)
    blurred = gaussian_filter(grid, blur_sigma)
    shell = blurred > envelope_threshold
    inside_distance_cm = distance_transform_edt(shell) * voxel_cm
    coordinates = _grid_coordinates(rows[:, :3] * 100.0, grid.shape, voxel_cm)
    point_distance_cm = map_coordinates(
        inside_distance_cm, coordinates.T, order=1, mode="constant"
    )

    covariance = np.empty((len(rows), 3, 3), dtype=np.float32)
    covariance[:, 0, 0] = rows[:, 4]
    covariance[:, 0, 1] = covariance[:, 1, 0] = rows[:, 5]
    covariance[:, 0, 2] = covariance[:, 2, 0] = rows[:, 6]
    covariance[:, 1, 1] = rows[:, 7]
    covariance[:, 1, 2] = covariance[:, 2, 1] = rows[:, 8]
    covariance[:, 2, 2] = rows[:, 9]
    max_sigma_cm = np.sqrt(np.linalg.eigvalsh(covariance)[:, -1]) * 100.0
    distance_in_sigma = point_distance_cm / np.maximum(max_sigma_cm, 1.0e-5)
    shell_weight = 1.0 - _smoothstep01(distance_in_sigma / boundary_sigma)

    output_dir.mkdir(parents=True, exist_ok=False)
    outputs = {}
    frozen_center_j = np.concatenate((rows[:, :3], rows[:, 10:16]), axis=1).view(
        np.uint32
    )
    for spread in spreads:
        candidate = rows.copy()
        scale = 1.0 + spread * shell_weight
        scale2 = scale * scale
        candidate[:, 3] = rows[:, 3] / scale2
        candidate[:, 4:10] = rows[:, 4:10] * scale2[:, None]
        tag = f"spread{round(spread * 100):02d}"
        path = output_dir / f"S3_BoundaryShell_{tag}.ply"
        _write_rows(path, candidate, source, grid_path, tag, 0.5)

        decoded = _read_rows(path)
        decoded_center_j = np.concatenate(
            (decoded[:, :3], decoded[:, 10:16]), axis=1
        ).view(np.uint32)
        if not np.array_equal(decoded_center_j, frozen_center_j):
            raise AssertionError(f"{tag} changed frozen center or transport")
        decoded_covariance = np.empty_like(covariance)
        decoded_covariance[:, 0, 0] = decoded[:, 4]
        decoded_covariance[:, 0, 1] = decoded_covariance[:, 1, 0] = decoded[:, 5]
        decoded_covariance[:, 0, 2] = decoded_covariance[:, 2, 0] = decoded[:, 6]
        decoded_covariance[:, 1, 1] = decoded[:, 7]
        decoded_covariance[:, 1, 2] = decoded_covariance[:, 2, 1] = decoded[:, 8]
        decoded_covariance[:, 2, 2] = decoded[:, 9]
        if np.min(np.linalg.eigvalsh(decoded_covariance)) <= 0.0:
            raise AssertionError(f"{tag} produced a non-positive covariance")
        outputs[tag] = {
            "path": str(path.resolve()),
            "sha256": _sha256(path),
            "max_scale": float(scale.max()),
            "mean_scale": float(scale.mean()),
            "opacity_sum_ratio": float(candidate[:, 3].sum() / rows[:, 3].sum()),
        }

    report = {
        "source": str(source.resolve()),
        "source_sha256": _sha256(source),
        "grid": str(grid_path.resolve()),
        "grid_shape": list(grid.shape),
        "voxel_cm": voxel_cm,
        "blur_sigma_voxels": blur_sigma,
        "envelope_threshold": envelope_threshold,
        "boundary_sigma": boundary_sigma,
        "affected_fraction": float(np.mean(shell_weight > 0.0)),
        "strong_fraction": float(np.mean(shell_weight > 0.5)),
        "frozen": ["point_count", "center", "transport_j"],
        "outputs": outputs,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("grid", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--voxel-cm", type=float, default=3.2653061224489797)
    parser.add_argument("--blur-sigma", type=float, default=3.0)
    parser.add_argument("--envelope-threshold", type=float, default=0.1)
    parser.add_argument("--boundary-sigma", type=float, default=3.0)
    parser.add_argument("--spreads", type=float, nargs="+", default=(0.2, 0.35))
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.source,
                args.grid,
                args.output_dir,
                args.voxel_cm,
                args.blur_sigma,
                args.envelope_threshold,
                args.boundary_sigma,
                tuple(args.spreads),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
