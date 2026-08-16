"""Recover an exact-budget Gaussian initializer against held-out VDB tau/T rays."""

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

from build_contracted_50k import GAUSSIAN_VOLUME, matrix_to_quaternion
from evaluate_heldout import compute_metrics


def _read_exr_alpha(path: Path) -> np.ndarray:
    source = OpenEXR.InputFile(str(path))
    try:
        window = source.header()["dataWindow"]
        width = window.max.x - window.min.x + 1
        height = window.max.y - window.min.y + 1
        values = np.frombuffer(
            source.channel("A", Imath.PixelType(Imath.PixelType.FLOAT)),
            dtype=np.float32,
        )
        return values.reshape(height, width).copy()
    finally:
        source.close()


def load_rays(dataset: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    transforms = json.loads(
        (dataset / "transforms_train.json").read_text(encoding="utf-8")
    )
    width, height = int(transforms["w"]), int(transforms["h"])
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float32) + 0.5,
        np.arange(width, dtype=np.float32) + 0.5,
        indexing="ij",
    )
    camera_directions = np.stack(
        (
            (columns - float(transforms["cx"])) / float(transforms["fl_x"]),
            (rows - float(transforms["cy"])) / float(transforms["fl_y"]),
            np.ones_like(columns),
        ),
        axis=-1,
    )
    origins, directions, optical_depth = [], [], []
    for view, frame in enumerate(transforms["frames"]):
        matrix = np.asarray(frame["transform_matrix"], dtype=np.float32)
        world = camera_directions @ matrix[:3, :3].T
        world /= np.linalg.norm(world, axis=-1, keepdims=True)
        transmittance = np.clip(
            _read_exr_alpha(
                dataset / "J_TView" / f"view{view:04d}_light0000.exr"
            ),
            1e-7,
            1.0,
        )
        if transmittance.shape != (height, width):
            raise ValueError("reference image and camera resolution disagree")
        origins.append(
            np.broadcast_to(matrix[:3, 3], (height, width, 3)).copy()
        )
        directions.append(world)
        optical_depth.append(-np.log(transmittance))
    return (
        np.stack(origins),
        np.stack(directions),
        np.stack(optical_depth),
    )


def _rotation_from_vector(vector: torch.Tensor) -> torch.Tensor:
    theta2 = torch.sum(vector * vector, dim=-1, keepdim=True)
    theta = torch.sqrt(theta2 + 1e-12)
    a = torch.sin(theta) / theta
    b = (1.0 - torch.cos(theta)) / theta2.clamp_min(1e-12)
    x, y, z = vector.unbind(-1)
    zero = torch.zeros_like(x)
    skew = torch.stack(
        (zero, -z, y, z, zero, -x, -y, x, zero), dim=-1
    ).reshape(-1, 3, 3)
    identity = torch.eye(3, dtype=vector.dtype, device=vector.device)[None]
    return identity + a[..., None] * skew + b[..., None] * (skew @ skew)


class RecoveredGaussians(torch.nn.Module):
    def __init__(
        self,
        centers: np.ndarray,
        covariances: np.ndarray,
        extinction: np.ndarray,
        center_limit_factor: float = 0.75,
        scale_factor: float = 1.5,
        rotation_degrees: float = 15.0,
        anisotropy_boost: float = 1.0,
        max_anisotropy: float = 8.0,
    ) -> None:
        super().__init__()
        eigenvalues, eigenvectors = np.linalg.eigh(covariances)
        if np.any(eigenvalues <= 0.0) or np.any(extinction <= 0.0):
            raise ValueError("initializer must contain positive kernels")
        negative = np.linalg.det(eigenvectors) < 0.0
        eigenvectors[negative, :, 0] *= -1.0
        scales = np.sqrt(eigenvalues)
        log_scales = np.log(scales)
        mean_log_scale = log_scales.mean(axis=1, keepdims=True)
        shape = (log_scales - mean_log_scale) * anisotropy_boost
        shape *= np.minimum(
            1.0,
            math.log(max_anisotropy) / np.maximum(shape[:, 2] - shape[:, 0], 1e-8),
        )[:, None]
        scales = np.exp(mean_log_scale + shape)
        self.register_buffer(
            "initial_centers", torch.as_tensor(centers, dtype=torch.float32)
        )
        self.register_buffer(
            "initial_rotations",
            torch.as_tensor(eigenvectors, dtype=torch.float32),
        )
        self.register_buffer(
            "initial_scales", torch.as_tensor(scales, dtype=torch.float32)
        )
        self.register_buffer(
            "initial_extinction",
            torch.as_tensor(extinction, dtype=torch.float32),
        )
        self.center_delta = torch.nn.Parameter(torch.zeros_like(self.initial_centers))
        self.scale_delta = torch.nn.Parameter(torch.zeros_like(self.initial_scales))
        self.rotation_delta = torch.nn.Parameter(
            torch.zeros_like(self.initial_centers)
        )
        self.extinction_delta = torch.nn.Parameter(
            torch.zeros_like(self.initial_extinction)
        )
        self.center_limit_factor = center_limit_factor
        self.scale_factor = scale_factor
        self.rotation_degrees = rotation_degrees

    def kernels(self) -> tuple[torch.Tensor, ...]:
        center_limit = self.center_limit_factor * torch.prod(
            self.initial_scales, dim=-1, keepdim=True
        ).pow(1.0 / 3.0)
        centers = self.initial_centers + center_limit * torch.tanh(
            self.center_delta
        )
        scales = self.initial_scales * torch.exp(
            math.log(self.scale_factor) * torch.tanh(self.scale_delta)
        )
        angle = math.radians(self.rotation_degrees) * torch.tanh(self.rotation_delta)
        rotations = self.initial_rotations @ _rotation_from_vector(angle)
        extinction = self.initial_extinction * torch.exp(
            math.log(4.0) * torch.tanh(self.extinction_delta)
        )
        return centers, rotations, scales, extinction

    def optical_depth(
        self,
        origins: torch.Tensor,
        directions: torch.Tensor,
        chunk: int,
    ) -> torch.Tensor:
        centers, rotations, scales, extinction = self.kernels()
        result = torch.zeros(
            len(origins), dtype=origins.dtype, device=origins.device
        )
        for start in range(0, len(centers), chunk):
            stop = min(start + chunk, len(centers))
            rotation = rotations[start:stop]
            local_origin = torch.einsum(
                "bki,kij->bkj",
                origins[:, None] - centers[None, start:stop],
                rotation,
            )
            local_direction = torch.einsum(
                "bi,kij->bkj", directions, rotation
            )
            inverse_scale2 = scales[start:stop].square().reciprocal()
            along = torch.sum(
                local_direction.square() * inverse_scale2[None], dim=-1
            ).clamp_min(1e-10)
            linear = torch.sum(
                local_origin * local_direction * inverse_scale2[None], dim=-1
            )
            closest = local_origin - (
                linear / along
            )[..., None] * local_direction
            perpendicular = torch.sum(
                closest.square() * inverse_scale2[None], dim=-1
            ).clamp(0.0, 80.0)
            basis = (
                math.sqrt(2.0 * math.pi)
                * torch.rsqrt(along)
                * torch.exp(-0.5 * perpendicular)
            )
            result = result + torch.sum(
                basis * extinction[None, start:stop], dim=1
            )
        return result

    def mass(self) -> torch.Tensor:
        _, _, scales, extinction = self.kernels()
        return torch.sum(extinction * GAUSSIAN_VOLUME * torch.prod(scales, dim=1))

    def scale_growth(self) -> torch.Tensor:
        _, _, scales, _ = self.kernels()
        return torch.relu(torch.log(scales / self.initial_scales)).square().mean()


def _edge_strength(optical_depth: np.ndarray) -> np.ndarray:
    values = np.log1p(optical_depth)
    strength = np.zeros_like(optical_depth)
    for offset in (1, 2, 4):
        strength[:, offset:] += np.abs(
            values[:, offset:] - values[:, :-offset]
        ) / offset
        strength[:, :, offset:] += np.abs(
            values[:, :, offset:] - values[:, :, :-offset]
        ) / offset
    return strength


def _patch_pool(
    optical_depth: np.ndarray, views: np.ndarray, margin: int = 1
) -> tuple[np.ndarray, np.ndarray]:
    height, width = optical_depth.shape[1:]
    yy, xx = np.meshgrid(
        np.arange(margin, height - margin),
        np.arange(margin, width - margin),
        indexing="ij",
    )
    centers = np.stack(
        (
            np.repeat(views, yy.size),
            np.tile(yy.ravel(), len(views)),
            np.tile(xx.ravel(), len(views)),
        ),
        axis=1,
    )
    tau = optical_depth[centers[:, 0], centers[:, 1], centers[:, 2]]
    edge = _edge_strength(optical_depth)[
        centers[:, 0], centers[:, 1], centers[:, 2]
    ]
    thin = (tau > 0.02) & (tau < 2.0)
    weights = 0.05 + (tau > 1e-4) + 2.0 * thin + 4.0 * np.minimum(edge, 1.0)
    return centers, weights / weights.sum()


def _gather_patches(
    origins: np.ndarray,
    directions: np.ndarray,
    optical_depth: np.ndarray,
    centers: np.ndarray,
    radius: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    offsets = np.asarray(
        [
            (y, x)
            for y in range(-radius, radius + 1)
            for x in range(-radius, radius + 1)
        ],
        dtype=np.int64,
    )
    patch_area = len(offsets)
    view = np.repeat(centers[:, 0], patch_area)
    pixels = np.repeat(centers[:, 1:], patch_area, axis=0) + np.tile(
        offsets, (len(centers), 1)
    )
    return (
        origins[view, pixels[:, 0], pixels[:, 1]],
        directions[view, pixels[:, 0], pixels[:, 1]],
        optical_depth[view, pixels[:, 0], pixels[:, 1]],
    )


def _edge_loss(
    prediction: torch.Tensor, target: torch.Tensor, patch_size: int = 3
) -> torch.Tensor:
    predicted = torch.log1p(prediction.reshape(-1, patch_size, patch_size))
    reference = torch.log1p(target.reshape(-1, patch_size, patch_size))
    horizontal = (predicted[:, :, 1:] - predicted[:, :, :-1]) - (
        reference[:, :, 1:] - reference[:, :, :-1]
    )
    vertical = (predicted[:, 1:] - predicted[:, :-1]) - (
        reference[:, 1:] - reference[:, :-1]
    )
    laplacian_predicted = (
        4.0 * predicted[:, 1:-1, 1:-1]
        - predicted[:, :-2, 1:-1]
        - predicted[:, 2:, 1:-1]
        - predicted[:, 1:-1, :-2]
        - predicted[:, 1:-1, 2:]
    )
    laplacian_reference = (
        4.0 * reference[:, 1:-1, 1:-1]
        - reference[:, :-2, 1:-1]
        - reference[:, 2:, 1:-1]
        - reference[:, 1:-1, :-2]
        - reference[:, 1:-1, 2:]
    )
    return (
        horizontal.abs().mean()
        + vertical.abs().mean()
        + 0.25 * (laplacian_predicted - laplacian_reference).abs().mean()
    )


def _frequency_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    patch_size: int,
    phase_weight: float = 1.0,
) -> torch.Tensor:
    if patch_size < 5:
        raise ValueError("frequency loss requires at least a 5x5 patch")
    coordinates = torch.arange(
        patch_size, dtype=prediction.dtype, device=prediction.device
    ) - patch_size // 2
    yy, xx = torch.meshgrid(coordinates, coordinates, indexing="ij")
    filters = []
    for wavelength, sigma in ((2.5, 1.0), (4.0, 1.6)):
        envelope = torch.exp(-(xx.square() + yy.square()) / (2.0 * sigma * sigma))
        for angle in (0.0, math.pi / 4.0, math.pi / 2.0, 3.0 * math.pi / 4.0):
            oriented = xx * math.cos(angle) + yy * math.sin(angle)
            phase = 2.0 * math.pi * oriented / wavelength
            for carrier in (torch.cos(phase), torch.sin(phase)):
                kernel = envelope * carrier
                kernel = kernel - kernel.mean()
                filters.append(kernel / kernel.abs().sum().clamp_min(1e-8))
    bank = torch.stack(filters)[:, None]
    predicted = torch.log1p(prediction).reshape(-1, 1, patch_size, patch_size)
    reference = torch.log1p(target).reshape(-1, 1, patch_size, patch_size)
    predicted_response = F.conv2d(predicted, bank).reshape(-1, 2, 4, 2)
    reference_response = F.conv2d(reference, bank).reshape(-1, 2, 4, 2)
    predicted_energy = torch.sqrt(
        predicted_response.square().sum(dim=-1) + 1e-10
    )
    reference_energy = torch.sqrt(
        reference_response.square().sum(dim=-1) + 1e-10
    )
    phase_loss = F.smooth_l1_loss(
        predicted_response, reference_response, beta=0.02
    )
    return phase_weight * phase_loss + F.smooth_l1_loss(
        predicted_energy, reference_energy, beta=0.02
    )


@torch.no_grad()
def evaluate(
    model: RecoveredGaussians,
    origins: np.ndarray,
    directions: np.ndarray,
    optical_depth: np.ndarray,
    patch_centers: np.ndarray,
    chunk: int,
    device: torch.device,
    patch_radius: int = 1,
) -> dict:
    ray_origins, ray_directions, target = _gather_patches(
        origins, directions, optical_depth, patch_centers, radius=patch_radius
    )
    predictions = []
    for start in range(0, len(target), 18):
        predictions.append(
            model.optical_depth(
                torch.as_tensor(
                    ray_origins[start : start + 18],
                    dtype=torch.float32,
                    device=device,
                ),
                torch.as_tensor(
                    ray_directions[start : start + 18],
                    dtype=torch.float32,
                    device=device,
                ),
                chunk,
            ).cpu()
        )
    prediction = torch.cat(predictions)
    target_tensor = torch.as_tensor(target, dtype=torch.float32)
    metrics = compute_metrics(
        np.exp(-target),
        prediction.numpy(),
        alpha_threshold=1e-4,
    )
    patch_size = patch_radius * 2 + 1
    metrics["edge_l1"] = float(
        _edge_loss(prediction, target_tensor, patch_size)
    )
    if patch_size >= 5:
        metrics["gabor_energy_l1"] = float(
            _frequency_loss(prediction, target_tensor, patch_size, phase_weight=0.0)
        )
        metrics["gabor_phase_energy_l1"] = float(
            _frequency_loss(prediction, target_tensor, patch_size)
        )
    metrics["reference_tau_mean"] = float(np.mean(target))
    metrics["candidate_tau_mean"] = float(prediction.mean())
    metrics["tau_bias"] = float(prediction.mean() - np.mean(target))
    return metrics


def _write_outputs(
    model: RecoveredGaussians,
    output: Path,
    source: Path,
    report: dict,
    write_json: bool = True,
) -> None:
    with torch.no_grad():
        centers_t, rotations_t, scales_t, extinction_t = model.kernels()
        centers = centers_t.cpu().numpy()
        rotations = rotations_t.cpu().numpy()
        scales = scales_t.cpu().numpy()
        extinction = extinction_t.cpu().numpy()
    covariances = rotations @ (
        scales[:, :, None] ** 2 * np.transpose(rotations, (0, 2, 1))
    )
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output / "recovered.npz",
        center_m=centers.astype(np.float32),
        covariance_m2=covariances.astype(np.float32),
        sigma_t_per_m=extinction.astype(np.float32),
    )
    if write_json:
        primitives = [
            {
                "center": (centers[index] * 100.0).tolist(),
                "scale": (scales[index] * 100.0).tolist(),
                "rotation": matrix_to_quaternion(rotations[index]),
                "sigma_t": float(extinction[index] / 100.0),
                "omega": 0.0,
                "albedo": [1.0, 1.0, 1.0],
                "emission": 0.0,
            }
            for index in range(len(centers))
        ]
        kernel_label = f"{len(primitives) // 1000}K"
        (output / f"GaussianVolume_Hero_TauRecovered{kernel_label}.json").write_text(
            json.dumps(
                {
                    "schema": "GaussianVolume.Primitives.v1",
                    "source": str(source.resolve()),
                    "method": f"adaptive_detail_{kernel_label.lower()}_tau_t_recovery",
                    "primitive_count": len(primitives),
                    "gaussians": primitives,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    (output / "recovery_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


def recover(args: argparse.Namespace) -> dict:
    data = np.load(args.input_npz)
    centers = np.asarray(data["center_m"], dtype=np.float32)
    covariances = np.asarray(data["covariance_m2"], dtype=np.float32)
    extinction = np.asarray(data["sigma_t_per_m"], dtype=np.float32)
    kernel_count = len(centers)
    if (
        kernel_count <= 0
        or centers.shape != (kernel_count, 3)
        or covariances.shape != (kernel_count, 3, 3)
        or extinction.shape != (kernel_count,)
        or not all(np.isfinite(item).all() for item in (centers, covariances, extinction))
    ):
        raise ValueError("recovery requires a finite exact-budget initializer")
    origins, directions, optical_depth = load_rays(args.dataset)
    view_count = len(origins)
    heldout = np.arange(1, view_count, 4)
    train_views = np.setdiff1d(np.arange(view_count), heldout)
    train_centers, train_weights = _patch_pool(
        optical_depth, train_views, args.patch_radius
    )
    heldout_centers, heldout_weights = _patch_pool(
        optical_depth, heldout, args.patch_radius
    )
    rng = np.random.default_rng(args.seed)
    patch_area = (args.patch_radius * 2 + 1) ** 2
    eval_count = max(1, args.eval_rays // patch_area)
    eval_centers = heldout_centers[
        rng.choice(
            len(heldout_centers),
            size=eval_count,
            replace=False,
            p=heldout_weights,
        )
    ]

    device = torch.device(args.device)
    model = RecoveredGaussians(
        centers,
        covariances,
        extinction,
        center_limit_factor=args.center_limit_factor,
        scale_factor=args.scale_factor,
        rotation_degrees=args.rotation_degrees,
        anisotropy_boost=args.anisotropy_boost,
        max_anisotropy=args.max_anisotropy,
    ).to(device)
    geometry_parameters = (
        model.center_delta,
        model.scale_delta,
        model.rotation_delta,
    )
    if args.extinction_only:
        for parameter in geometry_parameters:
            parameter.requires_grad_(False)
    initial_mass = model.mass().detach()
    initial_metrics = evaluate(
        model,
        origins,
        directions,
        optical_depth,
        eval_centers,
        args.kernel_chunk,
        device,
        args.patch_radius,
    )
    groups = [{"params": (model.extinction_delta,), "lr": args.extinction_lr}]
    if not args.extinction_only:
        groups.append({"params": geometry_parameters, "lr": 0.0})
    optimizer = torch.optim.Adam(groups)
    history = []
    for step in range(args.steps):
        if not args.extinction_only and step == args.geometry_warmup:
            optimizer.param_groups[1]["lr"] = args.geometry_lr
        selected = train_centers[
            rng.choice(
                len(train_centers),
                size=args.patches_per_step,
                replace=False,
                p=train_weights,
            )
        ]
        ray_origins, ray_directions, target_np = _gather_patches(
            origins,
            directions,
            optical_depth,
            selected,
            radius=args.patch_radius,
        )
        ray_origins_t = torch.as_tensor(
            ray_origins, dtype=torch.float32, device=device
        )
        ray_directions_t = torch.as_tensor(
            ray_directions, dtype=torch.float32, device=device
        )
        target = torch.as_tensor(target_np, dtype=torch.float32, device=device)
        prediction = model.optical_depth(
            ray_origins_t, ray_directions_t, args.kernel_chunk
        )
        importance = (
            0.25
            + (target > 1e-4).float()
            + 2.0 * ((target > 0.02) & (target < 2.0)).float()
        )
        importance /= importance.mean()
        tau_loss = (
            importance
            * F.smooth_l1_loss(
                torch.log1p(prediction),
                torch.log1p(target),
                beta=0.1,
                reduction="none",
            )
        ).mean()
        transmittance_loss = (
            importance * (torch.exp(-prediction) - torch.exp(-target)).abs()
        ).mean()
        patch_size = args.patch_radius * 2 + 1
        edge_loss = _edge_loss(prediction, target, patch_size)
        frequency_loss = (
            _frequency_loss(prediction, target, patch_size)
            if args.frequency_weight > 0.0
            else prediction.new_zeros(())
        )
        frequency_scale = min(
            max((step - args.frequency_warmup + 1) / max(args.frequency_ramp, 1), 0.0),
            1.0,
        )
        mass_loss = torch.log(model.mass() / initial_mass).square()
        scale_growth_loss = model.scale_growth()
        anchor_loss = (
            model.center_delta.square().mean()
            + model.scale_delta.square().mean()
            + model.rotation_delta.square().mean()
        )
        loss = (
            tau_loss
            + args.transmittance_weight * transmittance_loss
            + args.edge_weight * edge_loss
            + args.frequency_weight * frequency_scale * frequency_loss
            + args.mass_weight * mass_loss
            + args.scale_growth_weight * scale_growth_loss
            + args.anchor_weight * anchor_loss
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        if (step + 1) % args.log_every == 0 or step in (0, args.steps - 1):
            row = {
                "step": step + 1,
                "loss": float(loss.detach()),
                "tau": float(tau_loss.detach()),
                "transmittance": float(transmittance_loss.detach()),
                "edge": float(edge_loss.detach()),
                "frequency": float(frequency_loss.detach()),
                "frequency_scale": frequency_scale,
                "mass": float(mass_loss.detach()),
                "scale_growth": float(scale_growth_loss.detach()),
            }
            history.append(row)
            print(json.dumps(row))

    final_metrics = (
        initial_metrics
        if args.steps == 0
        else evaluate(
            model,
            origins,
            directions,
            optical_depth,
            eval_centers,
            args.kernel_chunk,
            device,
            args.patch_radius,
        )
    )
    with torch.no_grad():
        final_mass = float(model.mass().cpu())
        _, _, scales_t, extinction_t = model.kernels()
    report = {
        "source": str(args.input_npz.resolve()),
        "dataset": str(args.dataset.resolve()),
        "kernel_count": kernel_count,
        "steps": args.steps,
        "train_views": train_views.tolist(),
        "heldout_views": heldout.tolist(),
        "evaluation_rays": int(len(eval_centers) * patch_area),
        "training_patch_size": args.patch_radius * 2 + 1,
        "geometry_limits": {
            "extinction_only": args.extinction_only,
            "center_local_scale": args.center_limit_factor,
            "scale_factor": args.scale_factor,
            "rotation_degrees": args.rotation_degrees,
            "anisotropy_boost": args.anisotropy_boost,
            "max_anisotropy": args.max_anisotropy,
        },
        "loss_weights": {
            "transmittance": args.transmittance_weight,
            "edge": args.edge_weight,
            "frequency": args.frequency_weight,
            "scale_growth": args.scale_growth_weight,
            "mass": args.mass_weight,
            "anchor": args.anchor_weight,
        },
        "initial_metrics": initial_metrics,
        "final_metrics": final_metrics,
        "numeric_gate_passed": (
            final_metrics["tau_mae"] < initial_metrics["tau_mae"]
            and final_metrics["transmittance_psnr_foreground_db"]
            > initial_metrics["transmittance_psnr_foreground_db"]
            and final_metrics["edge_l1"] <= initial_metrics["edge_l1"]
        ),
        "mass_relative_change": abs(final_mass - float(initial_mass.cpu()))
        / float(initial_mass.cpu()),
        "scale_p01_p50_p99_m": np.percentile(
            scales_t.detach().cpu().numpy(), (1, 50, 99)
        ).tolist(),
        "extinction_p01_p50_p99_per_m": np.percentile(
            extinction_t.detach().cpu().numpy(), (1, 50, 99)
        ).tolist(),
        "history": history,
        "status": "exact-budget numeric recovery; UE visual Gate required",
    }
    _write_outputs(
        model,
        args.output,
        args.input_npz,
        report,
        write_json=not getattr(args, "skip_json", False),
    )
    return report


def _self_check() -> None:
    centers = np.asarray(((0.0, 0.0, 0.0), (0.2, 0.0, 0.0)), np.float32)
    covariances = np.repeat(
        (np.eye(3, dtype=np.float32) * 0.1**2)[None], 2, axis=0
    )
    extinction = np.asarray((1.0, 0.5), np.float32)
    model = RecoveredGaussians(centers, covariances, extinction)
    origins = torch.tensor(((0.0, 0.0, -1.0),), dtype=torch.float32)
    directions = torch.tensor(((0.0, 0.0, 1.0),), dtype=torch.float32)
    tau = model.optical_depth(origins, directions, 1)
    expected = math.sqrt(2.0 * math.pi) * 0.1 * (
        1.0 + 0.5 * math.exp(-2.0)
    )
    assert torch.allclose(tau, torch.tensor((expected,)), atol=1e-5)
    rotation = _rotation_from_vector(torch.zeros(1, 3))
    assert torch.allclose(rotation, torch.eye(3)[None], atol=1e-6)
    shape_model = RecoveredGaussians(
        centers[:1],
        np.diag((0.05**2, 0.1**2, 0.2**2))[None],
        extinction[:1],
        anisotropy_boost=2.0,
        max_anisotropy=6.0,
    )
    boosted = shape_model.initial_scales.numpy()[0]
    assert np.isclose(np.prod(boosted), 0.05 * 0.1 * 0.2)
    assert np.isclose(boosted[-1] / boosted[0], 6.0)
    target = torch.arange(25, dtype=torch.float32)
    assert _frequency_loss(target, target, 5) == 0.0
    assert _frequency_loss(target + torch.eye(5).flatten(), target, 5) > 0.0
    tau.sum().backward()
    assert all(
        parameter.grad is not None and torch.isfinite(parameter.grad).all()
        for parameter in model.parameters()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-npz", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--patches-per-step", type=int, default=4)
    parser.add_argument("--patch-radius", type=int, default=1)
    parser.add_argument("--kernel-chunk", type=int, default=4096)
    parser.add_argument("--eval-rays", type=int, default=1024)
    parser.add_argument("--geometry-warmup", type=int, default=40)
    parser.add_argument("--extinction-only", action="store_true")
    parser.add_argument("--extinction-lr", type=float, default=0.01)
    parser.add_argument("--geometry-lr", type=float, default=0.002)
    parser.add_argument("--transmittance-weight", type=float, default=2.0)
    parser.add_argument("--edge-weight", type=float, default=2.0)
    parser.add_argument("--frequency-weight", type=float, default=0.0)
    parser.add_argument("--frequency-warmup", type=int, default=100)
    parser.add_argument("--frequency-ramp", type=int, default=300)
    parser.add_argument("--scale-growth-weight", type=float, default=0.0)
    parser.add_argument("--mass-weight", type=float, default=0.1)
    parser.add_argument("--anchor-weight", type=float, default=0.01)
    parser.add_argument("--center-limit-factor", type=float, default=0.75)
    parser.add_argument("--scale-factor", type=float, default=1.5)
    parser.add_argument("--rotation-degrees", type=float, default=15.0)
    parser.add_argument("--anisotropy-boost", type=float, default=1.0)
    parser.add_argument("--max-anisotropy", type=float, default=8.0)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--skip-json", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("recover_contracted_50k self-check passed")
        return
    if any(path is None for path in (args.input_npz, args.dataset, args.output)):
        parser.error("input, dataset and output are required")
    if (
        args.steps < 0
        or args.patches_per_step <= 0
        or args.patch_radius <= 0
        or args.kernel_chunk <= 0
        or args.eval_rays < 9
        or args.geometry_warmup < 0
        or args.frequency_warmup < 0
        or args.frequency_ramp < 0
        or args.extinction_lr <= 0.0
        or args.geometry_lr <= 0.0
        or min(
            args.transmittance_weight,
            args.edge_weight,
            args.frequency_weight,
            args.scale_growth_weight,
            args.mass_weight,
            args.anchor_weight,
        )
        < 0.0
        or args.center_limit_factor <= 0.0
        or args.scale_factor < 1.0
        or args.rotation_degrees <= 0.0
        or args.anisotropy_boost <= 0.0
        or args.max_anisotropy < 1.0
        or args.log_every <= 0
    ):
        parser.error("training counts and learning rates must be positive")
    if args.frequency_weight > 0.0 and args.patch_radius < 2:
        parser.error("frequency loss requires --patch-radius >= 2")
    print(json.dumps(recover(args), indent=2))


if __name__ == "__main__":
    main()
