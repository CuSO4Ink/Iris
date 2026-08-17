"""Create a determinant-preserving random covariance-orientation probe."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def rotate_covariances(
    covariance: np.ndarray,
    max_degrees: float,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    axes = rng.normal(size=(len(covariance), 3))
    axes /= np.linalg.norm(axes, axis=1, keepdims=True)
    angles = rng.uniform(-np.deg2rad(max_degrees), np.deg2rad(max_degrees), len(covariance))
    x, y, z = axes.T
    zeros = np.zeros(len(covariance))
    skew = np.stack(
        (
            zeros,
            -z,
            y,
            z,
            zeros,
            -x,
            -y,
            x,
            zeros,
        ),
        axis=1,
    ).reshape(-1, 3, 3)
    identity = np.eye(3)[None]
    rotation = (
        identity
        + np.sin(angles)[:, None, None] * skew
        + (1.0 - np.cos(angles))[:, None, None] * (skew @ skew)
    )
    return rotation @ covariance @ np.transpose(rotation, (0, 2, 1))


def self_check() -> None:
    covariance = np.asarray((np.diag((1.0, 2.0, 4.0)), np.diag((0.5, 1.5, 3.0))))
    rotated = rotate_covariances(covariance, 90.0, 7)
    np.testing.assert_allclose(
        np.linalg.eigvalsh(rotated),
        np.linalg.eigvalsh(covariance),
        rtol=1e-12,
        atol=1e-12,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-degrees", type=float)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("rotate_covariance_probe self-check passed")
        return
    if args.input is None or args.output is None or args.max_degrees is None:
        parser.error("--input, --output and --max-degrees are required")

    data = np.load(args.input)
    covariance = np.asarray(data["covariance_m2"], dtype=np.float64)
    rotated = rotate_covariances(covariance, args.max_degrees, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        center_m=data["center_m"],
        covariance_m2=rotated.astype(np.float32),
        sigma_t_per_m=data["sigma_t_per_m"],
    )


if __name__ == "__main__":
    main()
