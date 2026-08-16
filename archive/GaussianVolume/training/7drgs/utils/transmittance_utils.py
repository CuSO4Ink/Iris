#***REngine Begin Modify added by tuckersu. [Add two-stage relight loss functions for RGS training]
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

import torch
import torch.nn.functional as F
from torch import Tensor
from typing import Dict, Tuple


def _masked_mean(loss: Tensor, mask: Tensor) -> Tensor:
    """Compute masked mean: (loss * mask).sum() / mask.sum().clamp_min(1)."""
    return (loss * mask).sum() / mask.sum().clamp(min=1.0)


def _bce_loss(pred: Tensor, target: Tensor, eps: float = 1e-6) -> Tensor:
    """Binary cross-entropy with clamping for numerical stability."""
    pred_clamped = pred.clamp(eps, 1.0 - eps)
    return -(target * torch.log(pred_clamped) + (1.0 - target) * torch.log(1.0 - pred_clamped))


#***REngine Begin Modify added by tuckersu. [Fix 2: depth-gradient consistency loss on patches]
def _depth_grad_loss(depth_pred: Tensor, depth_gt: Tensor, mask: Tensor,
                     n_patches: int, patch_size: int) -> Tensor:
    """
    L1 consistency between predicted and GT depth GRADIENTS inside KxK patches.

    Rays must be laid out patch-major / row-major (see RelightDataset.sample_patch_batch),
    so [B] tensors reshape to [P, K, K]. Finite-difference gradients along the two image
    axes give a lateral (perpendicular-to-view) shape signal that breaks the spherical
    symmetry of the Gaussians. Gradients are masked so only fully-foreground neighbour
    pairs contribute.
    """
    K = int(patch_size)
    P = int(n_patches)
    dp = depth_pred.view(P, K, K)
    dg = depth_gt.view(P, K, K)
    mk = mask.view(P, K, K)

    # Horizontal (x) gradients
    gpx = dp[:, :, 1:] - dp[:, :, :-1]
    ggx = dg[:, :, 1:] - dg[:, :, :-1]
    mx = mk[:, :, 1:] * mk[:, :, :-1]
    # Vertical (y) gradients
    gpy = dp[:, 1:, :] - dp[:, :-1, :]
    ggy = dg[:, 1:, :] - dg[:, :-1, :]
    my = mk[:, 1:, :] * mk[:, :-1, :]

    lx = (torch.abs(gpx - ggx) * mx).sum() / mx.sum().clamp(min=1.0)
    ly = (torch.abs(gpy - ggy) * my).sum() / my.sum().clamp(min=1.0)
    return lx + ly
#***REngine End Modify



def relight_total_loss(
    pred: Dict[str, Tensor],
    gt: Dict[str, Tensor],
    gs_model,
    opt,
    iteration: int,
    stage: str,
) -> Tuple[Tensor, Dict[str, float]]:
    """
    Compute total loss for relightable GS training.

    Args:
        pred: dict of predicted tensors from renderer.
            Stage "geom": T_view_pred[B], depth_pred[B]
            Stage "appearance": J_pred[B, 3], T_view_pred[B] (optional)
        gt: dict of ground truth tensors.
            J_gt[B, 3], T_view_gt[B], depth_gt[B], mask[B]
        gs_model: GaussianModelRelight instance.
        opt: OptimizationParams with loss weights.
        iteration: current training iteration.
        stage: "geom" or "appearance".

    Returns:
        loss_total: scalar tensor.
        log_dict: dict of loss component values (floats) for TB logging.
    """
    log_dict = {}
    device = gt["mask"].device
    mask = gt["mask"]  # [B], 0 or 1

    if stage == "geom":
        # ---------- Stage-1: Geometry (only sigma_t/geometry) ----------
        T_view_pred = pred["T_view_pred"]  # [B]
        T_view_gt = gt["T_view_gt"]        # [B]
        depth_pred = pred["d_near_pred"]   # [B] renderer outputs d_near_pred (view-space depth)
        depth_gt = gt["depth_gt"]          # [B]

        # L_T_view: L2 or log form
        if getattr(opt, 't_view_loss_form', 'linear') == 'log':
            eps_log = 1e-6
            l_T_view = ((torch.log(T_view_pred.clamp(min=eps_log))
                        - torch.log(T_view_gt.clamp(min=eps_log))) ** 2).mean()
        else:
            l_T_view = ((T_view_pred - T_view_gt) ** 2).mean()

        # L_depth: L2, only foreground
        l_depth = _masked_mean((depth_pred - depth_gt) ** 2, mask)

        # L_mask_BCE: BCE(1 - T_geo_view, mask)
        occupancy_pred = 1.0 - T_view_pred  # predicted occupancy
        l_mask_bce = _masked_mean(
            _bce_loss(occupancy_pred, mask),
            torch.ones_like(mask)  # BCE applied to all pixels
        )

        # L_reg_sigma: ||sigma_t||^2
        sigma_t = gs_model.get_sigma_t  # [N]
        l_reg_sigma = (sigma_t ** 2).mean()

        #***REngine Begin Modify added by tuckersu. [Fix 2: add depth-gradient consistency term]
        # L_depth_grad: lateral shape signal from patch depth gradients (only when the
        # batch was produced by RelightDataset.sample_patch_batch).
        lambda_depth_grad = getattr(opt, 'lambda_depth_grad', 0.0)
        l_depth_grad = torch.zeros((), device=device)
        patch_size = gt.get("patch_size", 0)
        if lambda_depth_grad > 0 and patch_size and patch_size > 1:
            l_depth_grad = _depth_grad_loss(
                depth_pred, depth_gt, mask,
                n_patches=gt["n_patches_total"], patch_size=patch_size,
            )
        #***REngine End Modify

        # Total
        loss_total = (
            opt.lambda_T_view * l_T_view
            + opt.lambda_depth * l_depth
            + opt.lambda_mask_bce * l_mask_bce
            + opt.lambda_sigma_reg * l_reg_sigma
            + lambda_depth_grad * l_depth_grad
        )

        log_dict["loss/T_view"] = l_T_view.item()
        log_dict["loss/depth"] = l_depth.item()
        log_dict["loss/mask_bce"] = l_mask_bce.item()
        log_dict["loss/reg_sigma"] = l_reg_sigma.item()
        log_dict["loss/depth_grad"] = float(l_depth_grad)
        log_dict["loss/total"] = loss_total.item()

    elif stage == "appearance":
        from utils.sh_utils_relight import sh_high_order_l2
        # ---------- Stage-2: Appearance (tau_sh, optionally sigma_t finetune) ----------
        J_pred = pred["J_pred"]  # [B, 3]
        J_gt = gt["J_gt"]        # [B, 3]

        # L_J: selectable form — scale_invariant (default) / log / l1
        mask_3 = mask.unsqueeze(-1)  # [B, 1]
        j_loss_form = getattr(opt, 'j_loss_form', 'l1')
        if j_loss_form == "scale_invariant":
            # Normalize by GT mean magnitude to counteract small J values
            J_scale = J_gt.detach().abs().mean().clamp(min=1e-3)
            l_J_per_channel = torch.abs(J_pred - J_gt) / J_scale  # [B, 3]
            l_J = _masked_mean(l_J_per_channel.mean(dim=-1), mask)
        elif j_loss_form == "log":
            eps_log_j = 1e-4
            l_J_per_channel = torch.abs(
                torch.log(J_pred.clamp(min=eps_log_j))
                - torch.log(J_gt.clamp(min=eps_log_j))
            )  # [B, 3]
            l_J = _masked_mean(l_J_per_channel.mean(dim=-1), mask)
        else:
            # Default L1
            l_J_per_channel = torch.abs(J_pred - J_gt)  # [B, 3]
            l_J = _masked_mean(l_J_per_channel.mean(dim=-1), mask)

        # L_reg_SH: high-order SH L2
        tau_sh = gs_model.get_tau_sh  # [N, K, C]
        l_reg_sh = sh_high_order_l2(tau_sh, l_min=1)

        # L_T_view_s2: Stage-2 geometry anchor (prevent drift)
        lambda_T_view_s2 = getattr(opt, 'lambda_T_view_s2', 0.0)
        l_T_view_s2 = torch.zeros(1, device=device)
        if lambda_T_view_s2 > 0 and "T_view_pred" in pred and "T_view_gt" in gt:
            T_view_pred_s2 = pred["T_view_pred"]  # [B]
            T_view_gt_s2 = gt["T_view_gt"]        # [B]
            l_T_view_s2 = ((T_view_pred_s2 - T_view_gt_s2) ** 2).mean()

        # Total
        loss_total = (
            opt.lambda_J * l_J
            + opt.lambda_sh_reg * l_reg_sh
            + lambda_T_view_s2 * l_T_view_s2
        )

        log_dict["loss/J"] = l_J.item()
        log_dict["loss/reg_sh"] = l_reg_sh.item()
        log_dict["loss/T_view_s2"] = l_T_view_s2.item()
        log_dict["loss/total"] = loss_total.item()

    else:
        raise ValueError(f"Unknown stage: {stage}")

    return loss_total, log_dict
#***REngine End Modify
