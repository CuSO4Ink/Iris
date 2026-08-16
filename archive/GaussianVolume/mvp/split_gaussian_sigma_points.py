"""Split each Gaussian into a randomly oriented, moment-matched 8-point mixture."""

from __future__ import annotations

import argparse
import json
import math
from itertools import product
from pathlib import Path

import numpy as np


CUBE = np.asarray(list(product((-1.0, 1.0), repeat=3)), np.float64)


def random_rotations(count: int, seed: int) -> np.ndarray:
    u1, u2, u3 = np.random.default_rng(seed).random((3, count))
    q = np.stack(
        (
            np.sqrt(1.0 - u1) * np.sin(2.0 * math.pi * u2),
            np.sqrt(1.0 - u1) * np.cos(2.0 * math.pi * u2),
            np.sqrt(u1) * np.sin(2.0 * math.pi * u3),
            np.sqrt(u1) * np.cos(2.0 * math.pi * u3),
        ),
        axis=1,
    )
    x, y, z, w = q.T
    return np.stack(
        (
            1 - 2 * (y * y + z * z),
            2 * (x * y - z * w),
            2 * (x * z + y * w),
            2 * (x * y + z * w),
            1 - 2 * (x * x + z * z),
            2 * (y * z - x * w),
            2 * (x * z - y * w),
            2 * (y * z + x * w),
            1 - 2 * (x * x + y * y),
        ),
        axis=1,
    ).reshape(-1, 3, 3)


def sigma_points(count: int, seed: int, pattern: str) -> np.ndarray:
    if pattern == "cube":
        return np.einsum("nij,kj->nki", random_rotations(count, seed), CUBE)

    points = np.random.default_rng(seed).standard_normal((count, len(CUBE), 3))
    points -= points.mean(axis=1, keepdims=True)
    covariance = np.einsum("nki,nkj->nij", points, points) / len(CUBE)
    values, vectors = np.linalg.eigh(covariance)
    inverse_sqrt = (
        vectors * (1.0 / np.sqrt(values))[:, None, :]
    ) @ np.transpose(vectors, (0, 2, 1))
    return np.einsum("nij,nkj->nki", inverse_sqrt, points)


def split(
    input_npz: Path,
    output_npz: Path,
    beta: float,
    seed: int,
    isotropy: float,
    point_pattern: str,
) -> dict:
    source = np.load(input_npz)
    centers = source["center_m"].astype(np.float64)
    covariances = source["covariance_m2"].astype(np.float64)
    extinction = source["sigma_t_per_m"].astype(np.float64)
    values, vectors = np.linalg.eigh(covariances)
    if np.any(values <= 0.0):
        raise ValueError("input covariance must be positive definite")

    child_values = beta * (
        (1.0 - isotropy) * values
        + isotropy * values[:, :1] * np.ones((1, 3))
    )
    child_covariance = (vectors * child_values[:, None, :]) @ np.transpose(
        vectors, (0, 2, 1)
    )
    residual_sqrt = (
        vectors * np.sqrt(values - child_values)[:, None, :]
    ) @ np.transpose(vectors, (0, 2, 1))
    points = sigma_points(len(centers), seed, point_pattern)
    offsets = np.einsum("nij,nkj->nki", residual_sqrt, points)
    child_centers = (centers[:, None, :] + offsets).reshape(-1, 3)
    child_covariances = np.repeat(
        child_covariance[:, None, :, :], len(CUBE), axis=1
    ).reshape(-1, 3, 3)
    child_extinction = np.repeat(
        extinction
        * np.sqrt(np.prod(values, axis=1))
        / (len(CUBE) * np.sqrt(np.prod(child_values, axis=1))),
        len(CUBE),
    )

    reconstructed_center = child_centers.reshape(-1, len(CUBE), 3).mean(axis=1)
    reconstructed_covariance = child_covariance + np.einsum(
        "nki,nkj->nij", offsets, offsets
    ) / len(CUBE)
    center_error = np.linalg.norm(reconstructed_center - centers, axis=1)
    covariance_error = np.linalg.norm(
        reconstructed_covariance - covariances, axis=(1, 2)
    ) / np.maximum(np.linalg.norm(covariances, axis=(1, 2)), 1e-20)
    parent_mass = extinction * np.sqrt(np.prod(values, axis=1))
    child_mass = (
        len(CUBE)
        * child_extinction.reshape(-1, len(CUBE))[:, 0]
        * np.sqrt(np.prod(child_values, axis=1))
    )
    mass_error = np.max(
        np.abs(child_mass - parent_mass) / np.maximum(parent_mass, 1e-30)
    )
    if center_error.max() > 1e-10 or covariance_error.max() > 1e-7 or mass_error > 1e-12:
        raise RuntimeError(
            "sigma-point split did not preserve parent moments: "
            f"center={center_error.max():.3g}, covariance={covariance_error.max():.3g}, "
            f"mass={mass_error:.3g}"
        )

    output_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_npz,
        center_m=child_centers.astype(np.float32),
        covariance_m2=child_covariances.astype(np.float32),
        sigma_t_per_m=child_extinction.astype(np.float32),
    )
    report = {
        "source": str(input_npz),
        "parent_count": len(centers),
        "child_count": len(child_centers),
        "children_per_parent": len(CUBE),
        "child_covariance_fraction": beta,
        "child_isotropy": isotropy,
        "point_pattern": point_pattern,
        "seed": seed,
        "center_error_m_max": float(center_error.max()),
        "covariance_relative_error_max": float(covariance_error.max()),
        "mass_relative_error_max": float(mass_error),
    }
    output_npz.with_name("split_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-npz", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    parser.add_argument("--child-covariance-fraction", type=float, default=0.5)
    parser.add_argument("--child-isotropy", type=float, default=0.0)
    parser.add_argument("--isotropic-children", action="store_true")
    parser.add_argument(
        "--point-pattern",
        choices=("cube", "normal-whitened"),
        default="cube",
    )
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()
    if not 0.0 < args.child_covariance_fraction < 1.0:
        parser.error("child covariance fraction must be between zero and one")
    isotropy = 1.0 if args.isotropic_children else args.child_isotropy
    if not 0.0 <= isotropy <= 1.0:
        parser.error("child isotropy must be between zero and one")
    print(
        json.dumps(
            split(
                args.input_npz,
                args.output_npz,
                args.child_covariance_fraction,
                args.seed,
                isotropy,
                args.point_pattern,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
