"""Create a smooth divergence-free center-warp probe."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np


def warp_centers(
    centers: np.ndarray,
    pitch_m: float,
    amplitude_fraction: float,
) -> np.ndarray:
    phase = centers / pitch_m
    amplitude = pitch_m * amplitude_fraction
    displacement = np.empty_like(centers, dtype=np.float64)
    displacement[:, 0] = amplitude * np.sin(
        2.0 * math.pi * phase[:, 1] / 8.0 + 0.7
    ) * np.sin(2.0 * math.pi * phase[:, 2] / 11.0 + 1.9)
    displacement[:, 1] = amplitude * np.sin(
        2.0 * math.pi * phase[:, 2] / 11.0 + 2.3
    ) * np.sin(2.0 * math.pi * phase[:, 0] / 13.0 + 0.4)
    displacement[:, 2] = amplitude * np.sin(
        2.0 * math.pi * phase[:, 0] / 13.0 + 1.1
    ) * np.sin(2.0 * math.pi * phase[:, 1] / 8.0 + 2.7)
    displacement -= displacement.mean(axis=0, keepdims=True)
    return centers + displacement


def self_check() -> None:
    centers = np.stack(
        np.meshgrid(*(np.arange(8.0),) * 3, indexing="ij"), axis=-1
    ).reshape(-1, 3)
    warped = warp_centers(centers, 1.0, 0.25)
    np.testing.assert_allclose(
        (warped - centers).mean(axis=0), 0.0, atol=1e-15
    )
    assert np.linalg.norm(warped - centers, axis=1).max() < math.sqrt(3.0) * 0.26


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pitch-m", type=float, default=0.0653061224489796)
    parser.add_argument("--amplitude-fraction", type=float)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("warp_centers_probe self-check passed")
        return
    if args.input is None or args.output is None or args.amplitude_fraction is None:
        parser.error("--input, --output and --amplitude-fraction are required")

    data = np.load(args.input)
    centers = warp_centers(
        np.asarray(data["center_m"], dtype=np.float64),
        args.pitch_m,
        args.amplitude_fraction,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        center_m=centers.astype(np.float32),
        covariance_m2=data["covariance_m2"],
        sigma_t_per_m=data["sigma_t_per_m"],
    )


if __name__ == "__main__":
    main()
