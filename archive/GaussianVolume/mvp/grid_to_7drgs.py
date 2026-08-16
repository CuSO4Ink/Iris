"""Convert a dense VDB-derived NumPy grid to an analytic relightable 7DRGS PLY."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from bake_directional_tau_basis import (
    ASSET_AXIS_FROM_UE,
    _axis_tau,
    _grid_coordinates,
)
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

COMPACT_PROPERTIES = (
    "x",
    "y",
    "z",
    "lobe_opacity",
    "cov_00",
    "cov_01",
    "cov_02",
    "cov_11",
    "cov_12",
    "cov_22",
    *(f"j_{index}" for index in range(6)),
)


def _aggregate_grid(
    grid: np.ndarray, block_size: int, spatial_sigma_ratio: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if grid.size >= 50_000_000:
        return _aggregate_grid_chunked(grid, block_size, spatial_sigma_ratio)

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


def _aggregate_grid_chunked(
    grid: np.ndarray, block_size: int, spatial_sigma_ratio: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    block_shape = tuple(math.ceil(size / block_size) for size in grid.shape)
    yz_block_count = block_shape[1] * block_shape[2]
    centers_parts = []
    sums_parts = []
    covariance_parts = []

    for block_x in range(block_shape[0]):
        x_start = block_x * block_size
        slab = np.asarray(
            grid[x_start : min(x_start + block_size, grid.shape[0])],
            dtype=np.float32,
        )
        local = np.argwhere(slab > 0.0)
        if not len(local):
            continue
        density = slab[tuple(local.T)].astype(np.float64, copy=False)
        coordinates = local.astype(np.float64)
        coordinates[:, 0] += x_start
        yz_ids = (
            (local[:, 1] // block_size) * block_shape[2]
            + local[:, 2] // block_size
        )
        sums = np.bincount(
            yz_ids, weights=density, minlength=yz_block_count
        )
        occupied = np.flatnonzero(sums > 0.0)
        occupied_sums = sums[occupied]

        centers = np.empty((len(occupied), 3), dtype=np.float64)
        for axis in range(3):
            weighted = np.bincount(
                yz_ids,
                weights=density * coordinates[:, axis],
                minlength=yz_block_count,
            )
            centers[:, axis] = weighted[occupied] / occupied_sums

        covariance = np.empty((len(occupied), 3, 3), dtype=np.float64)
        for row in range(3):
            for column in range(row + 1):
                weighted = np.bincount(
                    yz_ids,
                    weights=(
                        density
                        * coordinates[:, row]
                        * coordinates[:, column]
                    ),
                    minlength=yz_block_count,
                )
                value = (
                    weighted[occupied] / occupied_sums
                    - centers[:, row] * centers[:, column]
                )
                covariance[:, row, column] = value
                covariance[:, column, row] = value
        centers_parts.append(centers)
        sums_parts.append(occupied_sums)
        covariance_parts.append(covariance)

    if not centers_parts:
        raise ValueError("grid contains no positive density")
    centers = np.concatenate(centers_parts)
    sums = np.concatenate(sums_parts)
    covariance_ue = np.concatenate(covariance_parts)
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
    mean_density = sums / float(block_size**3)
    sample_indices = np.rint(centers).astype(np.int32)
    for axis, size in enumerate(grid.shape):
        sample_indices[:, axis] = np.clip(sample_indices[:, axis], 0, size - 1)
    return (
        centers,
        mean_density,
        sample_indices,
        np.linalg.cholesky(covariance_gl),
    )


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


def _compact_rows(
    centers_cm: np.ndarray,
    mean_density: np.ndarray,
    light_transmittance: np.ndarray,
    spatial_cholesky_voxels: np.ndarray,
    block_size: int,
    voxel_cm: float,
    density_scale: float,
    angular_sigma: float,
    ambient: float,
) -> np.ndarray:
    spatial_cholesky_m = (
        spatial_cholesky_voxels.astype(np.float32, copy=False)
        * (voxel_cm / 100.0)
    )
    covariance_gl = spatial_cholesky_m @ np.transpose(spatial_cholesky_m, (0, 2, 1))
    kernel_sum = (
        1.0
        + math.exp(-1.0 / (angular_sigma * angular_sigma))
        + 4.0 * math.exp(-0.5 / (angular_sigma * angular_sigma))
    )
    target_alpha = 1.0 - np.exp(
        -mean_density * density_scale * voxel_cm * block_size
    )
    rows = np.empty((len(centers_cm), len(COMPACT_PROPERTIES)), dtype="<f4")
    centered = centers_cm.astype(np.float32, copy=False)
    rows[:, :3] = np.stack(
        (centered[:, 0], -centered[:, 2], -centered[:, 1]), axis=1
    ) / 100.0
    rows[:, 3] = np.clip(target_alpha / kernel_sum, 1e-6, 1.0 - 1e-6)
    rows[:, 4:10] = covariance_gl[:, (0, 0, 0, 1, 1, 2), (0, 1, 2, 1, 2, 2)]
    rows[:, 10:16] = (
        ambient + (1.0 - ambient) * light_transmittance
    ).T
    return rows


def convert_initializer(
    initializer: Path,
    reference_grid: Path,
    output: Path,
    voxel_cm: float,
    density_scale: float = 0.04,
    angular_sigma: float = 0.5,
    ambient: float = 0.12,
) -> dict:
    """Export a fixed-budget Gaussian initializer to the 64-byte runtime layout."""
    if min(voxel_cm, density_scale, angular_sigma) <= 0.0:
        raise ValueError("scale values must be positive")
    if not 0.0 <= ambient <= 1.0:
        raise ValueError("ambient must be in [0,1]")

    data = np.load(initializer)
    centers = np.asarray(data["center_m"], dtype=np.float32)
    covariances = np.asarray(data["covariance_m2"], dtype=np.float32)
    extinction = np.asarray(data["sigma_t_per_m"], dtype=np.float32)
    count = len(centers)
    if (
        centers.shape != (count, 3)
        or covariances.shape != (count, 3, 3)
        or extinction.shape != (count,)
        or not all(np.isfinite(value).all() for value in (centers, covariances, extinction))
        or np.any(extinction < 0.0)
    ):
        raise ValueError("initializer must contain finite center/covariance/extinction arrays")
    determinants = np.linalg.det(covariances)
    if np.any(determinants <= 0.0):
        raise ValueError("initializer covariance must be positive definite")

    grid = np.load(reference_grid, mmap_mode="r").squeeze()
    if grid.ndim != 3 or not np.isfinite(grid).all() or np.min(grid) < 0.0:
        raise ValueError("reference grid must be finite, non-negative and 3D")
    coordinates = _grid_coordinates(centers * 100.0, grid.shape, voxel_cm)
    inside = np.all(
        (coordinates >= 0.0) & (coordinates <= np.asarray(grid.shape) - 1.0),
        axis=1,
    )
    if inside.mean() < 0.99:
        raise ValueError(f"only {inside.mean():.3%} of Gaussian centers lie inside the grid")
    ue_tau = [
        _axis_tau(grid, coordinates, axis, positive, density_scale, voxel_cm)
        for axis in range(3)
        for positive in (True, False)
    ]
    asset_tau = np.stack([ue_tau[index] for index in ASSET_AXIS_FROM_UE], axis=1)

    kernel_sum = (
        1.0
        + math.exp(-1.0 / (angular_sigma * angular_sigma))
        + 4.0 * math.exp(-0.5 / (angular_sigma * angular_sigma))
    )
    equivalent_scale_m = determinants ** (1.0 / 6.0)
    center_tau = extinction * math.sqrt(2.0 * math.pi) * equivalent_scale_m
    rows = np.empty((count, len(COMPACT_PROPERTIES)), dtype="<f4")
    rows[:, :3] = centers
    rows[:, 3] = np.clip(-np.expm1(-center_tau) / kernel_sum, 1e-6, 1.0 - 1e-6)
    rows[:, 4:10] = covariances[:, (0, 0, 0, 1, 1, 2), (0, 1, 2, 1, 2, 2)]
    rows[:, 10:16] = ambient + (1.0 - ambient) * np.exp(-asset_tau)

    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment source_initializer {initializer.as_posix()}",
        f"comment reference_grid {reference_grid.as_posix()}",
        f"comment spatial_points {count}",
        "comment light_lobes 6",
        "comment compact_static_transport 1",
        f"comment angular_sigma {angular_sigma}",
        "comment opacity_calibration gaussian_central_tau",
        f"element vertex {count}",
        *(f"property float {name}" for name in COMPACT_PROPERTIES),
        "end_header",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        stream.write(rows.tobytes(order="C"))
    return {
        "source": str(initializer),
        "reference_grid": str(reference_grid),
        "output": str(output),
        "spatial_points": count,
        "point_count": count,
        "expanded_equivalent": count * len(LIGHT_DIRECTIONS_GL),
        "format": "compact_static_transport",
        "bytes_per_point": rows.strides[0],
        "density_scale": density_scale,
        "voxel_cm": voxel_cm,
        "angular_sigma": angular_sigma,
        "ambient": ambient,
        "inside_grid_fraction": float(inside.mean()),
    }


def transfer_standard_transport(
    source: Path,
    transport_source: Path,
    output: Path,
    scene_scale: float,
    neighbors: int,
) -> dict:
    """Keep standard 3DGS geometry/opacity and transfer G2's compact light field."""
    from plyfile import PlyData
    from scipy.spatial import cKDTree

    if scene_scale <= 0.0 or neighbors < 1:
        raise ValueError("scene scale and neighbors must be positive")
    source_ply = PlyData.read(source, mmap="r")
    transport_ply = PlyData.read(transport_source, mmap="r")
    vertices = source_ply.elements[0].data
    transport = transport_ply.elements[0].data
    required = {
        "x", "y", "z", "opacity",
        "f_dc_0", "f_dc_1", "f_dc_2",
        "scale_0", "scale_1", "scale_2",
        "rot_0", "rot_1", "rot_2", "rot_3",
    }
    if missing := required.difference(vertices.dtype.names):
        raise ValueError(f"standard 3DGS PLY is missing: {sorted(missing)}")
    if missing := set(COMPACT_PROPERTIES).difference(transport.dtype.names):
        raise ValueError(f"transport PLY is missing: {sorted(missing)}")

    angular_sigma = next(
        (
            float(comment.split(maxsplit=1)[1])
            for comment in transport_ply.comments
            if comment.startswith("angular_sigma ")
        ),
        0.75,
    )
    scale_factor = 1.0 / scene_scale
    centers = np.stack(
        [np.asarray(vertices[name], np.float32) for name in ("x", "y", "z")],
        axis=1,
    ) * scale_factor
    quaternion = np.stack(
        [np.asarray(vertices[f"rot_{axis}"], np.float64) for axis in range(4)],
        axis=1,
    )
    quaternion /= np.linalg.norm(quaternion, axis=1, keepdims=True)
    w, x, y, z = quaternion.T
    rotation = np.empty((len(vertices), 3, 3), np.float64)
    rotation[:, 0, 0] = 1 - 2 * (y * y + z * z)
    rotation[:, 0, 1] = 2 * (x * y - w * z)
    rotation[:, 0, 2] = 2 * (x * z + w * y)
    rotation[:, 1, 0] = 2 * (x * y + w * z)
    rotation[:, 1, 1] = 1 - 2 * (x * x + z * z)
    rotation[:, 1, 2] = 2 * (y * z - w * x)
    rotation[:, 2, 0] = 2 * (x * z - w * y)
    rotation[:, 2, 1] = 2 * (y * z + w * x)
    rotation[:, 2, 2] = 1 - 2 * (x * x + y * y)
    scales = np.exp(
        np.stack(
            [
                np.asarray(vertices[f"scale_{axis}"], np.float64)
                for axis in range(3)
            ],
            axis=1,
        )
    ) * scale_factor
    transform = rotation * scales[:, None, :]
    covariance = transform @ np.transpose(transform, (0, 2, 1))

    alpha = 1.0 / (
        1.0 + np.exp(-np.asarray(vertices["opacity"], dtype=np.float64))
    )
    lobe_opacity = alpha.astype(np.float32)
    transport_xyz = np.stack(
        [np.asarray(transport[name], np.float32) for name in ("x", "y", "z")],
        axis=1,
    )
    distances, indices = cKDTree(transport_xyz).query(
        centers, k=min(neighbors, len(transport)), workers=-1
    )
    transport_j = np.stack(
        [np.asarray(transport[f"j_{index}"], np.float32) for index in range(6)],
        axis=1,
    )
    transport_ambient = float(np.min(transport_j))
    transport_j = np.clip(
        (transport_j - transport_ambient) / max(1.0 - transport_ambient, 1.0e-6),
        0.0,
        1.0,
    )
    if np.ndim(indices) == 1:
        light_field = transport_j[indices]
    else:
        weights = 1.0 / np.maximum(distances, 1.0e-6) ** 2
        light_field = np.sum(
            transport_j[indices] * weights[:, :, None], axis=1
        ) / np.sum(weights, axis=1)[:, None]
    rows = np.empty((len(vertices), len(COMPACT_PROPERTIES)), dtype="<f4")
    rows[:, :3] = centers
    rows[:, 3] = lobe_opacity
    rows[:, 4:10] = covariance[:, (0, 0, 0, 1, 1, 2), (0, 1, 2, 1, 2, 2)]
    rows[:, 10:16] = light_field
    alpha_error = float(np.max(np.abs(lobe_opacity - alpha)))
    if alpha_error > 1.0e-5 or not np.isfinite(rows).all():
        raise ValueError(f"compact transfer self-check failed: alpha error {alpha_error}")

    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment source_standard_3dgs {source.as_posix()}",
        f"comment source_transport {transport_source.as_posix()}",
        f"comment spatial_points {len(rows)}",
        "comment light_lobes 6",
        "comment compact_static_transport 1",
        "comment compact_shared_opacity 1",
        f"comment angular_sigma {angular_sigma}",
        "comment opacity_calibration shared_standard_3dgs",
        f"comment removed_transport_ambient {transport_ambient}",
        f"element vertex {len(rows)}",
        *(f"property float {name}" for name in COMPACT_PROPERTIES),
        "end_header",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        stream.write(rows.tobytes(order="C"))
    nearest_distance = distances if np.ndim(distances) == 1 else distances[:, 0]
    report = {
        "source": str(source.resolve()),
        "transport_source": str(transport_source.resolve()),
        "output": str(output.resolve()),
        "spatial_points": len(rows),
        "bytes_per_point": rows.strides[0],
        "scene_scale_restored": scene_scale,
        "angular_sigma": angular_sigma,
        "transport_neighbors": neighbors,
        "nearest_transport_distance_m": dict(
            zip(
                ("p50", "p95", "p99", "max"),
                map(
                    float,
                    np.percentile(nearest_distance, (50.0, 95.0, 99.0, 100.0)),
                ),
            )
        ),
        "max_opacity_reconstruction_error": alpha_error,
        "removed_transport_ambient": transport_ambient,
        "source_dc_gain": "disabled_to_keep_transport_free_of_baked_rgb_lighting",
    }
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def convert(
    source: Path,
    output: Path,
    block_size: int = 4,
    longest_size_cm: float = 1000.0,
    density_scale: float = 1.0,
    spatial_sigma_ratio: float = 0.55,
    angular_sigma: float = 0.75,
    ambient: float = 0.12,
    compact: bool = False,
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
    point_count = len(centers) if compact else len(centers) * len(LIGHT_DIRECTIONS_GL)
    properties = COMPACT_PROPERTIES if compact else PLY_PROPERTIES
    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"comment source_grid {source.as_posix()}",
        f"comment block_size {block_size}",
        f"comment spatial_points {len(centers)}",
        f"comment light_lobes {len(LIGHT_DIRECTIONS_GL)}",
        *(("comment compact_static_transport 1", f"comment angular_sigma {angular_sigma}")
          if compact else ()),
        f"element vertex {point_count}",
        *(f"property float {name}" for name in properties),
        "end_header",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write("\n".join(header).encode("ascii"))
        if compact:
            stream.write(_compact_rows(
                centers_cm,
                mean_density,
                transmittance,
                spatial_cholesky_voxels,
                block_size,
                voxel_cm,
                density_scale,
                angular_sigma,
                ambient,
            ).tobytes(order="C"))
        else:
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
        "expanded_equivalent": len(centers) * len(LIGHT_DIRECTIONS_GL),
        "format": "compact_static_transport" if compact else "7drgs",
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
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--reference-grid", type=Path)
    parser.add_argument("--voxel-cm", type=float, default=0.0)
    parser.add_argument("--transport-source", type=Path)
    parser.add_argument("--scene-scale", type=float, default=0.2)
    parser.add_argument("--transport-neighbors", type=int, default=4)
    args = parser.parse_args()
    if args.transport_source is not None:
        result = transfer_standard_transport(
            args.source,
            args.transport_source,
            args.output,
            args.scene_scale,
            args.transport_neighbors,
        )
    elif args.source.suffix.lower() == ".npz":
        if not args.compact or args.reference_grid is None or args.voxel_cm <= 0.0:
            parser.error("NPZ export requires --compact, --reference-grid and --voxel-cm")
        result = convert_initializer(
            args.source,
            args.reference_grid,
            args.output,
            args.voxel_cm,
            args.density_scale,
            args.angular_sigma,
            args.ambient,
        )
    else:
        result = convert(
            args.source,
            args.output,
            args.block_size,
            args.longest_size_cm,
            args.density_scale,
            args.spatial_sigma_ratio,
            args.angular_sigma,
            args.ambient,
            args.compact,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
