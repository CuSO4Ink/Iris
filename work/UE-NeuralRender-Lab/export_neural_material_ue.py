from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from PIL import Image

from train_neural_material import (
    ROOT,
    TAU,
    TinyNeuralMaterial,
    directions,
    final_metrics,
    material_fields,
    split_direction_pairs,
)


DEFAULT_RUN = ROOT / "tmp" / "UE-NeuralRender-Lab" / "neural-material" / "r1"
DEFAULT_OUTPUT = ROOT / "tmp" / "UE-NeuralRender-Lab" / "neural-material" / "r2-export"


def rgba_image(values: torch.Tensor, path: Path) -> None:
    Image.fromarray(values.clamp(0, 255).byte().cpu().numpy(), "RGBA").save(path)


def hlsl_values(values: torch.Tensor) -> str:
    return ",".join(f"{value:.9g}" for value in values.flatten().tolist())


def hlsl_array(name: str, values: torch.Tensor) -> str:
    return f"static const float {name}[{values.numel()}] = {{{hlsl_values(values)}}};"


def hlsl_vector(values: torch.Tensor) -> str:
    return f"float4({hlsl_values(values)})"


def quantize_latent(latent: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    minimum = latent.amin(dim=(1, 2))
    scale = (latent.amax(dim=(1, 2)) - minimum).clamp_min(1e-8)
    encoded = ((latent - minimum[:, None, None]) / scale[:, None, None] * 255.0).round().byte()
    decoded = encoded.float() / 255.0 * scale[:, None, None] + minimum[:, None, None]
    return encoded, decoded, torch.stack((minimum, scale))


def write_textures(model: TinyNeuralMaterial, output: Path, field_size: int) -> dict[str, list[float]]:
    encoded, decoded, quantization = quantize_latent(model.latent.detach().cpu()[0])
    for index, name in ((0, "T_NRL_R2_Latent0.png"), (4, "T_NRL_R2_Latent1.png")):
        rgba_image(encoded[index : index + 4].permute(1, 2, 0), output / name)

    coordinates = (torch.arange(field_size, dtype=torch.float32) + 0.5) / field_size
    y, x = torch.meshgrid(coordinates, coordinates, indexing="ij")
    uv = torch.stack((x, y), dim=-1).reshape(-1, 2)
    base, normal, roughness, wet, dust, pores, orientation = material_fields(uv)
    normal_roughness = torch.cat(((normal * 0.5 + 0.5), roughness[:, None]), dim=-1)
    base_rgba = torch.cat((base, torch.ones_like(roughness[:, None])), dim=-1)
    layers = torch.stack((wet, dust, pores, torch.remainder(orientation, TAU) / TAU), dim=-1)
    rgba_image((normal_roughness.reshape(field_size, field_size, 4) * 255.0).round(), output / "T_NRL_R2_NormalRoughness.png")
    rgba_image((base_rgba.reshape(field_size, field_size, 4) * 255.0).round(), output / "T_NRL_R2_BaseColor.png")
    rgba_image((layers.reshape(field_size, field_size, 4) * 255.0).round(), output / "T_NRL_R2_Layers.png")
    model.latent.data.copy_(decoded.unsqueeze(0).to(model.latent.device))
    return {
        "minimum": quantization[0].tolist(),
        "scale": quantization[1].tolist(),
    }


def write_hlsl(model: TinyNeuralMaterial, quantization: dict[str, list[float]], path: Path) -> None:
    layer0, layer1, layer2 = model.layers[0], model.layers[2], model.layers[4]
    minimum = torch.tensor(quantization["minimum"])
    scale = torch.tensor(quantization["scale"])
    arrays = "\n".join(
        (
            hlsl_array("NRL_W0", layer0.weight.detach().cpu()),
            hlsl_array("NRL_B0", layer0.bias.detach().cpu()),
            hlsl_array("NRL_W1", layer1.weight.detach().cpu()),
            hlsl_array("NRL_B1", layer1.bias.detach().cpu()),
            hlsl_array("NRL_W2", layer2.weight.detach().cpu()),
            hlsl_array("NRL_B2", layer2.bias.detach().cpu()),
        )
    )
    code = f"""#pragma once

#define NRL_INPUTS 24
#define NRL_WIDTH 64

static const float3 NRL_LIGHT = normalize(float3(0.5416752, 0.4545195, 0.7071068));
static const float3 NRL_VIEW = normalize(float3(0.6942720, 0.5825634, 0.4226183));
static const float4 NRL_LATENT_MIN_0 = {hlsl_vector(minimum[:4])};
static const float4 NRL_LATENT_MIN_1 = {hlsl_vector(minimum[4:])};
static const float4 NRL_LATENT_SCALE_0 = {hlsl_vector(scale[:4])};
static const float4 NRL_LATENT_SCALE_1 = {hlsl_vector(scale[4:])};

{arrays}

float3 NRL_Fresnel(float cosine, float3 f0)
{{
    return f0 + (1.0 - f0) * pow(saturate(1.0 - cosine), 5.0);
}}

float3 NRL_GGX(float3 n, float3 wi, float3 wo, float roughness, float3 f0)
{{
    float3 h = normalize(wi + wo);
    float nl = max(dot(n, wi), 0.0001);
    float nv = max(dot(n, wo), 0.0001);
    float nh = max(dot(n, h), 0.0001);
    float vh = max(dot(wo, h), 0.0001);
    float alpha = max(roughness * roughness, 0.0025);
    float alpha2 = alpha * alpha;
    float denominator = max(pow(nh * nh * (alpha2 - 1.0) + 1.0, 2.0), 0.000001);
    float distribution = alpha2 / (3.14159265 * denominator);
    float k = pow(roughness + 1.0, 2.0) / 8.0;
    float geometry = (nl / (nl * (1.0 - k) + k)) * (nv / (nv * (1.0 - k) + k));
    return distribution * geometry * NRL_Fresnel(vh, f0) / (4.0 * nl * nv);
}}

float3 NRL_Anisotropic(float3 n, float3 wi, float3 wo, float orientation, float roughX, float roughY, float3 f0)
{{
    float3 h = normalize(wi + wo);
    float3 tangent0 = normalize(float3(1.0, 0.0, 0.0) - n * dot(float3(1.0, 0.0, 0.0), n));
    float3 bitangent0 = normalize(cross(n, tangent0));
    float sine, cosine;
    sincos(orientation, sine, cosine);
    float3 tangent = tangent0 * cosine + bitangent0 * sine;
    float3 bitangent = -tangent0 * sine + bitangent0 * cosine;
    float ht = dot(h, tangent);
    float hb = dot(h, bitangent);
    float hn = max(dot(h, n), 0.0001);
    float nl = max(dot(n, wi), 0.0001);
    float nv = max(dot(n, wo), 0.0001);
    float vh = max(dot(wo, h), 0.0001);
    float denominator = max(pow(ht * ht / (roughX * roughX) + hb * hb / (roughY * roughY) + hn * hn, 2.0), 0.000001);
    float distribution = 1.0 / (3.14159265 * roughX * roughY * denominator);
    float averageRoughness = sqrt(roughX * roughY);
    float k = pow(averageRoughness + 1.0, 2.0) / 8.0;
    float geometry = (nl / (nl * (1.0 - k) + k)) * (nv / (nv * (1.0 - k) + k));
    return distribution * geometry * NRL_Fresnel(vh, f0) / (4.0 * nl * nv);
}}

float3 NRL_PBR(float4 baseSample, float4 normalRoughness)
{{
    float3 base = baseSample.rgb;
    float3 n = normalize(normalRoughness.rgb * 2.0 - 1.0);
    float roughness = normalRoughness.a;
    float nl = saturate(dot(n, NRL_LIGHT));
    float3 direct = base / 3.14159265 + NRL_GGX(n, NRL_LIGHT, NRL_VIEW, roughness, 0.04.xxx);
    return min(2.4 * direct * nl + 0.025 * base, 32.0.xxx);
}}

float3 NRL_Teacher(float4 baseSample, float4 normalRoughness, float4 layers)
{{
    float3 base = baseSample.rgb;
    float3 n = normalize(normalRoughness.rgb * 2.0 - 1.0);
    float roughness = normalRoughness.a;
    float wet = layers.r;
    float dust = layers.g;
    float pores = layers.b;
    float orientation = layers.a * 6.28318531;
    float3 h = normalize(NRL_LIGHT + NRL_VIEW);
    float nl = saturate(dot(n, NRL_LIGHT));
    float nv = saturate(dot(n, NRL_VIEW));
    float vh = saturate(dot(NRL_VIEW, h));
    float3 diffuse = base * (1.0 - 0.58 * wet) / 3.14159265;
    float substrateRoughness = clamp(roughness + 0.12 * dust - 0.10 * wet, 0.10, 0.90);
    float3 substrate = NRL_GGX(n, NRL_LIGHT, NRL_VIEW, substrateRoughness, 0.045.xxx);
    float phase = 18.0 * (1.0 - vh) + 5.0 * wet + 2.0 * pores;
    float3 filmTint = 0.72 + 0.28 * (0.5 + 0.5 * sin(phase + float3(0.0, 2.1, 4.2)));
    float coatRoughness = clamp(0.045 + 0.10 * (1.0 - wet) + 0.03 * pores, 0.04, 0.18);
    float3 clearcoat = NRL_GGX(n, NRL_LIGHT, NRL_VIEW, coatRoughness, 0.055.xxx);
    float roughX = clamp(0.055 + 0.055 * pores, 0.04, 0.13);
    float roughY = clamp(0.22 + 0.12 * dust, 0.18, 0.38);
    float3 directional = NRL_Anisotropic(n, NRL_LIGHT, NRL_VIEW, orientation, roughX, roughY, 0.035.xxx);
    float sparkle = 1.0 / (1.0 + exp(-7.0 * (pores - 0.60)));
    float3 sheen = dust * sqrt(base) * pow(1.0 - nv, 2.0) * 0.20;
    float3 direct = diffuse + substrate + wet * clearcoat * filmTint * 0.72;
    direct += (0.18 + 0.52 * wet) * sparkle * directional;
    float3 ambient = base * (0.018 + 0.035 * dust) + sheen;
    return min(2.4 * direct * nl + ambient, 32.0.xxx);
}}

float3 NRL_Student(float4 latent0Sample, float4 latent1Sample, float4 normalRoughness)
{{
    float4 latent0 = latent0Sample * NRL_LATENT_SCALE_0 + NRL_LATENT_MIN_0;
    float4 latent1 = latent1Sample * NRL_LATENT_SCALE_1 + NRL_LATENT_MIN_1;
    float3 n = normalize(normalRoughness.rgb * 2.0 - 1.0);
    float3 h = normalize(NRL_LIGHT + NRL_VIEW);
    float input[NRL_INPUTS] = {{
        latent0.r, latent0.g, latent0.b, latent0.a, latent1.r, latent1.g, latent1.b, latent1.a,
        NRL_LIGHT.x, NRL_LIGHT.y, NRL_LIGHT.z, NRL_VIEW.x, NRL_VIEW.y, NRL_VIEW.z,
        n.x, n.y, n.z, h.x, h.y, h.z,
        dot(n, NRL_LIGHT), dot(n, NRL_VIEW), dot(n, h), dot(NRL_VIEW, h)
    }};
    float hidden0[NRL_WIDTH];
    float hidden1[NRL_WIDTH];
    float raw[3];
    [unroll] for (int i = 0; i < NRL_WIDTH; ++i)
    {{
        float value = NRL_B0[i];
        [unroll] for (int j = 0; j < NRL_INPUTS; ++j) value += NRL_W0[i * NRL_INPUTS + j] * input[j];
        hidden0[i] = max(value, 0.0);
    }}
    [unroll] for (int i = 0; i < NRL_WIDTH; ++i)
    {{
        float value = NRL_B1[i];
        [unroll] for (int j = 0; j < NRL_WIDTH; ++j) value += NRL_W1[i * NRL_WIDTH + j] * hidden0[j];
        hidden1[i] = max(value, 0.0);
    }}
    [unroll] for (int i = 0; i < 3; ++i)
    {{
        float value = NRL_B2[i];
        [unroll] for (int j = 0; j < NRL_WIDTH; ++j) value += NRL_W2[i * NRL_WIDTH + j] * hidden1[j];
        raw[i] = value;
    }}
    return min(exp(float3(raw[0], raw[1], raw[2])), 32.0.xxx);
}}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the trained R1 material for the UE R2 shader probe.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_RUN / "best.pt")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--shader-output", type=Path, required=True)
    parser.add_argument("--field-size", type=int, default=256)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = torch.load(args.checkpoint.resolve(), map_location="cpu", weights_only=False)
    model = TinyNeuralMaterial(checkpoint["latent_resolution"], checkpoint["latent_channels"], checkpoint["width"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    quantization = write_textures(model, output, args.field_size)
    write_hlsl(model, quantization, args.shader_output.resolve())
    lights = directions(12, (25, 45, 65), torch.device("cpu"))
    views = directions(8, (25, 45, 65), torch.device("cpu"))
    _, held_pairs = split_direction_pairs(len(lights), len(views), torch.device("cpu"))
    quantized_metrics = final_metrics(model, lights, views, held_pairs, samples_per_pair=64)
    shader_bytes = args.shader_output.resolve().read_bytes()
    manifest = {
        "checkpoint": str(args.checkpoint.resolve()),
        "shader": str(args.shader_output.resolve()),
        "shader_sha256": hashlib.sha256(shader_bytes).hexdigest(),
        "shader_bytes": len(shader_bytes),
        "textures": sorted(path.name for path in output.glob("*.png")),
        "quantization": quantization,
        "quantized_metrics": quantized_metrics,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    assert len(manifest["textures"]) == 5 and len(quantization["minimum"]) == 8
    assert quantized_metrics["student_to_pbr_rmse_ratio"] <= 0.70
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
