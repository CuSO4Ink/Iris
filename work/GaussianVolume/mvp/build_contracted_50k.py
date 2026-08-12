"""Build an exact-budget moment-contracted GaussianVolume JSON from B2."""

from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np

from contract_tau_ab import GAUSSIAN_VOLUME, contract_gaussians


def adaptive_moment_partition(
    centers: np.ndarray,
    covariances: np.ndarray,
    extinction: np.ndarray,
    target: int,
    mass_exponent: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if target < 1 or target > len(centers):
        raise ValueError("target must be between one and the source count")
    if not 0.0 <= mass_exponent <= 1.0:
        raise ValueError("mass exponent must be in [0, 1]")
    masses = (
        extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariances))
    )
    if np.any(masses <= 0.0):
        raise ValueError("adaptive partition requires positive finite mass")

    next_id = 0

    def make_node(members: np.ndarray) -> tuple:
        nonlocal next_id
        weights = masses[members]
        mass = float(weights.sum())
        normalized = weights / mass
        mean = normalized @ centers[members]
        offsets = centers[members] - mean
        within = np.einsum(
            "n,nij->ij", normalized, covariances[members], optimize=True
        )
        between = np.einsum(
            "n,ni,nj->ij", normalized, offsets, offsets, optimize=True
        )
        covariance = within + between
        sigma_t = mass / (
            GAUSSIAN_VOLUME * math.sqrt(float(np.linalg.det(covariance)))
        )
        axis = None
        score = -math.inf
        if len(members) > 1:
            eigenvalues, eigenvectors = np.linalg.eigh(between)
            axis = eigenvectors[:, -1]
            within_scale = max(float(np.trace(within)) / 3.0, 1e-15)
            score = mass**mass_exponent * math.log1p(
                max(float(eigenvalues[-1]), 0.0) / within_scale
            )
        node = (
            next_id,
            members,
            mean,
            covariance,
            sigma_t,
            mass,
            axis,
            score,
        )
        next_id += 1
        return node

    root = make_node(np.arange(len(centers), dtype=np.int64))
    leaves = {root[0]: root}
    heap = [(-root[7], root[0])]
    while len(leaves) < target:
        if not heap:
            raise RuntimeError("adaptive partition ran out of splittable leaves")
        _, node_id = heapq.heappop(heap)
        node = leaves.pop(node_id)
        members, axis = node[1], node[6]
        projection = centers[members] @ axis
        order = np.argsort(projection, kind="stable")
        sorted_members = members[order]
        cumulative = np.cumsum(masses[sorted_members])
        cut = int(np.searchsorted(cumulative, cumulative[-1] * 0.5)) + 1
        cut = min(max(cut, 1), len(sorted_members) - 1)
        for child_members in (sorted_members[:cut], sorted_members[cut:]):
            child = make_node(child_members)
            leaves[child[0]] = child
            if len(child_members) > 1:
                heapq.heappush(heap, (-child[7], child[0]))
        if len(leaves) % 5000 == 0:
            print(f"[adaptive] {len(leaves)}/{target} leaves")

    nodes = list(leaves.values())
    return (
        np.stack([node[2] for node in nodes]),
        np.stack([node[3] for node in nodes]),
        np.asarray([node[4] for node in nodes]),
    )


def allocate_budgets(counts: np.ndarray, target: int) -> np.ndarray:
    if target < len(counts) or target > int(counts.sum()):
        raise ValueError("target must allow at least one and at most all kernels per block")
    ideal = target * counts / counts.sum()
    budgets = np.clip(np.floor(ideal).astype(np.int64), 1, counts)
    delta = target - int(budgets.sum())
    while delta > 0:
        candidates = np.flatnonzero(budgets < counts)
        order = candidates[np.argsort((ideal - budgets)[candidates])[::-1]]
        step = min(delta, len(order))
        budgets[order[:step]] += 1
        delta -= step
    while delta < 0:
        candidates = np.flatnonzero(budgets > 1)
        order = candidates[np.argsort((ideal - budgets)[candidates])]
        step = min(-delta, len(order))
        budgets[order[:step]] -= 1
        delta += step
    if int(budgets.sum()) != target:
        raise RuntimeError("exact budget allocation failed")
    return budgets


def load_b2(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from plyfile import PlyData

    vertices = PlyData.read(path, mmap="r").elements[0].data
    centers = np.stack(
        [np.asarray(vertices[name], dtype=np.float64) for name in ("x", "y", "z")],
        axis=1,
    )
    diagonal = np.stack(
        [
            np.exp(np.asarray(vertices[f"chol_diag_{axis}"], dtype=np.float64))
            for axis in range(3)
        ],
        axis=1,
    )
    cholesky = np.zeros((len(vertices), 3, 3), dtype=np.float64)
    cholesky[:, np.arange(3), np.arange(3)] = diagonal
    cholesky[:, 1, 0] = np.asarray(vertices["chol_offdiag_0"]) * diagonal[:, 1]
    cholesky[:, 2, 0] = np.asarray(vertices["chol_offdiag_1"]) * diagonal[:, 2]
    cholesky[:, 2, 1] = np.asarray(vertices["chol_offdiag_2"]) * diagonal[:, 2]
    covariances = cholesky @ np.transpose(cholesky, (0, 2, 1))
    opacity = np.asarray(vertices["opacity"], dtype=np.float64)
    alpha = 1.0 / (1.0 + np.exp(-np.clip(opacity, -80.0, 80.0)))
    path_tau = -np.log1p(-np.clip(alpha, 0.0, 1.0 - 1e-12))
    extinction = path_tau / (
        math.sqrt(2.0 * math.pi) * np.cbrt(np.prod(diagonal, axis=1))
    )
    return centers, covariances, extinction


def macroblock_ids(
    centers: np.ndarray,
    grid_shape: np.ndarray,
    voxel_cm: float,
    *,
    source_block_size: int = 2,
    macro_width: int = 4,
) -> np.ndarray:
    centered = np.empty_like(centers)
    centered[:, 0] = centers[:, 0] * 100.0 / voxel_cm
    centered[:, 1] = -centers[:, 2] * 100.0 / voxel_cm
    centered[:, 2] = -centers[:, 1] * 100.0 / voxel_cm
    grid_coordinates = centered + (grid_shape - 1.0) * 0.5
    source_blocks = np.floor(
        (grid_coordinates + 1e-4) / source_block_size
    ).astype(np.int64)
    macroblocks = source_blocks // macro_width
    source_shape = np.ceil(grid_shape / source_block_size).astype(np.int64)
    macro_shape = np.ceil(source_shape / macro_width).astype(np.int64)
    return np.ravel_multi_index(macroblocks.T, tuple(macro_shape))


def matrix_to_quaternion(matrix: np.ndarray) -> list[float]:
    trace = float(np.trace(matrix))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (matrix[2, 1] - matrix[1, 2]) / s
        y = (matrix[0, 2] - matrix[2, 0]) / s
        z = (matrix[1, 0] - matrix[0, 1]) / s
    else:
        axis = int(np.argmax(np.diag(matrix)))
        j, k = (axis + 1) % 3, (axis + 2) % 3
        s = math.sqrt(max(1.0 + matrix[axis, axis] - matrix[j, j] - matrix[k, k], 0.0)) * 2.0
        values = [0.0, 0.0, 0.0]
        values[axis] = 0.25 * s
        values[j] = (matrix[j, axis] + matrix[axis, j]) / s
        values[k] = (matrix[k, axis] + matrix[axis, k]) / s
        w = (matrix[k, j] - matrix[j, k]) / s
        x, y, z = values
    quaternion = np.asarray((x, y, z, w), dtype=np.float64)
    quaternion /= np.linalg.norm(quaternion)
    return quaternion.tolist()


def build(args: argparse.Namespace) -> dict:
    centers, covariances, extinction = load_b2(args.ply)
    report = json.loads(args.prepare_report.read_text(encoding="utf-8"))
    source_voxel_cm = args.source_voxel_cm or float(report["voxel_cm"])
    counts = budgets = starts = None
    if args.partition == "adaptive":
        centers_out, covariances_out, extinction_out = adaptive_moment_partition(
            centers,
            covariances,
            extinction,
            args.target_count,
            args.detail_mass_exponent,
        )
    else:
        ids = macroblock_ids(
            centers,
            np.asarray(report["grid_shape"], dtype=np.float64),
            source_voxel_cm,
            macro_width=args.macro_width,
        )
        order = np.argsort(ids, kind="stable")
        _, starts, counts = np.unique(ids[order], return_index=True, return_counts=True)
        budgets = allocate_budgets(counts, args.target_count)
        output_centers = []
        output_covariances = []
        output_extinction = []
        for block_index, (start, count, budget) in enumerate(
            zip(starts, counts, budgets)
        ):
            members = order[start : start + count]
            contracted = contract_gaussians(
                centers[members],
                covariances[members],
                extinction[members],
                int(budget),
            )
            output_centers.append(contracted[0])
            output_covariances.append(contracted[1])
            output_extinction.append(contracted[2])
            if (block_index + 1) % 1000 == 0:
                print(f"[contract] {block_index + 1}/{len(starts)} macroblocks")
        centers_out = np.concatenate(output_centers)
        covariances_out = np.concatenate(output_covariances)
        extinction_out = np.concatenate(output_extinction)
    if len(centers_out) != args.target_count:
        raise RuntimeError("contracted output missed the exact target")

    mass_before = float(
        np.sum(extinction * GAUSSIAN_VOLUME * np.sqrt(np.linalg.det(covariances)))
    )
    mass_after = float(
        np.sum(
            extinction_out
            * GAUSSIAN_VOLUME
            * np.sqrt(np.linalg.det(covariances_out))
        )
    )
    eigenvalues, eigenvectors = np.linalg.eigh(covariances_out)
    if np.any(eigenvalues <= 0.0):
        raise RuntimeError("contracted covariance is not positive definite")
    negative = np.linalg.det(eigenvectors) < 0.0
    eigenvectors[negative, :, 0] *= -1.0
    scales_m = np.sqrt(eigenvalues)
    quaternions = [matrix_to_quaternion(matrix) for matrix in eigenvectors]

    for path in (args.output_npz, args.output_json, args.output_report):
        path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output_npz,
        center_m=centers_out.astype(np.float32),
        covariance_m2=covariances_out.astype(np.float32),
        sigma_t_per_m=extinction_out.astype(np.float32),
    )
    primitives = [
        {
            "center": (centers_out[index] * 100.0).tolist(),
            "scale": (scales_m[index] * 100.0).tolist(),
            "rotation": quaternions[index],
            "sigma_t": float(extinction_out[index] / 100.0),
            "omega": 0.0,
            "albedo": list(args.albedo),
            "emission": 0.0,
        }
        for index in range(len(centers_out))
    ]
    payload = {
        "schema": "GaussianVolume.Primitives.v1",
        "source": str(args.ply.resolve()),
        "method": (
            "adaptive_binary_partition_moment_contraction"
            if args.partition == "adaptive"
            else "disjoint_macroblock_weighted_lloyd_moment_contraction"
        ),
        "primitive_count": len(primitives),
        "gaussians": primitives,
    }
    args.output_json.write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    result = {
        "source_count": len(centers),
        "source_voxel_cm": source_voxel_cm,
        "partition": args.partition,
        "detail_mass_exponent": args.detail_mass_exponent,
        "target_count": len(centers_out),
        "mass_relative_error": abs(mass_after - mass_before) / mass_before,
        "npz": str(args.output_npz.resolve()),
        "json": str(args.output_json.resolve()),
        "status": "initializer only; global tau/T recovery and visual Gate pending",
    }
    if args.partition == "macro":
        result.update(
            {
                "macroblock_count": len(starts),
                "budget_min": int(budgets.min()),
                "budget_max": int(budgets.max()),
                "source_block_count_min": int(counts.min()),
                "source_block_count_max": int(counts.max()),
            }
        )
    args.output_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _self_check() -> None:
    counts = np.asarray((64, 32, 1, 7))
    budgets = allocate_budgets(counts, 20)
    assert budgets.sum() == 20
    assert np.all((budgets >= 1) & (budgets <= counts))
    identity = np.eye(3)
    quaternion = matrix_to_quaternion(identity)
    assert np.allclose(quaternion, (0.0, 0.0, 0.0, 1.0))
    centers = np.asarray(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (9.0, 0.0, 0.0)))
    covariances = np.repeat(identity[None], 3, axis=0)
    extinction = np.ones(3)
    contracted = adaptive_moment_partition(centers, covariances, extinction, 2)
    assert len(contracted[0]) == 2
    before = np.sum(extinction * GAUSSIAN_VOLUME)
    after = np.sum(
        contracted[2]
        * GAUSSIAN_VOLUME
        * np.sqrt(np.linalg.det(contracted[1]))
    )
    assert np.isclose(before, after)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path)
    parser.add_argument("--prepare-report", type=Path)
    parser.add_argument("--output-npz", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-report", type=Path)
    parser.add_argument("--target-count", type=int, default=50_000)
    parser.add_argument(
        "--partition", choices=("adaptive", "macro"), default="adaptive"
    )
    parser.add_argument("--detail-mass-exponent", type=float, default=1.0)
    parser.add_argument("--macro-width", type=int, default=4)
    parser.add_argument("--source-voxel-cm", type=float, default=0.0)
    parser.add_argument("--albedo", type=float, nargs=3, default=(1.0, 1.0, 1.0))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        _self_check()
        print("build_contracted_50k self-check passed")
        return
    required = (
        args.ply,
        args.prepare_report,
        args.output_npz,
        args.output_json,
        args.output_report,
    )
    if any(path is None for path in required):
        parser.error("all input and output paths are required")
    if (
        args.target_count <= 0
        or args.macro_width <= 0
        or args.source_voxel_cm < 0.0
        or not 0.0 <= args.detail_mass_exponent <= 1.0
    ):
        parser.error(
            "target/macro width must be positive, voxel override nonnegative, "
            "and detail mass exponent in [0, 1]"
        )
    result = build(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
