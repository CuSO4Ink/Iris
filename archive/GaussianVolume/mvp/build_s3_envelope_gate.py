"""Pull only silhouette-crossing S3 points into a low-frequency VDB envelope."""

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
    output: Path,
    *,
    voxel_cm: float,
    blur_sigma: float,
    envelope_threshold: float,
    support_sigma: float,
    opacity_cut: float,
    inward_sigma: float,
) -> dict:
    if min(voxel_cm, blur_sigma, envelope_threshold, support_sigma) <= 0.0:
        raise ValueError("envelope parameters must be positive")
    if not 0.0 <= opacity_cut <= 1.0 or not 0.0 <= inward_sigma <= 1.0:
        raise ValueError("opacity_cut and inward_sigma must be in [0, 1]")

    rows = _read_rows(source)
    grid = np.load(grid_path)
    shell = gaussian_filter(grid, blur_sigma) > envelope_threshold
    signed_cm = (
        distance_transform_edt(shell) - distance_transform_edt(~shell)
    ) * voxel_cm
    gradient = np.stack(np.gradient(signed_cm), axis=0)
    coordinates = _grid_coordinates(rows[:, :3] * 100.0, grid.shape, voxel_cm)
    point_signed_cm = map_coordinates(
        signed_cm, coordinates.T, order=1, mode="constant"
    )
    grid_normal = np.stack(
        [
            map_coordinates(axis, coordinates.T, order=1, mode="nearest")
            for axis in gradient
        ],
        axis=1,
    )
    local_normal = grid_normal[:, (0, 2, 1)] * np.asarray(
        (1.0, -1.0, -1.0), np.float32
    )
    normal_length = np.linalg.norm(local_normal, axis=1, keepdims=True)
    valid_normal = normal_length[:, 0] > 1.0e-5
    local_normal[valid_normal] /= normal_length[valid_normal]
    local_normal[~valid_normal] = 0.0

    covariance = np.empty((len(rows), 3, 3), dtype=np.float32)
    covariance[:, 0, 0] = rows[:, 4]
    covariance[:, 0, 1] = covariance[:, 1, 0] = rows[:, 5]
    covariance[:, 0, 2] = covariance[:, 2, 0] = rows[:, 6]
    covariance[:, 1, 1] = rows[:, 7]
    covariance[:, 1, 2] = covariance[:, 2, 1] = rows[:, 8]
    covariance[:, 2, 2] = rows[:, 9]
    normal_sigma_cm = (
        np.sqrt(
            np.maximum(
                np.einsum(
                    "ni,nij,nj->n", local_normal, covariance, local_normal
                ),
                0.0,
            )
        )
        * 100.0
    )
    max_sigma_cm = np.sqrt(np.linalg.eigvalsh(covariance)[:, -1]) * 100.0
    reach_cm = np.maximum(support_sigma * normal_sigma_cm, voxel_cm)
    crossing_weight = 1.0 - _smoothstep01(point_signed_cm / reach_cm)
    crossing_weight[~valid_normal] = 0.0
    training_mask = point_signed_cm < support_sigma * max_sigma_cm

    candidate = rows.copy()
    candidate[:, 3] *= 1.0 - opacity_cut * crossing_weight
    shift_cm = inward_sigma * normal_sigma_cm * crossing_weight
    candidate[:, :3] += local_normal * (shift_cm / 100.0)[:, None]

    output.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(output, candidate, source, grid_path, "envelope_gate", 0.5)
    decoded = _read_rows(output)
    if len(decoded) != len(rows) or not np.array_equal(
        decoded[:, 4:16].view(np.uint32), rows[:, 4:16].view(np.uint32)
    ):
        raise AssertionError("envelope gate changed point count, covariance, or J")
    if not np.isfinite(decoded).all() or np.any(decoded[:, 3] < 0.0):
        raise AssertionError("envelope gate produced invalid data")

    report = {
        "source": str(source.resolve()),
        "source_sha256": _sha256(source),
        "grid": str(grid_path.resolve()),
        "output": str(output.resolve()),
        "output_sha256": _sha256(output),
        "point_count": len(rows),
        "affected_fraction": float(np.mean(crossing_weight > 0.0)),
        "strong_fraction": float(np.mean(crossing_weight > 0.5)),
        "outside_fraction": float(np.mean(point_signed_cm <= 0.0)),
        "opacity_sum_ratio": float(candidate[:, 3].sum() / rows[:, 3].sum()),
        "max_shift_cm": float(shift_cm.max()),
        "mean_affected_shift_cm": float(
            shift_cm[crossing_weight > 0.0].mean()
        ),
        "frozen": ["point_count", "covariance", "transport_j"],
        "parameters": {
            "voxel_cm": voxel_cm,
            "blur_sigma_voxels": blur_sigma,
            "envelope_threshold": envelope_threshold,
            "support_sigma": support_sigma,
            "opacity_cut": opacity_cut,
            "inward_sigma": inward_sigma,
        },
    }
    np.save(output.with_suffix(".mask.npy"), training_mask)
    report["training_mask"] = str(output.with_suffix(".mask.npy").resolve())
    report["training_fraction"] = float(training_mask.mean())
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("grid", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--voxel-cm", type=float, default=3.2653061224489797)
    parser.add_argument("--blur-sigma", type=float, default=5.0)
    parser.add_argument("--envelope-threshold", type=float, default=0.1)
    parser.add_argument("--support-sigma", type=float, default=2.0)
    parser.add_argument("--opacity-cut", type=float, default=0.65)
    parser.add_argument("--inward-sigma", type=float, default=0.35)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.source,
                args.grid,
                args.output,
                voxel_cm=args.voxel_cm,
                blur_sigma=args.blur_sigma,
                envelope_threshold=args.envelope_threshold,
                support_sigma=args.support_sigma,
                opacity_cut=args.opacity_cut,
                inward_sigma=args.inward_sigma,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
