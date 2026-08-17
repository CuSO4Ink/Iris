from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from torch import nn


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "UE-NeuralRender-Lab" / "neural-material" / "r1"
TAU = 2.0 * math.pi


def normalize(value: torch.Tensor) -> torch.Tensor:
    return F.normalize(value, dim=-1, eps=1e-6)


def directions(azimuths: int, elevations: tuple[int, ...], device: torch.device) -> torch.Tensor:
    result = []
    for elevation in elevations:
        elevation_radians = math.radians(elevation)
        for index in range(azimuths):
            azimuth = TAU * index / azimuths
            result.append(
                (
                    math.cos(azimuth) * math.cos(elevation_radians),
                    math.sin(azimuth) * math.cos(elevation_radians),
                    math.sin(elevation_radians),
                )
            )
    return torch.tensor(result, dtype=torch.float32, device=device)


def split_direction_pairs(light_count: int, view_count: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    train, held = [], []
    for light_index in range(light_count):
        for view_index in range(view_count):
            pair = (light_index, view_index)
            (held if (light_index * 13 + view_index * 7) % 5 == 0 else train).append(pair)
    train_tensor = torch.tensor(train, dtype=torch.long, device=device)
    held_tensor = torch.tensor(held, dtype=torch.long, device=device)
    assert not set(train).intersection(held)
    assert set(train).union(held) == {
        (light_index, view_index)
        for light_index in range(light_count)
        for view_index in range(view_count)
    }
    assert set(train_tensor[:, 0].tolist()) == set(range(light_count))
    assert set(train_tensor[:, 1].tolist()) == set(range(view_count))
    return train_tensor, held_tensor


def material_fields(uv: torch.Tensor) -> tuple[torch.Tensor, ...]:
    x, y = uv.unbind(-1)
    px, py = TAU * x, TAU * y
    low = (
        0.50
        + 0.22 * torch.sin(2.0 * px + 0.45 * torch.sin(py))
        + 0.16 * torch.cos(3.0 * py - 0.35 * torch.sin(px))
        + 0.08 * torch.sin(3.0 * px + 4.0 * py)
    ).clamp(0.0, 1.0)
    grain = 0.5 + 0.5 * torch.sin(11.0 * px + 0.8 * torch.sin(7.0 * py)) * torch.cos(9.0 * py - px)
    pores = 0.5 + 0.5 * torch.sin(23.0 * px + 17.0 * py) * torch.sin(19.0 * px - 13.0 * py)
    wet = torch.sigmoid((0.54 - low) * 9.0 + 1.1 * torch.sin(px - 1.5 * py))
    dust = torch.sigmoid((grain - 0.58) * 8.0) * (1.0 - 0.82 * wet)

    dark = uv.new_tensor((0.045, 0.055, 0.063))
    light = uv.new_tensor((0.28, 0.245, 0.19))
    base = dark + (light - dark) * low[..., None]
    base *= 0.86 + 0.14 * grain[..., None]

    slope_x = 0.17 * torch.cos(2.0 * px + 0.45 * torch.sin(py)) + 0.07 * torch.cos(3.0 * px + 4.0 * py)
    slope_y = -0.14 * torch.sin(3.0 * py - 0.35 * torch.sin(px)) + 0.08 * torch.cos(3.0 * px + 4.0 * py)
    normal = normalize(torch.stack((-slope_x, -slope_y, torch.ones_like(slope_x)), dim=-1))
    roughness = (0.29 + 0.34 * (1.0 - low) + 0.08 * pores).clamp(0.12, 0.82)
    orientation = px + 0.7 * py + 0.8 * torch.sin(2.0 * py)
    return base, normal, roughness, wet, dust, pores, orientation


def fresnel_schlick(cosine: torch.Tensor, f0: torch.Tensor) -> torch.Tensor:
    return f0 + (1.0 - f0) * (1.0 - cosine[..., None]).clamp(0.0, 1.0).pow(5)


def ggx_specular(
    normal: torch.Tensor,
    wi: torch.Tensor,
    wo: torch.Tensor,
    roughness: torch.Tensor,
    f0: torch.Tensor,
) -> torch.Tensor:
    half_vector = normalize(wi + wo)
    ndotl = (normal * wi).sum(-1).clamp_min(1e-4)
    ndotv = (normal * wo).sum(-1).clamp_min(1e-4)
    ndoth = (normal * half_vector).sum(-1).clamp_min(1e-4)
    vdoth = (wo * half_vector).sum(-1).clamp_min(1e-4)
    alpha = roughness.square().clamp_min(0.0025)
    alpha2 = alpha.square()
    denominator = (ndoth.square() * (alpha2 - 1.0) + 1.0).square().clamp_min(1e-6)
    distribution = alpha2 / (math.pi * denominator)
    k = (roughness + 1.0).square() / 8.0
    geometry_l = ndotl / (ndotl * (1.0 - k) + k)
    geometry_v = ndotv / (ndotv * (1.0 - k) + k)
    fresnel = fresnel_schlick(vdoth, f0)
    return distribution[..., None] * (geometry_l * geometry_v / (4.0 * ndotl * ndotv))[..., None] * fresnel


def anisotropic_specular(
    normal: torch.Tensor,
    wi: torch.Tensor,
    wo: torch.Tensor,
    orientation: torch.Tensor,
    rough_x: torch.Tensor,
    rough_y: torch.Tensor,
    f0: torch.Tensor,
) -> torch.Tensor:
    half_vector = normalize(wi + wo)
    reference = torch.zeros_like(normal)
    reference[..., 0] = 1.0
    tangent_0 = normalize(reference - normal * (reference * normal).sum(-1, keepdim=True))
    bitangent_0 = normalize(torch.cross(normal, tangent_0, dim=-1))
    cosine, sine = torch.cos(orientation)[..., None], torch.sin(orientation)[..., None]
    tangent = tangent_0 * cosine + bitangent_0 * sine
    bitangent = -tangent_0 * sine + bitangent_0 * cosine
    ht = (half_vector * tangent).sum(-1)
    hb = (half_vector * bitangent).sum(-1)
    hn = (half_vector * normal).sum(-1).clamp_min(1e-4)
    ndotl = (normal * wi).sum(-1).clamp_min(1e-4)
    ndotv = (normal * wo).sum(-1).clamp_min(1e-4)
    vdoth = (wo * half_vector).sum(-1).clamp_min(1e-4)
    denominator = ((ht / rough_x).square() + (hb / rough_y).square() + hn.square()).square().clamp_min(1e-6)
    distribution = 1.0 / (math.pi * rough_x * rough_y * denominator)
    average_roughness = torch.sqrt(rough_x * rough_y)
    k = (average_roughness + 1.0).square() / 8.0
    geometry = (ndotl / (ndotl * (1.0 - k) + k)) * (ndotv / (ndotv * (1.0 - k) + k))
    fresnel = fresnel_schlick(vdoth, f0)
    return distribution[..., None] * (geometry / (4.0 * ndotl * ndotv))[..., None] * fresnel


def pbr_baseline(uv: torch.Tensor, wi: torch.Tensor, wo: torch.Tensor) -> torch.Tensor:
    base, normal, roughness, *_ = material_fields(uv)
    ndotl = (normal * wi).sum(-1).clamp(0.0, 1.0)
    f0 = torch.full_like(base, 0.04)
    direct = base / math.pi + ggx_specular(normal, wi, wo, roughness, f0)
    return (2.4 * direct * ndotl[..., None] + 0.025 * base).clamp(0.0, 32.0)


def teacher(uv: torch.Tensor, wi: torch.Tensor, wo: torch.Tensor) -> torch.Tensor:
    base, normal, roughness, wet, dust, pores, orientation = material_fields(uv)
    half_vector = normalize(wi + wo)
    ndotl = (normal * wi).sum(-1).clamp(0.0, 1.0)
    ndotv = (normal * wo).sum(-1).clamp(0.0, 1.0)
    vdoth = (wo * half_vector).sum(-1).clamp(0.0, 1.0)

    diffuse = base * (1.0 - 0.58 * wet[..., None]) / math.pi
    substrate_roughness = (roughness + 0.12 * dust - 0.10 * wet).clamp(0.10, 0.90)
    substrate = ggx_specular(normal, wi, wo, substrate_roughness, torch.full_like(base, 0.045))

    film_phase = 18.0 * (1.0 - vdoth) + 5.0 * wet + 2.0 * pores
    film_tint = 0.72 + 0.28 * torch.stack(
        (
            0.5 + 0.5 * torch.sin(film_phase),
            0.5 + 0.5 * torch.sin(film_phase + 2.1),
            0.5 + 0.5 * torch.sin(film_phase + 4.2),
        ),
        dim=-1,
    )
    coat_roughness = (0.045 + 0.10 * (1.0 - wet) + 0.03 * pores).clamp(0.04, 0.18)
    clearcoat = ggx_specular(normal, wi, wo, coat_roughness, torch.full_like(base, 0.055))

    rough_x = (0.055 + 0.055 * pores).clamp(0.04, 0.13)
    rough_y = (0.22 + 0.12 * dust).clamp(0.18, 0.38)
    directional = anisotropic_specular(
        normal,
        wi,
        wo,
        orientation,
        rough_x,
        rough_y,
        torch.full_like(base, 0.035),
    )
    sparkle = torch.sigmoid(7.0 * (pores - 0.60))
    sheen = dust[..., None] * base.sqrt() * (1.0 - ndotv)[..., None].square() * 0.20
    direct = diffuse + substrate + wet[..., None] * clearcoat * film_tint * 0.72
    direct += (0.18 + 0.52 * wet)[..., None] * sparkle[..., None] * directional
    ambient = base * (0.018 + 0.035 * dust)[..., None] + sheen
    return (2.4 * direct * ndotl[..., None] + ambient).clamp(0.0, 32.0)


class TinyNeuralMaterial(nn.Module):
    def __init__(self, latent_resolution: int, latent_channels: int, width: int):
        super().__init__()
        self.latent = nn.Parameter(torch.randn(1, latent_channels, latent_resolution, latent_resolution) * 0.02)
        self.layers = nn.Sequential(
            nn.Linear(latent_channels + 16, width),
            nn.ReLU(),
            nn.Linear(width, width),
            nn.ReLU(),
            nn.Linear(width, 3),
        )
        nn.init.constant_(self.layers[-1].bias, -2.0)

    def forward(self, uv: torch.Tensor, wi: torch.Tensor, wo: torch.Tensor, normal: torch.Tensor) -> torch.Tensor:
        grid = uv.mul(2.0).sub(1.0).reshape(1, -1, 1, 2)
        latent = F.grid_sample(self.latent, grid, mode="bilinear", align_corners=False, padding_mode="border")
        latent = latent.squeeze(0).squeeze(-1).transpose(0, 1)
        half_vector = normalize(wi + wo)
        angles = torch.stack(
            (
                (normal * wi).sum(-1),
                (normal * wo).sum(-1),
                (normal * half_vector).sum(-1),
                (wo * half_vector).sum(-1),
            ),
            dim=-1,
        )
        features = torch.cat((latent, wi, wo, normal, half_vector, angles), dim=-1)
        return F.softplus(self.layers(features))


@torch.no_grad()
def validation_rmse(
    model: TinyNeuralMaterial,
    uv: torch.Tensor,
    wi: torch.Tensor,
    wo: torch.Tensor,
    normal: torch.Tensor,
    target_log: torch.Tensor,
) -> float:
    model.eval()
    prediction = model(uv, wi, wo, normal)
    return torch.mean((prediction - target_log).square()).sqrt().item()


def tone_map(rgb: torch.Tensor) -> torch.Tensor:
    return (rgb / (1.0 + rgb)).clamp(0.0, 1.0).pow(1.0 / 2.2)


def image_from_tensor(rgb: torch.Tensor) -> Image.Image:
    values = tone_map(rgb).mul(255.0).round().byte().cpu().numpy()
    return Image.fromarray(values, "RGB")


def heatmap(error: torch.Tensor) -> Image.Image:
    magnitude = error.mean(-1).mul(7.0).clamp(0.0, 1.0)
    rgb = torch.stack((magnitude, magnitude.square() * 0.8, magnitude.pow(4) * 0.15), dim=-1)
    return Image.fromarray(rgb.mul(255.0).round().byte().cpu().numpy(), "RGB")


@torch.no_grad()
def render_tile(
    model: TinyNeuralMaterial,
    light: torch.Tensor,
    view: torch.Tensor,
    size: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    coordinate = torch.linspace(0.0, 1.0, size, device=light.device)
    y, x = torch.meshgrid(coordinate, coordinate, indexing="ij")
    uv = torch.stack((x, y), dim=-1).reshape(-1, 2)
    wi = light.expand(len(uv), -1)
    wo = view.expand(len(uv), -1)
    normal = material_fields(uv)[1]
    baseline = pbr_baseline(uv, wi, wo).reshape(size, size, 3)
    prediction = torch.expm1(model(uv, wi, wo, normal)).clamp(0.0, 32.0).reshape(size, size, 3)
    target = teacher(uv, wi, wo).reshape(size, size, 3)
    return baseline, prediction, target


def labeled_strip(images: list[Image.Image], labels: list[str], label_height: int = 24) -> Image.Image:
    width, height = images[0].size
    result = Image.new("RGB", (width * len(images), height + label_height), (16, 18, 22))
    draw = ImageDraw.Draw(result)
    for index, (image, label) in enumerate(zip(images, labels, strict=True)):
        x = index * width
        result.paste(image, (x, label_height))
        draw.text((x + 6, 5), label, fill=(235, 235, 235))
    return result


@torch.no_grad()
def save_evidence(
    model: TinyNeuralMaterial,
    lights: torch.Tensor,
    views: torch.Tensor,
    held_pairs: torch.Tensor,
    output: Path,
    size: int,
    sweep_frames: int,
) -> None:
    model.eval()
    rows = []
    sample_indices = torch.linspace(0, len(held_pairs) - 1, 4).round().long()
    for pair_index in sample_indices:
        light_index, view_index = held_pairs[pair_index].tolist()
        baseline, prediction, target = render_tile(model, lights[light_index], views[view_index], size)
        mapped_baseline, mapped_prediction, mapped_target = map(tone_map, (baseline, prediction, target))
        rows.append(
            labeled_strip(
                [
                    image_from_tensor(baseline),
                    image_from_tensor(prediction),
                    image_from_tensor(target),
                    heatmap((mapped_prediction - mapped_target).abs()),
                    heatmap((mapped_baseline - mapped_target).abs()),
                ],
                ["PBR", "Student", "Teacher", "Student error", "PBR error"],
            )
        )
    comparison = Image.new("RGB", (rows[0].width, sum(row.height for row in rows)), (16, 18, 22))
    top = 0
    for row in rows:
        comparison.paste(row, (0, top))
        top += row.height
    comparison.save(output / "comparison.png")

    frames = []
    elevation = math.radians(45.0)
    for frame_index in range(sweep_frames):
        angle = TAU * frame_index / sweep_frames
        light = lights.new_tensor(
            (math.cos(angle) * math.cos(elevation), math.sin(angle) * math.cos(elevation), math.sin(elevation))
        )
        view_angle = angle * 0.35 + 0.7
        view = views.new_tensor(
            (
                math.cos(view_angle) * math.cos(elevation),
                math.sin(view_angle) * math.cos(elevation),
                math.sin(elevation),
            )
        )
        baseline, prediction, target = render_tile(model, light, view, size)
        frames.append(
            labeled_strip(
                [image_from_tensor(baseline), image_from_tensor(prediction), image_from_tensor(target)],
                ["PBR", "Student", "Teacher"],
            )
        )
    frames[0].save(output / "angular_sweep.gif", save_all=True, append_images=frames[1:], duration=110, loop=0)


@torch.no_grad()
def final_metrics(
    model: TinyNeuralMaterial,
    lights: torch.Tensor,
    views: torch.Tensor,
    held_pairs: torch.Tensor,
    samples_per_pair: int,
) -> dict[str, float]:
    device = lights.device
    pair_ids = held_pairs.repeat_interleave(samples_per_pair, dim=0)
    generator = torch.Generator(device=device).manual_seed(20260814)
    uv = torch.rand((len(pair_ids), 2), generator=generator, device=device)
    wi, wo = lights[pair_ids[:, 0]], views[pair_ids[:, 1]]
    normal = material_fields(uv)[1]
    target = teacher(uv, wi, wo)
    baseline = pbr_baseline(uv, wi, wo)
    prediction = torch.expm1(model(uv, wi, wo, normal)).clamp(0.0, 32.0)
    target_log = torch.log1p(target)
    baseline_rmse = torch.mean((torch.log1p(baseline) - target_log).square()).sqrt()
    student_rmse = torch.mean((torch.log1p(prediction) - target_log).square()).sqrt()
    target_mapped = tone_map(target)
    baseline_mse = torch.mean((tone_map(baseline) - target_mapped).square()).clamp_min(1e-12)
    student_mse = torch.mean((tone_map(prediction) - target_mapped).square()).clamp_min(1e-12)
    return {
        "pbr_log_rmse": baseline_rmse.item(),
        "student_log_rmse": student_rmse.item(),
        "student_to_pbr_rmse_ratio": (student_rmse / baseline_rmse).item(),
        "pbr_tonemapped_psnr_db": (-10.0 * torch.log10(baseline_mse)).item(),
        "student_tonemapped_psnr_db": (-10.0 * torch.log10(student_mse)).item(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the R1 tiny neural material experiment.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--steps", type=int, default=1800)
    parser.add_argument("--batch-size", type=int, default=32768)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--latent-resolution", type=int, default=64)
    parser.add_argument("--latent-channels", type=int, default=8)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--validation-points", type=int, default=65536)
    parser.add_argument("--samples-per-pair", type=int, default=256)
    parser.add_argument("--evidence-size", type=int, default=192)
    parser.add_argument("--sweep-frames", type=int, default=24)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.smoke:
        args.steps = 4
        args.batch_size = 1024
        args.validation_points = 2048
        args.samples_per_pair = 8
        args.evidence_size = 48
        args.sweep_frames = 4
        args.output = args.output.parent / "smoke"
    if min(args.steps, args.batch_size, args.latent_resolution, args.latent_channels, args.width) <= 0:
        raise ValueError("Training dimensions and steps must be positive")

    random.seed(20260814)
    torch.manual_seed(20260814)
    if not torch.cuda.is_available():
        raise RuntimeError("R1 requires a CUDA GPU")
    device = torch.device("cuda")
    torch.cuda.manual_seed_all(20260814)
    torch.backends.cudnn.benchmark = True
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    lights = directions(12, (25, 45, 65), device)
    views = directions(8, (25, 45, 65), device)
    train_pairs, held_pairs = split_direction_pairs(len(lights), len(views), device)
    model = TinyNeuralMaterial(args.latent_resolution, args.latent_channels, args.width).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-6)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.steps, eta_min=args.learning_rate * 0.05)
    scaler = torch.amp.GradScaler("cuda")

    generator = torch.Generator(device=device).manual_seed(20260815)
    held_choices = torch.randint(len(held_pairs), (args.validation_points,), generator=generator, device=device)
    validation_pairs = held_pairs[held_choices]
    validation_uv = torch.rand((args.validation_points, 2), generator=generator, device=device)
    validation_wi = lights[validation_pairs[:, 0]]
    validation_wo = views[validation_pairs[:, 1]]
    with torch.no_grad():
        validation_normal = material_fields(validation_uv)[1]
        validation_target = torch.log1p(teacher(validation_uv, validation_wi, validation_wo))

    best_rmse = math.inf
    best_state = None
    history = []
    validate_every = max(1, args.steps // 18)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    for step in range(1, args.steps + 1):
        model.train()
        choices = torch.randint(len(train_pairs), (args.batch_size,), device=device)
        pairs = train_pairs[choices]
        uv = torch.rand((args.batch_size, 2), device=device)
        wi, wo = lights[pairs[:, 0]], views[pairs[:, 1]]
        with torch.no_grad():
            normal = material_fields(uv)[1]
            target_log = torch.log1p(teacher(uv, wi, wo))
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=torch.float16):
            prediction_log = model(uv, wi, wo, normal)
            loss = F.smooth_l1_loss(prediction_log, target_log)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()

        if step == 1 or step % validate_every == 0 or step == args.steps:
            rmse = validation_rmse(
                model,
                validation_uv,
                validation_wi,
                validation_wo,
                validation_normal,
                validation_target,
            )
            history.append({"step": step, "train_loss": loss.item(), "heldout_log_rmse": rmse})
            print(f"step={step:4d}/{args.steps} loss={loss.item():.6f} heldout_log_rmse={rmse:.6f}", flush=True)
            if math.isfinite(rmse) and rmse < best_rmse:
                best_rmse = rmse
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}

    training_seconds = time.perf_counter() - started
    if best_state is None:
        raise RuntimeError("Training produced no finite checkpoint")
    model.load_state_dict(best_state)
    model.eval()

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    fp16_bytes = parameter_count * 2
    input_width = args.latent_channels + 16
    macs_per_query = input_width * args.width + args.width * args.width + args.width * 3 + 8
    metrics = final_metrics(model, lights, views, held_pairs, args.samples_per_pair)
    metrics.update(
        {
            "best_validation_log_rmse": best_rmse,
            "parameter_count": parameter_count,
            "fp16_bytes": fp16_bytes,
            "fp16_mib": fp16_bytes / 1048576.0,
            "linear_and_latent_fetch_macs_per_query": macs_per_query,
            "training_seconds": training_seconds,
            "peak_cuda_memory_mib": torch.cuda.max_memory_allocated() / 1048576.0,
            "train_direction_pairs": len(train_pairs),
            "heldout_direction_pairs": len(held_pairs),
        }
    )
    metrics["numeric_gate_pass"] = bool(
        metrics["student_to_pbr_rmse_ratio"] <= 0.70 and metrics["fp16_mib"] <= 1.0
    )
    metrics["visual_gate"] = "pending human review of comparison.png and angular_sweep.gif"

    torch.save(
        {
            "model": best_state,
            "latent_resolution": args.latent_resolution,
            "latent_channels": args.latent_channels,
            "width": args.width,
            "metrics": metrics,
        },
        output / "best.pt",
    )
    save_evidence(model, lights, views, held_pairs, output, args.evidence_size, args.sweep_frames)
    (output / "metrics.json").write_text(
        json.dumps({"arguments": vars(args), "history": history, "metrics": metrics}, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
