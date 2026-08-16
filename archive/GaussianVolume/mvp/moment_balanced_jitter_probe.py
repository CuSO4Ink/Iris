"""Break grid phase while preserving each local mixture's first two moments."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np


GAUSSIAN_VOLUME = (2.0 * math.pi) ** 1.5


def jitter_mixture(
    centers: np.ndarray,
    covariance: np.ndarray,
    extinction: np.ndarray,
    pitch_m: float,
    group_width: int,
    amplitude_fraction: float,
    seed: int,
    preserve_covariance: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    masses = extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariance))
    cells = np.floor((centers - centers.min(axis=0)) / pitch_m + 1.0e-5).astype(np.int64)
    group = cells // group_width
    _, inverse = np.unique(group, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    starts = np.r_[0, np.flatnonzero(np.diff(inverse[order])) + 1]
    stops = np.r_[starts[1:], len(order)]

    rng = np.random.default_rng(seed)
    displacement = rng.uniform(-1.0, 1.0, centers.shape) * (
        pitch_m * amplitude_fraction
    )
    output_covariance = covariance.copy()

    for start, stop in zip(starts, stops):
        indices = order[start:stop]
        weights = masses[indices]
        weight_sum = weights.sum()
        if len(indices) < 2 or weight_sum <= 0.0:
            displacement[indices] = 0.0
            continue
        local = displacement[indices]
        local -= np.average(local, axis=0, weights=weights)
        maximum = np.max(np.abs(local))
        if maximum > pitch_m * amplitude_fraction:
            local *= pitch_m * amplitude_fraction / maximum

        mean_covariance = np.average(covariance[indices], axis=0, weights=weights)
        original_offset = centers[indices] - np.average(
            centers[indices], axis=0, weights=weights
        )

        def moment_delta(candidate: np.ndarray) -> np.ndarray:
            moved_offset = original_offset + candidate
            return np.einsum(
                "n,nij->ij",
                weights,
                moved_offset[:, :, None] * moved_offset[:, None, :]
                - original_offset[:, :, None] * original_offset[:, None, :],
            ) / weight_sum

        second = moment_delta(local)
        allowed = 0.8 * np.linalg.eigvalsh(mean_covariance).min()
        largest = max(np.linalg.eigvalsh(second).max(), 0.0)
        if largest > allowed > 0.0:
            local *= allowed / largest
            second = moment_delta(local)

        displacement[indices] = local
        candidate = covariance[indices] - second
        values, vectors = np.linalg.eigh(candidate)
        floor = (0.04 * pitch_m) ** 2
        if not preserve_covariance:
            output_covariance[indices] = (
                vectors * np.maximum(values, floor)[:, None, :]
            ) @ np.transpose(vectors, (0, 2, 1))

    output_centers = centers + displacement
    if preserve_covariance:
        return output_centers, covariance.copy(), extinction.copy()
    output_extinction = extinction * np.sqrt(
        np.linalg.det(covariance) / np.linalg.det(output_covariance)
    )
    return output_centers, output_covariance, output_extinction


def mixture_moments(
    centers: np.ndarray, covariance: np.ndarray, extinction: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    weights = extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariance))
    mean = np.average(centers, axis=0, weights=weights)
    offset = centers - mean
    second = np.average(
        covariance + offset[:, :, None] * offset[:, None, :],
        axis=0,
        weights=weights,
    )
    return mean, second


def self_check() -> None:
    centers = np.stack(
        np.meshgrid(*(np.arange(4.0),) * 3, indexing="ij"), axis=-1
    ).reshape(-1, 3)
    covariance = np.repeat((np.eye(3) * 0.2)[None], len(centers), axis=0)
    extinction = np.ones(len(centers))
    before = mixture_moments(centers, covariance, extinction)
    moved = jitter_mixture(centers, covariance, extinction, 1.0, 4, 0.5, 7)
    after = mixture_moments(*moved)
    np.testing.assert_allclose(after[0], before[0], atol=1.0e-12)
    np.testing.assert_allclose(after[1], before[1], atol=1.0e-12)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pitch-m", type=float, default=0.0653061224489796)
    parser.add_argument("--group-width", type=int, default=4)
    parser.add_argument("--amplitude-fraction", type=float)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--preserve-covariance", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("moment_balanced_jitter_probe self-check passed")
        return
    if args.input is None or args.output is None or args.amplitude_fraction is None:
        parser.error("--input, --output and --amplitude-fraction are required")

    data = np.load(args.input)
    result = jitter_mixture(
        np.asarray(data["center_m"], dtype=np.float64),
        np.asarray(data["covariance_m2"], dtype=np.float64),
        np.asarray(data["sigma_t_per_m"], dtype=np.float64),
        args.pitch_m,
        args.group_width,
        args.amplitude_fraction,
        args.seed,
        args.preserve_covariance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        center_m=result[0].astype(np.float32),
        covariance_m2=result[1].astype(np.float32),
        sigma_t_per_m=result[2].astype(np.float32),
    )


if __name__ == "__main__":
    main()
