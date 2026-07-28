#***REngine Begin Modify added by tuckersu. [Add 7DRGS training entry: light-conditioned slicing + J(G-gain) + mask BCE + depth]
#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

"""train_7drgs.py — Relightable 7DGS training.

Slices the 7D gaussians under the per-image virtual LIGHT direction (decoupled
from the rasterization camera) and supervises the linear transmittance J with:

    L = (1-l)*L1(G*J*M, G*J_gt*M) + l*(1 - SSIM(G*J, G*J_gt))
        + lambda_mask * BCE(coverage, M)
        + depth_w(it) * |(invdepth_pred - invdepth_gt) * depth_mask|

The global gain G lifts the tiny J (~0.02) into O(1) so both L1 and SSIM stay in
their healthy regime (SSIM constants C1/C2 are tuned for dynamic range 1).

Usage:
    python train_7drgs.py -s data/RelightDataset -m output/7drgs \
        --j_gain 20 --j_init 0.02 --lambda_mask_bce 0.05
"""

import os
import sys
import uuid
import torch
from random import randint
from tqdm import tqdm
from argparse import ArgumentParser, Namespace

from utils.loss_utils import l1_loss, ssim
from utils.general_utils import safe_state, get_expon_lr_func
from utils.image_utils import psnr
from scene.gaussian_model_7drgs import GaussianModel7DRGS
from scene.dataset_7drgs import Dataset7DRGS
from gaussian_renderer.render_7drgs import render_7drgs
from utils.transmittance_utils import _bce_loss
from arguments import ModelParams, PipelineParams, OptimizationParams

try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_FOUND = True
except ImportError:
    TENSORBOARD_FOUND = False

try:
    from fused_ssim import fused_ssim
    FUSED_SSIM_AVAILABLE = True
except Exception:
    FUSED_SSIM_AVAILABLE = False


def prepare_output_and_logger(args):
    if not args.model_path:
        unique_str = os.getenv("OAR_JOB_ID") if os.getenv("OAR_JOB_ID") else str(uuid.uuid4())
        args.model_path = os.path.join("./output/", unique_str[0:10])

    print("Output folder: {}".format(args.model_path))
    os.makedirs(args.model_path, exist_ok=True)
    with open(os.path.join(args.model_path, "cfg_args"), "w") as cfg_log_f:
        cfg_log_f.write(str(Namespace(**vars(args))))

    if TENSORBOARD_FOUND:
        return SummaryWriter(args.model_path)
    print("Tensorboard not available: not logging progress")
    return None


def save_point_cloud(gaussians, model_path, iteration):
    path = os.path.join(model_path, "point_cloud", f"iteration_{iteration}", "point_cloud.ply")
    print(f"\n[ITER {iteration}] Saving Gaussians -> {path}")
    gaussians.save_ply(path)


def training_report(tb_writer, iteration, ll1, loss, elapsed, testing_iterations,
                    dataset, gaussians, pipe, background, light_lookup, j_gain):
    if tb_writer:
        tb_writer.add_scalar("train_loss_patches/l1_loss", ll1, iteration)
        tb_writer.add_scalar("train_loss_patches/total_loss", loss, iteration)
        tb_writer.add_scalar("iter_time", elapsed, iteration)

    if iteration not in testing_iterations:
        return

    torch.cuda.empty_cache()
    validation_configs = (
        {"name": "test", "cameras": dataset.getTestCameras()},
        {"name": "train", "cameras": [dataset.getTrainCameras()[idx % len(dataset.getTrainCameras())]
                                      for idx in range(5, 30, 5)]},
    )

    for config in validation_configs:
        cams = config["cameras"]
        if not cams:
            continue
        l1_test = 0.0
        psnr_test = 0.0
        tview_l1_test = 0.0
        tau_l1_test = 0.0
        mask_iou_test = 0.0
        invdepth_l1_test = 0.0
        for viewpoint in cams:
            render_pkg = render_7drgs(
                viewpoint, gaussians, pipe, background,
                light_dir=viewpoint.light_dir,
                need_coverage=True,
                render_tview=True,
            )
            J = render_pkg["render"]
            gt = viewpoint.original_image.to("cuda")
            # Evaluate in gain space (visual scale), masked to foreground.
            M = viewpoint.alpha_mask.to("cuda")
            image = (j_gain * J * M).clamp(0.0, 1.0)
            gt_image = (j_gain * gt * M).clamp(0.0, 1.0)
            l1_test += l1_loss(image, gt_image).mean().double()
            psnr_test += psnr(image, gt_image).mean().double()
            foreground = M.sum().clamp_min(1.0)
            tview = render_pkg["tview"].clamp(1e-6, 1.0)
            tview_gt = viewpoint.tview_gt.to("cuda").clamp(1e-6, 1.0)
            tview_l1_test += ((tview - tview_gt).abs() * M).sum().double() / foreground
            tau_l1_test += ((tview.log() - tview_gt.log()).abs() * M).sum().double() / foreground
            predicted_mask = render_pkg["coverage"] > 0.5
            target_mask = M > 0.5
            intersection = (predicted_mask & target_mask).sum()
            union = (predicted_mask | target_mask).sum().clamp_min(1)
            mask_iou_test += intersection.double() / union
            invdepth_l1_test += (
                (render_pkg["depth"] - viewpoint.invdepthmap.to("cuda")).abs() * M
            ).sum().double() / foreground
        psnr_test /= len(cams)
        l1_test /= len(cams)
        tview_l1_test /= len(cams)
        tau_l1_test /= len(cams)
        mask_iou_test /= len(cams)
        invdepth_l1_test /= len(cams)
        print(
            f"\n[ITER {iteration}] Evaluating {config['name']}: "
            f"J L1 {l1_test} PSNR {psnr_test} "
            f"TView L1 {tview_l1_test} Tau L1 {tau_l1_test} "
            f"Mask IoU {mask_iou_test} InvDepth L1 {invdepth_l1_test}"
        )
        if tb_writer:
            tb_writer.add_scalar(f"{config['name']}/loss_viewpoint - l1_loss", l1_test, iteration)
            tb_writer.add_scalar(f"{config['name']}/loss_viewpoint - psnr", psnr_test, iteration)
            tb_writer.add_scalar(f"{config['name']}/tview_l1", tview_l1_test, iteration)
            tb_writer.add_scalar(f"{config['name']}/tau_l1", tau_l1_test, iteration)
            tb_writer.add_scalar(f"{config['name']}/mask_iou", mask_iou_test, iteration)
            tb_writer.add_scalar(f"{config['name']}/invdepth_l1", invdepth_l1_test, iteration)

    if tb_writer:
        tb_writer.add_scalar("total_points", gaussians.get_xyz.shape[0], iteration)
    torch.cuda.empty_cache()


@torch.no_grad()
def save_training_vis(iteration, gaussians, pipe, background, cameras, j_gain, out_dir,
                      tb_writer=None, render_tview=False):
    import torchvision
    """Render one RANDOM (view, light) camera and dump a side-by-side comparison
    against the dataset GT. Both panels are multiplied by the global gain G so the
    tiny transmittance J (~0.02) becomes visible to the naked eye.

    Layout (left -> right): [GT*G | Render*G | |diff|*G], all clamped to [0,1].
    When render_tview=True, an additional row is appended below:
        [T_view_GT | T_view_Render | |T_diff|], displayed without gain (T is [0,1]).
    The same grid is mirrored to TensorBoard (tag "train_vis/<image_name>") when a
    SummaryWriter is supplied, so progress is visible without leaving the browser.
    """
    if not cameras:
        return
    cam = cameras[randint(0, len(cameras) - 1)]
    pkg = render_7drgs(cam, gaussians, pipe, background, light_dir=cam.light_dir,
                       render_tview=render_tview)
    J = pkg["render"].clamp(0.0, None)              # [3,H,W] linear
    gt = cam.original_image.cuda()                  # [3,H,W] linear
    M = cam.alpha_mask.cuda()                        # [1,H,W]

    vis_gt = (j_gain * gt).clamp(0.0, 1.0)
    vis_render = (j_gain * J).clamp(0.0, 1.0)
    vis_diff = (j_gain * (J - gt).abs() * M).clamp(0.0, 1.0)
    grid = torch.cat([vis_gt, vis_render, vis_diff], dim=2)  # concat along width

    #***REngine Begin Modify added by tuckersu. [T_view dual SH: visualization output]
    if render_tview and "tview" in pkg and cam.tview_gt is not None:
        T_pred = pkg["tview"].clamp(0.0, 1.0)       # [1,H,W]
        T_gt = cam.tview_gt.cuda()                   # [1,H,W]
        T_diff = (T_pred - T_gt).abs() * M           # [1,H,W]
        # Expand single-channel to 3-channel for grid consistency
        vis_t_gt = T_gt.expand(3, -1, -1)
        vis_t_pred = T_pred.expand(3, -1, -1)
        vis_t_diff = T_diff.expand(3, -1, -1).clamp(0.0, 1.0)
        tview_row = torch.cat([vis_t_gt, vis_t_pred, vis_t_diff], dim=2)
        grid = torch.cat([grid, tview_row], dim=1)   # concat along height
    #***REngine End Modify

    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, f"iter{iteration:06d}_{cam.image_name}.png")
    torchvision.utils.save_image(grid, fname)
    if tb_writer is not None:
        # add_image expects [C,H,W] in [0,1]; share a stable tag so the TB slider
        # scrubs through the same panel across iterations.
        tb_writer.add_image(f"train_vis/{cam.image_name}", grid, iteration)
    print(f"\n[ITER {iteration}] Vis (GT|Render|diff)x{j_gain:g} -> {fname}")


def training(dataset, opt, pipe, args):
    tb_writer = prepare_output_and_logger(args)

    data = Dataset7DRGS(
        source_path=dataset.source_path,
        sh_degree=dataset.sh_degree,
        val_ratio=args.val_ratio,
        eps_near=opt.eps_near,
    )

    gaussians = GaussianModel7DRGS(
        dataset.sh_degree,
        sh_degree_t=args.sh_degree_t,
        optimizer_type=opt.optimizer_type,
        is_dynamic=False,
        lambda_t_init=dataset.lambda_t_init,
        lambda_d_init=dataset.lambda_d_init,
    )
    init_ply = os.path.join(dataset.source_path, "init_points.ply")
    gaussians.create_from_init_ply(
        init_ply, data.light_dirs, data.cameras_extent,
        j_init=args.j_init, warmup_geometry=args.warmup_geometry,
    )
    gaussians.training_setup(opt)

    # J background MUST be 0 (transmittance vanishes off the medium).
    background = torch.zeros(3, dtype=torch.float32, device="cuda")

    iter_start = torch.cuda.Event(enable_timing=True)
    iter_end = torch.cuda.Event(enable_timing=True)

    depth_l1_weight = get_expon_lr_func(opt.depth_l1_weight_init, opt.depth_l1_weight_final,
                                        max_steps=opt.iterations)

    train_cams = data.getTrainCameras()
    G = float(args.j_gain)
    lambda_mask = float(opt.lambda_mask_bce)
    lambda_tview = float(args.lambda_tview)
    # tview_detach_geom reserved for future use (detach means/cov/opacity before
    # T_view raster so only SH_T learns, no geometry feedback from T_view loss).
    # Currently NOT implemented — T_view gradient flows through shared geometry.
    densify_enabled = not args.disable_densify
    vis_dir = os.path.join(args.model_path, "train_vis")

    viewpoint_stack = train_cams.copy()
    ema_loss_for_log = 0.0
    ema_depth_for_log = 0.0
    ema_mask_for_log = 0.0
    ema_tview_for_log = 0.0

    progress_bar = tqdm(range(opt.iterations), desc="Training progress (7DRGS)")

    for iteration in range(1, opt.iterations + 1):
        iter_start.record()
        gaussians.update_learning_rate(iteration)

        if iteration % 1000 == 0:
            gaussians.oneupSHdegree()

        if not viewpoint_stack:
            viewpoint_stack = train_cams.copy()
        viewpoint_cam = viewpoint_stack.pop(randint(0, len(viewpoint_stack) - 1))

        if (iteration - 1) == args.debug_from:
            pipe.debug = True

        render_pkg = render_7drgs(
            viewpoint_cam, gaussians, pipe, background,
            light_dir=viewpoint_cam.light_dir,
            need_coverage=(lambda_mask > 0),
            render_tview=(lambda_tview > 0),
        )
        J = render_pkg["render"]                       # [3,H,W] linear, NOT clamped
        gt = viewpoint_cam.original_image.cuda()       # [3,H,W]
        M = viewpoint_cam.alpha_mask.cuda()            # [1,H,W]

        # ---- J supervision in gain space (G lifts ~0.02 -> O(1)) ----
        ll1 = l1_loss(G * J * M, G * gt * M)
        if FUSED_SSIM_AVAILABLE:
            ssim_value = fused_ssim((G * J).unsqueeze(0), (G * gt).unsqueeze(0))
        else:
            ssim_value = ssim(G * J, G * gt)
        loss = (1.0 - opt.lambda_dssim) * ll1 + opt.lambda_dssim * (1.0 - ssim_value)

        # ---- mask BCE on coverage (light-conditioned, reusing slice_for_light) ----
        # Object Mask Constraint (Relightable 3D Gaussians):
        #   L_O = -M*log(O) - (1-M)*log(1-O), where O = coverage from LIGHT slice.
        # In 7DRGS, d-dim = light_dir (no view slice). Across all training lights
        # this acts as an aggregate silhouette constraint.
        mask_bce_val = 0.0
        if lambda_mask > 0:
            coverage = render_pkg["coverage"].clamp(1e-6, 1.0 - 1e-6)  # [1,H,W]
            mask_bce_term = _bce_loss(coverage, M).mean()
            loss = loss + lambda_mask * mask_bce_term
            mask_bce_val = mask_bce_term.item()

        #***REngine Begin Modify added by tuckersu. [T_view dual SH: auxiliary T_view loss]
        # T_view supervision: L1(T_view_pred, T_view_gt) masked to foreground.
        # T_view GT comes from J_TView EXR alpha channel.
        tview_loss_val = 0.0
        if lambda_tview > 0 and "tview" in render_pkg:
            T_pred = render_pkg["tview"]               # [1,H,W]
            T_gt = viewpoint_cam.tview_gt.cuda()       # [1,H,W]
            tview_l1 = (torch.abs(T_pred - T_gt) * M).sum() / M.sum().clamp(min=1.0)
            loss = loss + lambda_tview * tview_l1
            tview_loss_val = tview_l1.item()
        #***REngine End Modify

        # ---- depth (independent depth/*.exr -> inverse depth) ----
        depth_term_val = 0.0
        if depth_l1_weight(iteration) > 0 and viewpoint_cam.depth_reliable:
            inv_depth = render_pkg["depth"]
            gt_inv = viewpoint_cam.invdepthmap.cuda()
            depth_mask = viewpoint_cam.depth_mask.cuda()
            depth_pure = torch.abs((inv_depth - gt_inv) * depth_mask).mean()
            depth_term = depth_l1_weight(iteration) * depth_pure
            loss = loss + depth_term
            depth_term_val = depth_term.item()

        loss.backward()
        iter_end.record()

        with torch.no_grad():
            ema_loss_for_log = 0.4 * loss.item() + 0.6 * ema_loss_for_log
            ema_depth_for_log = 0.4 * depth_term_val + 0.6 * ema_depth_for_log
            ema_mask_for_log = 0.4 * mask_bce_val + 0.6 * ema_mask_for_log
            ema_tview_for_log = 0.4 * tview_loss_val + 0.6 * ema_tview_for_log

            if iteration % 10 == 0:
                progress_bar.set_postfix({
                    "Loss": f"{ema_loss_for_log:.5f}",
                    "Depth": f"{ema_depth_for_log:.5f}",
                    "Mask": f"{ema_mask_for_log:.4f}",
                    "Tv": f"{ema_tview_for_log:.4f}",
                    "N": gaussians.get_xyz.shape[0],
                })
                progress_bar.update(10)
            if iteration == opt.iterations:
                progress_bar.close()

            training_report(tb_writer, iteration, ll1.item(), loss.item(),
                            iter_start.elapsed_time(iter_end), args.test_iterations,
                            data, gaussians, pipe, background, None, G)
            if tb_writer and iteration % 10 == 0:
                tb_writer.add_scalar("train_loss_patches/mask_bce", ema_mask_for_log, iteration)
                tb_writer.add_scalar("train_loss_patches/tview_l1", ema_tview_for_log, iteration)

            # ---- periodic visual comparison (random view+light, gain-scaled) ----
            if args.vis_interval > 0 and iteration % args.vis_interval == 0:
                save_training_vis(iteration, gaussians, pipe, background,
                                  train_cams, G, vis_dir, tb_writer=tb_writer,
                                  render_tview=(lambda_tview > 0))


            if iteration in args.save_iterations:
                save_point_cloud(gaussians, args.model_path, iteration)

            # ---- densification (inherited 7D-aware clone/split/prune) ----
            if densify_enabled and iteration < opt.densify_until_iter:
                visibility_filter = render_pkg["visibility_filter"]
                radii = render_pkg["radii"]
                viewspace_point_tensor = render_pkg["viewspace_points"]
                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter], radii[visibility_filter]
                )
                gaussians.add_densification_stats(viewspace_point_tensor, visibility_filter)
                if iteration > opt.densify_from_iter and iteration % opt.densification_interval == 0:
                    size_threshold = 20 if iteration > opt.opacity_reset_interval else None
                    #***REngine Begin Modify added by tuckersu. [max_points hard cap for densification]
                    # Point-budget guard: once we hit the cap, skip clone/split (prune still runs).
                    if args.max_points > 0 and gaussians.get_xyz.shape[0] >= args.max_points:
                        # Set tmp_radii so prune_points can index it safely
                        gaussians.tmp_radii = radii
                        # Only prune, no growth
                        prune_mask = (gaussians.get_opacity < 0.005).squeeze()
                        if size_threshold:
                            big_points_vs = gaussians.max_radii2D > size_threshold
                            big_points_ws = gaussians.get_scaling.max(dim=1).values > 0.1 * data.cameras_extent
                            prune_mask = prune_mask | big_points_vs | big_points_ws
                        gaussians.prune_points(prune_mask)
                        gaussians.tmp_radii = None
                    else:
                        gaussians.densify_and_prune(opt.densify_grad_threshold, 0.005,
                                                    data.cameras_extent, size_threshold, radii)
                    #***REngine End Modify
                if iteration % opt.opacity_reset_interval == 0:
                    gaussians.reset_opacity()

            #***REngine Begin Modify added by tuckersu. [Log total_points every 100 iters for dense TB curve]
            if tb_writer and iteration % 100 == 0:
                tb_writer.add_scalar("total_points", gaussians.get_xyz.shape[0], iteration)
            #***REngine End Modify

            if iteration < opt.iterations:
                gaussians.exposure_optimizer.step()
                gaussians.exposure_optimizer.zero_grad(set_to_none=True)
                gaussians.optimizer.step()
                gaussians.optimizer.zero_grad(set_to_none=True)

            if iteration in args.checkpoint_iterations:
                print(f"\n[ITER {iteration}] Saving Checkpoint")
                torch.save((gaussians.capture(), iteration),
                           os.path.join(args.model_path, f"chkpnt{iteration}.pth"))

    if tb_writer:
        tb_writer.close()


if __name__ == "__main__":
    parser = ArgumentParser(description="7DRGS (relightable 7DGS) training script parameters")
    lp = ModelParams(parser)
    op = OptimizationParams(parser)
    pp = PipelineParams(parser)

    parser.add_argument("--debug_from", type=int, default=-1)
    parser.add_argument("--detect_anomaly", action="store_true", default=False)
    parser.add_argument("--test_iterations", nargs="+", type=int, default=[7_000, 30_000])
    parser.add_argument("--save_iterations", nargs="+", type=int, default=[7_000, 30_000])
    parser.add_argument("--checkpoint_iterations", nargs="+", type=int, default=[])
    parser.add_argument("--quiet", action="store_true")
    # 7DRGS-specific (kept local; arguments/__init__.py untouched)
    parser.add_argument("--j_gain", type=float, default=20.0, help="global gain G applied to J in the loss")
    parser.add_argument("--j_init", type=float, default=0.02, help="cold-start magnitude for J DC channel")
    parser.add_argument("--val_ratio", type=float, default=0.2)
    parser.add_argument("--warmup_geometry", action="store_true", default=False,
                        help="overwrite scale/rot from init ply (degenerate here; default off)")
    parser.add_argument("--disable_densify", action="store_true", default=False)
    #***REngine Begin Modify added by tuckersu. [max_points hard cap for densification]
    parser.add_argument("--max_points", type=int, default=-1,
                        help="hard cap on Gaussian count; skip clone/split once reached "
                             "(<= 0 means unlimited). Prune still runs.")
    #***REngine End Modify
    parser.add_argument("--vis_interval", type=int, default=500,
                        help="save a random (view,light) GT|Render|diff comparison every N iters (0 disables)")
    #***REngine Begin Modify added by tuckersu. [T_view dual SH: add training args]
    parser.add_argument("--sh_degree_t", type=int, default=0,
                        help="SH degree for T_view (0=DC only, 1=4 coeffs). Default 0.")
    parser.add_argument("--lambda_tview", type=float, default=0.5,
                        help="weight for T_view L1 loss (auxiliary geometry supervision)")
    parser.add_argument("--tview_detach_geom", action="store_true", default=False,
                        help="detach means/cov/opacity before T_view raster (only learn SH_T, no geometry feedback)")
    #***REngine End Modify

    args = parser.parse_args(sys.argv[1:])
    args.use_7dgs = True
    args.save_iterations.append(args.iterations)

    print("Optimizing (7DRGS) " + args.model_path)

    safe_state(args.quiet)
    torch.autograd.set_detect_anomaly(args.detect_anomaly)

    training(lp.extract(args), op.extract(args), pp.extract(args), args)

    print("\n7DRGS training complete.")
#***REngine End Modify
