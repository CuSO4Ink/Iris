"""Render initializer NPZ files with the project's CUDA Gaussian rasterizer."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


TRAINING_ROOT = Path(__file__).resolve().parents[1] / "training" / "7drgs"
sys.path.insert(0, str(TRAINING_ROOT))

from diff_gaussian_rasterization import (  # noqa: E402
    GaussianRasterizationSettings,
    GaussianRasterizer,
)
from utils.graphics_utils import focal2fov, getProjectionMatrix, getWorld2View2  # noqa: E402


def calibrated_opacity(
    covariance: np.ndarray,
    extinction: np.ndarray,
    multiplier: float,
    power: float,
) -> np.ndarray:
    angular_sigma = 0.5
    kernel_sum = (
        1.0
        + math.exp(-1.0 / angular_sigma**2)
        + 4.0 * math.exp(-0.5 / angular_sigma**2)
    )
    equivalent_scale = np.linalg.det(covariance) ** (1.0 / 6.0)
    center_tau = extinction * math.sqrt(2.0 * math.pi) * equivalent_scale
    base = np.clip(-np.expm1(-center_tau) / kernel_sum, 1e-6, 1.0 - 1e-6)
    return np.power(np.clip(base * multiplier, 0.0, 1.0), power)


def camera_settings(
    transforms: dict,
    frame_index: int,
    resolution: int,
    antialiasing: bool,
    radius_scale: float,
) -> GaussianRasterizationSettings:
    frame = transforms["frames"][frame_index]
    c2w = np.asarray(frame["transform_matrix"], dtype=np.float32)
    rotation = c2w[:3, :3]
    position = c2w[:3, 3] * radius_scale
    translation = -rotation.T @ position
    fov_x = focal2fov(transforms["fl_x"], transforms["w"])
    fov_y = focal2fov(transforms["fl_y"], transforms["h"])
    world_view = torch.tensor(
        getWorld2View2(rotation, translation), device="cuda"
    ).transpose(0, 1)
    projection = getProjectionMatrix(
        znear=float(frame.get("near", 0.1)),
        zfar=float(frame.get("far", 30.0)),
        fovX=fov_x,
        fovY=fov_y,
    ).transpose(0, 1).cuda()
    full_projection = world_view.unsqueeze(0).bmm(projection.unsqueeze(0)).squeeze(0)
    return GaussianRasterizationSettings(
        image_height=resolution,
        image_width=resolution,
        tanfovx=math.tan(fov_x * 0.5),
        tanfovy=math.tan(fov_y * 0.5),
        bg=torch.zeros(3, device="cuda"),
        scale_modifier=1.0,
        viewmatrix=world_view,
        projmatrix=full_projection,
        sh_degree=0,
        campos=world_view.inverse()[3, :3],
        prefiltered=False,
        debug=False,
        antialiasing=antialiasing,
    )


@torch.inference_mode()
def render(
    initializer: Path,
    settings: GaussianRasterizationSettings,
    opacity_multiplier: float,
    opacity_power: float,
    footprint_scale: float,
    mass_compensation: bool,
) -> np.ndarray:
    data = np.load(initializer)
    centers = np.asarray(data["center_m"], dtype=np.float32)
    covariance = np.asarray(data["covariance_m2"], dtype=np.float32)
    extinction = np.asarray(data["sigma_t_per_m"], dtype=np.float32)
    opacity = calibrated_opacity(
        covariance, extinction, opacity_multiplier, opacity_power
    ).astype(np.float32)
    packed_covariance = (covariance * footprint_scale**2)[
        :, (0, 0, 0, 1, 1, 2), (0, 1, 2, 1, 2, 2)
    ]
    if mass_compensation:
        opacity /= footprint_scale**2

    means = torch.from_numpy(centers).cuda()
    image, _, _ = GaussianRasterizer(settings)(
        means3D=means,
        means2D=torch.zeros_like(means),
        shs=None,
        colors_precomp=torch.ones_like(means),
        opacities=torch.from_numpy(opacity[:, None]).cuda(),
        scales=None,
        rotations=None,
        cov3D_precomp=torch.from_numpy(packed_covariance).cuda(),
    )
    return image.mean(0).clamp(0.0, 1.0).cpu().numpy()


def self_check() -> None:
    covariance = np.repeat(np.eye(3, dtype=np.float64)[None], 2, axis=0)
    opacity = calibrated_opacity(
        covariance, np.asarray((0.0, 2.0)), multiplier=0.6, power=0.9
    )
    assert opacity.shape == (2,)
    assert 0.0 <= opacity[0] < opacity[1] < 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "candidates",
        nargs="*",
        help="NAME[@FOOTPRINT_SCALE]=initializer.npz",
    )
    parser.add_argument("--transforms", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--views", type=int, nargs="+", default=(0, 1, 2))
    parser.add_argument("--resolution", type=int, default=768)
    parser.add_argument("--opacity-multiplier", type=float, default=0.6)
    parser.add_argument("--opacity-power", type=float, default=0.9)
    parser.add_argument("--camera-radius-scale", type=float, default=1.0)
    parser.add_argument("--antialiasing", action="store_true")
    parser.add_argument("--no-mass-compensation", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("render_initializer_splats self-check passed")
        return
    if not args.candidates or args.transforms is None or args.output is None:
        parser.error("candidates, --transforms and --output are required")

    named = []
    for candidate in args.candidates:
        label, separator, path = candidate.partition("=")
        if not separator:
            parser.error(f"candidate must be NAME=PATH: {candidate}")
        name, scale_separator, scale = label.rpartition("@")
        footprint_scale = float(scale) if scale_separator else 1.0
        named.append(
            (
                f"{name} @{footprint_scale:g}" if scale_separator else label,
                footprint_scale,
                Path(path),
            )
        )

    transforms = json.loads(args.transforms.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for view in args.views:
        settings = camera_settings(
            transforms,
            view,
            args.resolution,
            args.antialiasing,
            args.camera_radius_scale,
        )
        panels = []
        for name, footprint_scale, initializer in named:
            alpha = render(
                initializer,
                settings,
                args.opacity_multiplier,
                args.opacity_power,
                footprint_scale,
                not args.no_mass_compensation,
            )
            panel = np.repeat((alpha * 255.0).astype(np.uint8)[..., None], 3, axis=2)
            cv2.putText(
                panel,
                name,
                (16, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 190, 255),
                2,
                cv2.LINE_AA,
            )
            panels.append(panel)
        cv2.imwrite(str(args.output / f"view_{view:02d}.png"), np.concatenate(panels, axis=1))


if __name__ == "__main__":
    main()
