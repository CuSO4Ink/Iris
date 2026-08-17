from __future__ import annotations

import argparse
from pathlib import Path

import torch
from PIL import Image, ImageFilter, ImageOps

from train import image_tensor, save_tensor


def make_teacher(
    source_path: Path,
    reference_path: Path,
    output_path: Path,
    strength: float,
    radius: float,
    base_strength: float,
    focus: tuple[float, float, float, float] | None,
) -> None:
    with Image.open(source_path) as source_image, Image.open(reference_path) as reference_image:
        source_image = source_image.convert("RGB")
        reference_image = ImageOps.fit(reference_image.convert("RGB"), source_image.size, Image.Resampling.LANCZOS)
        source = image_tensor(source_image)
        source_low = image_tensor(source_image.filter(ImageFilter.GaussianBlur(radius)))
        reference_low = image_tensor(reference_image.filter(ImageFilter.GaussianBlur(radius)))

    # Transfer only broad lighting/color; retaining the source high frequencies locks geometry and cloud edges.
    weight: float | torch.Tensor = strength
    if focus:
        cx, cy, rx, ry = focus
        y = torch.linspace(0.0, 1.0, source.shape[1])[:, None]
        x = torch.linspace(0.0, 1.0, source.shape[2])[None, :]
        # ponytail: one soft emitter is enough for this fixed scene; add masks only when another emitter exists.
        mask = torch.exp(-2.0 * (((x - cx) / rx).square() + ((y - cy) / ry).square()))[None]
        weight = base_strength + (strength - base_strength) * mask
    target = torch.clamp(source + weight * (reference_low - source_low).clamp(-0.35, 0.35), 0.0, 1.0)
    save_tensor(output_path, target)
    assert target.shape == source.shape
    print(
        f"teacher={output_path.resolve()}, size={source.shape[2]}x{source.shape[1]}, "
        f"strength={strength}, base_strength={base_strength}, radius={radius}, focus={focus}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock an ImageGen lookdev reference to the source frame structure")
    parser.add_argument("source", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--strength", type=float, default=0.6)
    parser.add_argument("--base-strength", type=float, default=0.6)
    parser.add_argument("--radius", type=float, default=72.0)
    parser.add_argument("--focus", type=float, nargs=4, metavar=("CX", "CY", "RX", "RY"))
    args = parser.parse_args()
    if not 0.0 <= args.base_strength <= args.strength <= 1.0 or args.radius <= 0.0:
        parser.error("require 0 <= base-strength <= strength <= 1 and a positive radius")
    if args.focus and (not all(0.0 <= value <= 1.0 for value in args.focus[:2]) or not all(value > 0.0 for value in args.focus[2:])):
        parser.error("focus center must be normalized to [0, 1] and radii must be positive")
    make_teacher(
        args.source,
        args.reference,
        args.output,
        args.strength,
        args.radius,
        args.base_strength,
        tuple(args.focus) if args.focus else None,
    )


if __name__ == "__main__":
    main()
