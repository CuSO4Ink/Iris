"""Model Gaussian/VDB quality and runtime-memory break-even on the Hero cloud."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


PROJECT = Path(__file__).resolve().parents[1]
IRIS = PROJECT.parents[1]
HERO = IRIS / "tmp" / "cgheven_hero50"
MIB = 1 << 20
WIDTH = 1920
HEIGHT = 1080
TILE_SIZE = 32


def quantize_u8(grid: np.ndarray) -> np.ndarray:
    peak = float(np.max(grid))
    if peak <= 0.0:
        return np.zeros(grid.shape, np.uint8)
    return np.rint(np.clip(grid, 0.0, peak) * (255.0 / peak)).astype(np.uint8)


def _mip(values: np.ndarray) -> np.ndarray:
    shape = tuple((size + 1) // 2 for size in values.shape)
    padded = np.zeros(tuple(size * 2 for size in shape), np.uint8)
    padded[tuple(slice(0, size) for size in values.shape)] = values
    return np.rint(
        padded.reshape(shape[0], 2, shape[1], 2, shape[2], 2).mean((1, 3, 5))
    ).astype(np.uint8)


def svt_u8_memory(values: np.ndarray) -> dict:
    levels = []
    tile_data_bytes = page_table_bytes = 0
    mip = values
    while True:
        shape = mip.shape
        padded_shape = tuple(math.ceil(size / 16) * 16 for size in shape)
        padded = np.zeros(padded_shape, np.uint8)
        padded[tuple(slice(0, size) for size in shape)] = mip
        active = np.any(
            padded.reshape(
                padded_shape[0] // 16,
                16,
                padded_shape[1] // 16,
                16,
                padded_shape[2] // 16,
                16,
            ),
            axis=(1, 3, 5),
        )
        data_bytes = int(active.sum()) * 18**3
        page_bytes = active.size * 4
        levels.append(
            {
                "shape": list(shape),
                "active_tiles": int(active.sum()),
                "page_entries": int(active.size),
                "tile_data_bytes": data_bytes,
                "page_table_bytes": page_bytes,
            }
        )
        tile_data_bytes += data_bytes
        page_table_bytes += page_bytes
        if max(shape) == 1:
            break
        # ponytail: box-filter topology model; read UE cooked metadata if exact mip bytes matter.
        mip = _mip(mip)
    return {
        "tile_resolution": 16,
        "border_voxels": 1,
        "padded_voxels_per_tile": 18**3,
        "levels": levels,
        "tile_data_bytes": tile_data_bytes,
        "page_table_bytes": page_table_bytes,
        "total_bytes": tile_data_bytes + page_table_bytes,
    }


def gaussian_memory(kernel_count: int, width: int = 1920, height: int = 1080) -> dict:
    primitive_bytes = kernel_count * 48
    candidate_bytes = 512 * 1024 * 4
    tiles = math.ceil(width / 32) * math.ceil(height / 32)
    auxiliary_bytes = tiles * 4 * 4 + 6 * 4 + 4
    return {
        "kernel_count": kernel_count,
        "bytes_per_kernel": 48,
        "primitive_bytes": primitive_bytes,
        "candidate_bytes": candidate_bytes,
        "auxiliary_bytes": auxiliary_bytes,
        "total_bytes": primitive_bytes + candidate_bytes + auxiliary_bytes,
    }


def _axis_bounds(
    axis: np.ndarray,
    depth: np.ndarray,
    cov_axis: np.ndarray,
    cov_axis_depth: np.ndarray,
    cov_depth: np.ndarray,
    support: float,
    tan_half_fov: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    k2 = support * support
    a = depth * depth - k2 * cov_depth
    b = -2.0 * axis * depth + 2.0 * k2 * cov_axis_depth
    c = axis * axis - k2 * cov_axis
    discriminant = b * b - 4.0 * a * c
    full = a <= 1e-6
    valid = full | (discriminant >= 0.0)
    root = np.sqrt(np.maximum(discriminant, 0.0))
    denominator = np.where(full, 1.0, 2.0 * a)
    slope0 = (-b - root) / denominator
    slope1 = (-b + root) / denominator
    low = np.where(full, -tan_half_fov, np.minimum(slope0, slope1))
    high = np.where(full, tan_half_fov, np.maximum(slope0, slope1))
    visible = valid & (high >= -tan_half_fov) & (low <= tan_half_fov)
    return (
        np.clip(low / tan_half_fov, -1.0, 1.0),
        np.clip(high / tan_half_fov, -1.0, 1.0),
        visible,
    )


def _sphere_axis_bounds(
    axis: np.ndarray,
    depth: np.ndarray,
    radius: np.ndarray,
    tan_half_fov: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    distance = np.sqrt(axis * axis + depth * depth)
    full = distance <= radius
    center = np.arctan2(axis, depth)
    angular = np.arcsin(np.clip(radius / np.maximum(distance, 1e-12), 0.0, 1.0))
    half_fov = math.atan(tan_half_fov)
    low_angle = center - angular
    high_angle = center + angular
    visible = full | ((high_angle >= -half_fov) & (low_angle <= half_fov))
    low = np.where(full, -1.0, np.tan(np.clip(low_angle, -half_fov, half_fov)) / tan_half_fov)
    high = np.where(full, 1.0, np.tan(np.clip(high_angle, -half_fov, half_fov)) / tan_half_fov)
    return low, high, visible


def gaussian_view_work(
    centers: np.ndarray,
    covariances: np.ndarray,
    camera: np.ndarray,
    focal_x: float,
    focal_y: float,
    *,
    support: float = 3.0,
    width: int = WIDTH,
    height: int = HEIGHT,
    tile_size: int = TILE_SIZE,
) -> dict:
    origin = camera[:3, 3]
    right, up, forward = camera[:3, 0], -camera[:3, 1], camera[:3, 2]
    relative = centers - origin
    view_x = relative @ right
    view_y = relative @ up
    depth = relative @ forward
    radius = support * np.sqrt(np.linalg.eigvalsh(covariances)[:, -1])

    def quadratic(left: np.ndarray, right_axis: np.ndarray) -> np.ndarray:
        return np.einsum("i,nij,j->n", left, covariances, right_axis)

    cov_depth = quadratic(forward, forward)
    x0, x1, x_valid = _axis_bounds(
        view_x,
        depth,
        quadratic(right, right),
        quadratic(right, forward),
        cov_depth,
        support,
        width / (2.0 * focal_x),
    )
    y0, y1, y_valid = _axis_bounds(
        view_y,
        depth,
        quadratic(up, up),
        quadratic(up, forward),
        cov_depth,
        support,
        height / (2.0 * focal_y),
    )
    fallback = ~(x_valid & y_valid)
    sx0, sx1, sx_valid = _sphere_axis_bounds(
        view_x, depth, radius, width / (2.0 * focal_x)
    )
    sy0, sy1, sy_valid = _sphere_axis_bounds(
        view_y, depth, radius, height / (2.0 * focal_y)
    )
    x0, x1 = np.where(fallback, sx0, x0), np.where(fallback, sx1, x1)
    y0, y1 = np.where(fallback, sy0, y0), np.where(fallback, sy1, y1)
    visible = (depth + radius > 0.0) & np.where(fallback, sx_valid & sy_valid, True)

    pixel_x0 = np.clip((x0 * 0.5 + 0.5) * width, 0.0, width - 1.0)
    pixel_x1 = np.clip((x1 * 0.5 + 0.5) * width, 0.0, width - 1.0)
    pixel_y0 = np.clip((0.5 - y1 * 0.5) * height, 0.0, height - 1.0)
    pixel_y1 = np.clip((0.5 - y0 * 0.5) * height, 0.0, height - 1.0)
    visible &= (pixel_x1 >= pixel_x0) & (pixel_y1 >= pixel_y0)
    indices = np.flatnonzero(visible)
    px0 = np.floor(pixel_x0[indices]).astype(np.int32)
    px1 = np.floor(pixel_x1[indices]).astype(np.int32)
    py0 = np.floor(pixel_y0[indices]).astype(np.int32)
    py1 = np.floor(pixel_y1[indices]).astype(np.int32)
    tx0, tx1 = px0 // tile_size, px1 // tile_size
    ty0, ty1 = py0 // tile_size, py1 // tile_size
    tile_overlaps = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    tile_pixel_width = np.minimum(width, (tx1 + 1) * tile_size) - tx0 * tile_size
    tile_pixel_height = np.minimum(height, (ty1 + 1) * tile_size) - ty0 * tile_size
    tile_loop_tests = int(np.sum(tile_pixel_width.astype(np.int64) * tile_pixel_height))
    bbox_pixels = (px1 - px0 + 1).astype(np.int64) * (py1 - py0 + 1)

    safe_depth = np.maximum(depth[indices], 1e-6)
    jacobian_x = focal_x * (
        right[None] / safe_depth[:, None]
        - view_x[indices, None] * forward[None] / safe_depth[:, None] ** 2
    )
    jacobian_y = -focal_y * (
        up[None] / safe_depth[:, None]
        - view_y[indices, None] * forward[None] / safe_depth[:, None] ** 2
    )
    covariance = covariances[indices]
    var_x = np.einsum("ni,nij,nj->n", jacobian_x, covariance, jacobian_x)
    var_y = np.einsum("ni,nij,nj->n", jacobian_y, covariance, jacobian_y)
    cov_xy = np.einsum("ni,nij,nj->n", jacobian_x, covariance, jacobian_y)
    ellipse_pixels = np.minimum(
        math.pi * support * support * np.sqrt(np.maximum(var_x * var_y - cov_xy * cov_xy, 0.0)),
        bbox_pixels,
    )

    tile_count_x, tile_count_y = math.ceil(width / tile_size), math.ceil(height / tile_size)
    difference = np.zeros((tile_count_y + 1, tile_count_x + 1), np.int32)
    np.add.at(difference, (ty0, tx0), 1)
    np.add.at(difference, (ty1 + 1, tx0), -1)
    np.add.at(difference, (ty0, tx1 + 1), -1)
    np.add.at(difference, (ty1 + 1, tx1 + 1), 1)
    tile_counts = difference.cumsum(0).cumsum(1)[:-1, :-1]
    pixels = width * height
    return {
        "visible_kernels": int(len(indices)),
        "requested_candidate_ids": int(tile_overlaps.sum()),
        "max_candidates_in_one_tile": int(tile_counts.max()),
        "tile_loop_tests": tile_loop_tests,
        "tile_loop_tests_per_pixel": tile_loop_tests / pixels,
        "support_bbox_pixels_per_pixel": float(bbox_pixels.sum() / pixels),
        "linearized_ellipse_hits_per_pixel": float(ellipse_pixels.sum() / pixels),
        "mean_tiles_per_visible_kernel": float(tile_overlaps.mean()),
    }


def gaussian_runtime_work(path: Path, transforms_path: Path) -> dict:
    source = np.load(path)
    centers = source["center_m"].astype(np.float64)
    covariances = source["covariance_m2"].astype(np.float64)
    transforms = json.loads(transforms_path.read_text(encoding="utf-8"))
    scale_x, scale_y = WIDTH / transforms["w"], HEIGHT / transforms["h"]
    views = [
        gaussian_view_work(
            centers,
            covariances,
            np.asarray(frame["transform_matrix"], np.float64),
            transforms["fl_x"] * scale_x,
            transforms["fl_y"] * scale_y,
        )
        for frame in transforms["frames"]
    ]
    fields = (
        "visible_kernels",
        "requested_candidate_ids",
        "max_candidates_in_one_tile",
        "tile_loop_tests_per_pixel",
        "support_bbox_pixels_per_pixel",
        "linearized_ellipse_hits_per_pixel",
        "mean_tiles_per_visible_kernel",
    )
    average = {field: float(np.mean([view[field] for view in views])) for field in fields}
    average["candidate_pool_512k_overflow_views"] = sum(
        view["requested_candidate_ids"] > 512 * 1024 for view in views
    )
    return {
        "source": str(path),
        "resolution": [WIDTH, HEIGHT],
        "tile_size": TILE_SIZE,
        "support_sigma": 3.0,
        "views": views,
        "average": average,
    }


def _sample_index(grid: np.ndarray, points: np.ndarray) -> np.ndarray:
    base = np.clip(np.floor(points).astype(np.int32), 0, np.asarray(grid.shape) - 1)
    upper = np.minimum(base + 1, np.asarray(grid.shape) - 1)
    fraction = points - base
    result = np.zeros(len(points), np.float32)
    for x in (0, 1):
        ix = np.where(x, upper[:, 0], base[:, 0])
        wx = np.where(x, fraction[:, 0], 1.0 - fraction[:, 0])
        for y in (0, 1):
            iy = np.where(y, upper[:, 1], base[:, 1])
            wy = np.where(y, fraction[:, 1], 1.0 - fraction[:, 1])
            for z in (0, 1):
                iz = np.where(z, upper[:, 2], base[:, 2])
                wz = np.where(z, fraction[:, 2], 1.0 - fraction[:, 2])
                result += grid[ix, iy, iz] * wx * wy * wz
    return result


def _ray_summary(values: np.ndarray) -> dict:
    return {
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "max": int(values.max()),
    }


def vdb_runtime_work(
    grid: np.ndarray,
    scene_path: Path,
    transforms_path: Path,
    *,
    step_size: float = 0.75,
    max_steps: int = 1024,
    sample_width: int = 24,
    sample_height: int = 14,
) -> dict:
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    transforms = json.loads(transforms_path.read_text(encoding="utf-8"))
    bounds = np.asarray((scene["bbox_min"], scene["bbox_max"]), np.float64)
    rows, columns = np.meshgrid(
        (np.arange(sample_height) + 0.5) * transforms["h"] / sample_height,
        (np.arange(sample_width) + 0.5) * transforms["w"] / sample_width,
        indexing="ij",
    )
    camera_directions = np.stack(
        (
            (columns - transforms["cx"]) / transforms["fl_x"],
            (rows - transforms["cy"]) / transforms["fl_y"],
            np.ones_like(columns),
        ),
        axis=-1,
    ).reshape(-1, 3)
    origins, directions = [], []
    for frame in transforms["frames"]:
        camera = np.asarray(frame["transform_matrix"], np.float64)
        world = camera_directions @ camera[:3, :3].T
        world /= np.linalg.norm(world, axis=1, keepdims=True)
        origins.append(np.broadcast_to(camera[:3, 3], world.shape))
        directions.append(world)
    origins, directions = np.concatenate(origins), np.concatenate(directions)

    index_scale = np.asarray(
        (
            (grid.shape[0] - 1) / (bounds[1, 0] - bounds[0, 0]),
            (grid.shape[1] - 1) / (bounds[1, 2] - bounds[0, 2]),
            (grid.shape[2] - 1) / (bounds[1, 1] - bounds[0, 1]),
        )
    )
    index_origins = np.stack(
        (
            (origins[:, 0] - bounds[0, 0]) * index_scale[0],
            (bounds[1, 2] - origins[:, 2]) * index_scale[1],
            (bounds[1, 1] - origins[:, 1]) * index_scale[2],
        ),
        axis=1,
    )
    index_directions = np.stack(
        (
            directions[:, 0] * index_scale[0],
            -directions[:, 2] * index_scale[1],
            -directions[:, 1] * index_scale[2],
        ),
        axis=1,
    )
    index_directions /= np.linalg.norm(index_directions, axis=1, keepdims=True)

    active = grid > 0.0
    occupied_axes = (
        np.any(active, axis=(1, 2)),
        np.any(active, axis=(0, 2)),
        np.any(active, axis=(0, 1)),
    )
    active_min = np.asarray([np.flatnonzero(axis)[0] for axis in occupied_axes], np.float64)
    active_max = np.asarray([np.flatnonzero(axis)[-1] + 1 for axis in occupied_axes], np.float64)
    inverse = np.where(np.abs(index_directions) > 1e-12, 1.0 / index_directions, 1e12)
    t0 = (active_min - index_origins) * inverse
    t1 = (active_max - index_origins) * inverse
    enter = np.maximum(np.minimum(t0, t1).max(axis=1), 0.0)
    leave = np.maximum(t0, t1).min(axis=1)
    dense_steps = np.minimum(
        np.ceil(np.maximum(leave - enter, 0.0) / step_size).astype(np.int32), max_steps
    )

    padded_shape = tuple(math.ceil(size / 8) * 8 for size in grid.shape)
    padded = np.zeros(padded_shape, bool)
    padded[tuple(slice(0, size) for size in grid.shape)] = active
    active_leaf = np.any(
        padded.reshape(
            padded_shape[0] // 8,
            8,
            padded_shape[1] // 8,
            8,
            padded_shape[2] // 8,
            8,
        ),
        axis=(1, 3, 5),
    )
    active_voxel_steps = np.zeros(len(origins), np.int32)
    active_leaf_steps = np.zeros(len(origins), np.int32)
    empty_leaf_skips = np.zeros(len(origins), np.int32)
    inactive_voxel_skips = np.zeros(len(origins), np.int32)
    effective_steps = dense_steps.copy()
    threshold = -math.log(0.001)
    density_per_voxel = float(scene["density_scale"]) * float(scene["voxel_cm"])
    sequence = np.arange(max_steps)
    for start in range(0, len(origins), 384):
        stop = min(start + 384, len(origins))
        counts = dense_steps[start:stop]
        valid = sequence[None] < counts[:, None]
        t = enter[start:stop, None] + (sequence[None] + 0.5) * step_size
        points = index_origins[start:stop, None] + index_directions[start:stop, None] * t[..., None]
        flat_valid = valid.ravel()
        flat_points = points.reshape(-1, 3)[flat_valid]
        density = np.zeros(valid.size, np.float32)
        density[flat_valid] = _sample_index(grid, flat_points)
        tau = np.cumsum(density.reshape(valid.shape) * density_per_voxel * step_size, axis=1)
        terminated = tau >= threshold
        has_terminated = terminated.any(axis=1)
        first = np.argmax(terminated, axis=1) + 1
        effective = np.where(has_terminated, np.minimum(first, counts), counts)
        effective_steps[start:stop] = effective
        valid &= sequence[None] < effective[:, None]

        ijk = np.clip(
            np.floor(points).astype(np.int32), 0, np.asarray(grid.shape) - 1
        )
        voxel_active = active[ijk[..., 0], ijk[..., 1], ijk[..., 2]] & valid
        leaf = ijk // 8
        leaf_active = active_leaf[leaf[..., 0], leaf[..., 1], leaf[..., 2]] & valid
        active_voxel_steps[start:stop] = voxel_active.sum(axis=1)
        active_leaf_steps[start:stop] = leaf_active.sum(axis=1)
        leaf_id = (leaf[..., 0] * active_leaf.shape[1] + leaf[..., 1]) * active_leaf.shape[2] + leaf[..., 2]
        voxel_id = (ijk[..., 0] * grid.shape[1] + ijk[..., 1]) * grid.shape[2] + ijk[..., 2]
        previous_leaf_changed = np.ones(valid.shape, bool)
        previous_voxel_changed = np.ones(valid.shape, bool)
        previous_leaf_changed[:, 1:] = leaf_id[:, 1:] != leaf_id[:, :-1]
        previous_voxel_changed[:, 1:] = voxel_id[:, 1:] != voxel_id[:, :-1]
        empty_leaf_skips[start:stop] = (valid & ~leaf_active & previous_leaf_changed).sum(axis=1)
        inactive_voxel_skips[start:stop] = (
            valid & leaf_active & ~voxel_active & previous_voxel_changed
        ).sum(axis=1)

    nano_loop_lower = active_voxel_steps + inactive_voxel_skips + empty_leaf_skips
    nano_loop_upper = active_leaf_steps + empty_leaf_skips
    return {
        "ray_sample_grid_per_view": [sample_width, sample_height],
        "sampled_rays": len(origins),
        "step_size_voxels": step_size,
        "max_steps": max_steps,
        "dense_or_svt_trilinear_samples": _ray_summary(effective_steps),
        "nanovdb_expensive_trilinear_samples_lower": _ray_summary(active_voxel_steps),
        "nanovdb_expensive_trilinear_samples_leaf_upper": _ray_summary(active_leaf_steps),
        "nanovdb_loop_iterations_lower": _ray_summary(nano_loop_lower),
        "nanovdb_loop_iterations_leaf_upper": _ray_summary(nano_loop_upper),
        "early_terminated_fraction": float(np.mean(effective_steps < dense_steps)),
        "max_step_capped_fraction": float(np.mean(dense_steps >= max_steps)),
        "notes": [
            "NanoVDB lower treats active voxels as trilinear samples and counts inactive-voxel/empty-leaf skips.",
            "NanoVDB leaf upper pessimistically treats every 0.75-voxel step inside an occupied 8^3 leaf as a trilinear sample.",
            "Both are operation counts, not milliseconds; hierarchy and analytic kernel operations have different GPU costs.",
        ],
    }


def _sample_trilinear(grid: np.ndarray, points: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    normalized = (points - bounds[0]) / (bounds[1] - bounds[0])
    coordinates = np.stack(
        (
            normalized[:, 0] * (grid.shape[0] - 1),
            (1.0 - normalized[:, 2]) * (grid.shape[1] - 1),
            (1.0 - normalized[:, 1]) * (grid.shape[2] - 1),
        ),
        axis=1,
    )
    valid = np.all((coordinates >= 0.0) & (coordinates <= np.asarray(grid.shape) - 1), axis=1)
    base = np.clip(
        np.floor(coordinates).astype(np.int64), 0, np.asarray(grid.shape) - 1
    )
    upper = np.minimum(base + 1, np.asarray(grid.shape) - 1)
    fraction = coordinates - base
    result = np.zeros(len(points), np.float32)
    for x in (0, 1):
        ix = np.where(x, upper[:, 0], base[:, 0])
        wx = np.where(x, fraction[:, 0], 1.0 - fraction[:, 0])
        for y in (0, 1):
            iy = np.where(y, upper[:, 1], base[:, 1])
            wy = np.where(y, fraction[:, 1], 1.0 - fraction[:, 1])
            for z in (0, 1):
                iz = np.where(z, upper[:, 2], base[:, 2])
                wz = np.where(z, fraction[:, 2], 1.0 - fraction[:, 2])
                result += grid[ix, iy, iz] * wx * wy * wz * valid
    return result


def integrate_tau(
    grid: np.ndarray,
    origins: np.ndarray,
    directions: np.ndarray,
    bounds: np.ndarray,
    density_scale: float,
    steps: int,
) -> np.ndarray:
    inverse = np.where(np.abs(directions) > 1e-8, 1.0 / directions, 1e8)
    t0 = (bounds[0] - origins) * inverse
    t1 = (bounds[1] - origins) * inverse
    enter = np.maximum(np.minimum(t0, t1).max(axis=1), 0.0)
    leave = np.maximum(t0, t1).min(axis=1)
    distance = enter[:, None] + np.maximum(leave - enter, 0.0)[:, None] * (
        (np.arange(steps, dtype=np.float32) + 0.5) / steps
    )
    points = origins[:, None] + directions[:, None] * distance[:, :, None]
    density = _sample_trilinear(grid, points.reshape(-1, 3), bounds).reshape(-1, steps)
    delta_cm = np.maximum(leave - enter, 0.0) * (100.0 / steps)
    return density.sum(axis=1) * density_scale * delta_cm * (leave > enter)


def ray_quality(grid: np.ndarray, dataset: Path, seed: int = 20260727) -> dict:
    from evaluate_heldout import compute_metrics
    from recover_contracted_50k import _gather_patches, _patch_pool, load_rays

    origins, directions, target_tau = load_rays(dataset)
    heldout = np.arange(1, len(origins), 4)
    centers, weights = _patch_pool(target_tau, heldout)
    rng = np.random.default_rng(seed)
    selected = centers[
        rng.choice(len(centers), size=1024 // 9, replace=False, p=weights)
    ]
    ray_origins, ray_directions, target = _gather_patches(
        origins, directions, target_tau, selected
    )
    scene = json.loads((dataset / "scene.json").read_text(encoding="utf-8"))
    bounds = np.asarray((scene["bbox_min"], scene["bbox_max"]), np.float32)
    float_tau = integrate_tau(
        grid.astype(np.float32, copy=False),
        ray_origins,
        ray_directions,
        bounds,
        float(scene["density_scale"]),
        256,
    )
    u8 = quantize_u8(grid).astype(np.float32) * (float(np.max(grid)) / 255.0)
    u8_tau = integrate_tau(
        u8,
        ray_origins,
        ray_directions,
        bounds,
        float(scene["density_scale"]),
        256,
    )
    reference_t = np.exp(-target)
    return {
        "rays": len(target),
        "float_grid": compute_metrics(reference_t, float_tau, alpha_threshold=1e-4),
        "global_u8_grid": compute_metrics(reference_t, u8_tau, alpha_threshold=1e-4),
    }


def _file_bytes(path: Path, *, nanovdb: bool = False) -> dict | None:
    if not path.exists():
        return None
    size = path.stat().st_size
    result = {"path": str(path), "container_bytes": size}
    if nanovdb:
        result["raw_grid_bytes"] = max(0, size - 200)
    return result


def _load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "kernel_count": report["kernel_count"],
        "final_metrics": report["final_metrics"],
    }


def simulate(args: argparse.Namespace) -> dict:
    grid = np.load(args.grid, mmap_mode="r").squeeze()
    q8 = quantize_u8(grid)
    decoded = q8.astype(np.float32) * (float(np.max(grid)) / 255.0)
    error = decoded - grid
    svt = svt_u8_memory(q8)
    files = {
        "openvdb": _file_bytes(args.vdb),
        "ue_svt_u8": _file_bytes(args.svt),
        "nanovdb_fp8": _file_bytes(args.nanovdb_fp8, nanovdb=True),
        "nanovdb_fpn_abs1e_3": _file_bytes(args.nanovdb_fpn, nanovdb=True),
    }
    gaussian = {str(count): gaussian_memory(count) for count in args.kernel_counts}
    baselines = {
        "ue_svt_u8_full_resident": svt["total_bytes"],
        **{
            name: row["raw_grid_bytes"]
            for name, row in files.items()
            if row and "raw_grid_bytes" in row
        },
    }
    fixed = gaussian[str(args.kernel_counts[0])]["candidate_bytes"] + gaussian[
        str(args.kernel_counts[0])
    ]["auxiliary_bytes"]
    break_even = {
        name: max(0, (size - fixed) // 48) for name, size in baselines.items()
    }
    advantage_targets = {
        name: {
            f"{factor}x": max(0, (int(size / factor) - fixed) // 48)
            for factor in (1, 2, 4)
        }
        for name, size in baselines.items()
    }
    strongest_name = min(baselines, key=baselines.get)
    strongest_bytes = baselines[strongest_name]
    runtime_gaussian = runtime_vdb = runtime_break_even = None
    if not args.skip_runtime:
        transforms = args.dataset / "transforms_train.json"
        runtime_gaussian = gaussian_runtime_work(args.gaussian_50k, transforms)
        runtime_vdb = vdb_runtime_work(
            grid,
            args.dataset / "scene.json",
            transforms,
            step_size=args.vdb_step_size,
            max_steps=args.vdb_max_steps,
        )
        gaussian_hits = max(
            runtime_gaussian["average"]["linearized_ellipse_hits_per_pixel"], 1e-12
        )
        runtime_break_even = {
            "interpretation": "optimistic maximum cost of one analytic Gaussian integral relative to one VDB trilinear sample; candidate binning/rejection cost excluded",
            "vs_dense_or_svt_sample": runtime_vdb["dense_or_svt_trilinear_samples"]["mean"] / gaussian_hits,
            "vs_nanovdb_active_sample_lower": runtime_vdb[
                "nanovdb_expensive_trilinear_samples_lower"
            ]["mean"]
            / gaussian_hits,
            "vs_nanovdb_occupied_leaf_upper": runtime_vdb[
                "nanovdb_expensive_trilinear_samples_leaf_upper"
            ]["mean"]
            / gaussian_hits,
        }
    result = {
        "scope": "runtime representation only; offline fitting/training excluded",
        "source": {
            "grid": str(args.grid),
            "shape": list(grid.shape),
            "active_voxels": int(np.count_nonzero(grid > 0.0)),
            "float_grid_bytes": int(grid.nbytes),
        },
        "quality": {
            "global_u8_density_rmse": float(np.sqrt(np.mean(error * error))),
            "global_u8_density_psnr_db": float(-20.0 * np.log10(max(np.sqrt(np.mean(error * error)), 1e-30))),
            "heldout_rays": None if args.skip_rays else ray_quality(grid, args.dataset),
            "gaussian_reports": {
                "50k": _load_report(args.report_50k),
                "100k": _load_report(args.report_100k),
            },
        },
        "storage": {
            "files": files,
            "ue_svt_u8_model": svt,
            "gaussian": gaussian,
            "baseline_runtime_bytes": baselines,
            "break_even_kernel_count_at_48_bytes": break_even,
            "max_kernel_count_by_memory_advantage": advantage_targets,
        },
        "runtime_work": {
            "units": "per-frame operation counts, not milliseconds",
            "gaussian": runtime_gaussian,
            "vdb": runtime_vdb,
            "optimistic_analytic_cost_break_even": runtime_break_even,
        },
        "decision": {
            "strongest_runtime_baseline": strongest_name,
            "strongest_runtime_baseline_bytes": strongest_bytes,
            "max_kernels_to_beat_strongest_baseline": break_even[strongest_name],
            "max_kernels_for_2x_vs_strongest_baseline": advantage_targets[
                strongest_name
            ]["2x"],
            "50k_memory_advantage_x": strongest_bytes / gaussian["50000"]["total_bytes"]
            if "50000" in gaussian
            else None,
            "structural_feasibility": break_even[strongest_name] >= 50_000,
            "current_50k_matches_u8_quality": False,
        },
    }
    return result


def markdown(result: dict) -> str:
    decision = result["decision"]
    storage = result["storage"]
    quality = result["quality"]
    ray = quality["heldout_rays"]
    gaussian_50k = quality["gaussian_reports"]["50k"]
    runtime = result["runtime_work"]
    lines = [
        "# Gaussian vs VDB bottom-up simulation",
        "",
        "Offline fitting/training cost is excluded. All byte counts are final runtime representation costs.",
        "",
        "## Verdict",
        "",
        f"The data structure has a real win window: the final representation must stay at or below **{decision['max_kernels_to_beat_strongest_baseline']:,} kernels** to beat the strongest local baseline ({decision['strongest_runtime_baseline']}).",
        f"A portfolio-grade **2x** memory claim requires at most **{decision['max_kernels_for_2x_vs_strongest_baseline']:,} kernels**. At 50K it is **{decision['50k_memory_advantage_x']:.2f}x smaller**, including the 512K candidate pool and auxiliary buffers.",
        "The current 50K asset does not yet match VDB quality; this is a quality-fit gap, not a storage-layout failure.",
        "",
    ]
    if runtime["gaussian"]:
        gaussian_work = runtime["gaussian"]["average"]
        vdb_work = runtime["vdb"]
        cost_limit = runtime["optimistic_analytic_cost_break_even"]
        pixels_m = WIDTH * HEIGHT / 1e6
        view_count = len(runtime["gaussian"]["views"])
        lines += [
            "## Runtime GPU work at 1920x1080",
            "",
            f"These are shader-path work counts from the real 50K covariance, {view_count} camera poses, grid occupancy, 0.75-voxel NanoVDB step, HDDA leaf bounds, and T<0.001 early termination. They are not claimed milliseconds.",
            "",
            "| Work item | Mean per pixel/ray | 1080p events/frame |",
            "|---|---:|---:|",
            f"| Gaussian tile candidate loop | {gaussian_work['tile_loop_tests_per_pixel']:.2f} | {gaussian_work['tile_loop_tests_per_pixel'] * pixels_m:.1f}M |",
            f"| Gaussian analytic support hits (linearized estimate) | {gaussian_work['linearized_ellipse_hits_per_pixel']:.2f} | {gaussian_work['linearized_ellipse_hits_per_pixel'] * pixels_m:.1f}M |",
            f"| Gaussian support-bbox ceiling | {gaussian_work['support_bbox_pixels_per_pixel']:.2f} | {gaussian_work['support_bbox_pixels_per_pixel'] * pixels_m:.1f}M |",
            f"| Dense/SVT ray samples | {vdb_work['dense_or_svt_trilinear_samples']['mean']:.2f} | {vdb_work['dense_or_svt_trilinear_samples']['mean'] * pixels_m:.1f}M |",
            f"| NanoVDB active-voxel trilinear lower | {vdb_work['nanovdb_expensive_trilinear_samples_lower']['mean']:.2f} | {vdb_work['nanovdb_expensive_trilinear_samples_lower']['mean'] * pixels_m:.1f}M |",
            f"| NanoVDB occupied-leaf trilinear upper | {vdb_work['nanovdb_expensive_trilinear_samples_leaf_upper']['mean']:.2f} | {vdb_work['nanovdb_expensive_trilinear_samples_leaf_upper']['mean'] * pixels_m:.1f}M |",
            f"| NanoVDB total loop lower / leaf upper | {vdb_work['nanovdb_loop_iterations_lower']['mean']:.2f} / {vdb_work['nanovdb_loop_iterations_leaf_upper']['mean']:.2f} | {vdb_work['nanovdb_loop_iterations_lower']['mean'] * pixels_m:.1f}M / {vdb_work['nanovdb_loop_iterations_leaf_upper']['mean'] * pixels_m:.1f}M |",
            "",
            f"The configured 512K candidate pool would overflow in **{int(gaussian_work['candidate_pool_512k_overflow_views'])}/{view_count}** sampled views; average requested IDs are **{gaussian_work['requested_candidate_ids']:,.0f}**. Tile granularity amplifies the idealized ellipse work by **{gaussian_work['tile_loop_tests_per_pixel'] / gaussian_work['linearized_ellipse_hits_per_pixel']:.2f}x**. This is the first runtime failure condition to watch, because close-up projected overlap grows before kernel count changes.",
            "",
            "**Implementation prerequisite:** the plugin CVar currently defaults to `r.GaussianVolume.CandidatePoolCapacity=0` (exact worst-case allocation). The 4.32 MiB claim requires pinning it to `524288`; leaving it at 0 invalidates the bounded-memory result.",
            "",
            "Ignoring Gaussian binning and cheap sphere rejects, one analytic Gaussian integral may cost at most:",
            "",
            f"- **{cost_limit['vs_dense_or_svt_sample']:.2f}x** one dense/SVT sample to break even.",
            f"- **{cost_limit['vs_nanovdb_active_sample_lower']:.2f}x to {cost_limit['vs_nanovdb_occupied_leaf_upper']:.2f}x** one NanoVDB trilinear sample, depending on how much work HDDA removes inside occupied leaves.",
            "",
            "That ratio is the theoretical runtime gate. A Gaussian integral uses reciprocal/rsqrt/exp/erf, while the NanoVDB sample uses hierarchy reads plus eight density reads, so operation counts alone cannot honestly decide RTX 5060 milliseconds.",
            "Against dense/SVT marching the positive runtime window is broad enough to be plausible. Against the stronger NanoVDB baseline it is narrow: the current shader path is **not yet theoretically guaranteed faster**, but the representation can win if overlap is reduced and the analytic integral stays below the measured 1.77x-2.18x sample-cost gate. Comparable static self-shadowing would also add a light cache lookup or secondary work to the VDB side; the direct NanoVDB shader counted here has no such lighting cost.",
            "",
            "## Performance factor map",
            "",
            "| Factor | Gaussian kernels | VDB / NanoVDB | Bottom-level judgment |",
            "|---|---|---|---|",
            "| Resident payload | O(N kernels), 48 B each here | O(active voxels + hierarchy + mips) | **Gaussian structural win** only below the measured kernel break-even |",
            "| Auxiliary/transient memory | Candidate IDs, per-tile counts, optional LOD target | Page tables, caches, light volume, output target | Conditional; compare complete renderer state, not asset file size |",
            "| View culling | O(N) ellipsoid projection | O(pixels) ray-box + hierarchy entry | Gaussian advantage only when N is bounded and reused across many pixels |",
            "| Binning | Count + atomics + prefix + scatter over tile overlaps | None for direct ray march | **VDB advantage**; this is Gaussian overhead |",
            "| Per-pixel primary work | Candidate rejects + analytic integrals | HDDA iterations + trilinear samples | Winner is overlap-vs-sample break-even above |",
            "| Empty space | Support bounds skip non-overlapping kernels | Hierarchy skips empty nodes/bricks | **VDB structural win** for sparse/filamentary volumes |",
            "| Long ray segments | Integral cost is independent of segment sample count | Cost rises with occupied distance / step size | **Gaussian structural win** when few kernels cover long smooth segments |",
            "| Close-up / large screen support | Tile overlap and per-pixel candidate count can explode | Ray cost stays tied to depth samples | **VDB structural win** outside the mid/far window |",
            "| High spatial frequency | Needs more/smaller kernels and overlap | Native voxel samples preserve detail | VDB advantage; Gaussian win requires screen-space band limiting |",
            "| Early ray termination | Cannot safely stop before bounding unseen positive tau | Stops at T<0.001 | **VDB structural win** for opaque paths |",
            "| Filtering / LOD | Explicit kernel LOD can remove whole primitives | Native mip/filter hierarchy | Conditional; VDB has the safer default |",
            "| Lighting, static one-directional | Six baked per-kernel tau values, O(1) interpolation | Needs light cache lookup or secondary march for comparable self-shadow | **Gaussian conditional win** in this fixed portfolio scope |",
            "| Lighting, dynamic/multiple | Basis approximation or rebuild | Volume cache / ray marching generalizes naturally | VDB advantage when the lighting scope expands |",
            "| Appearance compositing | Uniform extinction is commutative; one final exp, no sort | Front-to-back step compositing | Gaussian advantage in this uniform-cloud scope |",
            "| Per-kernel colors/emission | Requires hit list, per-ray order and register-heavy sort | Naturally ordered along ray | **VDB advantage**; current 64-hit sort is not used by the uniform fast path |",
            "| Math pipeline | SFU/ALU-heavy reciprocal, sqrt, exp, erf | Load/cache-heavy hierarchy and 8-corner interpolation | Hardware-dependent; must calibrate on RTX 5060 |",
            "| Register pressure / occupancy | Current dynamic uniform path still declares 64-hit arrays | Small per-ray traversal state | Current implementation favors VDB; static uniform shader permutation can remove this |",
            "| Cache locality | Compact sequential primitive records, tile ID reuse | Random hierarchy reads; nearby rays improve coherence | Conditional Gaussian advantage, SVT hardware texture cache narrows it |",
            "| Divergence | Different tile counts and support hits | Different HDDA steps and early exits | Neither has an unconditional advantage |",
            "| Atomics / serialization | Tile count/scatter atomics; current prefix is one thread | Traversal has no global binning atomics | VDB implementation advantage |",
            "| Resolution scaling | Main pixel work is O(pixels x overlap) | O(pixels x samples) | Both scale with pixels; Gaussian preprocessing is resolution-light |",
            "| Instances | Payload can be shared, but visible overlap multiplies | Grid can also be shared, ray work multiplies | Memory sharing is not a unique Gaussian runtime win |",
            "| Scene-depth occlusion | Clips analytic segments after candidates are fetched | Clips ray tMax before marching | VDB usually benefits earlier |",
            "| Quality knobs | Support threshold and kernel LOD trade overlap for error | Step size, mip and quantization trade samples for error | Must be locked by the same screen-space quality gate |",
            "| Precision | Packed FP16/SNorm kernel fields | Fp8/FpN density plus hierarchy | Representation-specific; include artifacts in the quality gate, not just time |",
            "| Output/composite path | In-place UAV can avoid owned fullscreen copy | Can use the same optimization | Implementation detail, not a representation advantage |",
            "| Upload/startup | Small kernel stream uploads quickly | Larger hierarchy/tiles cost more I/O | Gaussian conditional win; offline fitting remains excluded |",
            "",
            "## What is genuinely structural",
            "",
            "The positive window is: **screen-space matched quality + smooth coherent density + mid/far view + bounded projected overlap + uniform appearance + static single-directional lighting**. In that window Gaussian replaces many ray samples with a smaller number of continuous analytic kernels and keeps lighting state on those kernels.",
            "",
            "The negative window is equally structural: **close-up, high-frequency wisps, highly sparse topology, high opacity, per-kernel appearance, or dynamic lighting**. There NanoVDB's HDDA, early termination, native ordering and mip hierarchy are real advantages, not implementation accidents.",
            "",
        ]
    lines += [
        "## Runtime memory",
        "",
        "| Representation | MiB |",
        "|---|---:|",
    ]
    for name, size in storage["baseline_runtime_bytes"].items():
        lines.append(f"| {name} | {size / MIB:.3f} |")
    for count, row in storage["gaussian"].items():
        lines.append(f"| Gaussian {int(count):,} × 48 B + renderer buffers | {row['total_bytes'] / MIB:.3f} |")
    lines += ["", "## Quality on the shared held-out rays", ""]
    if ray:
        lines += [
            "| Representation | Foreground T PSNR | τ PSNR |",
            "|---|---:|---:|",
            f"| Float grid replay | {ray['float_grid']['transmittance_psnr_foreground_db']:.2f} dB | {ray['float_grid']['tau_psnr_db']:.2f} dB |",
            f"| Global U8 grid | {ray['global_u8_grid']['transmittance_psnr_foreground_db']:.2f} dB | {ray['global_u8_grid']['tau_psnr_db']:.2f} dB |",
        ]
    if gaussian_50k:
        metrics = gaussian_50k["final_metrics"]
        lines.append(
            f"| Current Gaussian 50K | {metrics['transmittance_psnr_foreground_db']:.2f} dB | {metrics['tau_psnr_db']:.2f} dB |"
        )
    lines += [
        "",
        "## TA-facing interpretation",
        "",
        "The defensible claim is not voxel-for-voxel compression. It is screen-space matched quality for a bounded 1080p mid/far use case. VDB pays for every active voxel and mip regardless of visibility; Gaussian pays for continuous kernels plus a view-dependent candidate set.",
        f"If matched visual quality needs more than {decision['max_kernels_to_beat_strongest_baseline']:,} kernels, Gaussian loses to the strongest NanoVDB baseline even if it still beats UE SVT.",
        "",
    ]
    return "\n".join(lines)


def self_check() -> None:
    grid = np.ones((1, 1, 1), np.float32)
    assert quantize_u8(grid).item() == 255
    assert svt_u8_memory(quantize_u8(grid))["total_bytes"] == 18**3 + 4
    assert gaussian_memory(50_000)["total_bytes"] == 4_529_820
    sampled = _sample_trilinear(
        np.arange(8, dtype=np.float32).reshape(2, 2, 2),
        np.asarray(((0.5, 0.5, 0.5),), np.float32),
        np.asarray(((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), np.float32),
    )
    assert np.allclose(sampled, 3.5)
    low, high, visible = _axis_bounds(
        np.asarray((0.0,)),
        np.asarray((2.0,)),
        np.asarray((1.0,)),
        np.asarray((0.0,)),
        np.asarray((1.0,)),
        1.0,
        1.0,
    )
    assert visible.item() and low.item() < 0.0 < high.item()
    assert np.allclose(_sample_index(grid, np.asarray(((0.0, 0.0, 0.0),))), 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=HERO / "Hero_Cloud_02_v50_density_pad8.npy")
    parser.add_argument("--vdb", type=Path, default=HERO / "Hero_Cloud_02_v50_density_only.vdb")
    parser.add_argument(
        "--svt",
        type=Path,
        default=Path(r"D:\Work\Personal\Project\Abyss\Content\GaussianVolume\Baselines\SVT_CGHEVEN_HeroCongestus50_U8.uasset"),
    )
    parser.add_argument("--nanovdb-fp8", type=Path, default=HERO / "nanovdb" / "Hero_Cloud_02_v50_density_fp8.nvdb")
    parser.add_argument("--nanovdb-fpn", type=Path, default=HERO / "nanovdb" / "Hero_Cloud_02_v50_density_fpn_abs1e-3.nvdb")
    parser.add_argument("--dataset", type=Path, default=PROJECT / "artifacts" / "hero_directional24")
    parser.add_argument("--report-50k", type=Path, default=PROJECT / "artifacts" / "hero_tau_recovered50k_v2" / "recovery_report.json")
    parser.add_argument("--report-100k", type=Path, default=PROJECT / "artifacts" / "hero_tau_recovered100k_step300" / "recovery_report.json")
    parser.add_argument("--gaussian-50k", type=Path, default=PROJECT / "artifacts" / "hero_tau_recovered50k_v2" / "recovered.npz")
    parser.add_argument(
        "--kernel-counts",
        type=int,
        nargs="+",
        default=(50_000, 100_000, 150_000, 165_000, 200_000),
    )
    parser.add_argument("--output", type=Path, default=PROJECT / "artifacts" / "storage_simulation" / "gaussian_vs_vdb.json")
    parser.add_argument("--skip-rays", action="store_true")
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--vdb-step-size", type=float, default=0.75)
    parser.add_argument("--vdb-max-steps", type=int, default=1024)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("simulate_gaussian_vs_vdb self-check passed")
        return
    result = simulate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = args.output.with_suffix(".md")
    report.write_text(markdown(result), encoding="utf-8")
    print(markdown(result))


if __name__ == "__main__":
    main()
