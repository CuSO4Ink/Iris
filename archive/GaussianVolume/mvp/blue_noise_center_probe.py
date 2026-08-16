"""Break lattice phase while preventing random center clumps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from run_degrid_overnight import lattice_order


def relax_offsets(
    centers: np.ndarray,
    pitch_m: float,
    amplitude: float,
    minimum_distance: float,
    iterations: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    limit = pitch_m * amplitude
    moved = centers + rng.uniform(-limit, limit, centers.shape)
    target = pitch_m * minimum_distance

    for _ in range(iterations):
        distances, neighbors = cKDTree(moved).query(moved, k=7, workers=-1)
        delta = moved[:, None] - moved[neighbors[:, 1:]]
        distance = distances[:, 1:, None]
        overlap = np.maximum(target - distance, 0.0) / target
        force = np.sum(delta / np.maximum(distance, 1.0e-12) * overlap, axis=1)
        moved += force * (0.2 * pitch_m)
        moved = centers + np.clip(moved - centers, -limit, limit)

    return moved


def self_check() -> None:
    centers = np.stack(
        np.meshgrid(*(np.arange(5.0),) * 3, indexing="ij"), axis=-1
    ).reshape(-1, 3)
    moved = relax_offsets(centers, 1.0, 0.25, 0.7, 3, 7)
    assert np.max(np.abs(moved - centers)) <= 0.25 + 1.0e-12
    assert lattice_order(moved, 1.0) < lattice_order(centers, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--pitch-m", type=float, default=0.0653061224489796)
    parser.add_argument("--amplitude", type=float, required=False)
    parser.add_argument("--minimum-distance", type=float, default=0.7)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    if args.self_check:
        self_check()
        print("blue_noise_center_probe self-check passed")
        return
    if args.input is None or args.output is None or args.amplitude is None:
        parser.error("--input, --output and --amplitude are required")
    if not 0.0 < args.amplitude <= 0.5:
        parser.error("--amplitude must be in (0, 0.5]")
    if not 0.0 < args.minimum_distance <= 1.0 or args.iterations < 0:
        parser.error("--minimum-distance must be in (0, 1] and iterations non-negative")

    data = np.load(args.input)
    centers = np.asarray(data["center_m"], dtype=np.float64)
    moved = relax_offsets(
        centers,
        args.pitch_m,
        args.amplitude,
        args.minimum_distance,
        args.iterations,
        args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        center_m=moved.astype(np.float32),
        covariance_m2=data["covariance_m2"],
        sigma_t_per_m=data["sigma_t_per_m"],
    )
    if args.report:
        shift_cm = np.linalg.norm(moved - centers, axis=1) * 100.0
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "count": len(moved),
                    "amplitude": args.amplitude,
                    "minimum_distance": args.minimum_distance,
                    "iterations": args.iterations,
                    "lattice_order": lattice_order(moved, args.pitch_m),
                    "center_shift_cm_p50_p90_p99": np.percentile(
                        shift_cm, (50, 90, 99)
                    ).tolist(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
