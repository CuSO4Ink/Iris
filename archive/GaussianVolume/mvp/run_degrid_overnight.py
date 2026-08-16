"""Run a resumable fixed-budget de-grid search without touching Unreal."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


WORK = Path(__file__).resolve().parents[1]
ARTIFACTS = WORK / "artifacts"
BASE = ARTIFACTS / "wdas_404k_sigma038_aniso115" / "initializer.npz"
BASE_REPORT = ARTIFACTS / "wdas_404k_sigma038_aniso115" / "report.json"
DATASET = ARTIFACTS / "wdas_half_screen400k_tau8"
GRID = WORK.parents[1] / "tmp" / "wdas_cloud" / "grids" / "wdas_cloud_half.npy"
TRAINER = Path(__file__).with_name("recover_contracted_50k.py")
COUNT = 404_524
BLOCK_SIZE = 8
SEED = 20_260_728
GAUSSIAN_VOLUME = (2.0 * math.pi) ** 1.5


@dataclass(frozen=True)
class Schedule:
    name: str
    steps: int
    geometry_lr: float
    extinction_lr: float
    transmittance_weight: float
    edge_weight: float
    frequency_weight: float
    center_limit: float
    scale_factor: float
    rotation_degrees: float
    scale_growth_weight: float
    mass_weight: float
    anchor_weight: float


SCHEDULES = (
    Schedule("conservative", 80, 0.002, 0.0007, 3.0, 5.0, 2.0, 0.02, 1.15, 8.0, 1.0, 1.0, 0.2),
    Schedule("recovery", 100, 0.0015, 0.0005, 4.0, 6.0, 1.0, 0.01, 1.10, 6.0, 1.0, 2.0, 0.3),
)
JITTER_FRACTIONS = (0.01, 0.02, 0.03, 0.04)


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def masses(data: np.lib.npyio.NpzFile) -> np.ndarray:
    determinants = np.linalg.det(data["covariance_m2"].astype(np.float64))
    return (
        data["sigma_t_per_m"].astype(np.float64)
        * GAUSSIAN_VOLUME
        * np.sqrt(determinants)
    )


def lattice_order(centers: np.ndarray, pitch_m: float) -> float:
    phase = centers.astype(np.float64) * (2.0 * math.pi / pitch_m)
    return float(np.mean(np.abs(np.mean(np.exp(1j * phase), axis=0))))


def make_initializer(
    source: Path, grid: Path, fraction: float, output: Path
) -> dict:
    data = np.load(source)
    centers = data["center_m"].astype(np.float64).copy()
    shape = np.asarray(np.load(grid, mmap_mode="r").shape, dtype=np.float64)
    voxel_cm = 1000.0 / float(np.max(shape))
    midpoint = (shape - 1.0) * 0.5
    coordinates = np.empty_like(centers)
    coordinates[:, 0] = centers[:, 0] * 100.0 / voxel_cm
    coordinates[:, 1] = -centers[:, 2] * 100.0 / voxel_cm
    coordinates[:, 2] = -centers[:, 1] * 100.0 / voxel_cm
    coordinates += midpoint

    rng = np.random.default_rng(SEED)
    jitter = rng.uniform(-1.0, 1.0, size=coordinates.shape)
    jitter -= jitter.mean(axis=0, keepdims=True)
    jitter *= BLOCK_SIZE * fraction
    moved = np.clip(coordinates + jitter, 0.25, shape - 1.25)
    centered = moved - midpoint
    centers[:, 0] = centered[:, 0] * voxel_cm / 100.0
    centers[:, 2] = -centered[:, 1] * voxel_cm / 100.0
    centers[:, 1] = -centered[:, 2] * voxel_cm / 100.0

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        center_m=centers.astype(np.float32),
        covariance_m2=data["covariance_m2"],
        sigma_t_per_m=data["sigma_t_per_m"],
    )
    shift_cm = np.linalg.norm(centers - data["center_m"], axis=1) * 100.0
    pitch_m = BLOCK_SIZE * voxel_cm / 100.0
    return {
        "jitter_fraction": fraction,
        "center_shift_cm_p50_p90_p99": np.percentile(
            shift_cm, (50, 90, 99)
        ).tolist(),
        "clipped_fraction": float(
            np.mean(np.any(np.abs(moved - coordinates - jitter) > 1e-9, axis=1))
        ),
        "lattice_order": lattice_order(centers, pitch_m),
        "pitch_m": pitch_m,
    }


def command(schedule: Schedule, initializer: Path, output: Path) -> list[str]:
    return [
        sys.executable,
        "-u",
        str(TRAINER),
        "--input-npz",
        str(initializer),
        "--dataset",
        str(DATASET),
        "--output",
        str(output),
        "--steps",
        str(schedule.steps),
        "--patches-per-step",
        "8",
        "--patch-radius",
        "2",
        "--kernel-chunk",
        "4096",
        "--eval-rays",
        "1000",
        "--geometry-warmup",
        "0",
        "--extinction-lr",
        str(schedule.extinction_lr),
        "--geometry-lr",
        str(schedule.geometry_lr),
        "--transmittance-weight",
        str(schedule.transmittance_weight),
        "--edge-weight",
        str(schedule.edge_weight),
        "--frequency-weight",
        str(schedule.frequency_weight),
        "--frequency-warmup",
        "0",
        "--frequency-ramp",
        "40",
        "--scale-growth-weight",
        str(schedule.scale_growth_weight),
        "--mass-weight",
        str(schedule.mass_weight),
        "--anchor-weight",
        str(schedule.anchor_weight),
        "--center-limit-factor",
        str(schedule.center_limit),
        "--scale-factor",
        str(schedule.scale_factor),
        "--rotation-degrees",
        str(schedule.rotation_degrees),
        "--anisotropy-boost",
        "1.0",
        "--max-anisotropy",
        "8",
        "--log-every",
        "20",
        "--seed",
        "20260727",
        "--device",
        "cuda",
    ]


def strict_gate(metrics: dict, baseline: dict) -> bool:
    return (
        metrics["tau_psnr_db"] >= baseline["tau_psnr_db"]
        and metrics["tau_mae"] <= baseline["tau_mae"]
        and metrics["transmittance_psnr_foreground_db"]
        >= baseline["foreground_t_psnr_db"]
        and metrics["edge_l1"] <= baseline["edge_l1"]
        and metrics["gabor_energy_l1"] <= baseline["gabor_energy_l1"]
        and metrics["gabor_phase_energy_l1"]
        <= baseline["gabor_phase_energy_l1"]
        and metrics["silhouette_iou"] >= baseline["silhouette_iou"]
    )


def bounded_gate(metrics: dict, baseline: dict, order: float, base_order: float) -> bool:
    return (
        metrics["tau_psnr_db"] >= baseline["tau_psnr_db"] - 0.05
        and metrics["tau_mae"] <= baseline["tau_mae"] * 1.005
        and metrics["transmittance_psnr_foreground_db"]
        >= baseline["foreground_t_psnr_db"] - 0.05
        and metrics["edge_l1"] <= baseline["edge_l1"] * 1.005
        and metrics["gabor_energy_l1"] <= baseline["gabor_energy_l1"] * 1.005
        and metrics["gabor_phase_energy_l1"]
        <= baseline["gabor_phase_energy_l1"] * 1.005
        and metrics["silhouette_iou"] >= baseline["silhouette_iou"] - 0.0011
        and order <= base_order * 0.98
    )


def validate_output(path: Path) -> dict:
    data = np.load(path)
    centers = data["center_m"]
    covariances = data["covariance_m2"]
    extinction = data["sigma_t_per_m"]
    if (
        centers.shape != (COUNT, 3)
        or covariances.shape != (COUNT, 3, 3)
        or extinction.shape != (COUNT,)
        or not all(np.isfinite(item).all() for item in (centers, covariances, extinction))
        or np.any(extinction <= 0.0)
    ):
        raise ValueError("invalid fixed-budget recovery output")
    minimum_eigenvalue = float(np.linalg.eigvalsh(covariances).min())
    if minimum_eigenvalue <= 0.0:
        raise ValueError("recovered covariance is not positive definite")
    return {
        "count": COUNT,
        "minimum_covariance_eigenvalue": minimum_eigenvalue,
        "mass": float(masses(data).sum()),
    }


def self_check() -> None:
    lattice = np.stack(np.meshgrid(*(np.arange(4.0),) * 3, indexing="ij"), axis=-1).reshape(-1, 3)
    assert math.isclose(lattice_order(lattice, 1.0), 1.0, abs_tol=1e-12)
    rng = np.random.default_rng(1)
    assert lattice_order(lattice + rng.uniform(-0.2, 0.2, lattice.shape), 1.0) < 0.9
    baseline = {
        "tau_psnr_db": 1.0,
        "tau_mae": 1.0,
        "foreground_t_psnr_db": 1.0,
        "edge_l1": 1.0,
        "gabor_energy_l1": 1.0,
        "gabor_phase_energy_l1": 1.0,
        "silhouette_iou": 1.0,
    }
    metrics = {
        "tau_psnr_db": 1.1,
        "tau_mae": 0.9,
        "transmittance_psnr_foreground_db": 1.1,
        "edge_l1": 0.9,
        "gabor_energy_l1": 0.9,
        "gabor_phase_energy_l1": 0.9,
        "silhouette_iou": 1.0,
    }
    assert strict_gate(metrics, baseline)


def run(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "summary.json"
    baseline = json.loads(BASE_REPORT.read_text(encoding="utf-8"))[
        "heldout_1000_ray_metrics"
    ]
    base_data = np.load(BASE)
    shape = np.asarray(np.load(GRID, mmap_mode="r").shape)
    pitch_m = BLOCK_SIZE * (1000.0 / float(np.max(shape))) / 100.0
    base_order = lattice_order(base_data["center_m"], pitch_m)
    rows: list[dict] = []
    started = time.time()

    for schedule in SCHEDULES:
        for fraction in JITTER_FRACTIONS:
            label = f"{schedule.name}_j{fraction:.3f}".replace(".", "p")
            candidate = root / label
            initializer = candidate / "initializer.npz"
            recovery = candidate / "recovery"
            report_path = recovery / "recovery_report.json"
            initializer_report = candidate / "initializer_report.json"
            if not initializer.exists():
                write_json(
                    initializer_report,
                    make_initializer(BASE, GRID, fraction, initializer),
                )
            initial = json.loads(initializer_report.read_text(encoding="utf-8"))
            if not report_path.exists():
                candidate.mkdir(parents=True, exist_ok=True)
                with (candidate / "train.stdout.log").open(
                    "w", encoding="utf-8"
                ) as stdout, (candidate / "train.stderr.log").open(
                    "w", encoding="utf-8"
                ) as stderr:
                    result = subprocess.run(
                        command(schedule, initializer, recovery),
                        cwd=Path(__file__).parent,
                        stdout=stdout,
                        stderr=stderr,
                        check=False,
                    )
                if result.returncode:
                    raise RuntimeError(f"{label} training failed with {result.returncode}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            validation = validate_output(recovery / "recovered.npz")
            metrics = report["final_metrics"]
            row = {
                "label": label,
                "schedule": schedule.name,
                "jitter_fraction": fraction,
                "initializer": initial,
                "metrics": metrics,
                "validation": validation,
                "strict_gate": strict_gate(metrics, baseline),
                "bounded_gate": bounded_gate(
                    metrics, baseline, initial["lattice_order"], base_order
                ),
                "output": str((recovery / "recovered.npz").resolve()),
            }
            rows.append(row)
            write_json(
                summary_path,
                {
                    "status": "running",
                    "baseline": baseline,
                    "baseline_lattice_order": base_order,
                    "elapsed_minutes": (time.time() - started) / 60.0,
                    "completed": rows,
                },
            )

    strict = [row for row in rows if row["strict_gate"]]
    bounded = [row for row in rows if row["bounded_gate"]]
    selected = min(strict, key=lambda row: row["initializer"]["lattice_order"]) if strict else None
    summary = {
        "status": "complete",
        "baseline": baseline,
        "baseline_lattice_order": base_order,
        "elapsed_minutes": (time.time() - started) / 60.0,
        "completed": rows,
        "strict_candidates": [row["label"] for row in strict],
        "bounded_candidates": [row["label"] for row in bounded],
        "selected_strict_candidate": selected,
        "ue_deployed": False,
        "note": "No UE deployment before user live visual Gate.",
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=ARTIFACTS / "wdas_404k_degrid_overnight"
    )
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("run_degrid_overnight self-check passed")
        return
    print(json.dumps(run(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
