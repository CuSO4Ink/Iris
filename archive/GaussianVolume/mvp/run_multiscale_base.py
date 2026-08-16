"""Build and evaluate exact-G2-preserving multi-scale split candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from run_degrid_overnight import (
    bounded_gate,
    lattice_order,
    strict_gate,
    validate_output,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "wdas_404k_multiscale_moment_base"
BASE = ROOT / "artifacts" / "wdas_404k_sigma038_aniso115" / "initializer.npz"
PARENT = (
    ROOT
    / "artifacts"
    / "wdas_404k_multiscale_moment"
    / "parent_b8_sigma038.npz"
)
GRID = ROOT.parents[1] / "tmp" / "wdas_cloud" / "grids" / "wdas_cloud_half.npy"
DATASET = ROOT / "artifacts" / "wdas_half_screen400k_tau8"
SPLITS = (0, 1_000, 2_000, 4_000)
COUNT = 404_524


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def run(command: list[str], stdout: Path, stderr: Path) -> None:
    with stdout.open("a", encoding="utf-8") as out, stderr.open(
        "a", encoding="utf-8"
    ) as err:
        subprocess.run(
            command,
            cwd=Path(__file__).parent,
            check=True,
            stdout=out,
            stderr=err,
        )


def normalized_baseline(metrics: dict) -> dict:
    return {
        **metrics,
        "foreground_t_psnr_db": metrics["transmittance_psnr_foreground_db"],
    }


def candidate_row(directory: Path, base_metrics: dict, base_order: dict) -> dict:
    report = json.loads(
        (directory / "eval0" / "recovery_report.json").read_text(encoding="utf-8")
    )
    metrics = report["final_metrics"]
    validation = validate_output(directory / "initializer.npz")
    order = lattice_order(
        np.load(directory / "initializer.npz")["center_m"], base_order["pitch_m"]
    )
    baseline = normalized_baseline(base_metrics)
    return {
        "split_parent_count": int(directory.name.rsplit("_", 1)[1]),
        "metrics": metrics,
        "validation": validation,
        "lattice_order": order,
        "strict_gate": strict_gate(metrics, baseline),
        "bounded_gate": bounded_gate(
            metrics, baseline, order, base_order["lattice_order"]
        ),
        "initializer": str((directory / "initializer.npz").resolve()),
    }


def self_check() -> None:
    metrics = {
        "tau_psnr_db": 2.0,
        "tau_mae": 0.5,
        "transmittance_psnr_foreground_db": 2.0,
        "edge_l1": 0.5,
        "gabor_energy_l1": 0.5,
        "gabor_phase_energy_l1": 0.5,
        "silhouette_iou": 1.0,
    }
    assert strict_gate(metrics, normalized_baseline(metrics))
    assert not bounded_gate(
        metrics, normalized_baseline(metrics), order=1.0, base_order=1.0
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("run_multiscale_base self-check passed")
        return

    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT / "summary.json"
    started = time.time()
    rows = []
    grid_shape = np.load(GRID, mmap_mode="r").squeeze().shape
    pitch_m = 8.0 * (10.0 / max(grid_shape))

    for split in SPLITS:
        directory = OUTPUT / f"base_split_{split:06d}"
        directory.mkdir(exist_ok=True)
        initializer = directory / "initializer.npz"
        initializer_report = directory / "initializer_report.json"
        if not initializer_report.exists():
            run(
                [
                    sys.executable,
                    "build_adaptive_grid_budget.py",
                    "--parent-npz",
                    str(PARENT),
                    "--base-npz",
                    str(BASE),
                    "--grid",
                    str(GRID),
                    "--output-npz",
                    str(initializer),
                    "--output-report",
                    str(initializer_report),
                    "--target-count",
                    str(COUNT),
                    "--split-parent-count",
                    str(split),
                    "--spatial-sigma-ratio",
                    "0.38",
                    "--anisotropy-boost",
                    "1.15",
                ],
                directory / "build.stdout.log",
                directory / "build.stderr.log",
            )
        eval_dir = directory / "eval0"
        if not (eval_dir / "recovery_report.json").exists():
            run(
                [
                    sys.executable,
                    "recover_contracted_50k.py",
                    "--input-npz",
                    str(initializer),
                    "--dataset",
                    str(DATASET),
                    "--output",
                    str(eval_dir),
                    "--steps",
                    "0",
                    "--eval-rays",
                    "1000",
                    "--patch-radius",
                    "2",
                    "--skip-json",
                ],
                directory / "eval0.stdout.log",
                directory / "eval0.stderr.log",
            )

        if split == 0:
            base_metrics = json.loads(
                (eval_dir / "recovery_report.json").read_text(encoding="utf-8")
            )["final_metrics"]
            base_order = {
                "pitch_m": pitch_m,
                "lattice_order": lattice_order(
                    np.load(initializer)["center_m"], pitch_m
                ),
            }
        rows.append(candidate_row(directory, base_metrics, base_order))
        atomic_json(
            summary_path,
            {
                "status": "running",
                "elapsed_minutes": (time.time() - started) / 60.0,
                "baseline_metrics": base_metrics,
                "baseline_lattice": base_order,
                "completed": rows,
            },
        )

    atomic_json(
        summary_path,
        {
            "status": "complete",
            "elapsed_minutes": (time.time() - started) / 60.0,
            "baseline_metrics": base_metrics,
            "baseline_lattice": base_order,
            "completed": rows,
            "strict_candidates": [
                row["split_parent_count"] for row in rows[1:] if row["strict_gate"]
            ],
            "bounded_candidates": [
                row["split_parent_count"] for row in rows[1:] if row["bounded_gate"]
            ],
        },
    )


if __name__ == "__main__":
    main()
