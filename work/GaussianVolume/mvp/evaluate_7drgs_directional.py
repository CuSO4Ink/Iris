"""Score 7DRGS PLYs on completely held-out light directions."""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import torch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("ply", nargs="+", type=Path)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    args = parser.parse_args()

    training = Path(__file__).resolve().parents[1] / "training" / "7drgs"
    sys.path.insert(0, str(training))
    from gaussian_renderer.render_7drgs import render_7drgs
    from scene.dataset_7drgs import Dataset7DRGS
    from scene.gaussian_model_7drgs_improved import GaussianModel7DRGSImproved

    data = Dataset7DRGS(
        str(args.dataset.resolve()), sh_degree=2, val_ratio=args.val_ratio
    )
    pipe = SimpleNamespace(
        convert_SHs_python=False,
        compute_cov3D_python=False,
        debug=False,
        antialiasing=False,
    )
    background = torch.zeros(3, dtype=torch.float32, device="cuda")
    results = {}
    for ply in args.ply:
        print(f"[evaluate] {ply}", flush=True)
        model = GaussianModel7DRGSImproved(2, sh_degree_t=1)
        model.create_from_init_ply(
            str(ply.resolve()), data.light_dirs, data.cameras_extent
        )
        model.active_sh_degree = 2
        model.active_sh_degree_t = 1
        l1_values, psnr_values = [], []
        with torch.inference_mode():
            for camera in data.getTestCameras():
                prediction = render_7drgs(
                    camera,
                    model,
                    pipe,
                    background,
                    light_dir=camera.light_dir,
                )["render"]
                mask = camera.alpha_mask.cuda()
                target = camera.original_image.cuda()
                error = (prediction * mask).clamp(0.0, 1.0) - target * mask
                l1_values.append(error.abs().mean())
                psnr_values.append(-10.0 * torch.log10(error.square().mean().clamp_min(1e-12)))
        results[f"{ply.parents[2].name}/{ply.parent.name}"] = {
            "heldout_lights": len(data.getTestCameras()),
            "l1": float(torch.stack(l1_values).mean()),
            "psnr_db": float(torch.stack(psnr_values).mean()),
        }
        del model
        gc.collect()
        torch.cuda.empty_cache()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
