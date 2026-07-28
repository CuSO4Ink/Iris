#***REngine Begin Modify added by tuckersu. [7DRGS ImprovedGS training entry with GC/LAS/RAP/MU/EAS]
import os
import sys
import random
import numpy as np
import OpenEXR
import torch
from random import randint, sample
from tqdm import tqdm
from argparse import ArgumentParser

from utils.loss_utils import bounded_parameter_regularization, l1_loss, ssim
from utils.general_utils import safe_state, get_expon_lr_func
from scene.gaussian_model_7drgs_improved import GaussianModel7DRGSImproved
from scene.dataset_7drgs import Dataset7DRGS
from gaussian_renderer.render_7drgs import render_7drgs
from utils.transmittance_utils import _bce_loss
from arguments import ModelParams, PipelineParams, OptimizationParams
from scene.improvedgs_ops import compute_current_budget, should_run_parameter_update, normalize_to_unit_range
from utils.edge_map_utils import compute_edge_map
from train_7drgs import prepare_output_and_logger, save_point_cloud, training_report, save_training_vis

try:
    from fused_ssim import fused_ssim
    FUSED_SSIM_AVAILABLE = True
except Exception:
    FUSED_SSIM_AVAILABLE = False


def _save_checkpoint(path, gaussians, iteration, args, viewpoint_stack, rap_state, gns_state):
    torch.save({
        "version": 1,
        "model": gaussians.capture(),
        "iteration": iteration,
        "stage": args.stage,
        "point_budget": int(args.final_budget),
        "remaining_cameras": [cam.image_name for cam in viewpoint_stack],
        "rap_state": rap_state,
        "gns_state": gns_state,
        "python_rng": random.getstate(),
        "numpy_rng": np.random.get_state(),
        "torch_rng": torch.get_rng_state(),
        "cuda_rng": torch.cuda.get_rng_state_all(),
    }, path)


def _compute_eas_scores(gaussians, train_cams, pipe, background, args):
    if not args.use_eas:
        return None
    if len(train_cams) == 0:
        return None

    sample_count = len(train_cams) if args.edge_sample_cams < 0 else min(int(args.edge_sample_cams), len(train_cams))
    sampled = sample(train_cams, sample_count)
    importance = torch.zeros((gaussians.get_xyz.shape[0],), dtype=torch.float32, device="cuda")
    visited = torch.zeros_like(importance, dtype=torch.bool)

    for cam in sampled:
        edge_map = getattr(cam, "edge_map", None)
        if edge_map is None:
            continue
        pkg = render_7drgs(
            cam,
            gaussians,
            pipe,
            background,
            light_dir=cam.light_dir,
            track_gradients=False,
            pixel_weights=edge_map,
            return_accum_weights=True,
        )
        accum_weights = pkg.get("accum_weights", None)
        if accum_weights is None or accum_weights.numel() == 0:
            continue
        vis = pkg["visibility_filter"]
        norm_aw = normalize_to_unit_range(accum_weights)
        importance[vis] += norm_aw[vis]
        visited[vis] = True

    if sample_count > 0:
        importance /= float(sample_count)
    if not torch.any(visited):
        return None
    return importance


def training(dataset, opt, pipe, args):
    tb_writer = prepare_output_and_logger(args)

    data = Dataset7DRGS(
        source_path=dataset.source_path,
        sh_degree=dataset.sh_degree,
        val_ratio=args.val_ratio,
        eps_near=opt.eps_near,
    )

    gaussians = GaussianModel7DRGSImproved(
        dataset.sh_degree,
        sh_degree_t=args.sh_degree_t,
        optimizer_type=opt.optimizer_type,
        is_dynamic=False,
        lambda_t_init=dataset.lambda_t_init,
        lambda_d_init=dataset.lambda_d_init,
    )
    #***REngine Begin Modify added by tuckersu. [Sync Improved/GNS schedule args into opt for shared budget and cadence]
    opt.final_budget = int(args.final_budget)
    opt.budget = int(args.budget)
    opt.budget_multiplier = float(args.budget_multiplier)
    opt.budget_warmup_until_offset = int(args.budget_warmup_until_offset)
    opt.use_las = bool(args.use_las)
    opt.split_distance = float(args.split_distance)
    opt.opacity_reduction = float(args.opacity_reduction)
    opt.opacity_reg_lr = float(args.opacity_reg_lr)
    opt.reg_interval = max(int(args.reg_interval), 1)
    opt.reg_start = int(args.reg_start)
    opt.reg_end = int(args.reg_end)
    #***REngine End Modify

    gaussians.training_stage = args.stage
    resume_state = None
    first_iteration = 0
    init_ply = os.path.abspath(
        args.init_ply or os.path.join(dataset.source_path, "init_points.ply")
    )
    if args.resume:
        resume_state = torch.load(args.resume, map_location="cuda", weights_only=False)
        stage_transition = (resume_state["stage"], args.stage)
        if resume_state["stage"] != args.stage and stage_transition != ("smoke", "relight"):
            raise ValueError(
                f"checkpoint stage {resume_state['stage']} != requested stage {args.stage}"
            )
        if int(resume_state["point_budget"]) != int(args.final_budget):
            raise ValueError("checkpoint point budget does not match --final_budget")
        gaussians.restore(resume_state["model"], opt)
        first_iteration = int(resume_state["iteration"])
    else:
        gaussians.create_from_init_ply(
            init_ply,
            data.light_dirs,
            data.cameras_extent,
            j_init=args.j_init,
            warmup_geometry=args.warmup_geometry,
        )
        gaussians.training_setup(opt)
    if args.activate_max_sh_degree:
        gaussians.active_sh_degree = gaussians.max_sh_degree
    if args.stage in ("smoke", "relight"):
        gaussians.restore_spatial_cholesky_from_ply(init_ply)
    if resume_state:
        gaussians.load_teacher_anchors_from_ply(init_ply)

    background = torch.zeros(3, dtype=torch.float32, device="cuda")

    iter_start = torch.cuda.Event(enable_timing=True)
    iter_end = torch.cuda.Event(enable_timing=True)

    depth_l1_weight = get_expon_lr_func(
        opt.depth_l1_weight_init,
        opt.depth_l1_weight_final,
        max_steps=opt.iterations,
    )

    train_cams = data.getTrainCameras()
    G = float(args.j_gain)
    # B2 T_view is zero-color over a white background; static opacity carries T.
    static_stage = args.stage in ("smoke", "relight")
    lambda_mask = 0.0 if static_stage else float(opt.lambda_mask_bce)
    lambda_tview = 0.0 if static_stage else float(args.lambda_tview)
    densify_enabled = not args.disable_densify
    vis_dir = os.path.join(args.model_path, "train_vis")

    if args.use_eas:
        for cam in train_cams:
            cam.edge_map = compute_edge_map(G * cam.original_image, cam.alpha_mask).to("cuda", non_blocking=True)

    rap_state = {
        "rap_reset_count": 0,
        "rap_trigger_iterations": set(),
    }

    #***REngine Begin Modify added by tuckersu. [GNS natural-selection state machine and safety guard]
    gns_state = {
        "prune_reg_active": bool(args.use_gns),
        "opacity_min": None,
        "opacity_reg_lr": float(args.opacity_reg_lr),
        "prune_iter": -1,
        "lr_boosted": False,
        "lr_restored": False,
    }
    if args.use_gns:
        assert int(args.reg_start) >= int(opt.densify_until_iter), (
            f"GNS reg_start ({args.reg_start}) must be >= densify_until_iter ({opt.densify_until_iter})."
        )
    gns_reg_interval = max(int(args.reg_interval), 1)
    #***REngine End Modify

    if resume_state:
        camera_by_name = {cam.image_name: cam for cam in train_cams}
        viewpoint_stack = [
            camera_by_name[name] for name in resume_state["remaining_cameras"]
        ]
    else:
        viewpoint_stack = train_cams.copy()
    ema_loss_for_log = 0.0
    ema_depth_for_log = 0.0
    ema_mask_for_log = 0.0
    ema_tview_for_log = 0.0
    #***REngine Begin Modify added by tuckersu. [Track GNS regularization for logging]
    ema_gns_reg_for_log = 0.0
    ema_bound_reg_for_log = 0.0
    #***REngine End Modify

    progress_bar = tqdm(
        total=opt.iterations,
        initial=first_iteration,
        desc="Training progress (7DRGS Improved)",
    )

    if resume_state:
        rap_state = resume_state["rap_state"]
        gns_state = resume_state["gns_state"]
        random.setstate(resume_state["python_rng"])
        np.random.set_state(resume_state["numpy_rng"])
        torch.set_rng_state(resume_state["torch_rng"].cpu())
        torch.cuda.set_rng_state_all(
            [state.cpu() for state in resume_state["cuda_rng"]]
        )

    for iteration in range(first_iteration + 1, opt.iterations + 1):
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
            viewpoint_cam,
            gaussians,
            pipe,
            background,
            light_dir=viewpoint_cam.light_dir,
            need_coverage=(lambda_mask > 0),
            render_tview=(lambda_tview > 0),
            track_gradients=True,
            return_accum_weights=False,
        )
        J = render_pkg["render"]
        gt = viewpoint_cam.original_image.cuda()
        M = viewpoint_cam.alpha_mask.cuda()

        ll1 = l1_loss(G * J * M, G * gt * M)
        if FUSED_SSIM_AVAILABLE:
            ssim_value = fused_ssim((G * J).unsqueeze(0), (G * gt).unsqueeze(0))
        else:
            ssim_value = ssim(G * J, G * gt)
        loss = (1.0 - opt.lambda_dssim) * ll1 + opt.lambda_dssim * (1.0 - ssim_value)

        mask_bce_val = 0.0
        if lambda_mask > 0:
            coverage = render_pkg["coverage"].clamp(1e-6, 1.0 - 1e-6)
            mask_bce_term = _bce_loss(coverage, M).mean()
            loss = loss + lambda_mask * mask_bce_term
            mask_bce_val = mask_bce_term.item()

        tview_loss_val = 0.0
        if lambda_tview > 0 and "tview" in render_pkg:
            T_pred = render_pkg["tview"]
            T_gt = viewpoint_cam.tview_gt.cuda()
            tview_l1 = (torch.abs(T_pred - T_gt) * M).sum() / M.sum().clamp(min=1.0)
            loss = loss + lambda_tview * tview_l1
            tview_loss_val = tview_l1.item()

        depth_term_val = 0.0
        if (
            not static_stage
            and depth_l1_weight(iteration) > 0
            and viewpoint_cam.depth_reliable
        ):
            inv_depth = render_pkg["depth"]
            gt_inv = viewpoint_cam.invdepthmap.cuda()
            depth_mask = viewpoint_cam.depth_mask.cuda()
            depth_pure = torch.abs((inv_depth - gt_inv) * depth_mask).mean()
            depth_term = depth_l1_weight(iteration) * depth_pure
            loss = loss + depth_term
            depth_term_val = depth_term.item()

        covariance_parameters = tuple(
            parameter
            for parameter in (
                gaussians._cholesky_diag,
                gaussians._cholesky_offdiag,
            )
            if parameter.requires_grad
        )
        sh_reg, sigma_reg = bounded_parameter_regularization(
            gaussians._features_rest,
            gaussians._features_rest_t,
            covariance_parameters,
        )
        teacher_anchor = gaussians.teacher_anchor_loss()
        j_values = render_pkg["j_values"]
        energy_reg = (
            torch.relu(-j_values).square() + torch.relu(j_values - 1.0).square()
        ).mean()
        bound_reg = (
            opt.lambda_sh_reg * sh_reg
            + opt.lambda_sigma_reg * sigma_reg
            + args.lambda_teacher_anchor * teacher_anchor
            + args.lambda_energy_reg * energy_reg
        )
        loss = loss + bound_reg
        bound_reg_val = bound_reg.item()

        #***REngine Begin Modify added by tuckersu. [Inject GNS opacity natural-selection regularizer]
        gns_reg_val = 0.0
        if (
            args.use_gns
            and gns_state["prune_reg_active"]
            and args.reg_end >= iteration >= args.reg_start
            and (iteration - 1) % gns_reg_interval == 0
        ):
            if gns_state["opacity_min"] is None:
                sorted_vals, _ = torch.sort(gaussians.get_opacity.flatten())
                idx = max(int(gaussians.get_opacity.shape[0]) - int(args.final_budget), 0)
                baseline = sorted_vals[idx].item()
                gns_state["opacity_min"] = baseline * 0.8
            elif (iteration - 1) % 100 == 0:
                denom = max(int(args.reg_end) - int(args.reg_start) - 1000, 1)
                opacity_goal = max(
                    (1.0 - (iteration - int(args.reg_start)) / float(denom)) * float(gns_state["opacity_min"]),
                    0.0,
                )
                sorted_vals, _ = torch.sort(gaussians.get_opacity.flatten())
                idx = max(int(gaussians.get_opacity.shape[0]) - int(args.final_budget), 0)
                cur_val = sorted_vals[idx].item()
                if cur_val < opacity_goal * 0.9:
                    gns_state["opacity_reg_lr"] *= 0.8
                elif cur_val > opacity_goal * 1.1:
                    gns_state["opacity_reg_lr"] *= 1.2

            reg_lr = float(gns_state["opacity_reg_lr"])
            if iteration < int(args.reg_start) + 1000:
                rate_l = torch.max(
                    torch.ones_like(gaussians.get_opacity) * 0.05,
                    1.0 - gaussians.get_opacity,
                )
                reg_term = reg_lr * (torch.mean((gaussians._opacity + 20.0) / rate_l)) ** 2
            else:
                reg_term = 3.0 * reg_lr * (torch.mean(gaussians._opacity) + 20.0) ** 2
            loss = loss + reg_term
            gns_reg_val = reg_term.item()
        #***REngine End Modify

        loss.backward()
        iter_end.record()

        with torch.no_grad():
            ema_loss_for_log = 0.4 * loss.item() + 0.6 * ema_loss_for_log
            ema_depth_for_log = 0.4 * depth_term_val + 0.6 * ema_depth_for_log
            ema_mask_for_log = 0.4 * mask_bce_val + 0.6 * ema_mask_for_log
            ema_tview_for_log = 0.4 * tview_loss_val + 0.6 * ema_tview_for_log
            #***REngine Begin Modify added by tuckersu. [EMA logging for GNS regularization term]
            ema_gns_reg_for_log = 0.4 * gns_reg_val + 0.6 * ema_gns_reg_for_log
            ema_bound_reg_for_log = 0.4 * bound_reg_val + 0.6 * ema_bound_reg_for_log
            #***REngine End Modify

            if iteration % 10 == 0:
                progress_bar.set_postfix({
                    "Loss": f"{ema_loss_for_log:.5f}",
                    "Depth": f"{ema_depth_for_log:.5f}",
                    "Mask": f"{ema_mask_for_log:.4f}",
                    "Tv": f"{ema_tview_for_log:.4f}",
                    "Reg": f"{ema_bound_reg_for_log:.4f}",
                    "GNS": f"{ema_gns_reg_for_log:.4f}",
                    "N": gaussians.get_xyz.shape[0],
                })
                progress_bar.update(10)
            if iteration == opt.iterations:
                progress_bar.close()

            training_report(
                tb_writer,
                iteration,
                ll1.item(),
                loss.item(),
                iter_start.elapsed_time(iter_end),
                args.test_iterations,
                data,
                gaussians,
                pipe,
                background,
                None,
                G,
            )

            #***REngine Begin Modify added by tuckersu. [Run GNS prune schedule and opacity-LR cadence]
            if args.use_gns:
                if args.gns_early_prune:
                    if iteration == 300:
                        gaussians.only_prune(0.02)
                    elif iteration in (3300, 6300):
                        gaussians.only_prune(0.2, percent=True)

                should_early_final = (
                    gns_state["prune_reg_active"]
                    and (not args.no_final_prune)
                    and iteration > int(args.reg_start)
                    and int(gaussians.get_opacity.shape[0]) < int(args.final_budget * 1.05)
                )
                if should_early_final:
                    gaussians.final_prune(int(args.final_budget))
                    gns_state["prune_reg_active"] = False
                    gns_state["prune_iter"] = iteration

                if gns_state["prune_reg_active"] and int(args.reg_end) > iteration >= int(args.reg_start):
                    if iteration == int(args.reg_start) and (not gns_state["lr_boosted"]):
                        gaussians.update_opacity_lr(4.0)
                        gns_state["lr_boosted"] = True

                    if (iteration % gns_reg_interval == 0) and (iteration >= int(args.reg_start) + 1000):
                        gaussians.only_prune(0.001)
                elif (
                    gns_state["prune_reg_active"]
                    and (not args.no_final_prune)
                    and iteration == int(args.reg_end)
                ):
                    gaussians.final_prune(int(args.final_budget))
                    gns_state["prune_reg_active"] = False
                    gns_state["prune_iter"] = iteration

                if (
                    gns_state["prune_iter"] > 0
                    and iteration == int(gns_state["prune_iter"]) + 1000
                    and gns_state["lr_boosted"]
                    and (not gns_state["lr_restored"])
                ):
                    gaussians.update_opacity_lr(0.25)
                    gns_state["lr_restored"] = True
            #***REngine End Modify

            if tb_writer and iteration % 10 == 0:
                tb_writer.add_scalar("train_loss_patches/mask_bce", ema_mask_for_log, iteration)
                tb_writer.add_scalar("train_loss_patches/tview_l1", ema_tview_for_log, iteration)
                tb_writer.add_scalar("train_loss_patches/bounded_reg", ema_bound_reg_for_log, iteration)
                #***REngine Begin Modify added by tuckersu. [TensorBoard traces for GNS dynamics]
                tb_writer.add_scalar("train_loss_patches/gns_reg", ema_gns_reg_for_log, iteration)
                if args.use_gns:
                    tb_writer.add_scalar("gns/opacity_reg_lr", float(gns_state["opacity_reg_lr"]), iteration)
                    tb_writer.add_scalar("gns/prune_reg_active", int(gns_state["prune_reg_active"]), iteration)
                #***REngine End Modify

            if args.vis_interval > 0 and iteration % args.vis_interval == 0:
                save_training_vis(
                    iteration,
                    gaussians,
                    pipe,
                    background,
                    train_cams,
                    G,
                    vis_dir,
                    tb_writer=tb_writer,
                    render_tview=(lambda_tview > 0),
                )

            if iteration in args.save_iterations:
                save_point_cloud(gaussians, args.model_path, iteration)

            if densify_enabled and iteration < opt.densify_until_iter:
                visibility_filter = render_pkg["visibility_filter"]
                radii = render_pkg["radii"]
                viewspace_point_tensor = render_pkg["viewspace_points"]

                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter],
                    radii[visibility_filter],
                )
                gaussians.add_densification_stats_abs(viewspace_point_tensor, visibility_filter)

                if iteration > opt.densify_from_iter and iteration % opt.densification_interval == 0:
                    if args.max_points > 0 and gaussians.get_xyz.shape[0] >= args.max_points:
                        gaussians.tmp_radii = radii
                        prune_mask = (gaussians.get_opacity < 0.005).squeeze()
                        gaussians.prune_points(prune_mask)
                        gaussians.tmp_radii = None
                    else:
                        scores = _compute_eas_scores(gaussians, train_cams, pipe, background, args)
                        budget = compute_current_budget(iteration, opt) if args.use_gc else int(getattr(opt, "budget", 600000))
                        gaussians.tmp_radii = radii
                        gaussians.densify_and_prune_improved(
                            scores,
                            float(args.improvedgs_min_opacity),
                            budget,
                            opt,
                            iteration,
                            data.cameras_extent,
                        )
                        gaussians.tmp_radii = None

                if args.use_rap:
                    if iteration in rap_state["rap_trigger_iterations"]:
                        gaussians.only_prune(float(args.rap_prune_ratio), percent=True)
                        rap_state["rap_trigger_iterations"].discard(iteration)

                    if iteration % opt.opacity_reset_interval == 0:
                        gaussians.reset_opacity(float(args.improvedgs_reset_min_opacity))
                        if (
                            float(args.rap_prune_ratio) > 0
                            and rap_state["rap_reset_count"] < int(args.rap_rounds)
                        ):
                            rap_state["rap_trigger_iterations"].add(iteration + int(args.rap_prune_offset))
                        rap_state["rap_reset_count"] += 1
                else:
                    if iteration % opt.opacity_reset_interval == 0:
                        gaussians.reset_opacity(float(args.improvedgs_reset_min_opacity))

            if tb_writer and iteration % 100 == 0:
                tb_writer.add_scalar("total_points", gaussians.get_xyz.shape[0], iteration)

            if should_run_parameter_update(iteration, opt, args.use_mu):
                gaussians.optimizer.step()
            gaussians.optimizer.zero_grad(set_to_none=True)

            if (
                iteration in args.checkpoint_iterations
                or (args.checkpoint_interval > 0 and iteration % args.checkpoint_interval == 0)
            ):
                print(f"\n[ITER {iteration}] Saving Checkpoint")
                _save_checkpoint(
                    os.path.join(args.model_path, f"chkpnt{iteration}.pth"),
                    gaussians,
                    iteration,
                    args,
                    viewpoint_stack,
                    rap_state,
                    gns_state,
                )

    if tb_writer:
        tb_writer.close()


def add_improved_args(parser: ArgumentParser):
    parser.add_argument("--use_las", action="store_true", default=True)
    parser.add_argument("--no_las", dest="use_las", action="store_false")
    parser.add_argument("--use_eas", action="store_true", default=True)
    parser.add_argument("--no_eas", dest="use_eas", action="store_false")
    parser.add_argument("--use_rap", action="store_true", default=True)
    parser.add_argument("--no_rap", dest="use_rap", action="store_false")
    parser.add_argument("--use_mu", action="store_true", default=True)
    parser.add_argument("--no_mu", dest="use_mu", action="store_false")
    parser.add_argument("--use_gc", action="store_true", default=True)
    parser.add_argument("--no_gc", dest="use_gc", action="store_false")

    parser.add_argument("--split_distance", type=float, default=0.45)
    parser.add_argument("--opacity_reduction", type=float, default=0.6)
    parser.add_argument("--budget", type=int, default=0)
    parser.add_argument("--final_budget", type=int, default=600000)
    parser.add_argument("--budget_multiplier", type=float, default=3.0)
    parser.add_argument("--budget_warmup_until_offset", type=int, default=500)

    parser.add_argument("--rap_prune_ratio", type=float, default=0.2)
    parser.add_argument("--rap_prune_offset", type=int, default=300)
    parser.add_argument("--rap_rounds", type=int, default=2)

    parser.add_argument("--mu_start_iter", type=int, default=20000)
    parser.add_argument("--mu_interval", type=int, default=5)
    parser.add_argument("--mu_second_start_iter", type=int, default=25000)
    parser.add_argument("--mu_second_interval", type=int, default=10)

    parser.add_argument("--edge_sample_cams", type=int, default=10)
    parser.add_argument("--improvedgs_min_opacity", type=float, default=0.005)
    parser.add_argument("--improvedgs_reset_min_opacity", type=float, default=0.01)

    #***REngine Begin Modify added by tuckersu. [Expose GNS natural-selection controls]
    parser.add_argument("--use_gns", action="store_true", default=False)
    parser.add_argument("--no_gns", dest="use_gns", action="store_false")
    parser.add_argument("--no_final_prune", action="store_true", default=False)
    parser.add_argument("--gns_early_prune", action="store_true", default=False)
    parser.add_argument("--opacity_reg_lr", type=float, default=2e-4)
    parser.add_argument("--reg_interval", type=int, default=50)
    parser.add_argument("--reg_start", type=int, default=15000)
    parser.add_argument("--reg_end", type=int, default=23000)
    #***REngine End Modify



if __name__ == "__main__":
    parser = ArgumentParser(description="7DRGS ImprovedGS training script parameters")
    lp = ModelParams(parser)
    op = OptimizationParams(parser)
    pp = PipelineParams(parser)

    parser.add_argument("--debug_from", type=int, default=-1)
    parser.add_argument("--detect_anomaly", action="store_true", default=False)
    parser.add_argument("--test_iterations", nargs="+", type=int, default=[7000, 30000])
    parser.add_argument("--save_iterations", nargs="+", type=int, default=[7000, 30000])
    parser.add_argument("--checkpoint_iterations", nargs="+", type=int, default=[])
    parser.add_argument("--checkpoint_interval", type=int, default=0)
    parser.add_argument("--resume", type=str)
    parser.add_argument("--init_ply", type=str)
    parser.add_argument("--activate_max_sh_degree", action="store_true")
    parser.add_argument(
        "--stage",
        choices=("smoke", "relight", "geometry", "recover"),
        default="relight",
    )
    parser.add_argument("--quiet", action="store_true")

    parser.add_argument("--j_gain", type=float, default=20.0)
    parser.add_argument("--j_init", type=float, default=0.02)
    parser.add_argument("--val_ratio", type=float, default=0.2)
    parser.add_argument("--warmup_geometry", action="store_true", default=True)
    parser.add_argument("--no_warmup_geometry", dest="warmup_geometry", action="store_false")
    parser.add_argument("--disable_densify", action="store_true", default=False)
    parser.add_argument("--max_points", type=int, default=-1)
    parser.add_argument("--vis_interval", type=int, default=500)
    parser.add_argument("--sh_degree_t", type=int, default=0)
    parser.add_argument("--lambda_tview", type=float, default=0.5)
    parser.add_argument("--lambda_teacher_anchor", type=float, default=10.0)
    parser.add_argument("--lambda_energy_reg", type=float, default=1.0)

    add_improved_args(parser)

    args = parser.parse_args(sys.argv[1:])
    args.use_7dgs = True
    args.save_iterations.append(args.iterations)

    print("Optimizing (7DRGS Improved) " + args.model_path)
    safe_state(args.quiet)
    torch.autograd.set_detect_anomaly(args.detect_anomaly)

    training(lp.extract(args), op.extract(args), pp.extract(args), args)
    print("\n7DRGS Improved training complete.")
#***REngine End Modify
