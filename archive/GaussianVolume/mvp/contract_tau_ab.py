"""Local moment-contracted Gaussian A/B against same-count contribution pruning."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from evaluate_heldout import compute_metrics
from qirf_tau_ab import (
    camera_ray_basis_response,
    load_b2_block,
    load_camera_origins,
    nonnegative_refit,
)


GAUSSIAN_VOLUME = (2.0 * math.pi) ** 1.5


def contract_gaussians(
    centers: np.ndarray,
    covariances: np.ndarray,
    extinction: np.ndarray,
    count: int,
    *,
    iterations: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Weighted Lloyd clusters followed by exact mixture moment matching."""
    if not 0 < count <= len(centers):
        raise ValueError("contracted count must be in [1, input count]")
    mass = extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariances))
    seeds = [int(np.argmax(mass))]
    nearest2 = np.sum((centers - centers[seeds[0]]) ** 2, axis=1)
    while len(seeds) < count:
        index = int(np.argmax(nearest2 * mass))
        seeds.append(index)
        nearest2 = np.minimum(
            nearest2, np.sum((centers - centers[index]) ** 2, axis=1)
        )
    centroids = centers[seeds].copy()
    labels = np.zeros(len(centers), dtype=np.int64)
    for _ in range(iterations):
        distance2 = np.sum(
            (centers[:, None] - centroids[None, :]) ** 2, axis=2
        )
        updated = np.argmin(distance2, axis=1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for cluster in range(count):
            members = labels == cluster
            if np.any(members):
                centroids[cluster] = np.average(
                    centers[members], axis=0, weights=mass[members]
                )

    output_covariances = np.empty((count, 3, 3), dtype=np.float64)
    output_mass = np.empty(count, dtype=np.float64)
    for cluster in range(count):
        members = labels == cluster
        if not np.any(members):
            raise RuntimeError("weighted Lloyd produced an empty cluster")
        local_mass = mass[members]
        output_mass[cluster] = local_mass.sum()
        delta = centers[members] - centroids[cluster]
        output_covariances[cluster] = np.average(
            covariances[members]
            + np.einsum("ni,nj->nij", delta, delta),
            axis=0,
            weights=local_mass,
        )
    output_extinction = output_mass / (
        GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(output_covariances))
    )
    return centroids, output_covariances, output_extinction


def compare(
    centers: np.ndarray,
    covariances: np.ndarray,
    extinction: np.ndarray,
    camera_origins: np.ndarray,
    keep_ratios: tuple[float, ...],
) -> dict:
    train_origins, heldout_origins = camera_origins[::2], camera_origins[1::2]
    teacher_train_basis = camera_ray_basis_response(
        centers, covariances, train_origins
    )
    teacher_heldout_basis = camera_ray_basis_response(
        centers, covariances, heldout_origins
    )
    train_tau = teacher_train_basis @ extinction
    heldout_tau = teacher_heldout_basis @ extinction
    contribution = np.sum(
        (teacher_train_basis * extinction[None]) ** 2, axis=0
    )
    rows = []
    for ratio in keep_ratios:
        keep = max(1, int(math.ceil(ratio * len(centers))))
        contracted = contract_gaussians(
            centers, covariances, extinction, keep
        )
        selected = np.argsort(contribution)[-keep:]
        methods = {
            "moment_contracted": contracted[:2],
            "contribution": (centers[selected], covariances[selected]),
        }
        row = {"keep_ratio": ratio, "keep_count": keep, "methods": {}}
        for name, (candidate_centers, candidate_covariances) in methods.items():
            train_basis = camera_ray_basis_response(
                candidate_centers, candidate_covariances, train_origins
            )
            heldout_basis = camera_ray_basis_response(
                candidate_centers, candidate_covariances, heldout_origins
            )
            fitted = nonnegative_refit(train_basis, train_tau)
            metrics = compute_metrics(
                np.exp(-heldout_tau),
                heldout_basis @ fitted,
                alpha_threshold=1e-4,
            )
            row["methods"][name] = {"metrics": metrics}
        contracted_metrics = row["methods"]["moment_contracted"]["metrics"]
        baseline_metrics = row["methods"]["contribution"]["metrics"]
        row["contracted_wins_tau_mae"] = (
            contracted_metrics["tau_mae"] < baseline_metrics["tau_mae"]
        )
        row["contracted_wins_transmittance"] = (
            contracted_metrics["transmittance_psnr_foreground_db"]
            > baseline_metrics["transmittance_psnr_foreground_db"]
        )
        rows.append(row)
    return {"kernel_count": len(centers), "results": rows}


def _self_check() -> None:
    centers = np.asarray(((0.0, 0.0, 0.0), (0.1, 0.0, 0.0)))
    covariances = np.repeat((np.eye(3) * 0.05**2)[None], 2, axis=0)
    extinction = np.asarray((1.0, 2.0))
    contracted = contract_gaussians(centers, covariances, extinction, 1)
    before = np.sum(
        extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariances))
    )
    after = np.sum(
        contracted[2]
        * GAUSSIAN_VOLUME
        * np.sqrt(np.linalg.det(contracted[1]))
    )
    assert np.isclose(before, after) and contracted[2][0] > 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path)
    parser.add_argument("--transforms", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--anchor-index", type=int, default=-1)
    parser.add_argument("--keep-ratios", type=float, nargs="+", default=(0.7, 0.5, 0.3))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("contract_tau_ab self-check passed")
        return
    if args.ply is None or args.transforms is None or args.output is None:
        parser.error("--ply, --transforms and --output are required")

    centers, covariances, extinction, indices, anchor = load_b2_block(
        args.ply, args.block_size, args.anchor_index
    )
    report = compare(
        centers,
        covariances,
        extinction,
        load_camera_origins(args.transforms),
        tuple(args.keep_ratios),
    )
    report.update(
        {
            "scope": "local contracted-kernel geometry smoke; not a global 50K result",
            "source_ply": str(args.ply.resolve()),
            "anchor_global_index": anchor,
            "global_indices": indices.tolist(),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
