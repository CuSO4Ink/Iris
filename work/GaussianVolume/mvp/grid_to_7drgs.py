"""Convert a dense VDB-derived NumPy grid to an analytic relightable 7DRGS PLY."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from lift_volprim_to_7drgs import (
    PLY_PROPERTIES,
    SH_C0,
    _inverse_softplus,
)


LIGHT_DIRECTIONS_UE = np.asarray(
    (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    ),
    dtype=np.float32,
)
LIGHT_DIRECTIONS_GL = LIGHT_DIRECTIONS_UE[:, (0, 2, 1)] * np.asarray(
    (1.0, -1.0, -1.0), dtype=np.float32
)


def _aggregate_grid(
    grid: np.ndarray, block_size: int, spatial_sigma_ratio: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    active_indices = np.argwhere(grid > 0.0)
    if not len(active_indices):
        raise ValueError("grid contains no positive density")

    block_shape = tuple(math.ceil(size / block_size) for size in grid.shape)
    block_ids_3d = active_indices // block_size
    block_ids = np.ravel_multi_index(block_ids_3d.T, block_shape)
    densities = grid[tuple(active_indices.T)].astype(np.float64, copy=False)
    block_count = math.prod(block_shape)
    density_sums = np.bincount(
        block_ids, weights=densities, minlength=block_count
    )
    occupied = np.flatnonzero(density_sums > 0.0)
    sums = density_sums[occupied]

    centers = np.empty((len(occupied), 3), dtype=np.float64)
    for axis in range(3):
        weighted = np.bincount(
            block_ids,
            weights=densities * active_indices[:, axis],
            minlength=block_count,
        )
        centers[:, axis] = weighted[occupied] / sums

    covariance_ue = np.empty((len(occupied), 3, 3), dtype=np.float64)
    for row in range(3):
        for column in range(row + 1):
            weighted = np.bincount(
                block_ids,
                weights=densities
                * active_indices[:, row]
                * active_indices[:, column],
                minlength=block_count,
            )
            value = weighted[occupied] / sums - centers[:, row] * centers[:, column]
            covariance_ue[:, row, column] = value
            covariance_ue[:, column, row] = value

    # Preserve the old overlap for a full block while adapting each splat to
    # the density distribution inside its block. This removes the visible
    # equal-size-cell pattern without opening holes at thin cloud boundaries.
    kernel_variance = spatial_sigma_ratio**2
    variance_scale = (block_size * spatial_sigma_ratio) ** 2 / (
        (block_size**2 - 1.0) / 12.0 + kernel_variance
    )
    covariance_ue += np.eye(3, dtype=np.float64) * kernel_variance
    covariance_ue *= variance_scale
    ue_to_gl = np.asarray(
        ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
        dtype=np.float64,
    )
    covariance_gl = ue_to_gl @ covariance_ue @ ue_to_gl.T
    spatial_cholesky_voxels = np.linalg.cholesky(covariance_gl)

    mean_density = sums / float(block_size**3)
    sample_indices = np.rint(centers).astype(np.int32)
    for axis, size in enumerate(grid.shape):
        sample_indices[:, axis] = np.clip(sample_indices[:, axis], 0, size - 1)
    return centers, mean_density, sample_indices, spatial_cholesky_voxels


def _directional_transmittance(
    grid: np.ndarray,
    sample_indices: np.ndarray,
    voxel_cm: float,
    density_scale: float,
) -> np.ndarray:
    values = []
    coordinates = tuple(sample_indices.T)
    for direction in LIGHT_DIRECTIONS_UE:
        axis = int(np.flatnonzero(direction)[0])
        toward_positive = direction[axis] > 0.0
        source = np.flip(grid, axis=axis) if toward_positive else grid
        optical_depth = np.cumsum(source, axis=axis, dtype=np.float32)
        if toward_positive:
            optical_depth = np.flip(optical_depth, axis=axis)
        values.append(
            np.exp(-optical_depth[coordinates] * density_scale * voxel_cm)
        )
    return np.stack(values, axis=0)


def _iter_rows(
    centers_cm: np.ndarray,
    mean_density: np.ndarray,
    light_transmittance: np.ndarray,
    spatial_cholesky_voxels: np.ndarray,
    block_size: int,
    voxel_cm: float,
    density_scale: float,
    angular_sigma: float,
    ambient: float,
):
    property_index = {name: index for index, name in enumerate(PLY_PROPERTIES)}
    count = len(centers_cm)
    spatial_cholesky_m = (
        spatial_cholesky_voxels.astype(np.float32, copy=False)
        * (voxel_cm / 100.0)
    )
    spatial_std_m = np.sqrt(
        np.sum(spatial_cholesky_m * spatial_cholesky_m, axis=2)
    )
    kernel_sum = (
        1.0
        + math.exp(-1.0 / (angular_sigma * angular_sigma))
        + 4.0 * math.exp(-0.5 / (angular_sigma * angular_sigma))
    )
    target_alpha = 1.0 - np.exp(
        -mean_density * density_scale * voxel_cm * block_size
    )
    lobe_alpha = np.clip(target_alpha / kernel_sum, 1e-6, 1.0 - 1e-6)
    centered = centers_cm.astype(np.float32, copy=False)
    xyz_gl = np.stack(
        (centered[:, 0], -centered[:, 2], -centered[:, 1]), axis=1
    ) / 100.0

    for direction_index, direction_gl in enumerate(LIGHT_DIRECTIONS_GL):
        rows = np.zeros((count, len(PLY_PROPERTIES)), dtype="<f4")
        rows[:, :3] = xyz_gl
        j = ambient + (1.0 - ambient) * light_transmittance[direction_index]
        rows[:, property_index["f_dc_j"]] = (j - 0.5) / SH_C0
        rows[:, property_index["opacity"]] = np.log(
            lobe_alpha / (1.0 - lobe_alpha)
        )
        for axis in range(3):
            rows[:, property_index[f"scale_{axis}"]] = np.log(
                spatial_std_m[:, axis]
            )
        rows[:, property_index["rot_3"]] = 1.0
        rows[:, property_index["mu_d_0"]:property_index["mu_d_2"] + 1] = direction_gl
        for axis in range(3):
            rows[:, property_index[f"chol_diag_{axis}"]] = np.log(
                spatial_cholesky_m[:, axis, axis]
            )
        rows[:, property_index["chol_diag_3"]] = math.log(0.1)
        for axis in range(4, 7):
            rows[:, property_index[f"chol_diag_{axis}"]] = math.log(angular_sigma)
        rows[:, property_index["chol_offdiag_0"]] = (
            spatial_cholesky_m[:, 1, 0] / spatial_cholesky_m[:, 1, 1]
        )
        rows[:, property_index["chol_offdiag_1"]] = (
            spatial_cholesky_m[:, 2, 0] / spatial_cholesky_m[:, 2, 2]
        )
        rows[:, property_index["chol_offdiag_2"]] = (
            spatial_cholesky_m[:, 2, 1] / spatial_cholesky_m[:, 2, 2]
        )
        rows[:, property_index["lambda_t"]] = _inverse_softplus(1e-6)
        rows[:, property_index["lambda_d"]] = _inverse_softplus(1.0)
        rows[:, property_index["f_dc_t"]] = -0.5 / SH_C0
        yield rows


def convert(
    source: Path,
    output: Path,
    block_size: int = 4,
    longest_size_cm: float = 1000.0,
    density_scale: float = 1.0,
    spatial_sigma_ratio: float = 0.55,
    angular_sigma: float = 0.75,
    ambient: float = 0.12,
) -> dict:
    if block_size < 1:
        raise ValueError("block size must be positive")
    if min(longest_size_cm, density_scale, spatial_sigma_ratio, angular_sigma) <= 0.0:
        raise ValueError("scale values must be positive")
    if not 0.0 <= ambient <= 1.0:
        raise ValueError("ambient must be in [0,1]")

    grid = np.load(source).squeeze().astype(np.float32, copy=False)
    if grid.ndim != 3 or not np.isfinite(grid).all() or np.min(grid) < 0.0:
        raise ValueError("source must be a finite non-negative 3D grid")
    voxel_cm = longest_size_cm / max(grid.shape)
    centers, mean_density, sample_indices, spatial_cholesky_voxels = _aggregate_grid(
        grid, block_size, spatial_sigma_ratio
    )
    centered_indices = centers - (np.asarray(grid.shape, dtype=np.float64) - 1.0) * 0.5
    centers_cm = centered_indices * voxel_cm
    transmittance = _directional_transmittance(
        grid, sample_indices, voxel_cm, density_scale
    )
    point_count = len(centers) * len(LIGHT_DIRECTIONS_GL)
    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment source_grid {source.as_posix()}",
        f"comment block_size {block_size}",
        f"comment spatial_points {len(centers)}",
        f"comment light_lobes {len(LIGHT_DIRECTIONS_GL)}",
        f"element vertex {point_count}",
        *(f"property float {name}" for name in PLY_PROPERTIES),
        "end_header",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        for chunk in _iter_rows(
            centers_cm,
            mean_density,
            transmittance,
            spatial_cholesky_voxels,
            block_size,
            voxel_cm,
            density_scale,
            angular_sigma,
            ambient,
        ):
            stream.write(chunk.tobytes(order="C"))
    return {
        "source": str(source),
        "output": str(output),
        "grid_shape": list(grid.shape),
        "block_size": block_size,
        "voxel_cm": voxel_cm,
        "spatial_points": len(centers),
        "light_lobes": len(LIGHT_DIRECTIONS_GL),
        "point_count": point_count,
        "density_scale": density_scale,
        "spatial_sigma_ratio": spatial_sigma_ratio,
        "angular_sigma": angular_sigma,
        "ambient": ambient,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--block-size", type=int, default=4)
    parser.add_argument("--longest-size-cm", type=float, default=1000.0)
    parser.add_argument("--density-scale", type=float, default=1.0)
    parser.add_argument("--spatial-sigma-ratio", type=float, default=0.55)
    parser.add_argument("--angular-sigma", type=float, default=0.75)
    parser.add_argument("--ambient", type=float, default=0.12)
    args = parser.parse_args()
    print(json.dumps(convert(
        args.source,
        args.output,
        args.block_size,
        args.longest_size_cm,
        args.density_scale,
        args.spatial_sigma_ratio,
        args.angular_sigma,
        args.ambient,
    ), indent=2))


if __name__ == "__main__":
    main()
