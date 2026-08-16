"""Build deterministic linear 7DRGS supervision and a B2 spatial initializer."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import Imath
import numpy as np
import OpenEXR
import torch
import torch.nn.functional as F
from PIL import Image
from plyfile import PlyData, PlyElement

from grid_to_7drgs import (
    LIGHT_DIRECTIONS_GL,
    LIGHT_DIRECTIONS_UE,
    _aggregate_grid,
)
from lift_volprim_to_7drgs import SH_C0, _inverse_softplus


INIT_PROPERTIES = (
    "x", "y", "z",
    "f_dc_j", "f_rest_j_0", "f_rest_j_1", "f_rest_j_2",
    "opacity",
    "scale_0", "scale_1", "scale_2",
    "rot_0", "rot_1", "rot_2", "rot_3",
    "mu_t", "mu_d_0", "mu_d_1", "mu_d_2",
    *(f"chol_diag_{index}" for index in range(7)),
    *(f"chol_offdiag_{index}" for index in range(21)),
    "lambda_t", "lambda_d",
    "f_dc_t", "f_rest_t_0", "f_rest_t_1", "f_rest_t_2",
)
SH_C1 = 0.4886025119029199
STATIC_LAMBDA_RAW = _inverse_softplus(1e-8)
SH1_BASIS = np.stack(
    (
        np.full(len(LIGHT_DIRECTIONS_GL), SH_C0),
        -SH_C1 * LIGHT_DIRECTIONS_GL[:, 1],
        SH_C1 * LIGHT_DIRECTIONS_GL[:, 2],
        -SH_C1 * LIGHT_DIRECTIONS_GL[:, 0],
    ),
    axis=1,
).astype(np.float64)
SH1_PINV = np.linalg.pinv(SH1_BASIS)


def _write_exr(path: Path, rgba: np.ndarray) -> None:
    rgba = np.asarray(rgba, dtype=np.float32)
    height, width, channels = rgba.shape
    if channels != 4 or not np.isfinite(rgba).all():
        raise ValueError(f"invalid RGBA image for {path}")
    header = OpenEXR.Header(width, height)
    pixel_type = Imath.PixelType(Imath.PixelType.FLOAT)
    header["channels"] = {
        name: Imath.Channel(pixel_type) for name in ("R", "G", "B", "A")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    output = OpenEXR.OutputFile(str(path), header)
    try:
        output.writePixels({
            name: np.ascontiguousarray(rgba[:, :, index]).tobytes()
            for index, name in enumerate(("R", "G", "B", "A"))
        })
    finally:
        output.close()


def _write_init_ply(
    path: Path,
    centers_cm: np.ndarray,
    spatial_cholesky_voxels: np.ndarray,
    voxel_cm: float,
) -> int:
    cholesky = spatial_cholesky_voxels.astype(np.float32) * (voxel_cm / 100.0)
    centers = centers_cm.astype(np.float32)
    xyz = np.stack((centers[:, 0], -centers[:, 2], -centers[:, 1]), axis=1) / 100.0
    diag = np.diagonal(cholesky, axis1=1, axis2=2)
    row_norm = np.sqrt(np.sum(cholesky * cholesky, axis=2))

    rows = np.empty(len(xyz), dtype=[(name, "<f4") for name in INIT_PROPERTIES])
    rows[:] = tuple(0.0 for _ in INIT_PROPERTIES)
    for axis, name in enumerate(("x", "y", "z")):
        rows[name] = xyz[:, axis]
    for axis in range(3):
        rows[f"scale_{axis}"] = np.log(np.maximum(row_norm[:, axis], 1e-8))
    rows["rot_0"] = 1.0
    rows["rot_1"] = rows["rot_2"] = rows["rot_3"] = 0.0
    rows["f_dc_j"] = (0.02 - 0.5) / SH_C0
    rows["opacity"] = math.log(0.1 / 0.9)
    rows["mu_d_2"] = 1.0
    for axis in range(3):
        rows[f"chol_diag_{axis}"] = np.log(np.maximum(diag[:, axis], 1e-8))
    rows["chol_offdiag_0"] = cholesky[:, 1, 0] / diag[:, 1]
    rows["chol_offdiag_1"] = cholesky[:, 2, 0] / diag[:, 2]
    rows["chol_offdiag_2"] = cholesky[:, 2, 1] / diag[:, 2]
    rows["chol_diag_3"] = math.log(0.1)
    rows["chol_diag_4"] = rows["chol_diag_5"] = rows["chol_diag_6"] = 0.0
    rows["lambda_t"] = rows["lambda_d"] = STATIC_LAMBDA_RAW
    rows["f_dc_t"] = -0.5 / SH_C0

    path.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(rows, "vertex")], text=False).write(path)
    return len(rows)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values.astype(np.float64, copy=False), -80.0, 80.0)
    return 1.0 / (1.0 + np.exp(-values))


def _write_init_from_b2(source: Path, path: Path, limit: int = 0) -> dict:
    ply = PlyData.read(source, mmap="r")
    vertices = ply.elements[0].data
    leaf_count = len(LIGHT_DIRECTIONS_GL)
    if len(vertices) % leaf_count:
        raise ValueError("B2 PLY vertex count is not divisible by six light leaves")
    required = set(INIT_PROPERTIES) | {
        *(f"f_rest_j_{index}" for index in range(15)),
        *(f"f_rest_t_{index}" for index in range(15)),
    }
    missing = required.difference(vertices.dtype.names)
    if missing:
        raise ValueError(f"B2 PLY is missing fields: {sorted(missing)}")

    spatial_count = len(vertices) // leaf_count
    point_count = spatial_count
    if limit > 0:
        point_count = min(point_count, limit)
    indices = np.linspace(0, spatial_count - 1, point_count, dtype=np.int64)
    leaf_indices = np.stack(
        [leaf * spatial_count + indices for leaf in range(leaf_count)]
    )

    def field(name: str) -> np.ndarray:
        return np.asarray(vertices[name][leaf_indices], dtype=np.float64)

    spatial_fields = (
        "x", "y", "z",
        "scale_0", "scale_1", "scale_2",
        "rot_0", "rot_1", "rot_2", "rot_3",
        "chol_diag_0", "chol_diag_1", "chol_diag_2",
        "chol_offdiag_0", "chol_offdiag_1", "chol_offdiag_2",
    )
    for name in spatial_fields:
        values = field(name)
        if not np.isfinite(values).all() or not np.allclose(
            values, values[:1], rtol=0.0, atol=1e-6
        ):
            raise ValueError(f"B2 leaves disagree on spatial field {name}")

    directions = np.stack(
        [field(f"mu_d_{axis}") for axis in range(3)], axis=2
    )
    expected_directions = np.broadcast_to(
        LIGHT_DIRECTIONS_GL[:, None, :], directions.shape
    )
    if not np.allclose(directions, expected_directions, rtol=0.0, atol=1e-6):
        raise ValueError("B2 leaves do not match the expected six light directions")
    for index in range(3, 21):
        values = field(f"chol_offdiag_{index}")
        if not np.allclose(values, 0.0, rtol=0.0, atol=1e-7):
            raise ValueError("B2 teacher has light-conditioned spatial/cross covariance")
    for index in range(15):
        if not np.allclose(field(f"f_rest_j_{index}"), 0.0, rtol=0.0, atol=1e-7):
            raise ValueError("B2 teacher has view-dependent J that cannot be six-leaf aggregated")
        values = field(f"f_rest_t_{index}")
        if not np.allclose(values, values[:1], rtol=0.0, atol=1e-7):
            raise ValueError(f"B2 leaves disagree on TView SH field {index}")
    if not np.allclose(field("f_dc_t"), field("f_dc_t")[:1], rtol=0.0, atol=1e-7):
        raise ValueError("B2 leaves disagree on TView DC")

    opacity = _sigmoid(field("opacity"))
    j_values = field("f_dc_j") * SH_C0 + 0.5
    angular_sigma = np.exp(
        np.stack([field(f"chol_diag_{axis}") for axis in range(4, 7)], axis=2)
    )
    lambda_d = np.logaddexp(0.0, field("lambda_d"))
    teacher_j = np.empty((leaf_count, point_count), dtype=np.float64)
    teacher_alpha = np.empty_like(teacher_j)
    for query_index, query_direction in enumerate(LIGHT_DIRECTIONS_GL):
        mahalanobis = np.zeros_like(opacity)
        for axis in range(3):
            mahalanobis += (
                (query_direction[axis] - directions[:, :, axis])
                / angular_sigma[:, :, axis]
            ) ** 2
        # Match the UE B2 shader: AlphaCond = opacity * sqrt(exp(-0.5 λ q)).
        conditioned_alpha = opacity * np.exp(-0.25 * lambda_d * mahalanobis)
        transmittance = np.ones(point_count, dtype=np.float64)
        radiance = np.zeros(point_count, dtype=np.float64)
        for leaf in range(leaf_count):
            radiance += transmittance * conditioned_alpha[leaf] * j_values[leaf]
            transmittance *= 1.0 - conditioned_alpha[leaf]
        teacher_alpha[query_index] = 1.0 - transmittance
        teacher_j[query_index] = radiance / np.maximum(
            teacher_alpha[query_index], 1e-12
        )

    alpha_spread = np.ptp(teacher_alpha, axis=0)
    if float(np.max(alpha_spread)) > 1e-6:
        raise ValueError("six-leaf B2 density is not direction invariant")
    aggregate_alpha = np.clip(teacher_alpha.mean(axis=0), 1e-8, 1.0 - 1e-8)
    sh_coefficients = SH1_PINV @ (teacher_j - 0.5)
    fitted_j = SH1_BASIS @ sh_coefficients + 0.5

    rows = np.empty(point_count, dtype=[(name, "<f4") for name in INIT_PROPERTIES])
    rows[:] = tuple(0.0 for _ in INIT_PROPERTIES)
    for name in spatial_fields:
        rows[name] = field(name)[0]
    rows["f_dc_j"] = sh_coefficients[0]
    for index in range(3):
        rows[f"f_rest_j_{index}"] = sh_coefficients[index + 1]
    rows["opacity"] = np.log(aggregate_alpha / (1.0 - aggregate_alpha))
    rows["mu_d_2"] = 1.0
    for axis in range(3, 7):
        rows[f"chol_diag_{axis}"] = field(f"chol_diag_{axis}")[0]
    rows["lambda_t"] = rows["lambda_d"] = STATIC_LAMBDA_RAW
    rows["f_dc_t"] = field("f_dc_t")[0]
    for index in range(3):
        rows[f"f_rest_t_{index}"] = field(f"f_rest_t_{index}")[0]

    path.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(rows, "vertex")], text=False).write(path)
    return {
        "spatial_points": point_count,
        "teacher_alpha_min": float(aggregate_alpha.min()),
        "teacher_alpha_max": float(aggregate_alpha.max()),
        "sh_degree": 1,
        "sh_anchor_rmse": float(np.sqrt(np.mean((fitted_j - teacher_j) ** 2))),
        "sh_anchor_max_error": float(np.max(np.abs(fitted_j - teacher_j))),
    }


def _light_transmittance(
    grid: np.ndarray,
    density_scale: float,
    voxel_cm: float,
) -> list[np.ndarray]:
    volumes = []
    for direction in LIGHT_DIRECTIONS_UE:
        axis = int(np.flatnonzero(direction)[0])
        positive = bool(direction[axis] > 0.0)
        source = np.flip(grid, axis=axis) if positive else grid
        optical_depth = np.cumsum(source, axis=axis, dtype=np.float32)
        if positive:
            optical_depth = np.flip(optical_depth, axis=axis)
        volumes.append(
            np.exp(-optical_depth * density_scale * voxel_cm).astype(np.float16)
        )
    return volumes


def _light_directions(count: int) -> tuple[np.ndarray, np.ndarray]:
    if count < 6:
        raise ValueError("at least six light directions are required")
    if count == 6:
        directions_ue = LIGHT_DIRECTIONS_UE.copy()
    else:
        extra_count = count - 6
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        extra = []
        for index in range(extra_count):
            z = 1.0 - 2.0 * (index + 0.5) / extra_count
            radius = math.sqrt(max(1.0 - z * z, 0.0))
            angle = golden_angle * index
            extra.append((radius * math.cos(angle), radius * math.sin(angle), z))
        extra = np.asarray(extra, dtype=np.float32)
        validation_count = max(1, int(count * 0.2))
        validation_indices = np.linspace(
            0, extra_count - 1, validation_count, dtype=np.int64
        )
        train_mask = np.ones(extra_count, dtype=bool)
        train_mask[validation_indices] = False
        directions_ue = np.concatenate(
            (LIGHT_DIRECTIONS_UE, extra[train_mask], extra[validation_indices])
        )
    directions_gl = directions_ue[:, (0, 2, 1)] * np.asarray(
        (1.0, -1.0, -1.0), dtype=np.float32
    )
    return directions_ue, directions_gl


@torch.inference_mode()
def _directional_light_transmittance(
    grid: torch.Tensor,
    direction_ue: np.ndarray,
    density_scale: float,
    voxel_cm: float,
) -> torch.Tensor:
    direction = torch.as_tensor(
        direction_ue, dtype=grid.dtype, device=grid.device
    )
    direction = direction / direction.norm().clamp_min(1e-8)
    major_axis = int(direction.abs().argmax())
    major = float(direction[major_axis])
    positive = major > 0.0
    if int((direction.abs() > 1e-7).sum()) == 1:
        source = torch.flip(grid, (major_axis,)) if positive else grid
        optical_depth = torch.cumsum(source, dim=major_axis)
        if positive:
            optical_depth = torch.flip(optical_depth, (major_axis,))
        return torch.exp(-optical_depth * density_scale * voxel_cm)

    minor_axes = [axis for axis in range(3) if axis != major_axis]
    plane_shape = [grid.shape[axis] for axis in minor_axes]
    rows = torch.linspace(-1.0, 1.0, plane_shape[0], device=grid.device)
    cols = torch.linspace(-1.0, 1.0, plane_shape[1], device=grid.device)
    yy, xx = torch.meshgrid(rows, cols, indexing="ij")
    offset = direction / abs(major)
    sample_grid = torch.stack(
        (
            xx + 2.0 * offset[minor_axes[1]] / max(plane_shape[1] - 1, 1),
            yy + 2.0 * offset[minor_axes[0]] / max(plane_shape[0] - 1, 1),
        ),
        dim=-1,
    )[None]

    optical_depth = torch.empty_like(grid)
    previous = torch.zeros(plane_shape, dtype=grid.dtype, device=grid.device)
    indices = (
        range(grid.shape[major_axis] - 1, -1, -1)
        if positive
        else range(grid.shape[major_axis])
    )
    step_cm = voxel_cm / abs(major)
    for index in indices:
        ahead = F.grid_sample(
            previous[None, None],
            sample_grid,
            mode="bilinear",
            padding_mode="zeros",
            align_corners=True,
        )[0, 0]
        current = grid.select(major_axis, index) * step_cm + ahead
        optical_depth.select(major_axis, index).copy_(current)
        previous = current
    return torch.exp(-optical_depth * density_scale)


def _look_at(position: np.ndarray) -> np.ndarray:
    forward = -position / np.linalg.norm(position)
    world_up = np.array((0.0, -1.0, 0.0), dtype=np.float64)
    right = np.cross(world_up, forward)
    if np.linalg.norm(right) < 1e-5:
        world_up = np.array((0.0, 0.0, 1.0), dtype=np.float64)
        right = np.cross(world_up, forward)
    right /= np.linalg.norm(right)
    up = np.cross(forward, right)
    c2w = np.eye(4, dtype=np.float64)
    c2w[:3, 0] = right
    c2w[:3, 1] = -up
    c2w[:3, 2] = forward
    c2w[:3, 3] = position
    return c2w


def _cameras(count: int, radius_m: float) -> list[np.ndarray]:
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cameras = []
    for index in range(count):
        vertical = 0.65 * (1.0 - 2.0 * (index + 0.5) / count)
        horizontal = math.sqrt(max(1.0 - vertical * vertical, 0.0))
        angle = golden_angle * index
        position = radius_m * np.array(
            (horizontal * math.cos(angle), vertical, horizontal * math.sin(angle))
        )
        cameras.append(_look_at(position))
    return cameras


def _sample_volume(volume: torch.Tensor, points: torch.Tensor, bounds: torch.Tensor) -> torch.Tensor:
    normalized = (points - bounds[0]) / (bounds[1] - bounds[0]) * 2.0 - 1.0
    grid = torch.stack(
        (-normalized[..., 1], -normalized[..., 2], normalized[..., 0]), dim=-1
    )
    sample_shape = grid.shape[:-1]
    grid = grid.reshape(1, 1, -1, sample_shape[-1], 3)
    sampled = F.grid_sample(
        volume,
        grid,
        mode="bilinear",
        padding_mode="zeros",
        align_corners=True,
    )
    return sampled[0, 0, 0].reshape(sample_shape)


@torch.inference_mode()
def _render_view(
    density: torch.Tensor,
    light_volumes: list[torch.Tensor],
    bounds: torch.Tensor,
    c2w: np.ndarray,
    resolution: int,
    focal: float,
    density_scale: float,
    steps: int,
    row_chunk: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    device = density.device
    outputs = np.zeros((max(1, len(light_volumes)), resolution, resolution, 4), np.float32)
    depth_cm = np.zeros((resolution, resolution), np.float32)
    mask = np.zeros((resolution, resolution), np.uint8)
    rotation = torch.tensor(c2w[:3, :3], dtype=torch.float32, device=device)
    origin = torch.tensor(c2w[:3, 3], dtype=torch.float32, device=device)
    for row0 in range(0, resolution, row_chunk):
        row1 = min(row0 + row_chunk, resolution)
        rows, cols = torch.meshgrid(
            torch.arange(row0, row1, device=device, dtype=torch.float32) + 0.5,
            torch.arange(resolution, device=device, dtype=torch.float32) + 0.5,
            indexing="ij",
        )
        camera_dirs = torch.stack(
            (
                (cols - resolution * 0.5) / focal,
                (rows - resolution * 0.5) / focal,
                torch.ones_like(cols),
            ),
            dim=-1,
        )
        world_dirs = F.normalize(camera_dirs @ rotation.T, dim=-1)
        inverse = torch.where(
            world_dirs.abs() > 1e-8,
            world_dirs.reciprocal(),
            torch.full_like(world_dirs, 1e8),
        )
        t0 = (bounds[0] - origin) * inverse
        t1 = (bounds[1] - origin) * inverse
        enter = torch.minimum(t0, t1).amax(dim=-1).clamp_min(0.0)
        leave = torch.maximum(t0, t1).amin(dim=-1)
        valid = leave > enter
        fraction = (torch.arange(steps, device=device) + 0.5) / steps
        distance = enter[..., None] + (leave - enter).clamp_min(0.0)[..., None] * fraction
        points = origin + world_dirs[..., None, :] * distance[..., None]
        sigma = _sample_volume(density, points, bounds)
        sigma = sigma * valid[..., None]
        delta_cm = ((leave - enter).clamp_min(0.0) * 100.0 / steps)[..., None]
        alpha = 1.0 - torch.exp(-sigma * density_scale * delta_cm)
        trans_before = torch.cumprod(
            torch.cat((torch.ones_like(alpha[..., :1]), 1.0 - alpha[..., :-1]), dim=-1),
            dim=-1,
        )
        weights = trans_before * alpha
        transmittance = torch.prod(1.0 - alpha, dim=-1)
        opacity = 1.0 - transmittance
        depth = (weights * distance).sum(dim=-1) / weights.sum(dim=-1).clamp_min(1e-8)

        depth_cm[row0:row1] = (depth * 100.0).cpu().numpy()
        mask[row0:row1] = (opacity > 0.01).to(torch.uint8).cpu().numpy() * 255
        t_cpu = transmittance.cpu().numpy()
        outputs[:, row0:row1, :, 3] = t_cpu
        for light_index, light in enumerate(light_volumes):
            light_t = _sample_volume(light, points, bounds)
            radiance = (weights * light_t).sum(dim=-1).cpu().numpy()
            outputs[light_index, row0:row1, :, :3] = radiance[..., None]

    return outputs, depth_cm, mask


def build(args: argparse.Namespace) -> dict:
    grid = np.load(args.grid).squeeze().astype(np.float32, copy=False)
    if grid.ndim != 3 or np.min(grid) < 0 or not np.isfinite(grid).all():
        raise ValueError("grid must be finite, non-negative and 3D")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    voxel_cm = args.longest_size_cm / max(grid.shape)
    init_report = None
    if args.b2_ply:
        init_report = _write_init_from_b2(
            args.b2_ply, output / "init_points.ply", args.init_limit
        )
        point_count = init_report["spatial_points"]
    else:
        centers, _, _, cholesky = _aggregate_grid(
            grid, args.block_size, args.spatial_sigma_ratio
        )
        centered = centers - (np.asarray(grid.shape, np.float64) - 1.0) * 0.5
        point_count = _write_init_ply(
            output / "init_points.ply",
            centered * voxel_cm,
            cholesky,
            voxel_cm,
        )

    half_extent_m = np.asarray(grid.shape, np.float32) * (voxel_cm / 200.0)
    bounds_np = np.stack(
        (
            (-half_extent_m[0], -half_extent_m[2], -half_extent_m[1]),
            (half_extent_m[0], half_extent_m[2], half_extent_m[1]),
        )
    )
    cameras = _cameras(args.views, args.camera_radius_m)
    light_directions_ue, light_directions_gl = _light_directions(args.lights)
    focal = 0.5 * args.resolution / math.tan(math.radians(args.fov_degrees) * 0.5)
    frames = []
    for index, c2w in enumerate(cameras):
        frames.append({
            "file_path": f"view{index:04d}",
            "transform_matrix": c2w.tolist(),
            "near": 0.1,
            "far": args.camera_radius_m * 2.0,
        })
    (output / "transforms_train.json").write_text(json.dumps({
        "fl_x": focal,
        "fl_y": focal,
        "cx": args.resolution * 0.5,
        "cy": args.resolution * 0.5,
        "w": args.resolution,
        "h": args.resolution,
        "frames": frames,
    }, indent=2), encoding="utf-8")
    (output / "lights.json").write_text(json.dumps({
        "L": len(light_directions_gl),
        "light_dirs": light_directions_gl.tolist(),
        "heldout_count": max(1, int(len(light_directions_gl) * 0.2)),
    }, indent=2), encoding="utf-8")
    (output / "scene.json").write_text(json.dumps({
        "bbox_min": bounds_np[0].tolist(),
        "bbox_max": bounds_np[1].tolist(),
        "phase_function": {"type": "isotropic", "g": 0.0},
        "depth_thresholds": {"eps_near": 0.01},
        "background_value": {"J": 0.0, "trans_view": 1.0, "depth_near": 0.0, "depth_far": 0.0},
        "density_scale": args.density_scale,
        "voxel_cm": voxel_cm,
    }, indent=2), encoding="utf-8")

    device = torch.device("cuda")
    density = torch.from_numpy(grid)[None, None].to(device)
    bounds = torch.tensor(bounds_np, dtype=torch.float32, device=device)
    light_volumes = []
    if not args.tau_only:
        for index, direction in enumerate(light_directions_ue):
            print(f"[prepare] light volume {index + 1}/{len(light_directions_ue)}")
            light_volumes.append(
                _directional_light_transmittance(
                    density[0, 0], direction, args.density_scale, voxel_cm
                )[None, None]
            )
    for view_index, c2w in enumerate(cameras):
        images, depth_cm, mask = _render_view(
            density,
            light_volumes,
            bounds,
            c2w,
            args.resolution,
            focal,
            args.density_scale,
            args.steps,
            args.row_chunk,
        )
        for light_index, image in enumerate(images):
            _write_exr(
                output / "J_TView" / f"view{view_index:04d}_light{light_index:04d}.exr",
                image,
            )
        depth_rgba = np.repeat(depth_cm[:, :, None], 4, axis=2)
        _write_exr(output / "depth" / f"view{view_index:04d}.exr", depth_rgba)
        mask_path = output / "mask" / f"view{view_index:04d}.png"
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(mask, mode="L").save(mask_path)

    report = {
        "grid": str(args.grid.resolve()),
        "grid_shape": list(grid.shape),
        "spatial_points": point_count,
        "views": args.views,
        "lights": 1 if args.tau_only else len(light_directions_gl),
        "heldout_lights": max(1, int(len(light_directions_gl) * 0.2)),
        "resolution": args.resolution,
        "ray_steps": args.steps,
        "block_size": args.block_size,
        "density_scale": args.density_scale,
        "voxel_cm": voxel_cm,
    }
    if init_report is not None:
        report["b2_init"] = init_report
    (output / "prepare_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def _self_check() -> None:
    camera = _look_at(np.array((0.0, 0.0, 2.0)))
    assert np.allclose(camera[:3, 2], (0.0, 0.0, -1.0))
    grid = np.ones((2, 3, 4), np.float32)
    lights = _light_transmittance(grid, 0.1, 1.0)
    assert len(lights) == 6 and all(np.isfinite(volume).all() for volume in lights)
    grid_t = torch.from_numpy(grid)
    for direction, expected in zip(LIGHT_DIRECTIONS_UE, lights):
        actual = _directional_light_transmittance(grid_t, direction, 0.1, 1.0)
        assert np.allclose(actual.numpy(), expected.astype(np.float32), atol=5e-4)
    directions_ue, directions_gl = _light_directions(24)
    assert directions_ue.shape == directions_gl.shape == (24, 3)
    assert np.allclose(np.linalg.norm(directions_ue, axis=1), 1.0)
    diagonal = _directional_light_transmittance(
        grid_t, np.asarray((1.0, 1.0, 0.0), np.float32), 0.1, 1.0
    )
    assert diagonal.shape == grid_t.shape and torch.isfinite(diagonal).all()
    bounds = torch.tensor(((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)))
    outputs, _, _ = _render_view(
        grid_t[None, None], [], bounds, _look_at(np.array((0.0, 0.0, 2.0))),
        2, 2.0, 0.1, 2, 1,
    )
    assert outputs.shape == (1, 2, 2, 4) and np.all(outputs[..., 3] <= 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grid", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--views", type=int, default=8)
    parser.add_argument("--lights", type=int, default=6)
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--steps", type=int, default=192)
    parser.add_argument("--row-chunk", type=int, default=16)
    parser.add_argument("--block-size", type=int, default=2)
    parser.add_argument("--longest-size-cm", type=float, default=1000.0)
    parser.add_argument("--density-scale", type=float, default=0.04)
    parser.add_argument("--spatial-sigma-ratio", type=float, default=0.48)
    parser.add_argument("--b2-ply", type=Path)
    parser.add_argument("--init-limit", type=int, default=0)
    parser.add_argument("--camera-radius-m", type=float, default=15.0)
    parser.add_argument("--fov-degrees", type=float, default=42.0)
    parser.add_argument("--tau-only", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("prepare_7drgs_dataset self-check passed")
        return
    if args.grid is None or args.output is None:
        parser.error("grid and output are required")
    print(json.dumps(build(args), indent=2))


if __name__ == "__main__":
    main()
