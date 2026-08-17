"""Minimal local tau-QIRF selection A/B for an aggregated B2 Gaussian PLY."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from evaluate_heldout import compute_metrics


SQRT_2PI = math.sqrt(2.0 * math.pi)
TRAIN_DIRECTIONS = np.asarray(
    ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)),
    dtype=np.float64,
)
HELDOUT_DIRECTIONS = np.asarray(
    (
        (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1),
        (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1),
    ),
    dtype=np.float64,
) / math.sqrt(3.0)


def gaussian_overlap(centers: np.ndarray, covariances: np.ndarray) -> np.ndarray:
    """Return the normalized analytic L2 overlap of anisotropic Gaussians."""
    summed = covariances[:, None] + covariances[None, :]
    delta = centers[:, None] - centers[None, :]
    logdet = np.linalg.slogdet(covariances)[1]
    summed_logdet = np.linalg.slogdet(summed)[1]
    mahalanobis = np.einsum(
        "abi,abij,abj->ab", delta, np.linalg.inv(summed), delta
    )
    log_overlap = (
        1.5 * math.log(2.0 * math.pi)
        + 0.5 * logdet[:, None]
        + 0.5 * logdet[None, :]
        - 0.5 * summed_logdet
        - 0.5 * mahalanobis
    )
    overlap = np.exp(log_overlap)
    diagonal = np.sqrt(np.diag(overlap))
    overlap /= diagonal[:, None] * diagonal[None, :]
    return 0.5 * (overlap + overlap.T)


def ray_basis_response(
    centers: np.ndarray,
    covariances: np.ndarray,
    directions: np.ndarray,
) -> np.ndarray:
    """Integrate every unit Gaussian along lines through every local center."""
    inverse = np.linalg.inv(covariances)
    responses = []
    offsets = centers[:, None] - centers[None, :]
    for direction in directions:
        projected = np.einsum("nij,j->ni", inverse, direction)
        along = np.einsum("ni,i->n", projected, direction)
        linear = np.einsum("abi,bi->ab", offsets, projected)
        closest = offsets - (linear / along)[..., None] * direction
        perpendicular = np.einsum(
            "abi,bij,abj->ab", closest, inverse, closest
        )
        responses.append(
            SQRT_2PI / np.sqrt(along)[None, :] * np.exp(-0.5 * perpendicular)
        )
    return np.concatenate(responses, axis=0)


def camera_ray_basis_response(
    centers: np.ndarray,
    covariances: np.ndarray,
    camera_origins: np.ndarray,
) -> np.ndarray:
    """Integrate a small projected ray grid covering the local block and its edge."""
    centroid = centers.mean(axis=0)
    extent = float(np.max(np.linalg.norm(centers - centroid, axis=1)))
    extent += 3.0 * math.sqrt(float(np.max(np.linalg.eigvalsh(covariances))))
    coordinates = np.linspace(-extent, extent, 9)
    all_origins = []
    all_targets = []
    for origin in camera_origins:
        forward = centroid - origin
        forward /= np.linalg.norm(forward)
        seed = np.asarray((0.0, 0.0, 1.0))
        if abs(float(forward @ seed)) > 0.9:
            seed = np.asarray((0.0, 1.0, 0.0))
        right = np.cross(forward, seed)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        offsets = np.asarray(
            [x * right + y * up for y in coordinates for x in coordinates]
        )
        all_origins.append(np.repeat(origin[None], len(offsets), axis=0))
        all_targets.append(centroid + offsets)
    origins = np.concatenate(all_origins)
    targets = np.concatenate(all_targets)
    directions = targets - origins
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    inverse = np.linalg.inv(covariances)
    offsets = origins[:, None] - centers[None, :]
    projected = np.einsum("nij,rj->rni", inverse, directions)
    along = np.einsum("rni,ri->rn", projected, directions)
    linear = np.einsum("rni,rni->rn", offsets, projected)
    closest = offsets - (linear / along)[..., None] * directions[:, None]
    perpendicular = np.einsum(
        "rni,nij,rnj->rn", closest, inverse, closest
    )
    return SQRT_2PI / np.sqrt(along) * np.exp(-0.5 * perpendicular)


def qirf_scores(
    overlap: np.ndarray,
    response: np.ndarray,
    *,
    energy: float = 0.95,
    regularization: float = 1e-4,
) -> tuple[np.ndarray, int, np.ndarray]:
    """Solve P u = lambda S u and return occupation-weighted participation."""
    if not 0.0 < energy <= 1.0 or regularization <= 0.0:
        raise ValueError("energy must be in (0, 1] and regularization must be positive")
    density = response.T @ response
    density /= np.trace(density) + np.finfo(np.float64).eps
    metric = overlap + regularization * np.eye(len(overlap))
    cholesky = np.linalg.cholesky(metric)
    whitened = np.linalg.solve(cholesky, density)
    whitened = np.linalg.solve(cholesky, whitened.T).T
    eigenvalues, whitened_modes = np.linalg.eigh(0.5 * (whitened + whitened.T))
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    modes = np.linalg.solve(cholesky.T, whitened_modes[:, order])
    cumulative = np.cumsum(eigenvalues)
    mode_count = int(np.searchsorted(cumulative, energy * cumulative[-1]) + 1)
    scores = np.sum(
        eigenvalues[None, :mode_count] * modes[:, :mode_count] ** 2, axis=1
    )
    return scores, mode_count, eigenvalues


def nonnegative_refit(
    design: np.ndarray,
    target: np.ndarray,
    *,
    iterations: int = 2000,
) -> np.ndarray:
    """Small projected-gradient NNLS; selection A/B shares this recovery."""
    gram = design.T @ design
    rhs = design.T @ target
    step = 1.0 / max(float(np.linalg.eigvalsh(gram)[-1]), 1e-12)
    weights = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(iterations):
        updated = np.maximum(weights - step * (gram @ weights - rhs), 0.0)
        if np.max(np.abs(updated - weights)) <= 1e-10 * (
            1.0 + np.max(np.abs(weights))
        ):
            weights = updated
            break
        weights = updated
    return weights


def compare_selection(
    centers: np.ndarray,
    covariances: np.ndarray,
    extinction: np.ndarray,
    keep_ratios: tuple[float, ...],
    camera_origins: np.ndarray | None = None,
) -> dict:
    if camera_origins is None:
        train_basis = ray_basis_response(centers, covariances, TRAIN_DIRECTIONS)
        heldout_basis = ray_basis_response(centers, covariances, HELDOUT_DIRECTIONS)
        sampling = "six axis train directions; eight diagonal held-out directions"
    else:
        if len(camera_origins) < 4:
            raise ValueError("at least four camera origins are required")
        train_basis = camera_ray_basis_response(
            centers, covariances, camera_origins[::2]
        )
        heldout_basis = camera_ray_basis_response(
            centers, covariances, camera_origins[1::2]
        )
        sampling = "even camera origins train; odd camera origins held out"
    train_response = train_basis * extinction[None, :]
    train_tau = train_response.sum(axis=1)
    heldout_tau = (heldout_basis * extinction[None, :]).sum(axis=1)
    overlap = gaussian_overlap(centers, covariances)
    scores, mode_count, eigenvalues = qirf_scores(overlap, train_response)
    contribution = np.sum(train_response * train_response, axis=0)
    results = []
    safeguard_count = max(1, int(math.ceil(0.05 * len(centers))))
    for ratio in keep_ratios:
        if not 0.0 < ratio < 1.0:
            raise ValueError("keep ratios must be in (0, 1)")
        keep = max(1, int(math.ceil(ratio * len(centers))))
        row = {"keep_ratio": ratio, "keep_count": keep, "methods": {}}
        qirf_base_count = max(1, keep - min(safeguard_count, keep - 1))
        qirf_selected = np.argsort(scores)[-qirf_base_count:]
        inactive = np.setdiff1d(np.arange(len(centers)), qirf_selected)
        safeguard = keep - qirf_base_count
        safeguarded = (
            inactive[np.argsort(contribution[inactive])[-safeguard:]]
            if safeguard
            else np.empty(0, dtype=np.int64)
        )
        selections = (
            ("tau_qirf", np.concatenate((qirf_selected, safeguarded))),
            ("contribution", np.argsort(contribution)[-keep:]),
        )
        for name, selected in selections:
            fitted = nonnegative_refit(train_basis[:, selected], train_tau)
            candidate_tau = heldout_basis[:, selected] @ fitted
            row["methods"][name] = {
                "selected_local_indices": selected.tolist(),
                "metrics": compute_metrics(
                    np.exp(-heldout_tau),
                    candidate_tau,
                    alpha_threshold=1e-4,
                ),
            }
        qirf = row["methods"]["tau_qirf"]["metrics"]
        baseline = row["methods"]["contribution"]["metrics"]
        row["tau_qirf_wins_tau_mae"] = qirf["tau_mae"] < baseline["tau_mae"]
        row["tau_qirf_wins_transmittance"] = (
            qirf["transmittance_psnr_foreground_db"]
            > baseline["transmittance_psnr_foreground_db"]
        )
        results.append(row)
    return {
        "kernel_count": len(centers),
        "ray_sampling": sampling,
        "fixed_budget_detail_safeguard_count": safeguard_count,
        "mode_count_at_95pct_energy": mode_count,
        "leading_occupation_values": eigenvalues[:8].tolist(),
        "results": results,
    }


def load_b2_block(path: Path, block_size: int, anchor_index: int) -> tuple:
    from plyfile import PlyData

    vertices = PlyData.read(path, mmap="r").elements[0].data
    if not 1 < block_size <= len(vertices):
        raise ValueError("block size must be between 2 and the PLY vertex count")
    opacity = np.asarray(vertices["opacity"])
    if anchor_index < 0:
        anchor_index = int(np.argmax(opacity))
    if anchor_index >= len(vertices):
        raise ValueError("anchor index is outside the PLY")

    anchor = np.asarray(
        [vertices[name][anchor_index] for name in ("x", "y", "z")],
        dtype=np.float64,
    )
    distance2 = sum(
        (np.asarray(vertices[name], dtype=np.float64) - anchor[axis]) ** 2
        for axis, name in enumerate(("x", "y", "z"))
    )
    indices = np.argpartition(distance2, block_size - 1)[:block_size]
    indices = indices[np.argsort(distance2[indices])]
    centers = np.stack(
        [np.asarray(vertices[name][indices], dtype=np.float64) for name in ("x", "y", "z")],
        axis=1,
    )

    cholesky = np.zeros((block_size, 3, 3), dtype=np.float64)
    diagonal = np.stack(
        [
            np.exp(np.asarray(vertices[f"chol_diag_{axis}"][indices], dtype=np.float64))
            for axis in range(3)
        ],
        axis=1,
    )
    cholesky[:, np.arange(3), np.arange(3)] = diagonal
    cholesky[:, 1, 0] = np.asarray(vertices["chol_offdiag_0"][indices]) * diagonal[:, 1]
    cholesky[:, 2, 0] = np.asarray(vertices["chol_offdiag_1"][indices]) * diagonal[:, 2]
    cholesky[:, 2, 1] = np.asarray(vertices["chol_offdiag_2"][indices]) * diagonal[:, 2]
    covariances = cholesky @ np.transpose(cholesky, (0, 2, 1))

    alpha = 1.0 / (1.0 + np.exp(-np.clip(opacity[indices], -80.0, 80.0)))
    path_tau = -np.log1p(-np.clip(alpha, 0.0, 1.0 - 1e-12))
    effective_sigma = np.cbrt(np.prod(diagonal, axis=1))
    extinction = path_tau / (SQRT_2PI * effective_sigma)
    return centers, covariances, extinction, indices, anchor_index


def load_camera_origins(path: Path) -> np.ndarray:
    payload = json.loads(path.read_text(encoding="utf-8"))
    origins = [
        np.asarray(frame["transform_matrix"], dtype=np.float64)[:3, 3]
        for frame in payload["frames"]
    ]
    return np.stack(origins)


def _self_check() -> None:
    centers = np.asarray(
        ((0.0, 0.0, 0.0), (0.01, 0.0, 0.0), (0.8, 0.0, 0.0), (0.0, 0.8, 0.0))
    )
    covariances = np.repeat((np.eye(3) * 0.1**2)[None], len(centers), axis=0)
    extinction = np.asarray((1.0, 1.0, 0.7, 0.5))
    overlap = gaussian_overlap(centers, covariances)
    assert np.allclose(np.diag(overlap), 1.0)
    assert overlap[0, 1] > 0.99 and overlap[0, 2] < 1e-3
    report = compare_selection(centers, covariances, extinction, (0.75,))
    methods = report["results"][0]["methods"]
    assert methods["tau_qirf"]["metrics"]["candidate_negative_tau_fraction"] == 0.0
    assert methods["contribution"]["metrics"]["candidate_negative_tau_fraction"] == 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--anchor-index", type=int, default=-1)
    parser.add_argument("--keep-ratios", type=float, nargs="+", default=(0.7, 0.5, 0.3))
    parser.add_argument("--transforms", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("qirf_tau_ab self-check passed")
        return
    if args.ply is None or args.output is None:
        parser.error("--ply and --output are required unless --self-check is used")

    centers, covariances, extinction, indices, anchor = load_b2_block(
        args.ply, args.block_size, args.anchor_index
    )
    report = compare_selection(
        centers,
        covariances,
        extinction,
        tuple(args.keep_ratios),
        load_camera_origins(args.transforms) if args.transforms else None,
    )
    report.update(
        {
            "scope": (
                "local algorithm smoke only; this does not validate global 50K "
                "compression or thin-boundary quality"
            ),
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
