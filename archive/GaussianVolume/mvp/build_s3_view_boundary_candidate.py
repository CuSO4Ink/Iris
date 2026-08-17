"""Finalize a masked S3 silhouette fine-tune without changing its runtime layout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from plyfile import PlyData, PlyElement

from grid_to_7drgs import COMPACT_PROPERTIES


def read_rows(path: Path) -> np.ndarray:
    vertices = PlyData.read(path, mmap="r").elements[0].data
    if tuple(vertices.dtype.names or ()) != COMPACT_PROPERTIES:
        raise ValueError(f"{path} is not the 16-float compact layout")
    return np.stack(
        [np.asarray(vertices[name], dtype="<f4") for name in COMPACT_PROPERTIES],
        axis=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("mask")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    baseline_comments = PlyData.read(args.baseline, mmap="r").comments
    angular_sigma = next(
        (comment for comment in baseline_comments if comment.startswith("angular_sigma ")),
        None,
    )
    if angular_sigma is None:
        raise ValueError("baseline is missing required angular_sigma metadata")
    baseline = read_rows(args.baseline)
    candidate = read_rows(args.candidate)
    mask = (
        np.ones(len(baseline), dtype=np.bool_)
        if args.mask == "all"
        else np.load(Path(args.mask))
    )
    if candidate.shape != baseline.shape or mask.shape != (len(baseline),):
        raise ValueError("baseline, candidate, and mask point counts differ")
    if mask.dtype != np.bool_:
        raise ValueError("mask must be a bool NPY")
    if args.mask == "all" and (
        not np.array_equal(candidate[:, :3].view(np.uint32), baseline[:, :3].view(np.uint32))
        or not np.array_equal(candidate[:, 4:10].view(np.uint32), baseline[:, 4:10].view(np.uint32))
    ):
        raise ValueError("opacity-only fine-tune changed geometry")
    if not np.array_equal(
        candidate[~mask, :10].view(np.uint32),
        baseline[~mask, :10].view(np.uint32),
    ):
        raise ValueError("fine-tune changed frozen non-selected geometry")

    target_mass = baseline[:, 3].sum(dtype=np.float64)
    fixed_mass = candidate[~mask, 3].sum(dtype=np.float64)
    selected_mass = candidate[mask, 3].sum(dtype=np.float64)
    opacity_scale = (target_mass - fixed_mass) / selected_mass
    candidate[mask, 3] *= opacity_scale
    candidate[:, 10:16] = baseline[:, 10:16]
    if not np.isfinite(candidate).all() or np.any(candidate[:, 3] <= 0.0):
        raise ValueError("final candidate contains invalid values")

    vertices = np.empty(len(candidate), dtype=[(name, "<f4") for name in COMPACT_PROPERTIES])
    for index, name in enumerate(COMPACT_PROPERTIES):
        vertices[name] = candidate[:, index]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    PlyData(
        [PlyElement.describe(vertices, "vertex")],
        text=False,
        comments=[
            "compact_static_transport 1",
            "compact_shared_opacity 1",
            angular_sigma,
        ],
    ).write(args.output)

    decoded = read_rows(args.output)
    output_comments = PlyData.read(args.output, mmap="r").comments
    shifts_cm = np.linalg.norm(decoded[mask, :3] - baseline[mask, :3], axis=1) * 100.0
    report = {
        "path": str(args.output.resolve()),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest().upper(),
        "boundary_opacity_scale": float(opacity_scale),
        "opacity_sum_ratio": float(
            decoded[:, 3].sum(dtype=np.float64) / target_mass
        ),
        "point_count": len(decoded),
        "selected_count": int(mask.sum()),
        "selected_fraction": float(mask.mean()),
        "center_shift_cm_p50_p95_max": np.percentile(
            shifts_cm, (50, 95, 100)
        ).tolist(),
        "j_columns_bit_identical": bool(
            np.array_equal(
                decoded[:, 10:16].view(np.uint32),
                baseline[:, 10:16].view(np.uint32),
            )
        ),
        "angular_sigma_preserved": angular_sigma in output_comments,
        "nonselected_center_cov_bit_identical": bool(
            np.array_equal(
                decoded[~mask, :10].view(np.uint32),
                baseline[~mask, :10].view(np.uint32),
            )
        ),
        "payload_bytes": int(decoded.nbytes),
        "bytes_per_point": int(decoded.strides[0]),
    }
    if (
        abs(report["opacity_sum_ratio"] - 1.0) > 1e-6
        or not report["j_columns_bit_identical"]
        or not report["angular_sigma_preserved"]
        or not report["nonselected_center_cov_bit_identical"]
        or report["bytes_per_point"] != 64
    ):
        raise AssertionError("candidate validation failed")
    args.output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
