"""Fit per-point light SH directly from VDB light transmittance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from plyfile import PlyData, PlyElement

from prepare_7drgs_dataset import (
    _directional_light_transmittance,
    _light_directions,
    _sample_volume,
)


C0 = 0.28209479177387814
C1 = 0.4886025119029199
C2 = np.asarray(
    (1.0925484305920792, -1.0925484305920792, 0.31539156525252005,
     -1.0925484305920792, 0.5462742152960396),
    dtype=np.float64,
)
C3 = np.asarray(
    (-0.5900435899266435, 2.890611442640554, -0.4570457994644658,
     0.3731763325901154, -0.4570457994644658, 1.445305721320277,
     -0.5900435899266435),
    dtype=np.float64,
)


def _sh_basis(directions: np.ndarray, degree: int) -> np.ndarray:
    x, y, z = directions.T.astype(np.float64)
    columns = [
        np.full(len(directions), C0),
        -C1 * y,
        C1 * z,
        -C1 * x,
        C2[0] * x * y,
        C2[1] * y * z,
        C2[2] * (2.0 * z * z - x * x - y * y),
        C2[3] * x * z,
        C2[4] * (x * x - y * y),
    ]
    if degree == 3:
        columns.extend(
            (
                C3[0] * y * (3.0 * x * x - y * y),
                C3[1] * x * y * z,
                C3[2] * y * (4.0 * z * z - x * x - y * y),
                C3[3] * z * (2.0 * z * z - 3.0 * x * x - 3.0 * y * y),
                C3[4] * x * (4.0 * z * z - x * x - y * y),
                C3[5] * z * (x * x - y * y),
                C3[6] * x * (x * x - 3.0 * y * y),
            )
        )
    return np.stack(columns, axis=1)


def _self_check() -> None:
    _, directions = _light_directions(24)
    for degree, count in ((2, 9), (3, 16)):
        basis = _sh_basis(directions, degree)
        assert basis.shape == (24, count)
        assert np.linalg.matrix_rank(basis[:-4]) == count
        coefficients = np.arange(count, dtype=np.float64)[:, None] * 0.01
        targets = basis[:-4] @ coefficients
        fitted = np.linalg.pinv(basis[:-4]) @ targets
        assert np.allclose(fitted, coefficients, atol=1e-10)


@torch.inference_mode()
def bake(args: argparse.Namespace) -> dict:
    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    density_scale = float(scene["density_scale"])
    voxel_cm = float(scene["voxel_cm"])
    bounds_np = np.asarray((scene["bbox_min"], scene["bbox_max"]), dtype=np.float32)

    source = PlyData.read(args.source_ply, mmap="r")
    vertices = source["vertex"].data
    coefficient_count = (args.degree + 1) ** 2
    required = {"x", "y", "z", "f_dc_j"}
    missing = required.difference(vertices.dtype.names)
    if missing:
        raise ValueError(f"source PLY is missing fields: {sorted(missing)}")

    points_np = np.stack(
        (vertices["x"], vertices["y"], vertices["z"]), axis=1
    ).astype(np.float32)
    inside = np.all((points_np >= bounds_np[0]) & (points_np <= bounds_np[1]), axis=1)
    if inside.mean() < 0.99:
        raise ValueError(f"only {inside.mean():.3%} of points lie inside the VDB bounds")

    grid_np = np.load(args.grid, mmap_mode="r").squeeze()
    if grid_np.ndim != 3 or not np.isfinite(grid_np).all() or np.min(grid_np) < 0.0:
        raise ValueError("grid must be finite, non-negative and 3D")

    directions_ue, directions_gl = _light_directions(args.lights)
    if not 0 < args.heldout < args.lights - 9:
        raise ValueError("heldout count leaves too few directions for degree-2 fitting")
    train_count = args.lights - args.heldout
    basis = _sh_basis(directions_gl, args.degree)

    device = torch.device(args.device)
    density = torch.from_numpy(np.asarray(grid_np, dtype=np.float32)).to(device)
    points = torch.from_numpy(points_np).to(device)
    bounds = torch.from_numpy(bounds_np).to(device)
    targets = np.empty((args.lights, len(vertices)), dtype=np.float32)

    for index, direction in enumerate(directions_ue):
        print(f"[pointwise-light] direction {index + 1}/{args.lights}", flush=True)
        light = _directional_light_transmittance(
            density, direction, density_scale, voxel_cm
        )[None, None]
        targets[index] = _sample_volume(light, points, bounds).cpu().numpy()
        del light

    if args.encoding == "optical_depth":
        fit_targets = -np.log(np.clip(targets, 1e-6, 1.0))
        coefficients = (
            np.linalg.pinv(basis[:train_count]) @ fit_targets[:train_count]
        ).astype(np.float32)
        predicted_tau = np.maximum(basis @ coefficients.astype(np.float64), 0.0)
        predicted = np.exp(-predicted_tau)
    else:
        coefficients = (
            np.linalg.pinv(basis[:train_count]) @ (targets[:train_count] - 0.5)
        ).astype(np.float32)
        predicted = basis @ coefficients.astype(np.float64) + 0.5

    missing_j_fields = [
        f"f_rest_j_{index}"
        for index in range(coefficient_count - 1)
        if f"f_rest_j_{index}" not in vertices.dtype.names
    ]
    if missing_j_fields:
        rows = np.empty(
            len(vertices),
            dtype=vertices.dtype.descr + [(name, "<f4") for name in missing_j_fields],
        )
        for name in vertices.dtype.names:
            rows[name] = vertices[name]
        for name in missing_j_fields:
            rows[name] = 0.0
    else:
        rows = np.array(vertices, copy=True)
    rows["f_dc_j"] = coefficients[0]
    for index in range(coefficient_count - 1):
        rows[f"f_rest_j_{index}"] = coefficients[index + 1]
    for index in range(coefficient_count - 1, 15):
        name = f"f_rest_j_{index}"
        if name in rows.dtype.names:
            rows[name] = 0.0

    j_fields = {"f_dc_j", *(f"f_rest_j_{i}" for i in range(15))}
    static_fields = [name for name in vertices.dtype.names if name not in j_fields]
    static_error = max(
        float(np.max(np.abs(rows[name] - vertices[name]))) for name in static_fields
    )
    if static_error != 0.0 or not all(np.isfinite(rows[name]).all() for name in rows.dtype.names):
        raise ValueError("output PLY failed static or finite-value validation")

    args.output_ply.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(rows, "vertex")], text=False).write(args.output_ply)

    train_error = predicted[:train_count] - targets[:train_count]
    heldout_error = predicted[train_count:] - targets[train_count:]
    report = {
        "source_ply": str(args.source_ply.resolve()),
        "output_ply": str(args.output_ply.resolve()),
        "grid": str(args.grid.resolve()),
        "points": len(vertices),
        "lights": args.lights,
        "heldout_lights": args.heldout,
        "sh_degree": args.degree,
        "encoding": args.encoding,
        "inside_bounds_fraction": float(inside.mean()),
        "target_transmittance_percentiles": np.percentile(
            targets, (0, 1, 50, 99, 100)
        ).tolist(),
        "predicted_transmittance_percentiles": np.percentile(
            predicted, (0, 1, 50, 99, 100)
        ).tolist(),
        "train_mae": float(np.mean(np.abs(train_error))),
        "train_rmse": float(np.sqrt(np.mean(train_error * train_error))),
        "heldout_mae": float(np.mean(np.abs(heldout_error))),
        "heldout_rmse": float(np.sqrt(np.mean(heldout_error * heldout_error))),
        "static_parameter_max_error": static_error,
        "status": f"pointwise light {args.encoding} fitted to degree-{args.degree} J SH",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ply", type=Path, required=True)
    parser.add_argument("--grid", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output-ply", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lights", type=int, default=24)
    parser.add_argument("--heldout", type=int, default=4)
    parser.add_argument("--degree", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--encoding",
        choices=("transmittance", "optical_depth"),
        default="transmittance",
    )
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    _self_check()
    print(json.dumps(bake(args), indent=2))


if __name__ == "__main__":
    main()
