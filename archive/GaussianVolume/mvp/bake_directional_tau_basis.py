"""Bake six local-axis light optical depths into an existing Gaussian JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


# Source volumes are UE +X/-X/+Y/-Y/+Z/-Z. Gaussian JSON coordinates are
# (UE X, -UE Z, -UE Y), so reorder into asset-local +X/-X/+Y/-Y/+Z/-Z.
ASSET_AXIS_FROM_UE = (0, 1, 5, 4, 3, 2)


def _grid_coordinates(centers_cm: np.ndarray, shape: tuple[int, ...], voxel_cm: float) -> np.ndarray:
    coordinates = np.empty_like(centers_cm, dtype=np.float32)
    coordinates[:, 0] = centers_cm[:, 0] / voxel_cm
    coordinates[:, 1] = -centers_cm[:, 2] / voxel_cm
    coordinates[:, 2] = -centers_cm[:, 1] / voxel_cm
    return coordinates + (np.asarray(shape, np.float32) - 1.0) * 0.5


def _sample_trilinear(volume: np.ndarray, coordinates: np.ndarray) -> np.ndarray:
    shape = np.asarray(volume.shape)
    valid = np.all((coordinates >= 0.0) & (coordinates <= shape - 1), axis=1)
    clipped = np.clip(coordinates, 0.0, shape - 1)
    lower = np.floor(clipped).astype(np.int64)
    upper = np.minimum(lower + 1, shape - 1)
    fraction = clipped - lower
    result = np.zeros(len(coordinates), dtype=np.float32)
    for bits in range(8):
        index = np.where(
            ((bits >> np.arange(3)) & 1).astype(bool),
            upper,
            lower,
        )
        weight = np.prod(
            np.where(
                ((bits >> np.arange(3)) & 1).astype(bool),
                fraction,
                1.0 - fraction,
            ),
            axis=1,
        )
        result += weight * volume[index[:, 0], index[:, 1], index[:, 2]]
    result[~valid] = 0.0
    return result


def _axis_tau(
    grid: np.ndarray,
    coordinates: np.ndarray,
    axis: int,
    positive: bool,
    density_scale: float,
    voxel_cm: float,
) -> np.ndarray:
    source = np.flip(grid, axis=axis) if positive else grid
    optical_depth = np.cumsum(source, axis=axis, dtype=np.float32)
    if positive:
        optical_depth = np.flip(optical_depth, axis=axis)
    return _sample_trilinear(optical_depth, coordinates) * density_scale * voxel_cm


def _self_check() -> None:
    volume = np.arange(8, dtype=np.float32).reshape(2, 2, 2)
    points = np.asarray(((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.5, 0.5, 0.5)))
    sampled = _sample_trilinear(volume, points)
    assert np.allclose(sampled, (0.0, 7.0, 3.5))
    assert ASSET_AXIS_FROM_UE == (0, 1, 5, 4, 3, 2)


def bake(
    source_json: Path,
    grid_path: Path,
    output_json: Path,
    report_path: Path,
    density_scale: float,
    voxel_cm: float,
) -> dict:
    payload = json.loads(source_json.read_text(encoding="utf-8"))
    gaussians = payload.get("gaussians", ())
    centers = np.asarray([item["center"] for item in gaussians], dtype=np.float32)
    grid = np.load(grid_path, mmap_mode="r")
    coordinates = _grid_coordinates(centers, grid.shape, voxel_cm)
    inside = np.all(
        (coordinates >= 0.0) & (coordinates <= np.asarray(grid.shape) - 1.0),
        axis=1,
    )
    if inside.mean() < 0.99:
        raise ValueError(f"only {inside.mean():.3%} of Gaussian centers lie inside the source grid")

    ue_tau = []
    for axis in range(3):
        ue_tau.append(_axis_tau(grid, coordinates, axis, True, density_scale, voxel_cm))
        ue_tau.append(_axis_tau(grid, coordinates, axis, False, density_scale, voxel_cm))
    asset_tau = np.stack([ue_tau[index] for index in ASSET_AXIS_FROM_UE], axis=1)
    if not np.isfinite(asset_tau).all() or np.any(asset_tau < 0.0):
        raise ValueError("baked directional optical depth is invalid")

    for primitive, tau in zip(gaussians, asset_tau):
        primitive["light_tau_axes"] = tau.tolist()
    payload["directional_tau_basis"] = {
        "space": "asset_local",
        "order": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
        "source_grid": str(grid_path.resolve()),
        "density_scale": density_scale,
        "voxel_cm": voxel_cm,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    percentiles = np.percentile(asset_tau, (0, 1, 50, 99, 100), axis=0)
    report = {
        "source_json": str(source_json.resolve()),
        "output_json": str(output_json.resolve()),
        "kernel_count": len(gaussians),
        "inside_grid_fraction": float(inside.mean()),
        "axis_order": payload["directional_tau_basis"]["order"],
        "tau_percentiles_p0_p1_p50_p99_p100": percentiles.tolist(),
        "bytes_per_kernel": 12,
        "status": "directional tau basis baked",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument("--grid", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--density-scale", type=float, required=True)
    parser.add_argument("--voxel-cm", type=float, required=True)
    args = parser.parse_args()
    if args.density_scale < 0.0 or args.voxel_cm <= 0.0:
        parser.error("density scale must be non-negative and voxel size must be positive")
    _self_check()
    print(json.dumps(bake(
        args.source_json,
        args.grid,
        args.output_json,
        args.report,
        args.density_scale,
        args.voxel_cm,
    ), indent=2))


if __name__ == "__main__":
    main()
