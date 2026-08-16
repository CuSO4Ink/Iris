#***REngine Begin Modify added by tuckersu. [GaussianModel7DRGS + ImprovedGS densification]
import math
import torch
from utils.general_utils import build_rotation, inverse_sigmoid
from scene.gaussian_model_7drgs import GaussianModel7DRGS


class GaussianModel7DRGSImproved(GaussianModel7DRGS):
    """7DRGS model with ImprovedGS GC/LAS/RAP/MU-compatible structure updates."""

    def _ensure_abs_stats(self) -> None:
        n_points = int(self.get_xyz.shape[0])
        if (not hasattr(self, "xyz_gradient_accum_abs")) or self.xyz_gradient_accum_abs.shape[0] != n_points:
            self.xyz_gradient_accum_abs = torch.zeros((n_points, 1), device="cuda")

    def reset_opacity(self, min_opacity: float = 0.01):
        new_op = self.inverse_opacity_activation(
            torch.min(self.get_opacity, torch.ones_like(self.get_opacity) * float(min_opacity))
        )
        optimizable_tensors = self.replace_tensor_to_optimizer(new_op, "opacity")
        self._opacity = optimizable_tensors["opacity"]

    def add_densification_stats_abs(self, viewspace_point_tensor: torch.Tensor, update_filter: torch.Tensor) -> None:
        self._ensure_abs_stats()
        abs_grad = getattr(viewspace_point_tensor, "absgrad", None)
        if abs_grad is None:
            grad_xy = torch.abs(viewspace_point_tensor.grad[update_filter, :2])
        else:
            grad_xy = abs_grad[update_filter, :2]
        grad_values = torch.norm(grad_xy, dim=-1, keepdim=True)
        self.xyz_gradient_accum_abs[update_filter] += grad_values
        self.denom[update_filter] += 1

    def only_prune(self, min_opacity: float, percent: bool = False) -> None:
        if self.get_opacity.numel() == 0:
            return
        if percent:
            threshold = torch.quantile(self.get_opacity.detach().flatten(), float(min_opacity))
            prune_mask = (self.get_opacity < threshold).squeeze()
        else:
            prune_mask = (self.get_opacity < min_opacity).squeeze()
        if prune_mask.any():
            self.prune_points(prune_mask)

    def long_axis_split(
        self,
        scores: torch.Tensor,
        budget: int,
        filter_mask: torch.Tensor,
        split_distance: float,
        opacity_reduction: float,
    ) -> int:
        if budget <= 0 or scores.numel() == 0 or not torch.any(filter_mask):
            return 0

        total_n = self.get_xyz.shape[0]
        padded_importance = torch.zeros((total_n,), dtype=torch.float32, device="cuda")
        padded_importance[:scores.shape[0]] = scores.detach().float().clamp_min(0.0)
        padded_importance[~filter_mask] = 0.0
        positive_count = int((padded_importance > 0).sum().item())
        if positive_count == 0:
            return 0

        budget = min(int(budget), positive_count)
        selected_indices = torch.argsort(
            padded_importance, descending=True, stable=True
        )[:budget]
        selected_pts_mask = torch.zeros_like(padded_importance, dtype=torch.bool)
        selected_pts_mask[selected_indices] = True

        stds = self.get_scaling[selected_pts_mask]
        max_values, max_indices = torch.max(stds, dim=1, keepdim=True)
        axis_mask = torch.zeros_like(stds, dtype=torch.bool).scatter(1, max_indices, True)
        axis_offsets = stds * axis_mask * 3.0 * float(split_distance)
        axis_offsets = torch.cat([axis_offsets, -axis_offsets], dim=0)

        rotation_mats = build_rotation(self._rotation[selected_pts_mask]).repeat(2, 1, 1)
        parent_xyz = self.get_xyz[selected_pts_mask].repeat(2, 1)
        new_xyz = torch.bmm(rotation_mats, axis_offsets.unsqueeze(-1)).squeeze(-1) + parent_xyz

        split_distance_sq = float(split_distance) * float(split_distance)
        rate_w = max(1.0 - float(split_distance), 1e-6)
        rate_h = math.sqrt(max(1.0 - split_distance_sq, 1e-6))
        new_scales = stds.scatter(1, max_indices, max_values * rate_w / rate_h).repeat(2, 1) * rate_h
        new_scaling = self.scaling_inverse_activation(new_scales)
        new_opacity = inverse_sigmoid(self.get_opacity[selected_pts_mask] * float(opacity_reduction)).repeat(2, 1)
        new_rotation = self._rotation[selected_pts_mask].repeat(2, 1)
        new_features_dc = self._features_dc[selected_pts_mask].repeat(2, 1, 1)
        new_features_rest = self._features_rest[selected_pts_mask].repeat(2, 1, 1)

        new_mu_t = self._mu_t[selected_pts_mask].repeat(2, 1)
        new_mu_d = self._mu_d[selected_pts_mask].repeat(2, 1)
        new_cholesky_diag = self._cholesky_diag[selected_pts_mask].repeat(2, 1)
        new_cholesky_offdiag = self._cholesky_offdiag[selected_pts_mask].repeat(2, 1)
        new_lambda_t = self._lambda_t[selected_pts_mask].repeat(2, 1)
        new_lambda_d = self._lambda_d[selected_pts_mask].repeat(2, 1)
        if self.tmp_radii is not None:
            new_tmp_radii = self.tmp_radii[selected_pts_mask].repeat(2)
        else:
            new_tmp_radii = torch.zeros((2 * int(selected_pts_mask.sum().item()),), device="cuda")

        new_features_dc_t = self._features_dc_t[selected_pts_mask].repeat(2, 1, 1)
        new_features_rest_t = self._features_rest_t[selected_pts_mask].repeat(2, 1, 1)

        self.densification_postfix(
            new_xyz,
            new_features_dc,
            new_features_rest,
            new_opacity,
            new_scaling,
            new_rotation,
            new_mu_t,
            new_mu_d,
            new_cholesky_diag,
            new_cholesky_offdiag,
            new_lambda_t,
            new_lambda_d,
            new_tmp_radii,
            new_features_dc_t,
            new_features_rest_t,
        )
        self._ensure_abs_stats()
        self.xyz_gradient_accum_abs = torch.zeros((self.get_xyz.shape[0], 1), device="cuda")

        prune_filter = torch.cat(
            (selected_pts_mask, torch.zeros(2 * int(selected_pts_mask.sum().item()), device="cuda", dtype=torch.bool))
        )
        self.prune_points(prune_filter)
        self._ensure_abs_stats()
        return budget

    def densify_and_prune_improved(
        self,
        scores: torch.Tensor,
        min_opacity: float,
        budget: int,
        opt,
        iteration: int,
        scene_extent: float,
    ) -> None:
        self._ensure_abs_stats()
        grad_values = self.xyz_gradient_accum_abs / self.denom.clamp_min(1.0)
        grad_values = torch.nan_to_num(grad_values, nan=0.0)

        min_grad = float(opt.densify_grad_threshold)
        late_densify_iter = max(int(opt.densify_until_iter) - 100, int(opt.densify_from_iter))
        if scores is None or iteration > late_densify_iter:
            scores = grad_values.squeeze(-1)
            if self.get_opacity.shape[0] < budget and iteration > late_densify_iter:
                min_grad = min_grad / 1.5

        grad_qualifiers = torch.where(torch.norm(grad_values, dim=-1) >= min_grad, True, False)
        total_candidates = int(grad_qualifiers.sum().item())
        current_points = int(self.get_xyz.shape[0])
        current_budget = min(int(budget), total_candidates + current_points)
        split_budget = current_budget - current_points

        if split_budget > 0:
            if bool(getattr(opt, "use_las", True)):
                self.long_axis_split(
                    scores,
                    split_budget,
                    grad_qualifiers,
                    float(getattr(opt, "split_distance", 0.45)),
                    float(getattr(opt, "opacity_reduction", 0.6)),
                )
            else:
                self.densify_and_split(grad_values, min_grad, float(scene_extent))

        if iteration < late_densify_iter:
            prune_mask = (self.get_opacity < min_opacity).squeeze()
            if prune_mask.any():
                self.prune_points(prune_mask)
        self._ensure_abs_stats()
        torch.cuda.empty_cache()

    #***REngine Begin Modify added by tuckersu. [Add GNS final_prune and opacity-lr schedule hook]
    def final_prune(self, final_budget: int) -> None:
        if self.get_opacity.numel() == 0:
            return
        target_budget = int(final_budget)
        if target_budget <= 0:
            return

        opacity_scores = self.get_opacity.detach().squeeze(-1).clamp_min(1e-12)
        if int(opacity_scores.shape[0]) <= target_budget:
            return

        sampled_indices = torch.argsort(
            opacity_scores, descending=True, stable=True
        )[:target_budget]
        keep_mask = torch.zeros_like(opacity_scores, dtype=torch.bool)
        keep_mask[sampled_indices] = True
        self.prune_points(~keep_mask)

    def update_opacity_lr(self, rate: float) -> None:
        ratio = float(rate)
        if ratio == 1.0:
            return
        for param_group in self.optimizer.param_groups:
            if param_group.get("name") == "opacity":
                param_group["lr"] = param_group["lr"] * ratio
    #***REngine End Modify
#***REngine End Modify
