"""Build one exact-budget adaptive moment partition from a dense grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from build_contracted_50k import (
    GAUSSIAN_VOLUME,
    adaptive_moment_partition,
    load_grid_blocks,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-count", type=int, default=404_524)
    parser.add_argument("--source-block-size", type=int, default=4)
    parser.add_argument("--source-sigma-ratio", type=float, default=0.38)
    parser.add_argument("--mass-exponent", type=float, default=1.0)
    parser.add_argument("--organic-jitter", type=float, default=0.0)
    args = parser.parse_args()

    centers, covariance, extinction, voxel_cm, _ = load_grid_blocks(
        args.grid, args.source_block_size, args.source_sigma_ratio, 1000.0, 0.04
    )
    result = adaptive_moment_partition(
        centers,
        covariance,
        extinction,
        args.target_count,
        args.mass_exponent,
        args.organic_jitter,
        20260729,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output / "initializer.npz",
        center_m=result[0].astype(np.float32),
        covariance_m2=result[1].astype(np.float32),
        sigma_t_per_m=result[2].astype(np.float32),
    )
    source_mass = np.sum(
        extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariance))
    )
    output_mass = np.sum(
        result[2] * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(result[1]))
    )
    (args.output / "report.json").write_text(
        json.dumps(
            {
                "source_count": len(centers),
                "target_count": len(result[0]),
                "source_voxel_cm": voxel_cm,
                "mass_relative_error": float(abs(output_mass - source_mass) / source_mass),
                "mass_exponent": args.mass_exponent,
                "organic_jitter": args.organic_jitter,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
