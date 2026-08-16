"""Merge small interior gaps without changing S3's outer silhouette or runtime layout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from plyfile import PlyData, PlyElement

from build_s3_view_boundary_candidate import read_rows
from grid_to_7drgs import COMPACT_PROPERTIES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("boundary_mask", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, default=1.04)
    args = parser.parse_args()
    if args.scale <= 1.0:
        parser.error("--scale must be greater than 1")

    source = read_rows(args.source)
    rows = source.copy()
    boundary = np.load(args.boundary_mask)
    if boundary.dtype != np.bool_ or boundary.shape != (len(rows),):
        raise ValueError("boundary mask must be a bool NPY matching the point count")
    interior = ~boundary
    variance_scale = args.scale**2
    rows[interior, 3] /= variance_scale
    rows[interior, 4:10] *= variance_scale
    if not np.isfinite(rows).all() or np.any(rows[:, 3] <= 0.0):
        raise ValueError("smoothed candidate contains invalid values")

    vertices = np.empty(len(rows), dtype=[(name, "<f4") for name in COMPACT_PROPERTIES])
    for index, name in enumerate(COMPACT_PROPERTIES):
        vertices[name] = rows[:, index]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    PlyData(
        [PlyElement.describe(vertices, "vertex")],
        text=False,
        comments=["compact_static_transport 1", "compact_shared_opacity 1"],
    ).write(args.output)

    decoded = read_rows(args.output)
    report = {
        "path": str(args.output.resolve()),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest().upper(),
        "point_count": len(decoded),
        "bytes_per_point": int(decoded.strides[0]),
        "interior_fraction": float(interior.mean()),
        "interior_sigma_scale": args.scale,
        "boundary_geometry_opacity_bit_identical": bool(
            np.array_equal(
                decoded[boundary, :10].view(np.uint32),
                source[boundary, :10].view(np.uint32),
            )
        ),
        "j_columns_bit_identical": bool(
            np.array_equal(
                decoded[:, 10:16].view(np.uint32),
                source[:, 10:16].view(np.uint32),
            )
        ),
    }
    if (
        report["bytes_per_point"] != 64
        or not report["boundary_geometry_opacity_bit_identical"]
        or not report["j_columns_bit_identical"]
    ):
        raise AssertionError("candidate validation failed")
    args.output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
