"""Prepare a static VDB teacher for official 3DGS and adapt its PLY for UE."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from plyfile import PlyData, PlyElement

from prepare_7drgs_dataset import (
    INIT_PROPERTIES,
    SH_C0,
    STATIC_LAMBDA_RAW,
    _cameras,
    _directional_light_transmittance,
    _render_view,
)

OUTPUT_PROPERTIES = INIT_PROPERTIES + tuple(
    f"f_rest_j_{index}" for index in range(3, 15)
)


def _rgb(
    radiance: np.ndarray,
    transmittance: np.ndarray,
    ambient: float = 0.0,
) -> np.ndarray:
    opacity = np.clip(1.0 - transmittance, 0.0, 1.0)
    color = radiance + ambient * opacity[..., None]
    return np.round(np.clip(color, 0.0, 1.0) * 255.0).astype(np.uint8)


def _write_seed_points(
    path: Path,
    density: torch.Tensor,
    voxel_cm: float,
    scene_scale: float,
    count: int,
    threshold: float,
) -> int:
    coarse_factor = 4
    coarse = F.avg_pool3d(
        density[None, None], coarse_factor, coarse_factor
    )[0, 0]
    active = torch.nonzero(coarse >= threshold)
    if not len(active):
        raise ValueError("cannot seed 3DGS from an empty density grid")
    generator = torch.Generator().manual_seed(0)
    if count < len(active):
        active = active[torch.randperm(len(active), generator=generator)[:count]]
    count = len(active)
    source_indices = (
        active.float() * coarse_factor
        + torch.rand((count, 3), generator=generator) * coarse_factor
    )
    source_indices -= (torch.as_tensor(density.shape) - 1.0) * 0.5
    xyz = source_indices.numpy() * (voxel_cm / 100.0) * scene_scale
    xyz = xyz[:, (0, 2, 1)] * np.asarray((1.0, -1.0, -1.0), np.float32)

    dtype = [
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
    ]
    rows = np.zeros(count, dtype=dtype)
    for axis, name in enumerate(("x", "y", "z")):
        rows[name] = xyz[:, axis]
    rows["red"] = rows["green"] = rows["blue"] = 153
    PlyData([PlyElement.describe(rows, "vertex")], text=False).write(path)
    return count


def prepare(args: argparse.Namespace) -> dict:
    if min(
        args.views, args.resolution, args.steps, args.row_chunk, args.downsample,
        args.test_every, args.seed_points,
    ) < 1 or args.scene_scale <= 0.0 or args.seed_threshold < 0.0 or not 0.0 <= args.ambient <= 1.0:
        raise ValueError("counts and scene scale must be positive")
    output = args.output.resolve()
    images = output / "images"
    images.mkdir(parents=True, exist_ok=True)
    source = np.load(args.grid, mmap_mode="r")
    if source.ndim != 3 or source.dtype != np.float32:
        raise ValueError("grid must be a 3D float32 .npy")
    if not np.isfinite(source).all() or float(source.min()) < 0.0:
        raise ValueError("grid must be finite and non-negative")

    original_shape = np.asarray(source.shape)
    voxel_cm = args.longest_size_cm / max(source.shape)
    density_cpu = torch.from_numpy(source)
    if args.downsample > 1:
        factor = args.downsample
        density_cpu = F.avg_pool3d(
            density_cpu[None, None],
            kernel_size=factor,
            stride=factor,
        )[0, 0]
        voxel_cm *= factor
    seed_points = _write_seed_points(
        output / "points3d.ply",
        density_cpu,
        voxel_cm,
        args.scene_scale,
        args.seed_points,
        args.seed_threshold,
    )
    density = density_cpu.contiguous()[None, None].cuda()
    del density_cpu, source

    half_extent_m = np.asarray(density.shape[-3:]) * (voxel_cm / 200.0)
    bounds_np = np.stack(
        (
            (-half_extent_m[0], -half_extent_m[2], -half_extent_m[1]),
            (half_extent_m[0], half_extent_m[2], half_extent_m[1]),
        )
    ).astype(np.float32)
    bounds = torch.as_tensor(bounds_np, device="cuda")
    light_direction = np.asarray(args.light_direction_ue, np.float32)
    light_norm = np.linalg.norm(light_direction)
    if not np.isfinite(light_norm) or light_norm < 1e-8:
        raise ValueError("light direction must be finite and non-zero")
    light_direction /= light_norm
    print("[prepare] building one static directional-light volume")
    light = _directional_light_transmittance(
        density[0, 0], light_direction, args.density_scale, voxel_cm
    )[None, None]

    focal = 0.5 * args.resolution / math.tan(
        math.radians(args.fov_degrees) * 0.5
    )
    train_frames, test_frames = [], []
    cameras = _cameras(args.views, args.camera_radius_m)
    for index, camera in enumerate(cameras):
        rendered, _, _ = _render_view(
            density,
            [light],
            bounds,
            camera,
            args.resolution,
            focal,
            args.density_scale,
            args.steps,
            args.row_chunk,
        )
        rgb = _rgb(
            rendered[0, ..., :3], rendered[0, ..., 3], args.ambient
        )
        alpha = np.round(
            np.clip(1.0 - rendered[0, ..., 3], 0.0, 1.0) * 255.0
        ).astype(np.uint8)
        Image.fromarray(
            np.dstack((rgb, alpha)), "RGBA"
        ).save(images / f"view{index:04d}.png")
        blender_camera = camera.copy()
        blender_camera[:3, 1:3] *= -1.0
        blender_camera[:3, 3] *= args.scene_scale
        frame = {
            "file_path": f"./images/view{index:04d}",
            "transform_matrix": blender_camera.tolist(),
        }
        (test_frames if index % args.test_every == 0 else train_frames).append(frame)
        print(f"[prepare] rendered view {index + 1}/{len(cameras)}")

    common = {"camera_angle_x": math.radians(args.fov_degrees)}
    for split, frames in (("train", train_frames), ("test", test_frames)):
        (output / f"transforms_{split}.json").write_text(
            json.dumps({**common, "frames": frames}, indent=2),
            encoding="utf-8",
        )
    report = {
        "grid": str(args.grid.resolve()),
        "original_grid_shape": original_shape.tolist(),
        "teacher_grid_shape": list(density.shape[-3:]),
        "views": args.views,
        "train_views": len(train_frames),
        "test_views": len(test_frames),
        "seed_points": seed_points,
        "seed_threshold": args.seed_threshold,
        "resolution": args.resolution,
        "ray_steps": args.steps,
        "density_scale": args.density_scale,
        "ambient": args.ambient,
        "voxel_cm": voxel_cm,
        "light_direction_ue_toward_light": light_direction.tolist(),
        "scene_scale": args.scene_scale,
    }
    (output / "prepare_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def _rotation(quaternion: np.ndarray) -> np.ndarray:
    q = quaternion / np.linalg.norm(quaternion, axis=1, keepdims=True)
    w, x, y, z = q.T
    result = np.empty((len(q), 3, 3), q.dtype)
    result[:, 0, 0] = 1 - 2 * (y * y + z * z)
    result[:, 0, 1] = 2 * (x * y - w * z)
    result[:, 0, 2] = 2 * (x * z + w * y)
    result[:, 1, 0] = 2 * (x * y + w * z)
    result[:, 1, 1] = 1 - 2 * (x * x + z * z)
    result[:, 1, 2] = 2 * (y * z - w * x)
    result[:, 2, 0] = 2 * (x * z - w * y)
    result[:, 2, 1] = 2 * (y * z + w * x)
    result[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return result


def convert(args: argparse.Namespace) -> dict:
    if args.scene_scale <= 0.0 or args.chunk_size < 1:
        raise ValueError("scene scale and chunk size must be positive")
    vertices = PlyData.read(args.source, mmap="r").elements[0].data
    required = {
        "x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
        "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3",
    }
    missing = required.difference(vertices.dtype.names)
    if missing:
        raise ValueError(f"standard 3DGS PLY is missing: {sorted(missing)}")

    count = len(vertices)
    rows = np.zeros(count, dtype=[(name, "<f4") for name in OUTPUT_PROPERTIES])
    scale_factor = 1.0 / args.scene_scale
    for axis, name in enumerate(("x", "y", "z")):
        rows[name] = np.asarray(vertices[name], np.float32) * scale_factor
    rgb_dc = np.stack(
        [np.asarray(vertices[f"f_dc_{axis}"], np.float32) for axis in range(3)],
        axis=1,
    )
    rows["f_dc_j"] = rgb_dc @ np.asarray((0.2126, 0.7152, 0.0722), np.float32)
    rest_names = sorted(
        (name for name in vertices.dtype.names if name.startswith("f_rest_")),
        key=lambda name: int(name.rsplit("_", 1)[1]),
    )
    if len(rest_names) % 3:
        raise ValueError("standard 3DGS SH field count is not divisible by RGB")
    rest_count = len(rest_names) // 3
    for coefficient in range(min(rest_count, 15)):
        rows[f"f_rest_j_{coefficient}"] = sum(
            weight * np.asarray(
                vertices[rest_names[channel * rest_count + coefficient]],
                np.float32,
            )
            for channel, weight in enumerate((0.2126, 0.7152, 0.0722))
        )
    rows["opacity"] = np.asarray(vertices["opacity"], np.float32)
    for axis in range(3):
        rows[f"scale_{axis}"] = (
            np.asarray(vertices[f"scale_{axis}"], np.float32)
            + math.log(scale_factor)
        )
    for axis in range(4):
        rows[f"rot_{axis}"] = np.asarray(vertices[f"rot_{axis}"], np.float32)
    rows["mu_d_2"] = 1.0
    rows["chol_diag_3"] = math.log(0.1)
    rows["lambda_t"] = rows["lambda_d"] = STATIC_LAMBDA_RAW
    rows["f_dc_t"] = -0.5 / SH_C0

    for start in range(0, count, args.chunk_size):
        stop = min(start + args.chunk_size, count)
        sl = slice(start, stop)
        quaternion = np.stack(
            [np.asarray(vertices[f"rot_{axis}"][sl], np.float64) for axis in range(4)],
            axis=1,
        )
        scales = np.exp(
            np.stack(
                [np.asarray(vertices[f"scale_{axis}"][sl], np.float64) for axis in range(3)],
                axis=1,
            )
        ) * scale_factor
        transform = _rotation(quaternion) * scales[:, None, :]
        covariance = transform @ np.transpose(transform, (0, 2, 1))
        cholesky = np.linalg.cholesky(covariance)
        diagonal = np.diagonal(cholesky, axis1=1, axis2=2)
        for axis in range(3):
            rows[f"chol_diag_{axis}"][sl] = np.log(diagonal[:, axis])
        rows["chol_offdiag_0"][sl] = cholesky[:, 1, 0] / diagonal[:, 1]
        rows["chol_offdiag_1"][sl] = cholesky[:, 2, 0] / diagonal[:, 2]
        rows["chol_offdiag_2"][sl] = cholesky[:, 2, 1] / diagonal[:, 2]

    if not all(np.isfinite(rows[name]).all() for name in OUTPUT_PROPERTIES):
        raise ValueError("converted PLY contains non-finite values")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(rows, "vertex")], text=False).write(args.output)
    report = {
        "source": str(args.source.resolve()),
        "output": str(args.output.resolve()),
        "points": count,
        "scene_scale_restored": args.scene_scale,
        "color": f"Rec.709 monochrome SH{int(math.sqrt(rest_count + 1) - 1)}",
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def _self_check() -> None:
    radiance = np.full((2, 2, 3), 0.25, np.float32)
    transmittance = np.full((2, 2), 0.5, np.float32)
    rgb = _rgb(radiance, transmittance, 0.4)
    assert np.all(rgb == 115)
    rotation = _rotation(np.asarray(((1.0, 0.0, 0.0, 0.0),), np.float32))
    assert np.allclose(rotation[0], np.eye(3))
    with TemporaryDirectory() as directory:
        path = Path(directory) / "points3d.ply"
        count = _write_seed_points(path, torch.ones((8, 8, 8)), 1.0, 0.2, 32, 0.01)
        assert count == len(PlyData.read(path).elements[0].data) == 8


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("grid", type=Path)
    prepare_parser.add_argument("output", type=Path)
    prepare_parser.add_argument("--views", type=int, default=64)
    prepare_parser.add_argument("--resolution", type=int, default=512)
    prepare_parser.add_argument("--steps", type=int, default=256)
    prepare_parser.add_argument("--row-chunk", type=int, default=8)
    prepare_parser.add_argument("--downsample", type=int, default=2)
    prepare_parser.add_argument("--seed-points", type=int, default=400_000)
    prepare_parser.add_argument("--seed-threshold", type=float, default=0.01)
    prepare_parser.add_argument("--longest-size-cm", type=float, default=1000.0)
    prepare_parser.add_argument("--density-scale", type=float, default=0.04)
    prepare_parser.add_argument("--ambient", type=float, default=0.4)
    prepare_parser.add_argument("--camera-radius-m", type=float, default=15.0)
    prepare_parser.add_argument("--fov-degrees", type=float, default=42.0)
    prepare_parser.add_argument("--scene-scale", type=float, default=0.2)
    prepare_parser.add_argument("--test-every", type=int, default=8)
    prepare_parser.add_argument(
        "--light-direction-ue",
        type=float,
        nargs=3,
        default=(-0.682970, -0.004826, 0.730431),
        metavar=("X", "Y", "Z"),
    )

    convert_parser = subparsers.add_parser("convert")
    convert_parser.add_argument("source", type=Path)
    convert_parser.add_argument("output", type=Path)
    convert_parser.add_argument("--scene-scale", type=float, default=0.2)
    convert_parser.add_argument("--chunk-size", type=int, default=250_000)

    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("standard_3dgs_baseline self-check passed")
    elif args.command == "prepare":
        print(json.dumps(prepare(args), indent=2))
    elif args.command == "convert":
        print(json.dumps(convert(args), indent=2))
    else:
        parser.error("choose prepare or convert")


if __name__ == "__main__":
    main()
