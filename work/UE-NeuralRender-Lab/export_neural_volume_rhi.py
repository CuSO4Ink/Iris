from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from train_neural_volume import DEFAULT_OUTPUT, PROXY_HALF_EXTENT, PROXY_MAX_CHORD, NeuralVolumeProxy, normalize


ORDER = (
    ("planes", False),
    ("layers.0.weight", True),
    ("layers.0.bias", False),
    ("layers.2.weight", True),
    ("layers.2.bias", False),
    ("layers.4.weight", True),
    ("layers.4.bias", False),
    ("layers.6.weight", True),
    ("layers.6.bias", False),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the frozen world-box proxy for the UE RDG shader.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_OUTPUT / "best.pt")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "rhi")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = torch.load(args.checkpoint.resolve(), map_location="cpu", weights_only=False)
    config = checkpoint["arguments"]
    resolution = int(config["triplane_resolution"])
    channels = int(config["triplane_channels"])
    width = int(config["width"])
    if (resolution, channels, width) != (32, 8, 64):
        raise ValueError("R4b v1 requires the frozen 32x32x8 / width-64 architecture")

    model = NeuralVolumeProxy(resolution, channels, width).eval()
    model.load_state_dict(checkpoint["model"])
    state = model.state_dict()
    chunks: list[torch.Tensor] = []
    layout: dict[str, dict[str, object]] = {}
    half_offset = 0
    for name, transpose in ORDER:
        tensor = state[name].T if transpose else state[name]
        packed = tensor.contiguous().half().reshape(-1)
        chunks.append(packed)
        layout[name] = {
            "half_offset": half_offset,
            "half_count": packed.numel(),
            "runtime_shape": list(tensor.shape),
            "transposed": transpose,
        }
        half_offset += packed.numel()

    # ponytail: v1 deliberately has no extensible binary header; add one only when a second architecture ships.
    payload = torch.cat(chunks).contiguous()
    payload_bytes = payload.numpy().tobytes()
    if len(payload_bytes) != 68_744:
        raise AssertionError(f"Unexpected payload size: {len(payload_bytes)}")

    reconstructed: dict[str, torch.Tensor] = {}
    decoded = torch.frombuffer(bytearray(payload_bytes), dtype=torch.float16)
    for name, transpose in ORDER:
        entry = layout[name]
        start = int(entry["half_offset"])
        count = int(entry["half_count"])
        runtime_shape = tuple(int(value) for value in entry["runtime_shape"])
        tensor = decoded[start : start + count].reshape(runtime_shape).float()
        reconstructed[name] = tensor.T.contiguous() if transpose else tensor

    quantized = NeuralVolumeProxy(resolution, channels, width).eval()
    quantized.load_state_dict(reconstructed)
    generator = torch.Generator().manual_seed(20260814)
    sample_count = 4096
    entry = (torch.rand((sample_count, 3), generator=generator) * 2.0 - 1.0) * PROXY_HALF_EXTENT
    face_axis = torch.randint(0, 3, (sample_count,), generator=generator)
    face_sign = torch.where(torch.rand(sample_count, generator=generator) < 0.5, -1.0, 1.0)
    entry[torch.arange(sample_count), face_axis] = face_sign * PROXY_HALF_EXTENT
    view = normalize(torch.randn((sample_count, 3), generator=generator))
    sun = normalize(torch.randn((sample_count, 3), generator=generator))
    thickness = torch.rand(sample_count, generator=generator) * PROXY_MAX_CHORD
    with torch.no_grad():
        reference = model(entry, view, sun, thickness)
        candidate = quantized(entry, view, sun, thickness)
    difference = candidate - reference

    args.output.mkdir(parents=True, exist_ok=True)
    binary_path = args.output / "NRL_R4c_Box.fp16.bin"
    binary_path.write_bytes(payload_bytes)
    metadata = {
        "format": "nrl-r4c-box-fp16-v1",
        "checkpoint": str(args.checkpoint.resolve()),
        "resolution": resolution,
        "channels": channels,
        "width": width,
        "parameter_count": half_offset,
        "bytes": len(payload_bytes),
        "sha256": hashlib.sha256(payload_bytes).hexdigest().upper(),
        "quantized_output_rmse": difference.square().mean().sqrt().item(),
        "quantized_output_max_abs": difference.abs().max().item(),
        "layout": layout,
    }
    (args.output / "NRL_R4c_Box.fp16.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
