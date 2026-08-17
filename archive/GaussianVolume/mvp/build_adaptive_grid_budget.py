"""Redistribute a fixed Gaussian budget from smooth grid blocks to detail blocks."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from build_contracted_50k import GAUSSIAN_VOLUME, load_grid_blocks, matrix_to_quaternion


def detail_scores(
    masses: np.ndarray,
    coordinates: np.ndarray,
    block_shape: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    linear = np.ravel_multi_index(coordinates.T, block_shape)
    dense = np.zeros(block_shape, np.float64)
    dense.flat[linear] = masses
    padded = np.pad(dense, 1)
    sx, sy, sz = dense.shape
    neighbors = (
        padded[0:sx, 1 : sy + 1, 1 : sz + 1],
        padded[2 : sx + 2, 1 : sy + 1, 1 : sz + 1],
        padded[1 : sx + 1, 0:sy, 1 : sz + 1],
        padded[1 : sx + 1, 2 : sy + 2, 1 : sz + 1],
        padded[1 : sx + 1, 1 : sy + 1, 0:sz],
        padded[1 : sx + 1, 1 : sy + 1, 2 : sz + 2],
    )
    neighbor_mean = sum(neighbors) / 6.0
    gradient = np.maximum.reduce([np.abs(dense - value) for value in neighbors])
    contrast = (np.abs(dense - neighbor_mean) + 0.5 * gradient) / (
        dense + neighbor_mean + 1e-20
    )
    occupied_mass = dense.flat[linear]
    median_mass = max(float(np.median(occupied_mass)), 1e-20)
    mass_weight = np.clip(np.sqrt(occupied_mass / median_mass), 0.25, 4.0)
    return contrast.flat[linear] * mass_weight, linear


def choose_merge_targets(
    coordinates: np.ndarray,
    scores: np.ndarray,
    split_mask: np.ndarray,
    linear: np.ndarray,
    block_shape: tuple[int, int, int],
    merge_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    lookup = np.full(math.prod(block_shape), -1, np.int64)
    lookup[linear] = np.arange(len(coordinates))
    state = np.zeros(len(coordinates), np.int8)  # 0 free, 1 removed, 2 retained, 3 split
    state[split_mask] = 3
    target = np.full(len(coordinates), -1, np.int64)
    order = np.argsort(scores, kind="stable")
    removed = 0

    for radius in (1, 2, 3):
        offsets = sorted(
            (
                (x, y, z)
                for x in range(-radius, radius + 1)
                for y in range(-radius, radius + 1)
                for z in range(-radius, radius + 1)
                if (x, y, z) != (0, 0, 0)
                and max(abs(x), abs(y), abs(z)) == radius
            ),
            key=lambda value: sum(axis * axis for axis in value),
        )
        for index in order:
            if removed == merge_count:
                return state, target
            if state[index] != 0:
                continue
            coordinate = coordinates[index]
            candidates = []
            for offset in offsets:
                neighbor = coordinate + offset
                if np.any(neighbor < 0) or np.any(neighbor >= block_shape):
                    continue
                match = lookup[np.ravel_multi_index(neighbor, block_shape)]
                if match >= 0 and state[match] == 0:
                    candidates.append(match)
            if not candidates:
                continue
            match = max(candidates, key=lambda value: scores[value])
            state[index] = 1
            state[match] = 2
            target[index] = match
            removed += 1

    raise RuntimeError(f"could only merge {removed} of {merge_count} requested blocks")


def merge_selected(
    centers: np.ndarray,
    covariances: np.ndarray,
    masses: np.ndarray,
    state: np.ndarray,
    targets: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    keep = np.flatnonzero((state == 0) | (state == 2))
    removed = np.flatnonzero(state == 1)
    output_index = np.full(len(state), -1, np.int64)
    output_index[keep] = np.arange(len(keep))
    destination = output_index[targets[removed]]
    if np.any(destination < 0):
        raise RuntimeError("merge target was not retained")

    merged_mass = masses[keep].copy()
    first = merged_mass[:, None] * centers[keep]
    second = merged_mass[:, None, None] * (
        covariances[keep] + np.einsum("ni,nj->nij", centers[keep], centers[keep])
    )
    np.add.at(merged_mass, destination, masses[removed])
    np.add.at(first, destination, masses[removed, None] * centers[removed])
    np.add.at(
        second,
        destination,
        masses[removed, None, None]
        * (
            covariances[removed]
            + np.einsum("ni,nj->nij", centers[removed], centers[removed])
        ),
    )
    merged_centers = first / merged_mass[:, None]
    merged_covariances = second / merged_mass[:, None, None] - np.einsum(
        "ni,nj->nij", merged_centers, merged_centers
    )
    merged_covariances += np.eye(3)[None] * 1e-12
    return merged_centers, merged_covariances, merged_mass


def boost_anisotropy(
    covariances: np.ndarray,
    factor: float,
    max_anisotropy: float,
) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(covariances)
    log_scales = 0.5 * np.log(eigenvalues)
    mean_log_scale = log_scales.mean(axis=1, keepdims=True)
    shape = (log_scales - mean_log_scale) * factor
    shape *= np.minimum(
        1.0,
        math.log(max_anisotropy)
        / np.maximum(shape[:, 2] - shape[:, 0], 1e-12),
    )[:, None]
    scales = np.exp(mean_log_scale + shape)
    return eigenvectors @ (
        scales[:, :, None] ** 2 * np.transpose(eigenvectors, (0, 2, 1))
    )


def match_split_moments(
    parent_centers: np.ndarray,
    parent_covariances: np.ndarray,
    parent_masses: np.ndarray,
    child_centers: np.ndarray,
    child_covariances: np.ndarray,
    child_masses: np.ndarray,
    child_parent: np.ndarray,
    split: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    centers = child_centers.copy()
    covariances = child_covariances.copy()
    masses = child_masses.copy()
    max_mass_error = 0.0
    max_center_error = 0.0
    max_covariance_error = 0.0
    child_order = np.argsort(child_parent, kind="stable")
    sorted_parent = child_parent[child_order]

    for parent in split:
        start = int(np.searchsorted(sorted_parent, parent, side="left"))
        end = int(np.searchsorted(sorted_parent, parent, side="right"))
        members = child_order[start:end]
        weights = masses[members]
        child_mass = float(weights.sum())
        normalized = weights / child_mass
        child_center = normalized @ centers[members]
        offsets = centers[members] - child_center
        child_covariance = np.einsum(
            "n,nij->ij", normalized, covariances[members], optimize=True
        ) + np.einsum(
            "n,ni,nj->ij", normalized, offsets, offsets, optimize=True
        )

        parent_values, parent_vectors = np.linalg.eigh(
            parent_covariances[parent]
        )
        child_values, child_vectors = np.linalg.eigh(child_covariance)
        if np.min(parent_values) <= 0.0 or np.min(child_values) <= 0.0:
            raise RuntimeError("split moment matching requires positive covariance")
        parent_sqrt = (parent_vectors * np.sqrt(parent_values)) @ parent_vectors.T
        child_inv_sqrt = (
            child_vectors * (1.0 / np.sqrt(child_values))
        ) @ child_vectors.T
        transform = parent_sqrt @ child_inv_sqrt

        centers[members] = (
            parent_centers[parent]
            + (centers[members] - child_center) @ transform.T
        )
        covariances[members] = (
            transform[None]
            @ covariances[members]
            @ transform.T[None]
        )
        masses[members] *= parent_masses[parent] / child_mass

        check_weights = masses[members] / parent_masses[parent]
        check_center = check_weights @ centers[members]
        check_offsets = centers[members] - check_center
        check_covariance = np.einsum(
            "n,nij->ij", check_weights, covariances[members], optimize=True
        ) + np.einsum(
            "n,ni,nj->ij",
            check_weights,
            check_offsets,
            check_offsets,
            optimize=True,
        )
        max_mass_error = max(
            max_mass_error,
            abs(float(masses[members].sum()) / parent_masses[parent] - 1.0),
        )
        max_center_error = max(
            max_center_error,
            float(np.linalg.norm(check_center - parent_centers[parent])),
        )
        max_covariance_error = max(
            max_covariance_error,
            float(
                np.linalg.norm(check_covariance - parent_covariances[parent])
                / max(np.linalg.norm(parent_covariances[parent]), 1e-20)
            ),
        )

    return centers, covariances, masses, {
        "split_local_mass_relative_error_max": max_mass_error,
        "split_local_center_error_m_max": max_center_error,
        "split_local_covariance_relative_error_max": max_covariance_error,
    }


def mixture_moments(
    centers: np.ndarray,
    covariances: np.ndarray,
    masses: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    mass = float(masses.sum())
    weights = masses / mass
    center = weights @ centers
    offsets = centers - center
    covariance = np.einsum(
        "n,nij->ij", weights, covariances, optimize=True
    ) + np.einsum(
        "n,ni,nj->ij", weights, offsets, offsets, optimize=True
    )
    return mass, center, covariance


def write_outputs(
    output_npz: Path,
    output_json: Path | None,
    output_report: Path,
    centers: np.ndarray,
    covariances: np.ndarray,
    masses: np.ndarray,
    report: dict,
) -> None:
    extinction = masses / (
        GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariances))
    )
    eigenvalues = np.linalg.eigvalsh(covariances)
    if np.any(eigenvalues <= 0.0):
        raise RuntimeError("adaptive covariance is not positive definite")

    for path in (output_npz, output_report, output_json):
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_npz,
        center_m=centers.astype(np.float32),
        covariance_m2=covariances.astype(np.float32),
        sigma_t_per_m=extinction.astype(np.float32),
    )
    if output_json is not None:
        eigenvalues, eigenvectors = np.linalg.eigh(covariances)
        negative = np.linalg.det(eigenvectors) < 0.0
        eigenvectors[negative, :, 0] *= -1.0
        scales_m = np.sqrt(eigenvalues)
        quaternions = [matrix_to_quaternion(matrix) for matrix in eigenvectors]
        primitives = [
            {
                "center": (centers[index] * 100.0).tolist(),
                "scale": (scales_m[index] * 100.0).tolist(),
                "rotation": quaternions[index],
                "sigma_t": float(extinction[index] / 100.0),
                "omega": 0.0,
                "albedo": [1.0, 1.0, 1.0],
                "emission": 0.0,
            }
            for index in range(len(centers))
        ]
        payload = {
            "schema": "GaussianVolume.Primitives.v1",
            "method": "adaptive_grid_budget_surface_split_smooth_merge",
            "primitive_count": len(primitives),
            "gaussians": primitives,
        }
        output_json.write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
    output_report.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-npz", type=Path, required=True)
    parser.add_argument("--base-npz", type=Path)
    parser.add_argument("--grid", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--target-count", type=int, default=400_000)
    parser.add_argument("--split-parent-count", type=int, default=20_000)
    parser.add_argument(
        "--preserve-split-count",
        action="store_true",
        help="diagnostic: keep all split children instead of merging back to target count",
    )
    parser.add_argument("--parent-block-size", type=int, default=8)
    parser.add_argument("--child-block-size", type=int, default=4)
    parser.add_argument("--spatial-sigma-ratio", type=float, default=0.4)
    parser.add_argument("--child-jitter-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--longest-size-cm", type=float, default=1000.0)
    parser.add_argument("--density-scale", type=float, default=0.04)
    parser.add_argument("--anisotropy-boost", type=float, default=1.0)
    parser.add_argument("--max-anisotropy", type=float, default=8.0)
    args = parser.parse_args()
    if (
        args.anisotropy_boost <= 0.0
        or args.max_anisotropy < 1.0
        or args.child_jitter_ratio < 0.0
    ):
        parser.error("anisotropy controls must be positive and jitter non-negative")
    if args.preserve_split_count and args.base_npz is None:
        parser.error("--preserve-split-count requires --base-npz")

    grid_shape = tuple(np.load(args.grid, mmap_mode="r").squeeze().shape)
    parent_data = np.load(args.parent_npz)
    parent_centers = parent_data["center_m"].astype(np.float64)
    parent_covariances = parent_data["covariance_m2"].astype(np.float64)
    parent_extinction = parent_data["sigma_t_per_m"].astype(np.float64)
    parent_shape = tuple(
        np.ceil(np.asarray(grid_shape) / args.parent_block_size).astype(int)
    )
    parent_masses = (
        parent_extinction
        * GAUSSIAN_VOLUME
        * np.sqrt(np.linalg.det(parent_covariances))
    )
    parent_covariances = boost_anisotropy(
        parent_covariances, args.anisotropy_boost, args.max_anisotropy
    )
    child_centers, child_covariances, child_extinction, _, child_coordinates = (
        load_grid_blocks(
            args.grid,
            args.child_block_size,
            args.spatial_sigma_ratio,
            args.longest_size_cm,
            args.density_scale,
        )
    )
    child_parent_coordinates = child_coordinates // (
        args.parent_block_size // args.child_block_size
    )
    child_parent_linear = np.ravel_multi_index(child_parent_coordinates.T, parent_shape)
    parent_linear = np.unique(child_parent_linear)
    if len(parent_linear) != len(parent_centers):
        raise RuntimeError(
            f"parent NPZ has {len(parent_centers)} blocks but children map to "
            f"{len(parent_linear)} occupied parent blocks"
        )
    parent_coordinates = np.stack(np.unravel_index(parent_linear, parent_shape), axis=1)
    parent_lookup = np.full(math.prod(parent_shape), -1, np.int64)
    parent_lookup[parent_linear] = np.arange(len(parent_centers))
    child_parent = parent_lookup[child_parent_linear]
    if np.any(child_parent < 0):
        raise RuntimeError("child block could not be mapped to a parent")
    child_covariances = boost_anisotropy(
        child_covariances, args.anisotropy_boost, args.max_anisotropy
    )
    child_masses = (
        child_extinction
        * GAUSSIAN_VOLUME
        * np.sqrt(np.linalg.det(child_covariances))
    )

    protected_centers = np.empty((0, 3), np.float64)
    protected_covariances = np.empty((0, 3, 3), np.float64)
    protected_masses = np.empty(0, np.float64)
    if args.base_npz is not None:
        base_data = np.load(args.base_npz)
        base_centers = base_data["center_m"].astype(np.float64)
        base_covariances = base_data["covariance_m2"].astype(np.float64)
        base_extinction = base_data["sigma_t_per_m"].astype(np.float64)
        if len(base_centers) != args.target_count:
            raise ValueError("base NPZ must already have the exact target count")
        base_masses = (
            base_extinction
            * GAUSSIAN_VOLUME
            * np.sqrt(np.linalg.det(base_covariances))
        )
        rounded_parent = np.round(parent_centers, 6)
        rounded_base = np.round(base_centers, 6)
        singleton_lookup = {
            row.tobytes(): index for index, row in enumerate(rounded_parent)
        }
        if len(singleton_lookup) != len(parent_centers):
            raise RuntimeError("rounded parent centers are not unique")
        base_parent = np.fromiter(
            (
                singleton_lookup.get(row.tobytes(), -1)
                for row in rounded_base
            ),
            dtype=np.int64,
            count=len(base_centers),
        )
        eligible_base = np.flatnonzero(base_parent >= 0)
        protected_base = np.flatnonzero(base_parent < 0)
        if len(np.unique(base_parent[eligible_base])) != len(eligible_base):
            raise RuntimeError("base singleton mapping is not one-to-one")
        working_centers = base_centers[eligible_base]
        working_covariances = base_covariances[eligible_base]
        working_masses = base_masses[eligible_base]
        working_coordinates = parent_coordinates[base_parent[eligible_base]]
        working_scores, working_linear = detail_scores(
            working_masses, working_coordinates, parent_shape
        )
        parent_to_working = np.full(len(parent_centers), -1, np.int64)
        parent_to_working[base_parent[eligible_base]] = np.arange(
            len(eligible_base)
        )
        child_working = parent_to_working[child_parent]
        valid_children = child_working >= 0
        protected_centers = base_centers[protected_base]
        protected_covariances = base_covariances[protected_base]
        protected_masses = base_masses[protected_base]
        reference_centers = base_centers
        reference_covariances = base_covariances
        reference_masses = base_masses
        mode = "exact_base_preserving"
    else:
        working_centers = parent_centers
        working_covariances = parent_covariances
        working_masses = parent_masses
        working_coordinates = parent_coordinates
        working_scores, working_linear = detail_scores(
            working_masses, working_coordinates, parent_shape
        )
        child_working = child_parent
        valid_children = np.ones(len(child_parent), bool)
        eligible_base = np.arange(len(parent_centers))
        protected_base = np.empty(0, np.int64)
        reference_centers = parent_centers
        reference_covariances = parent_covariances
        reference_masses = parent_masses
        mode = "raw_parent"

    child_counts = np.bincount(
        child_working[valid_children], minlength=len(working_centers)
    )
    candidates = np.flatnonzero(child_counts > 1)
    split_count = min(args.split_parent_count, len(candidates))
    split = (
        candidates[
            np.argsort(working_scores[candidates], kind="stable")[-split_count:]
        ]
        if split_count
        else np.empty(0, np.int64)
    )
    split_mask = np.zeros(len(working_centers), bool)
    split_mask[split] = True
    if args.child_jitter_ratio > 0.0 and split_count:
        selected_children = np.zeros(len(child_working), bool)
        selected_children[valid_children] = split_mask[
            child_working[valid_children]
        ]
        child_pitch_m = (
            args.longest_size_cm
            / 100.0
            / max(grid_shape)
            * args.child_block_size
        )
        child_centers[selected_children] += np.random.default_rng(
            args.seed
        ).uniform(-1.0, 1.0, (int(selected_children.sum()), 3)) * (
            args.child_jitter_ratio * child_pitch_m
        )
    (
        child_centers,
        child_covariances,
        child_masses,
        split_moment_report,
    ) = match_split_moments(
        working_centers,
        working_covariances,
        working_masses,
        child_centers,
        child_covariances,
        child_masses,
        child_working,
        split,
    )
    extra_children = int(np.sum(child_counts[split] - 1))
    merge_count = (
        0
        if args.preserve_split_count
        else (
            extra_children
            if args.base_npz is not None
            else len(working_centers) + extra_children - args.target_count
        )
    )
    if merge_count < 0:
        raise ValueError("split budget is too small to reach the target")

    state, targets = choose_merge_targets(
        working_coordinates,
        working_scores,
        split_mask,
        working_linear,
        parent_shape,
        merge_count,
    )
    merged_centers, merged_covariances, merged_masses = merge_selected(
        working_centers,
        working_covariances,
        working_masses,
        state,
        targets,
    )
    selected_children = np.zeros(len(child_working), bool)
    selected_children[valid_children] = split_mask[
        child_working[valid_children]
    ]
    output_centers = np.concatenate(
        (
            merged_centers,
            child_centers[selected_children],
            protected_centers,
        )
    )
    output_covariances = np.concatenate(
        (
            merged_covariances,
            child_covariances[selected_children],
            protected_covariances,
        )
    )
    output_masses = np.concatenate(
        (
            merged_masses,
            child_masses[selected_children],
            protected_masses,
        )
    )
    if args.base_npz is not None and split_count == 0:
        output_centers = reference_centers.copy()
        output_covariances = reference_covariances.copy()
        output_masses = reference_masses.copy()
    expected_count = args.target_count + (
        extra_children if args.preserve_split_count else 0
    )
    if len(output_centers) != expected_count:
        raise RuntimeError(f"produced {len(output_centers)} instead of {expected_count}")
    mass_error = float(output_masses.sum() / reference_masses.sum() - 1.0)
    if abs(mass_error) > 1e-6:
        raise RuntimeError(f"mass drifted by {mass_error}")
    parent_moment = mixture_moments(
        reference_centers, reference_covariances, reference_masses
    )
    output_moment = mixture_moments(
        output_centers, output_covariances, output_masses
    )
    global_center_error = float(
        np.linalg.norm(output_moment[1] - parent_moment[1])
    )
    global_covariance_error = float(
        np.linalg.norm(output_moment[2] - parent_moment[2])
        / max(np.linalg.norm(parent_moment[2]), 1e-20)
    )
    if global_center_error > 1e-8 or global_covariance_error > 1e-8:
        raise RuntimeError("global mixture moments drifted")

    report = {
        "mode": mode,
        "parent_count": len(reference_centers),
        "target_count": args.target_count,
        "output_count": len(output_centers),
        "preserve_split_count": args.preserve_split_count,
        "eligible_singleton_count": len(eligible_base),
        "protected_contracted_count": len(protected_base),
        "split_parent_count": len(split),
        "selected_child_count": int(selected_children.sum()),
        "merged_parent_count": merge_count,
        "retained_merged_parent_count": len(merged_centers),
        "mass_relative_error": mass_error,
        "spatial_sigma_ratio": args.spatial_sigma_ratio,
        "child_jitter_ratio": args.child_jitter_ratio,
        "seed": args.seed,
        "anisotropy_boost": args.anisotropy_boost,
        "max_anisotropy": args.max_anisotropy,
        "global_center_error_m": global_center_error,
        "global_covariance_relative_error": global_covariance_error,
        **split_moment_report,
    }
    write_outputs(
        args.output_npz,
        args.output_json,
        args.output_report,
        output_centers,
        output_covariances,
        output_masses,
        report,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
