from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn

from train_neural_material import image_from_tensor, labeled_strip, tone_map


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "UE-NeuralRender-Lab" / "neural-volume" / "r4c-box"
TAU = 2.0 * math.pi
PROXY_HALF_EXTENT = 1.35
PROXY_MAX_CHORD = 2.0 * PROXY_HALF_EXTENT * math.sqrt(3.0)
CAMERA_RADIUS = 3.2
FOV_DEGREES = 45.0


def normalize(value: torch.Tensor) -> torch.Tensor:
    return F.normalize(value, dim=-1, eps=1e-6)


def spherical_directions(azimuths: int, elevations: tuple[int, ...], device: torch.device) -> torch.Tensor:
    directions = []
    for elevation in elevations:
        phi = math.radians(elevation)
        for index in range(azimuths):
            theta = TAU * index / azimuths
            directions.append((math.cos(theta) * math.cos(phi), math.sin(theta) * math.cos(phi), math.sin(phi)))
    return torch.tensor(directions, dtype=torch.float32, device=device)


def split_pairs(camera_count: int, sun_count: int) -> tuple[torch.Tensor, torch.Tensor]:
    train, held = [], []
    for camera_index in range(camera_count):
        for sun_index in range(sun_count):
            pair = (camera_index, sun_index)
            (held if (camera_index * 13 + sun_index * 7) % 5 == 0 else train).append(pair)
    assert not set(train).intersection(held)
    assert set(train).union(held) == {
        (camera_index, sun_index) for camera_index in range(camera_count) for sun_index in range(sun_count)
    }
    assert {pair[0] for pair in train} == set(range(camera_count))
    assert {pair[1] for pair in train} == set(range(sun_count))
    return torch.tensor(train, dtype=torch.long), torch.tensor(held, dtype=torch.long)


def camera_rays(camera_axis: torch.Tensor, ndc: torch.Tensor, aspect: float) -> tuple[torch.Tensor, torch.Tensor]:
    camera_axis = normalize(camera_axis)
    origin = camera_axis * CAMERA_RADIUS
    forward = -camera_axis
    world_up = camera_axis.new_tensor((0.0, 0.0, 1.0))
    if abs(float((forward * world_up).sum())) > 0.95:
        world_up = camera_axis.new_tensor((0.0, 1.0, 0.0))
    right = normalize(torch.cross(forward, world_up, dim=-1))
    up = normalize(torch.cross(right, forward, dim=-1))
    scale = math.tan(math.radians(FOV_DEGREES * 0.5))
    direction = normalize(
        forward
        + right * (ndc[:, :1] * aspect * scale)
        + up * (ndc[:, 1:] * scale)
    )
    return origin.expand_as(direction), direction


def full_frame_rays(camera_axis: torch.Tensor, width: int, height: int) -> tuple[torch.Tensor, torch.Tensor]:
    x = (torch.arange(width, device=camera_axis.device, dtype=torch.float32) + 0.5) / width * 2.0 - 1.0
    y = 1.0 - (torch.arange(height, device=camera_axis.device, dtype=torch.float32) + 0.5) / height * 2.0
    yy, xx = torch.meshgrid(y, x, indexing="ij")
    ndc = torch.stack((xx, yy), dim=-1).reshape(-1, 2)
    return camera_rays(camera_axis, ndc, width / height)


def intersect_proxy(origin: torch.Tensor, direction: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    safe_direction = torch.where(
        direction.abs() > 1e-6,
        direction,
        torch.where(direction >= 0.0, torch.full_like(direction, 1e-6), torch.full_like(direction, -1e-6)),
    )
    inverse_direction = safe_direction.reciprocal()
    t0 = (-PROXY_HALF_EXTENT - origin) * inverse_direction
    t1 = (PROXY_HALF_EXTENT - origin) * inverse_direction
    near = torch.minimum(t0, t1).amax(-1).clamp_min(0.0)
    far = torch.maximum(t0, t1).amin(-1)
    return near, far, far > near


def cloud_density(position: torch.Tensor) -> torch.Tensor:
    centers = position.new_tensor(
        ((-0.48, -0.05, -0.10), (0.05, 0.12, 0.10), (0.50, -0.08, -0.02), (-0.12, -0.28, 0.28))
    )
    scales = position.new_tensor(((0.62, 0.55, 0.50), (0.78, 0.60, 0.64), (0.58, 0.54, 0.48), (0.46, 0.42, 0.42)))
    weights = position.new_tensor((0.95, 1.15, 0.88, 0.60))
    local = (position[..., None, :] - centers) / scales
    lobes = (weights * torch.exp(-1.9 * local.square().sum(-1))).sum(-1)
    x, y, z = position.unbind(-1)
    detail = 0.10 * torch.sin(6.1 * x + 1.7 * y) * torch.cos(5.3 * z - 1.3 * x)
    detail += 0.055 * torch.sin(12.7 * x - 8.9 * y + 4.1 * z)
    detail += 0.035 * torch.cos(19.1 * x + 13.7 * y - 11.3 * z)
    envelope = torch.sigmoid((1.26 - position.norm(dim=-1)) * 24.0)
    return F.relu(lobes + detail - 0.32).pow(1.25) * 2.6 * envelope


def light_transmittance(position: torch.Tensor, sun: torch.Tensor, steps: int) -> torch.Tensor:
    step_size = 2.7 / steps
    optical_depth = torch.zeros(len(position), device=position.device)
    for index in range(steps):
        sample = position + sun * ((index + 0.5) * step_size)
        optical_depth += cloud_density(sample) * step_size * 1.35
    return torch.exp(-optical_depth)


def volume_teacher(
    origin: torch.Tensor,
    direction: torch.Tensor,
    sun: torch.Tensor,
    near: torch.Tensor,
    far: torch.Tensor,
    primary_steps: int,
    light_steps: int,
) -> torch.Tensor:
    step_size = (far - near) / primary_steps
    transmittance = torch.ones(len(origin), device=origin.device)
    rgb = torch.zeros((len(origin), 3), device=origin.device)
    cosine = (direction * sun).sum(-1).clamp(-1.0, 1.0)
    g = 0.58
    phase = (1.0 - g * g) / (1.0 + g * g - 2.0 * g * cosine).clamp_min(1e-4).pow(1.5)
    phase = (phase / (((1.0 + g) / (1.0 - g)) ** 2)).clamp(0.0, 1.0)
    warm = origin.new_tensor((1.35, 0.95, 0.62))
    cool = origin.new_tensor((0.20, 0.33, 0.52))
    for index in range(primary_steps):
        distance = near + (index + 0.5) * step_size
        position = origin + direction * distance[:, None]
        density = cloud_density(position)
        sample_alpha = 1.0 - torch.exp(-density * step_size * 1.65)
        sunlight = light_transmittance(position, sun, light_steps)
        height = ((position[:, 2] + 1.2) / 2.4).clamp(0.0, 1.0)
        radiance = cool * (0.24 + 0.18 * height[:, None])
        radiance += warm * sunlight[:, None] * (0.20 + 1.45 * phase[:, None])
        weight = transmittance * sample_alpha
        rgb += weight[:, None] * radiance
        transmittance *= 1.0 - sample_alpha
    return torch.cat((rgb.clamp(0.0, 8.0), (1.0 - transmittance).clamp(0.0, 1.0)[:, None]), dim=-1)


def proxy_inputs(
    origin: torch.Tensor,
    direction: torch.Tensor,
    sun: torch.Tensor,
    near: torch.Tensor,
    far: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    entry = origin + direction * near[:, None]
    return entry, -direction, sun, far - near


def analytic_features(entry: torch.Tensor, view: torch.Tensor, sun: torch.Tensor, thickness: torch.Tensor) -> torch.Tensor:
    position = entry / PROXY_HALF_EXTENT
    depth = thickness[:, None] / PROXY_MAX_CHORD
    angle = (view * sun).sum(-1, keepdim=True)
    return torch.cat(
        (
            torch.ones_like(depth),
            position,
            position.square(),
            view,
            sun,
            depth,
            depth.square(),
            angle,
            angle.square(),
            position * view,
            position * sun,
        ),
        dim=-1,
    )


def fit_analytic_proxy(data: dict[str, torch.Tensor]) -> torch.Tensor:
    features = analytic_features(data["entry"], data["view"], data["sun"], data["thickness"])
    target = torch.cat((torch.log1p(data["target"][:, :3]), data["target"][:, 3:]), dim=-1)
    regularizer = torch.eye(features.shape[1], device=features.device) * 1e-3
    return torch.linalg.solve(features.T @ features + regularizer, features.T @ target)


def analytic_prediction(
    weights: torch.Tensor,
    entry: torch.Tensor,
    view: torch.Tensor,
    sun: torch.Tensor,
    thickness: torch.Tensor,
) -> torch.Tensor:
    prediction = analytic_features(entry, view, sun, thickness) @ weights
    return torch.cat((prediction[:, :3].clamp_min(0.0), prediction[:, 3:].clamp(0.0, 1.0)), dim=-1)


class NeuralVolumeProxy(nn.Module):
    def __init__(self, resolution: int, channels: int, width: int):
        super().__init__()
        self.planes = nn.Parameter(torch.randn(3, channels, resolution, resolution) * 0.02)
        self.layers = nn.Sequential(
            nn.Linear(channels + 10, width),
            nn.ReLU(),
            nn.Linear(width, width),
            nn.ReLU(),
            nn.Linear(width, width),
            nn.ReLU(),
            nn.Linear(width, 4),
        )
        with torch.no_grad():
            self.layers[-1].bias.copy_(torch.tensor((-2.5, -2.5, -2.5, -1.0)))

    def forward(
        self,
        entry: torch.Tensor,
        view: torch.Tensor,
        sun: torch.Tensor,
        thickness: torch.Tensor,
    ) -> torch.Tensor:
        position = entry / PROXY_HALF_EXTENT
        grids = torch.stack(
            (position[:, (0, 1)], position[:, (0, 2)], position[:, (1, 2)]), dim=0
        ).unsqueeze(2)
        latent = F.grid_sample(self.planes, grids, mode="bilinear", padding_mode="border", align_corners=False)
        latent = latent.squeeze(-1).sum(0).transpose(0, 1)
        features = torch.cat((latent, position, view, sun, thickness[:, None] / PROXY_MAX_CHORD), dim=-1)
        raw = self.layers(features)
        return torch.cat((F.softplus(raw[:, :3]), torch.sigmoid(raw[:, 3:])), dim=-1)


@torch.no_grad()
def build_dataset(
    pairs: torch.Tensor,
    cameras: torch.Tensor,
    suns: torch.Tensor,
    samples_per_pair: int,
    generator: torch.Generator,
    sun_jitter_degrees: float,
    primary_steps: int,
    light_steps: int,
    teacher_batch: int,
) -> dict[str, torch.Tensor]:
    origins, directions, sun_values, near_values, far_values = [], [], [], [], []
    for camera_index, sun_index in pairs.tolist():
        collected = 0
        while collected < samples_per_pair:
            candidate_count = max(32, 2 * (samples_per_pair - collected))
            ndc = torch.rand((candidate_count, 2), generator=generator, device=cameras.device) * 2.0 - 1.0
            origin, direction = camera_rays(cameras[camera_index], ndc, 16.0 / 9.0)
            near, far, hit = intersect_proxy(origin, direction)
            take = min(samples_per_pair - collected, int(hit.sum()))
            if take == 0:
                continue
            selected = hit.nonzero(as_tuple=False).squeeze(-1)[:take]
            origins.append(origin[selected])
            directions.append(direction[selected])
            selected_sun = suns[sun_index].expand(take, -1)
            if sun_jitter_degrees > 0.0:
                angle = (torch.rand(take, generator=generator, device=cameras.device) * 2.0 - 1.0)
                angle *= math.radians(sun_jitter_degrees)
                cosine, sine = torch.cos(angle), torch.sin(angle)
                selected_sun = torch.stack(
                    (
                        selected_sun[:, 0] * cosine - selected_sun[:, 1] * sine,
                        selected_sun[:, 0] * sine + selected_sun[:, 1] * cosine,
                        selected_sun[:, 2],
                    ),
                    dim=-1,
                )
            sun_values.append(selected_sun)
            near_values.append(near[selected])
            far_values.append(far[selected])
            collected += take
    origin = torch.cat(origins)
    direction = torch.cat(directions)
    sun = torch.cat(sun_values)
    near = torch.cat(near_values)
    far = torch.cat(far_values)
    targets = []
    for start in range(0, len(origin), teacher_batch):
        stop = start + teacher_batch
        targets.append(
            volume_teacher(
                origin[start:stop],
                direction[start:stop],
                sun[start:stop],
                near[start:stop],
                far[start:stop],
                primary_steps,
                light_steps,
            )
        )
    entry, view, sun, thickness = proxy_inputs(origin, direction, sun, near, far)
    return {"entry": entry, "view": view, "sun": sun, "thickness": thickness, "target": torch.cat(targets)}


@torch.no_grad()
def predict_in_chunks(model: NeuralVolumeProxy, data: dict[str, torch.Tensor], chunk: int = 65536) -> torch.Tensor:
    return torch.cat(
        [
            model(data["entry"][start : start + chunk], data["view"][start : start + chunk], data["sun"][start : start + chunk], data["thickness"][start : start + chunk])
            for start in range(0, len(data["entry"]), chunk)
        ]
    )


def validation_loss(model: NeuralVolumeProxy, data: dict[str, torch.Tensor]) -> float:
    model.eval()
    with torch.no_grad():
        prediction = predict_in_chunks(model, data)
        target_rgb = torch.log1p(data["target"][:, :3])
        return (F.mse_loss(prediction[:, :3], target_rgb) + 0.4 * F.mse_loss(prediction[:, 3:], data["target"][:, 3:])).item()


def train(
    model: NeuralVolumeProxy,
    train_data: dict[str, torch.Tensor],
    held_data: dict[str, torch.Tensor],
    steps: int,
    batch_size: int,
    learning_rate: float,
) -> tuple[dict[str, torch.Tensor], list[dict[str, float]], float]:
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    target_rgb = torch.log1p(train_data["target"][:, :3])
    best_loss, best_state = math.inf, {}
    history = []
    started = time.perf_counter()
    for step in range(1, steps + 1):
        model.train()
        index = torch.randint(len(target_rgb), (min(batch_size, len(target_rgb)),), device=target_rgb.device)
        prediction = model(train_data["entry"][index], train_data["view"][index], train_data["sun"][index], train_data["thickness"][index])
        loss = F.mse_loss(prediction[:, :3], target_rgb[index])
        loss += 0.4 * F.mse_loss(prediction[:, 3:], train_data["target"][index, 3:])
        if not torch.isfinite(loss):
            raise RuntimeError("Training produced a non-finite loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step % max(1, steps // 12) == 0 or step == steps:
            held_loss = validation_loss(model, held_data)
            history.append({"step": step, "train_loss": loss.item(), "held_loss": held_loss})
            print(json.dumps(history[-1]), flush=True)
            if held_loss < best_loss:
                best_loss = held_loss
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    return best_state, history, time.perf_counter() - started


def decode_prediction(encoded: torch.Tensor) -> torch.Tensor:
    return torch.cat((torch.expm1(encoded[:, :3]).clamp(0.0, 8.0), encoded[:, 3:].clamp(0.0, 1.0)), dim=-1)


@torch.no_grad()
def final_metrics(
    model: NeuralVolumeProxy,
    analytic_weights: torch.Tensor,
    held_data: dict[str, torch.Tensor],
) -> dict[str, float | int]:
    target = held_data["target"]
    student_encoded = predict_in_chunks(model, held_data)
    analytic_encoded = analytic_prediction(
        analytic_weights, held_data["entry"], held_data["view"], held_data["sun"], held_data["thickness"]
    )
    student = decode_prediction(student_encoded)
    analytic = decode_prediction(analytic_encoded)
    target_log = torch.log1p(target[:, :3])
    student_log_rmse = F.mse_loss(student_encoded[:, :3], target_log).sqrt()
    analytic_log_rmse = F.mse_loss(analytic_encoded[:, :3], target_log).sqrt()
    student_mse = F.mse_loss(tone_map(student[:, :3]), tone_map(target[:, :3])).clamp_min(1e-12)
    analytic_mse = F.mse_loss(tone_map(analytic[:, :3]), tone_map(target[:, :3])).clamp_min(1e-12)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    return {
        "held_samples": len(target),
        "analytic_log_rgb_rmse": analytic_log_rmse.item(),
        "student_log_rgb_rmse": student_log_rmse.item(),
        "student_to_analytic_log_rgb_rmse_ratio": (student_log_rmse / analytic_log_rmse).item(),
        "analytic_tonemapped_rgb_psnr_db": (-10.0 * torch.log10(analytic_mse)).item(),
        "student_tonemapped_rgb_psnr_db": (-10.0 * torch.log10(student_mse)).item(),
        "analytic_alpha_rmse": F.mse_loss(analytic[:, 3:], target[:, 3:]).sqrt().item(),
        "student_alpha_rmse": F.mse_loss(student[:, 3:], target[:, 3:]).sqrt().item(),
        "parameter_count": parameter_count,
        "fp16_bytes": 2 * parameter_count,
        "fp16_mib": 2 * parameter_count / 1024**2,
    }


def error_image(prediction: torch.Tensor, target: torch.Tensor) -> Image.Image:
    magnitude = (tone_map(prediction) - tone_map(target)).abs().mean(-1).mul(6.0).clamp(0.0, 1.0)
    rgb = torch.stack((magnitude, magnitude.square() * 0.75, magnitude.pow(4) * 0.12), dim=-1)
    return Image.fromarray(rgb.mul(255.0).round().byte().cpu().numpy(), "RGB")


@torch.no_grad()
def render_frame(
    model: NeuralVolumeProxy,
    analytic_weights: torch.Tensor,
    camera: torch.Tensor,
    sun: torch.Tensor,
    width: int,
    height: int,
    primary_steps: int,
    light_steps: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    origin, direction = full_frame_rays(camera, width, height)
    near, far, hit = intersect_proxy(origin, direction)
    selected = hit.nonzero(as_tuple=False).squeeze(-1)
    hit_origin, hit_direction = origin[selected], direction[selected]
    hit_sun = sun.expand(len(selected), -1)
    entry, view, hit_sun, thickness = proxy_inputs(hit_origin, hit_direction, hit_sun, near[selected], far[selected])
    data = {"entry": entry, "view": view, "sun": hit_sun, "thickness": thickness}
    student = decode_prediction(predict_in_chunks(model, data))
    analytic = decode_prediction(analytic_prediction(analytic_weights, entry, view, hit_sun, thickness))
    teacher_parts = []
    for start in range(0, len(selected), 8192):
        stop = start + 8192
        teacher_parts.append(
            volume_teacher(
                hit_origin[start:stop],
                hit_direction[start:stop],
                hit_sun[start:stop],
                near[selected][start:stop],
                far[selected][start:stop],
                primary_steps,
                light_steps,
            )
        )
    teacher = torch.cat(teacher_parts)
    ray_z = direction[:, 2].reshape(height, width, 1)
    sky = origin.new_tensor((0.035, 0.09, 0.16)) + (ray_z * 0.5 + 0.5).clamp(0.0, 1.0) * origin.new_tensor((0.18, 0.28, 0.38))
    results = []
    for cloud in (analytic, student, teacher):
        image = sky.reshape(-1, 3).clone()
        image[selected] = cloud[:, :3] + (1.0 - cloud[:, 3:]) * image[selected]
        results.append(image.reshape(height, width, 3))
    return tuple(results)


@torch.no_grad()
def save_evidence(
    model: NeuralVolumeProxy,
    analytic_weights: torch.Tensor,
    cameras: torch.Tensor,
    suns: torch.Tensor,
    held_pairs: torch.Tensor,
    output: Path,
    width: int,
    height: int,
    sweep_frames: int,
    primary_steps: int,
    light_steps: int,
) -> dict[str, float]:
    model.eval()
    rows = []
    pair_indices = torch.linspace(0, len(held_pairs) - 1, 3).round().long()
    for pair_index in pair_indices:
        camera_index, sun_index = held_pairs[pair_index].tolist()
        analytic, student, teacher = render_frame(
            model, analytic_weights, cameras[camera_index], suns[sun_index], width, height, primary_steps, light_steps
        )
        rows.append(
            labeled_strip(
                [
                    image_from_tensor(analytic),
                    image_from_tensor(student),
                    image_from_tensor(teacher),
                    error_image(student, teacher),
                    error_image(analytic, teacher),
                ],
                ["Analytic", "Student", "Teacher", "Student error", "Analytic error"],
            )
        )
    comparison = Image.new("RGB", (rows[0].width, sum(row.height for row in rows)), (16, 18, 22))
    top = 0
    for row in rows:
        comparison.paste(row, (0, top))
        top += row.height
    comparison.save(output / "comparison.png")

    frames, frame_errors, delta_errors = [], [], []
    previous_student = previous_teacher = None
    camera = cameras[len(cameras) // 3]
    elevation = math.radians(45.0)
    for frame_index in range(sweep_frames):
        angle = TAU * frame_index / sweep_frames
        sun = cameras.new_tensor((math.cos(angle) * math.cos(elevation), math.sin(angle) * math.cos(elevation), math.sin(elevation)))
        _, student, teacher = render_frame(
            model, analytic_weights, camera, sun, width, height, primary_steps, light_steps
        )
        frames.append(labeled_strip([image_from_tensor(student), image_from_tensor(teacher)], ["Student", "Teacher"]))
        frame_errors.append(F.mse_loss(student, teacher).sqrt().item())
        if previous_student is not None:
            delta_errors.append(F.mse_loss(student - previous_student, teacher - previous_teacher).sqrt().item())
        previous_student, previous_teacher = student, teacher
    frames[0].save(output / "relight_sweep.gif", save_all=True, append_images=frames[1:], duration=120, loop=0)
    return {
        "relight_frame_rmse": sum(frame_errors) / len(frame_errors),
        "relight_worst_frame_rmse": max(frame_errors),
        "relight_delta_rmse": sum(delta_errors) / max(1, len(delta_errors)),
    }


def cuda_median_ms(function, warmup: int, samples: int) -> float:
    for _ in range(warmup):
        function()
    torch.cuda.synchronize()
    timings = []
    for _ in range(samples):
        start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record()
        function()
        end.record()
        end.synchronize()
        timings.append(start.elapsed_time(end))
    return float(torch.tensor(timings).median())


@torch.no_grad()
def benchmark(
    model: NeuralVolumeProxy,
    analytic_weights: torch.Tensor,
    camera: torch.Tensor,
    sun: torch.Tensor,
    width: int,
    height: int,
    primary_steps: int,
    light_steps: int,
    warmup: int,
    samples: int,
) -> dict[str, float | int | str]:
    origin, direction = full_frame_rays(camera, width, height)
    near, far, hit = intersect_proxy(origin, direction)
    selected = hit.nonzero(as_tuple=False).squeeze(-1)
    origin, direction, near, far = origin[selected], direction[selected], near[selected], far[selected]
    sun = sun.expand(len(selected), -1)
    entry, view, sun, thickness = proxy_inputs(origin, direction, sun, near, far)
    model.eval()
    teacher_ms = cuda_median_ms(
        lambda: volume_teacher(origin, direction, sun, near, far, primary_steps, light_steps), warmup, samples
    )
    student_ms = cuda_median_ms(lambda: model(entry, view, sun, thickness), warmup, samples)
    analytic_ms = cuda_median_ms(lambda: analytic_prediction(analytic_weights, entry, view, sun, thickness), warmup, samples)
    return {
        "backend": "PyTorch eager CUDA; hit-ray shading only; directional world-box screen, not UE proof",
        "width": width,
        "height": height,
        "hit_rays": len(selected),
        "teacher_median_ms": teacher_ms,
        "student_median_ms": student_ms,
        "analytic_median_ms": analytic_ms,
        "student_to_teacher_ratio": student_ms / teacher_ms,
    }


def self_check(device: torch.device) -> None:
    origin = torch.tensor(((0.0, 0.0, 3.2),), device=device)
    direction = torch.tensor(((0.0, 0.0, -1.0),), device=device)
    near, far, hit = intersect_proxy(origin, direction)
    assert bool(hit.item()) and abs(float(far - near) - 2.0 * PROXY_HALF_EXTENT) < 1e-4
    density = cloud_density(torch.tensor(((0.0, 0.0, 0.0), (2.0, 2.0, 2.0)), device=device))
    assert torch.isfinite(density).all() and density[0] > density[1]
    train_pairs, held_pairs = split_pairs(6, 5)
    assert len(train_pairs) + len(held_pairs) == 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the world-box neural volumetric proxy experiment.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--learning-rate", type=float, default=0.004)
    parser.add_argument("--samples-per-pair", type=int, default=384)
    parser.add_argument("--sun-jitter-degrees", type=float, default=22.5)
    parser.add_argument("--teacher-steps", type=int, default=64)
    parser.add_argument("--light-steps", type=int, default=8)
    parser.add_argument("--teacher-batch", type=int, default=8192)
    parser.add_argument("--triplane-resolution", type=int, default=32)
    parser.add_argument("--triplane-channels", type=int, default=8)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--evidence-width", type=int, default=192)
    parser.add_argument("--evidence-height", type=int, default=108)
    parser.add_argument("--sweep-frames", type=int, default=16)
    parser.add_argument("--benchmark-width", type=int, default=512)
    parser.add_argument("--benchmark-height", type=int, default=288)
    parser.add_argument("--benchmark-samples", type=int, default=12)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.smoke:
        args.steps = 3
        args.batch_size = 512
        args.samples_per_pair = 3
        args.teacher_steps = 8
        args.light_steps = 2
        args.teacher_batch = 2048
        args.triplane_resolution = 16
        args.triplane_channels = 4
        args.width = 16
        args.evidence_width = 64
        args.evidence_height = 36
        args.sweep_frames = 3
        args.benchmark_width = 96
        args.benchmark_height = 54
        args.benchmark_samples = 2
        args.output = args.output.parent / "r4c-box-smoke"
    numeric = (
        args.steps,
        args.batch_size,
        args.samples_per_pair,
        args.teacher_steps,
        args.light_steps,
        args.triplane_resolution,
        args.triplane_channels,
        args.width,
    )
    if min(numeric) <= 0:
        raise ValueError("All training and rendering dimensions must be positive")
    if args.sun_jitter_degrees < 0.0:
        raise ValueError("Sun jitter must be non-negative")
    if not torch.cuda.is_available():
        raise RuntimeError("The neural volume experiment requires CUDA for its fixed performance Gate")

    random.seed(20260814)
    torch.manual_seed(20260814)
    torch.cuda.manual_seed_all(20260814)
    device = torch.device("cuda")
    self_check(device)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cameras = spherical_directions(12, (-10, 15, 35), device)
    suns = spherical_directions(8, (15, 45, 75), device)
    train_pairs, held_pairs = split_pairs(len(cameras), len(suns))
    train_generator = torch.Generator(device=device).manual_seed(20260814)
    held_generator = torch.Generator(device=device).manual_seed(20260815)

    dataset_started = time.perf_counter()
    print("Generating ray-marched train targets", flush=True)
    train_data = build_dataset(
        train_pairs,
        cameras,
        suns,
        args.samples_per_pair,
        train_generator,
        args.sun_jitter_degrees,
        args.teacher_steps,
        args.light_steps,
        args.teacher_batch,
    )
    print("Generating ray-marched held-out targets", flush=True)
    held_data = build_dataset(
        held_pairs,
        cameras,
        suns,
        args.samples_per_pair,
        held_generator,
        0.0,
        args.teacher_steps,
        args.light_steps,
        args.teacher_batch,
    )
    dataset_seconds = time.perf_counter() - dataset_started
    analytic_weights = fit_analytic_proxy(train_data)

    model = NeuralVolumeProxy(args.triplane_resolution, args.triplane_channels, args.width).to(device)
    torch.cuda.reset_peak_memory_stats()
    best_state, history, training_seconds = train(
        model, train_data, held_data, args.steps, args.batch_size, args.learning_rate
    )
    model.load_state_dict(best_state)
    model.eval()
    metrics = final_metrics(model, analytic_weights, held_data)
    print("Rendering held-out evidence", flush=True)
    metrics.update(
        save_evidence(
            model,
            analytic_weights,
            cameras,
            suns,
            held_pairs,
            output,
            args.evidence_width,
            args.evidence_height,
            args.sweep_frames,
            args.teacher_steps,
            args.light_steps,
        )
    )
    print("Running CUDA timing", flush=True)
    timing = benchmark(
        model,
        analytic_weights,
        cameras[len(cameras) // 2],
        suns[len(suns) // 2],
        args.benchmark_width,
        args.benchmark_height,
        args.teacher_steps,
        args.light_steps,
        1 if args.smoke else 3,
        args.benchmark_samples,
    )
    metrics.update(
        {
            "dataset_seconds": dataset_seconds,
            "training_seconds": training_seconds,
            "peak_cuda_mib": torch.cuda.max_memory_allocated() / 1024**2,
            "gpu": torch.cuda.get_device_name(0),
            "torch": torch.__version__,
            "numeric_gate_pass": bool(
                metrics["student_tonemapped_rgb_psnr_db"] >= 26.0
                and metrics["student_to_analytic_log_rgb_rmse_ratio"] <= 0.70
                and metrics["student_alpha_rmse"] <= 0.06
                and metrics["fp16_mib"] <= 0.5
                and timing["student_to_teacher_ratio"] <= 0.50
            ),
            "visual_gate": "pending human review of comparison.png and relight_sweep.gif",
        }
    )
    torch.save(
        {
            "model": model.state_dict(),
            "analytic_weights": analytic_weights.cpu(),
            "arguments": vars(args),
            "metrics": metrics,
        },
        output / "best.pt",
    )
    payload = {"arguments": vars(args), "history": history, "metrics": metrics, "timing": timing}
    (output / "metrics.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
