"""Render fixed unseen views and score Gaussian/Gabor volume checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np


def _psnr(mse: float, data_range: float) -> float:
    return math.inf if mse == 0.0 else 10.0 * math.log10(data_range * data_range / mse)


def compute_metrics(
    reference_transmittance: np.ndarray,
    candidate_tau: np.ndarray,
    *,
    alpha_threshold: float = 0.01,
    epsilon: float = 1e-6,
) -> dict:
    """Compute pooled metrics; only the reference defines foreground."""
    if not 0.0 < alpha_threshold <= 1.0:
        raise ValueError("alpha_threshold must be in (0, 1]")
    if not 0.0 < epsilon < 1.0:
        raise ValueError("epsilon must be in (0, 1)")

    ref_t = np.asarray(reference_transmittance, dtype=np.float64)
    cand_tau = np.asarray(candidate_tau, dtype=np.float64)
    if ref_t.shape != cand_tau.shape:
        raise ValueError(f"shape mismatch: reference {ref_t.shape}, candidate {cand_tau.shape}")
    if not np.isfinite(ref_t).all() or not np.isfinite(cand_tau).all():
        raise ValueError("inputs contain NaN or infinity")

    ref_t = np.clip(ref_t, epsilon, 1.0)
    ref_tau = -np.log(ref_t)
    foreground = (1.0 - ref_t) >= alpha_threshold
    foreground_pixels = int(foreground.sum())
    if foreground_pixels == 0:
        raise ValueError("reference foreground mask is empty")

    # The exponent clamp is only an overflow guard. Negative candidate tau is
    # left visible as T > 1 and is therefore penalized by the metrics.
    cand_t = np.exp(np.clip(-cand_tau, -80.0, 80.0))
    tau_error = cand_tau[foreground] - ref_tau[foreground]
    tau_mse = float(np.mean(tau_error * tau_error))
    tau_peak = float(np.max(ref_tau[foreground]))
    trans_error = cand_t - ref_t
    trans_mse = float(np.mean(trans_error * trans_error))
    trans_fg_mse = float(np.mean(trans_error[foreground] ** 2))

    candidate_foreground = (1.0 - cand_t) >= alpha_threshold
    union = int(np.logical_or(foreground, candidate_foreground).sum())
    intersection = int(np.logical_and(foreground, candidate_foreground).sum())

    return {
        "foreground_definition": (
            "reference alpha = 1 - clamp(T_ref, epsilon, 1); foreground iff "
            "alpha >= alpha_threshold; background is the complement. Tau metrics "
            "and foreground transmittance PSNR exclude background; full "
            "transmittance PSNR includes every pixel."
        ),
        "alpha_threshold": alpha_threshold,
        "epsilon": epsilon,
        "foreground_pixels": foreground_pixels,
        "foreground_fraction": foreground_pixels / int(ref_t.size),
        "tau_data_range": tau_peak,
        "tau_psnr_db": _psnr(tau_mse, tau_peak),
        "tau_mae": float(np.mean(np.abs(tau_error))),
        "transmittance_psnr_full_db": _psnr(trans_mse, 1.0),
        "transmittance_psnr_foreground_db": _psnr(trans_fg_mse, 1.0),
        "silhouette_iou": 1.0 if union == 0 else intersection / union,
        "candidate_negative_tau_fraction": float(np.mean(cand_tau < 0.0)),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _vertex_count(path: Path) -> int:
    with path.open("rb") as stream:
        for line in stream:
            words = line.decode("ascii").strip().split()
            if words[:2] == ["element", "vertex"]:
                return int(words[2])
            if words[:1] == ["end_header"]:
                break
    raise ValueError(f"PLY has no vertex count: {path}")


def _exrs(path: Path) -> list[Path]:
    return sorted(path.glob("*.exr"))


def _prepare_cache(path: Path, config: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    config_path = path / "render_config.json"
    if config_path.exists():
        if json.loads(config_path.read_text(encoding="utf-8")) != config:
            raise ValueError(f"cache parameters changed; use a new directory: {path}")
    elif _exrs(path):
        raise ValueError(f"unidentified EXRs already exist in {path}")
    else:
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _read_scalar_exr(path: Path) -> np.ndarray:
    import mitsuba as mi

    image = np.asarray(mi.Bitmap(str(path)), dtype=np.float32)
    return image if image.ndim == 2 else image[..., : min(3, image.shape[-1])].mean(axis=-1)


def score(reference_dir: Path, candidate_dir: Path, threshold: float, epsilon: float) -> dict:
    references, candidates = _exrs(reference_dir), _exrs(candidate_dir)
    if not references or [p.name for p in references] != [p.name for p in candidates]:
        raise ValueError("reference and candidate EXR sets must be non-empty and have identical names")
    ref_t = np.stack([_read_scalar_exr(path) for path in references])
    cand_tau = np.stack([_read_scalar_exr(path) for path in candidates])
    result = compute_metrics(ref_t, cand_tau, alpha_threshold=threshold, epsilon=epsilon)
    result["views"] = len(references)
    result["resolution"] = [int(ref_t.shape[2]), int(ref_t.shape[1])]
    return result


def _pad_to_cube(grid: np.ndarray) -> np.ndarray:
    size = max(grid.shape)
    before = [(size - axis) // 2 for axis in grid.shape]
    return np.pad(grid, [(p, size - axis - p) for p, axis in zip(before, grid.shape)])


def render(
    checkpoint: Path,
    gfields_root: Path,
    reference_dir: Path,
    candidate_dir: Path,
    options: argparse.Namespace,
) -> tuple[Path, int, dict]:
    sys.path.insert(0, str(gfields_root))
    import drjit as dr
    import mitsuba as mi

    mi.set_variant("cuda_ad_rgb", "llvm_ad_rgb")
    import gfields  # noqa: F401  (registers custom plugins)
    from gfields.training.configs import get_volume_config
    from gfields.training.regression import load_model, prepare_cameras, render_sensor_chunked

    train_args = json.loads((checkpoint / "args.json").read_text(encoding="utf-8"))
    grid_path = Path(train_args["volume_grid"]).resolve()
    asset_path = checkpoint / "optimized_asset_pyr0"
    ply_path = asset_path / "data" / "root.primitives_pyr0.ply"
    if not grid_path.is_file() or not ply_path.is_file():
        raise FileNotFoundError(f"missing grid or completed checkpoint PLY: {grid_path}, {ply_path}")

    train_count = options.train_camera_count or int(train_args["cam_count"])
    heldout_count = options.heldout_camera_count
    resolution = options.resolution or int(train_args["cam_res_x"])
    cam_scale = float(train_args["cam_scale"])
    cam_y_offset = float(train_args["cam_y_offset"])
    hemisphere = bool(train_args["sample_single_hemisphere"])
    opacity_scale = float(train_args["opacity_scale"])
    ref_spp = options.reference_spp or int(train_args["ref_spp"])
    ref_chunk = options.reference_spp_chunk or int(train_args["ref_spp_chunk"])
    candidate_spp = options.candidate_spp or int(train_args["ref_kernel_spp"])
    if train_count < 0 or heldout_count <= 0 or resolution <= 0:
        raise ValueError("camera counts and resolution must be positive (train count may be zero)")
    if ref_spp <= 0 or ref_chunk <= 0 or candidate_spp <= 0:
        raise ValueError("render SPP values must be positive")

    np.random.seed(0)
    cameras = prepare_cameras(
        train_count + heldout_count,
        resolution,
        resolution,
        cam_scale=cam_scale,
        cam_y_offset=cam_y_offset,
        sample_single_hemisphere=hemisphere,
    )[train_count:]
    camera_spec = {
        "generator": "gfields.training.regression.prepare_cameras",
        "sequence": "Halton(2,3)" if hemisphere else "seed-0 arc with random elevation",
        "indices": list(range(train_count, train_count + heldout_count)),
        "resolution": [resolution, resolution],
        "cam_scale": cam_scale,
        "cam_y_offset": cam_y_offset,
        "sample_single_hemisphere": hemisphere,
    }
    reference_config = {
        "kind": "voxel_transmittance",
        "grid": str(grid_path),
        "grid_sha256": _sha256(grid_path),
        "pad_grid": bool(train_args["pad_grid"]),
        "opacity_scale": opacity_scale,
        "spp": ref_spp,
        "spp_chunk": ref_chunk,
        "cameras": camera_spec,
    }
    candidate_config = {
        "kind": "checkpoint_optical_depth",
        "checkpoint_ply": str(ply_path.resolve()),
        "checkpoint_sha256": _sha256(ply_path),
        "use_anyhit": options.use_anyhit,
        "spp": candidate_spp,
        "cameras": camera_spec,
    }
    _prepare_cache(reference_dir, reference_config)
    _prepare_cache(candidate_dir, candidate_config)

    if len(_exrs(reference_dir)) != heldout_count:
        grid = np.load(grid_path).squeeze().astype(np.float32, copy=False)
        if train_args["pad_grid"]:
            grid = _pad_to_cube(grid)
        volume_config = get_volume_config(str(grid_path), opacity_scale=opacity_scale)
        reference_scene = mi.load_dict({
            "type": "scene",
            "integrator": {
                "type": "gfields_reference",
                "background": 1.0,
                "to_world": volume_config.to_world,
                "sigma_t": {
                    "type": "gridvolume",
                    "data": mi.TensorXf(grid * opacity_scale),
                    "to_world": volume_config.to_world,
                },
            },
        })
        for offset, camera in enumerate(cameras):
            path = reference_dir / f"{offset:04d}.exr"
            if not path.exists():
                image = render_sensor_chunked(
                    reference_scene,
                    camera,
                    ref_spp,
                    seed=train_count + offset,
                    chunk_spp=ref_chunk,
                )
                mi.util.write_bitmap(str(path), image)
                del image
        del reference_scene, grid
        dr.flush_malloc_cache()

    if len(_exrs(candidate_dir)) != heldout_count:
        scene_dict = load_model(checkpoint, max_depth=-1, integrator_type="gfields_tomography")
        scene_dict["integrator"].update(
            output="optical_depth", use_anyhit=options.use_anyhit
        )
        candidate_scene = mi.load_dict(scene_dict)
        for offset, camera in enumerate(cameras):
            path = candidate_dir / f"{offset:04d}.exr"
            if not path.exists():
                image = mi.render(
                    candidate_scene,
                    sensor=camera,
                    spp=candidate_spp,
                    seed=train_count + offset,
                )
                mi.util.write_bitmap(str(path), image)
                del image
        del candidate_scene
        dr.flush_malloc_cache()

    return ply_path, _vertex_count(ply_path), camera_spec


def main() -> None:
    workspace = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="training output containing args.json")
    parser.add_argument("--gfields-root", type=Path, default=workspace / "tmp" / "gabor_fields")
    parser.add_argument("--reference-cache", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--train-camera-count", type=int)
    parser.add_argument("--heldout-camera-count", type=int, default=8)
    parser.add_argument("--resolution", type=int)
    parser.add_argument("--reference-spp", type=int)
    parser.add_argument("--reference-spp-chunk", type=int)
    parser.add_argument("--candidate-spp", type=int)
    parser.add_argument("--alpha-threshold", type=float, default=0.01)
    parser.add_argument("--epsilon", type=float, default=1e-6)
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--use-anyhit", action="store_true")
    args = parser.parse_args()

    checkpoint = args.checkpoint.resolve()
    train_args = json.loads((checkpoint / "args.json").read_text(encoding="utf-8"))
    train_count = args.train_camera_count or int(train_args["cam_count"])
    resolution = args.resolution or int(train_args["cam_res_x"])
    reference_dir = (args.reference_cache or (
        checkpoint.parent.parent / "evaluation" /
        f"heldout_{train_count}_{train_count + args.heldout_camera_count - 1}_{resolution}" / "reference"
    )).resolve()
    output = (args.output or checkpoint / "heldout_eval").resolve()
    candidate_dir = output / "candidate_tau"

    ply_path = checkpoint / "optimized_asset_pyr0" / "data" / "root.primitives_pyr0.ply"
    camera_spec = None
    primitive_count = _vertex_count(ply_path)
    if not args.score_only:
        ply_path, primitive_count, camera_spec = render(
            checkpoint, args.gfields_root.resolve(), reference_dir, candidate_dir, args
        )
    else:
        camera_spec = json.loads(
            (reference_dir / "render_config.json").read_text(encoding="utf-8")
        )["cameras"]

    metrics = score(reference_dir, candidate_dir, args.alpha_threshold, args.epsilon)
    report = {
        "checkpoint": str(checkpoint),
        "checkpoint_ply_sha256": _sha256(ply_path),
        "primitive_count": primitive_count,
        "reference_cache": str(reference_dir),
        "candidate_tau": str(candidate_dir),
        "heldout_cameras": camera_spec,
        "metrics": metrics,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
