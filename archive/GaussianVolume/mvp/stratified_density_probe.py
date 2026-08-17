"""Sample one density-weighted center per occupied source block."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def sample_centers(
    grid: np.ndarray,
    block_coordinates: np.ndarray,
    block_size: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centers = np.empty((len(block_coordinates), 3), dtype=np.float64)
    offsets = np.arange(block_size)

    for block_x in np.unique(block_coordinates[:, 0]):
        indices = np.flatnonzero(block_coordinates[:, 0] == block_x)
        blocks = block_coordinates[indices]
        x = blocks[:, 0, None, None, None] * block_size + offsets[None, :, None, None]
        y = blocks[:, 1, None, None, None] * block_size + offsets[None, None, :, None]
        z = blocks[:, 2, None, None, None] * block_size + offsets[None, None, None, :]
        valid = (x < grid.shape[0]) & (y < grid.shape[1]) & (z < grid.shape[2])
        density = np.where(
            valid,
            grid[
                np.minimum(x, grid.shape[0] - 1),
                np.minimum(y, grid.shape[1] - 1),
                np.minimum(z, grid.shape[2] - 1),
            ],
            0.0,
        ).reshape(len(indices), -1)
        totals = density.sum(axis=1)
        if np.any(totals <= 0.0):
            raise RuntimeError("base initializer mapped to an empty source block")
        selected = (
            np.cumsum(density, axis=1)
            < rng.random(len(indices))[:, None] * totals[:, None]
        ).sum(axis=1)
        local = np.column_stack(np.unravel_index(selected, (block_size,) * 3))
        subvoxel = rng.uniform(-0.5, 0.5, local.shape)
        centers[indices] = blocks * block_size + local + subvoxel

    return np.clip(centers, 0.0, np.asarray(grid.shape) - 1.0)


def grid_coordinates(
    centers_m: np.ndarray, grid_shape: tuple[int, int, int], voxel_cm: float
) -> np.ndarray:
    centered = np.empty_like(centers_m, dtype=np.float64)
    centered[:, 0] = centers_m[:, 0] * 100.0 / voxel_cm
    centered[:, 1] = -centers_m[:, 2] * 100.0 / voxel_cm
    centered[:, 2] = -centers_m[:, 1] * 100.0 / voxel_cm
    return centered + (np.asarray(grid_shape) - 1.0) * 0.5


def world_centers(
    coordinates: np.ndarray, grid_shape: tuple[int, int, int], voxel_cm: float
) -> np.ndarray:
    centered = coordinates - (np.asarray(grid_shape) - 1.0) * 0.5
    result = centered[:, (0, 2, 1)] * np.asarray((1.0, -1.0, -1.0))
    return result * (voxel_cm / 100.0)


def self_check() -> None:
    grid = np.zeros((9, 8, 8), dtype=np.float32)
    grid[1, 2, 3] = 1.0
    grid[8, 7, 7] = 2.0
    blocks = np.asarray(((0, 0, 0), (1, 0, 0)))
    centers = sample_centers(grid, blocks, 8, 7)
    assert np.all(np.abs(centers - ((1, 2, 3), (8, 7, 7))) <= 0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--grid", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--block-size", type=int, default=8)
    parser.add_argument("--longest-size-cm", type=float, default=1000.0)
    parser.add_argument("--covariance-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("stratified_density_probe self-check passed")
        return
    if args.input is None or args.grid is None or args.output is None:
        parser.error("--input, --grid and --output are required")
    if args.block_size <= 0 or args.longest_size_cm <= 0 or args.covariance_scale <= 0:
        parser.error("block size, longest size and covariance scale must be positive")

    data = np.load(args.input)
    grid = np.load(args.grid, mmap_mode="r").squeeze()
    voxel_cm = args.longest_size_cm / max(grid.shape)
    coordinates = grid_coordinates(data["center_m"], grid.shape, voxel_cm)
    blocks = np.floor((coordinates + 1.0e-3) / args.block_size).astype(np.int64)
    sampled = sample_centers(grid, blocks, args.block_size, args.seed)
    scale = args.covariance_scale
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        center_m=world_centers(sampled, grid.shape, voxel_cm).astype(np.float32),
        covariance_m2=(data["covariance_m2"] * scale**2).astype(np.float32),
        sigma_t_per_m=(data["sigma_t_per_m"] / scale**3).astype(np.float32),
    )


if __name__ == "__main__":
    main()
