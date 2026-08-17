#***REngine Begin Modify added by tuckersu. [Add 7D Gaussian model with conditional slicing support]
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

import os
import json
import torch
import numpy as np
from torch import nn
from plyfile import PlyData, PlyElement
from utils.system_utils import mkdir_p
from utils.graphics_utils import BasicPointCloud, getWorld2View2
from utils.sh_utils import RGB2SH
from simple_knn._C import distCUDA2
from scene.gaussian_model import GaussianModel
from utils.general_utils import build_rotation

from utils.slicing_utils import create_cholesky, slice_gaussian_dynamic


class GaussianModel7D(GaussianModel):
    """7DGS model built on top of original GaussianModel training infrastructure."""

    def __init__(
        self,
        sh_degree,
        optimizer_type="default",
        is_dynamic=False,
        lambda_t_init=0.35,
        lambda_d_init=0.35,
    ):
        super().__init__(sh_degree, optimizer_type=optimizer_type)
        self.is_dynamic = is_dynamic
        self._mu_t = torch.empty(0)
        self._mu_d = torch.empty(0)
        self._cholesky_diag = torch.empty(0)
        self._cholesky_offdiag = torch.empty(0)
        self._lambda_t = torch.empty(0)
        self._lambda_d = torch.empty(0)
        self.lambda_t_init = float(lambda_t_init)
        self.lambda_d_init = float(lambda_d_init)

    @staticmethod
    def _inv_softplus(x: float) -> float:
        x_clamped = max(float(x), 1e-6)
        return float(np.log(np.exp(x_clamped) - 1.0))

    @property
    def get_mu_t(self):
        return self._mu_t

    @property
    def get_mu_d(self):
        return torch.nn.functional.normalize(self._mu_d, dim=1)

    @property
    def get_cholesky_diag(self):
        return torch.exp(self._cholesky_diag)

    @property
    def get_lambda_t(self):
        return torch.nn.functional.softplus(self._lambda_t)

    @property
    def get_lambda_d(self):
        return torch.nn.functional.softplus(self._lambda_d)

    def get_covariance_7d(self):
        return create_cholesky(self.get_cholesky_diag, self._cholesky_offdiag)

    def capture(self):
        return (
            self.active_sh_degree,
            self._xyz,
            self._features_dc,
            self._features_rest,
            self._scaling,
            self._rotation,
            self._opacity,
            self._mu_t,
            self._mu_d,
            self._cholesky_diag,
            self._cholesky_offdiag,
            self._lambda_t,
            self._lambda_d,
            self.max_radii2D,
            self.xyz_gradient_accum,
            self.denom,
            self.optimizer.state_dict(),
            self.exposure_optimizer.state_dict(),
            self.spatial_lr_scale,
            self.is_dynamic,
        )

    def restore(self, model_args, training_args):
        (
            self.active_sh_degree,
            self._xyz,
            self._features_dc,
            self._features_rest,
            self._scaling,
            self._rotation,
            self._opacity,
            self._mu_t,
            self._mu_d,
            self._cholesky_diag,
            self._cholesky_offdiag,
            self._lambda_t,
            self._lambda_d,
            self.max_radii2D,
            xyz_gradient_accum,
            denom,
            opt_dict,
            exposure_opt_dict,
            self.spatial_lr_scale,
            self.is_dynamic,
        ) = model_args
        self._exposure = nn.Parameter(
            torch.empty((0, 3, 4), device=self._xyz.device).requires_grad_(True)
        )
        self.exposure_mapping = {}
        self.pretrained_exposures = None
        self.training_setup(training_args)
        self.xyz_gradient_accum = xyz_gradient_accum
        self.denom = denom
        self.optimizer.load_state_dict(opt_dict)
        self.exposure_optimizer.load_state_dict(exposure_opt_dict)

    def create_from_pcd(self, pcd: BasicPointCloud, cam_infos: int, spatial_lr_scale: float):
        super().create_from_pcd(pcd, cam_infos, spatial_lr_scale)

        n_points = self.get_xyz.shape[0]
        device = self.get_xyz.device
        dtype = self.get_xyz.dtype

        cam_centers = []
        for cam in cam_infos:
            w2c = getWorld2View2(cam.R, cam.T)
            c2w = np.linalg.inv(w2c)
            cam_centers.append(c2w[:3, 3])

        if len(cam_centers) > 0:
            cam_centers = torch.tensor(np.asarray(cam_centers), dtype=dtype, device=device)
            dir_vectors = self.get_xyz.unsqueeze(1) - cam_centers.unsqueeze(0)
            dir_vectors = dir_vectors / torch.clamp(dir_vectors.norm(dim=2, keepdim=True), min=1e-6)
            mu_d_init = dir_vectors.mean(dim=1)
        else:
            mu_d_init = torch.zeros((n_points, 3), dtype=dtype, device=device)
            mu_d_init[:, 2] = 1.0

        mu_t_init = torch.zeros((n_points, 1), dtype=dtype, device=device)

        spatial_diag = torch.clamp(self.get_scaling.detach(), min=1e-4)
        temporal_diag = torch.full((n_points, 1), 0.1, dtype=dtype, device=device)
        angular_diag = torch.full((n_points, 3), 1.0, dtype=dtype, device=device)
        chol_diag = torch.cat([spatial_diag, temporal_diag, angular_diag], dim=1)

        chol_offdiag = torch.zeros((n_points, 21), dtype=dtype, device=device)

        lambda_t_raw = torch.full(
            (n_points, 1),
            self._inv_softplus(self.lambda_t_init),
            dtype=dtype,
            device=device,
        )
        lambda_d_raw = torch.full(
            (n_points, 1),
            self._inv_softplus(self.lambda_d_init),
            dtype=dtype,
            device=device,
        )

        self._mu_t = nn.Parameter(mu_t_init.requires_grad_(True))
        self._mu_d = nn.Parameter(mu_d_init.requires_grad_(True))
        self._cholesky_diag = nn.Parameter(torch.log(chol_diag).requires_grad_(True))
        self._cholesky_offdiag = nn.Parameter(chol_offdiag.requires_grad_(True))
        self._lambda_t = nn.Parameter(lambda_t_raw.requires_grad_(True))
        self._lambda_d = nn.Parameter(lambda_d_raw.requires_grad_(True))

    def training_setup(self, training_args):
        super().training_setup(training_args)

        self.optimizer.add_param_group(
            {"params": [self._mu_t], "lr": training_args.position_lr_init * self.spatial_lr_scale * 0.5, "name": "mu_t"}
        )
        self.optimizer.add_param_group(
            {"params": [self._mu_d], "lr": training_args.rotation_lr, "name": "mu_d"}
        )
        self.optimizer.add_param_group(
            {"params": [self._cholesky_diag], "lr": training_args.scaling_lr, "name": "cholesky_diag"}
        )
        self.optimizer.add_param_group(
            {"params": [self._cholesky_offdiag], "lr": training_args.scaling_lr, "name": "cholesky_offdiag"}
        )
        self.optimizer.add_param_group(
            {"params": [self._lambda_t], "lr": training_args.lambda_lr, "name": "lambda_t"}
        )
        self.optimizer.add_param_group(
            {"params": [self._lambda_d], "lr": training_args.lambda_lr, "name": "lambda_d"}
        )

    def slice_for_camera(self, viewpoint_camera):
        n_points = self.get_xyz.shape[0]
        if n_points == 0:
            raise RuntimeError("No gaussian points to render")

        cam_center = viewpoint_camera.camera_center.unsqueeze(0)
        d = self.get_xyz - cam_center
        d = d / torch.clamp(d.norm(dim=1, keepdim=True), min=1e-6)

        timestamp = float(getattr(viewpoint_camera, "timestamp", 0.0))
        if not self.is_dynamic:
            timestamp = 0.0

        t = torch.full((n_points, 1), timestamp, dtype=self.get_xyz.dtype, device=self.get_xyz.device)

        sigma = self.get_covariance_7d()
        means3d, cov3d, f_cond = slice_gaussian_dynamic(
            mu_p=self.get_xyz,
            mu_t=self.get_mu_t,
            mu_d=self.get_mu_d,
            t=t,
            d=d,
            sigma=sigma,
            lambda_t=self.get_lambda_t,
            lambda_d=self.get_lambda_d,
        )

        opacity = self.get_opacity * f_cond
        return means3d, cov3d, opacity

    def construct_list_of_attributes(self):
        attributes = super().construct_list_of_attributes()
        attributes.extend(["mu_t", "mu_d_0", "mu_d_1", "mu_d_2"])
        for idx in range(7):
            attributes.append(f"chol_diag_{idx}")
        for idx in range(21):
            attributes.append(f"chol_offdiag_{idx}")
        attributes.append("lambda_t")
        attributes.append("lambda_d")
        return attributes

    def save_ply(self, path):
        mkdir_p(os.path.dirname(path))

        xyz = self._xyz.detach().cpu().numpy()
        normals = np.zeros_like(xyz)
        f_dc = self._features_dc.detach().transpose(1, 2).flatten(start_dim=1).contiguous().cpu().numpy()
        f_rest = self._features_rest.detach().transpose(1, 2).flatten(start_dim=1).contiguous().cpu().numpy()
        opacities = self._opacity.detach().cpu().numpy()
        scale = self._scaling.detach().cpu().numpy()
        rotation = self._rotation.detach().cpu().numpy()

        mu_t = self._mu_t.detach().cpu().numpy()
        mu_d = self._mu_d.detach().cpu().numpy()
        chol_diag = self._cholesky_diag.detach().cpu().numpy()
        chol_offdiag = self._cholesky_offdiag.detach().cpu().numpy()
        lambda_t = self._lambda_t.detach().cpu().numpy()
        lambda_d = self._lambda_d.detach().cpu().numpy()

        dtype_full = [(attribute, "f4") for attribute in self.construct_list_of_attributes()]
        elements = np.empty(xyz.shape[0], dtype=dtype_full)

        attributes = np.concatenate(
            [
                xyz,
                normals,
                f_dc,
                f_rest,
                opacities,
                scale,
                rotation,
                mu_t,
                mu_d,
                chol_diag,
                chol_offdiag,
                lambda_t,
                lambda_d,
            ],
            axis=1,
        )
        elements[:] = list(map(tuple, attributes))
        el = PlyElement.describe(elements, "vertex")
        PlyData([el]).write(path)

    def load_ply(self, path, use_train_test_exp=False):
        super().load_ply(path, use_train_test_exp=use_train_test_exp)

        plydata = PlyData.read(path)
        n_points = self._xyz.shape[0]

        def _read_column(name, default=0.0):
            if name in plydata.elements[0].data.dtype.names:
                return np.asarray(plydata.elements[0][name]).reshape(n_points, 1)
            return np.full((n_points, 1), default, dtype=np.float32)

        mu_t = _read_column("mu_t", 0.0)
        mu_d = np.concatenate([
            _read_column("mu_d_0", 0.0),
            _read_column("mu_d_1", 0.0),
            _read_column("mu_d_2", 1.0),
        ], axis=1)

        chol_diag = np.concatenate([_read_column(f"chol_diag_{idx}", 0.0) for idx in range(7)], axis=1)
        chol_offdiag = np.concatenate([_read_column(f"chol_offdiag_{idx}", 0.0) for idx in range(21)], axis=1)
        lambda_t = _read_column("lambda_t", self._inv_softplus(self.lambda_t_init))
        lambda_d = _read_column("lambda_d", self._inv_softplus(self.lambda_d_init))

        self._mu_t = nn.Parameter(torch.tensor(mu_t, dtype=torch.float, device="cuda").requires_grad_(True))
        self._mu_d = nn.Parameter(torch.tensor(mu_d, dtype=torch.float, device="cuda").requires_grad_(True))
        self._cholesky_diag = nn.Parameter(torch.tensor(chol_diag, dtype=torch.float, device="cuda").requires_grad_(True))
        self._cholesky_offdiag = nn.Parameter(torch.tensor(chol_offdiag, dtype=torch.float, device="cuda").requires_grad_(True))
        self._lambda_t = nn.Parameter(torch.tensor(lambda_t, dtype=torch.float, device="cuda").requires_grad_(True))
        self._lambda_d = nn.Parameter(torch.tensor(lambda_d, dtype=torch.float, device="cuda").requires_grad_(True))

    def prune_points(self, mask):
        valid_points_mask = ~mask
        optimizable_tensors = self._prune_optimizer(valid_points_mask)

        self._xyz = optimizable_tensors["xyz"]
        self._features_dc = optimizable_tensors["f_dc"]
        self._features_rest = optimizable_tensors["f_rest"]
        self._opacity = optimizable_tensors["opacity"]
        self._scaling = optimizable_tensors["scaling"]
        self._rotation = optimizable_tensors["rotation"]
        self._mu_t = optimizable_tensors["mu_t"]
        self._mu_d = optimizable_tensors["mu_d"]
        self._cholesky_diag = optimizable_tensors["cholesky_diag"]
        self._cholesky_offdiag = optimizable_tensors["cholesky_offdiag"]
        self._lambda_t = optimizable_tensors["lambda_t"]
        self._lambda_d = optimizable_tensors["lambda_d"]

        self.xyz_gradient_accum = self.xyz_gradient_accum[valid_points_mask]
        self.denom = self.denom[valid_points_mask]
        self.max_radii2D = self.max_radii2D[valid_points_mask]
        self.tmp_radii = self.tmp_radii[valid_points_mask]

    def densification_postfix(
        self,
        new_xyz,
        new_features_dc,
        new_features_rest,
        new_opacities,
        new_scaling,
        new_rotation,
        new_mu_t,
        new_mu_d,
        new_cholesky_diag,
        new_cholesky_offdiag,
        new_lambda_t,
        new_lambda_d,
        new_tmp_radii,
    ):
        d = {
            "xyz": new_xyz,
            "f_dc": new_features_dc,
            "f_rest": new_features_rest,
            "opacity": new_opacities,
            "scaling": new_scaling,
            "rotation": new_rotation,
            "mu_t": new_mu_t,
            "mu_d": new_mu_d,
            "cholesky_diag": new_cholesky_diag,
            "cholesky_offdiag": new_cholesky_offdiag,
            "lambda_t": new_lambda_t,
            "lambda_d": new_lambda_d,
        }

        optimizable_tensors = self.cat_tensors_to_optimizer(d)
        self._xyz = optimizable_tensors["xyz"]
        self._features_dc = optimizable_tensors["f_dc"]
        self._features_rest = optimizable_tensors["f_rest"]
        self._opacity = optimizable_tensors["opacity"]
        self._scaling = optimizable_tensors["scaling"]
        self._rotation = optimizable_tensors["rotation"]
        self._mu_t = optimizable_tensors["mu_t"]
        self._mu_d = optimizable_tensors["mu_d"]
        self._cholesky_diag = optimizable_tensors["cholesky_diag"]
        self._cholesky_offdiag = optimizable_tensors["cholesky_offdiag"]
        self._lambda_t = optimizable_tensors["lambda_t"]
        self._lambda_d = optimizable_tensors["lambda_d"]

        self.tmp_radii = torch.cat((self.tmp_radii, new_tmp_radii))
        self.xyz_gradient_accum = torch.zeros((self.get_xyz.shape[0], 1), device="cuda")
        self.denom = torch.zeros((self.get_xyz.shape[0], 1), device="cuda")
        self.max_radii2D = torch.zeros((self.get_xyz.shape[0]), device="cuda")

    def densify_and_split(self, grads, grad_threshold, scene_extent, n_split=2):
        n_init_points = self.get_xyz.shape[0]
        padded_grad = torch.zeros((n_init_points), device="cuda")
        padded_grad[:grads.shape[0]] = grads.squeeze()
        selected_pts_mask = torch.where(padded_grad >= grad_threshold, True, False)
        selected_pts_mask = torch.logical_and(
            selected_pts_mask,
            torch.max(self.get_scaling, dim=1).values > self.percent_dense * scene_extent,
        )

        stds = self.get_scaling[selected_pts_mask].repeat(n_split, 1)
        means = torch.zeros((stds.size(0), 3), device="cuda")
        samples = torch.normal(mean=means, std=stds)
        rots = build_rotation(self._rotation[selected_pts_mask]).repeat(n_split, 1, 1)
        new_xyz = torch.bmm(rots, samples.unsqueeze(-1)).squeeze(-1) + self.get_xyz[selected_pts_mask].repeat(n_split, 1)
        new_scaling = self.scaling_inverse_activation(self.get_scaling[selected_pts_mask].repeat(n_split, 1) / (0.8 * n_split))

        new_rotation = self._rotation[selected_pts_mask].repeat(n_split, 1)
        new_features_dc = self._features_dc[selected_pts_mask].repeat(n_split, 1, 1)
        new_features_rest = self._features_rest[selected_pts_mask].repeat(n_split, 1, 1)
        new_opacity = self._opacity[selected_pts_mask].repeat(n_split, 1)
        new_mu_t = self._mu_t[selected_pts_mask].repeat(n_split, 1)
        new_mu_d = self._mu_d[selected_pts_mask].repeat(n_split, 1)
        new_cholesky_diag = self._cholesky_diag[selected_pts_mask].repeat(n_split, 1)
        new_cholesky_offdiag = self._cholesky_offdiag[selected_pts_mask].repeat(n_split, 1)
        new_lambda_t = self._lambda_t[selected_pts_mask].repeat(n_split, 1)
        new_lambda_d = self._lambda_d[selected_pts_mask].repeat(n_split, 1)
        new_tmp_radii = self.tmp_radii[selected_pts_mask].repeat(n_split)

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
        )

        split_count = int(selected_pts_mask.sum().item())
        prune_filter = torch.cat(
            (
                selected_pts_mask,
                torch.zeros(n_split * split_count, device="cuda", dtype=bool),
            )
        )

        self.prune_points(prune_filter)

    def densify_and_clone(self, grads, grad_threshold, scene_extent):
        selected_pts_mask = torch.where(torch.norm(grads, dim=-1) >= grad_threshold, True, False)
        selected_pts_mask = torch.logical_and(
            selected_pts_mask,
            torch.max(self.get_scaling, dim=1).values <= self.percent_dense * scene_extent,
        )

        new_xyz = self._xyz[selected_pts_mask]
        new_features_dc = self._features_dc[selected_pts_mask]
        new_features_rest = self._features_rest[selected_pts_mask]
        new_opacities = self._opacity[selected_pts_mask]
        new_scaling = self._scaling[selected_pts_mask]
        new_rotation = self._rotation[selected_pts_mask]
        new_mu_t = self._mu_t[selected_pts_mask]
        new_mu_d = self._mu_d[selected_pts_mask]
        new_cholesky_diag = self._cholesky_diag[selected_pts_mask]
        new_cholesky_offdiag = self._cholesky_offdiag[selected_pts_mask]
        new_lambda_t = self._lambda_t[selected_pts_mask]
        new_lambda_d = self._lambda_d[selected_pts_mask]
        new_tmp_radii = self.tmp_radii[selected_pts_mask]

        self.densification_postfix(
            new_xyz,
            new_features_dc,
            new_features_rest,
            new_opacities,
            new_scaling,
            new_rotation,
            new_mu_t,
            new_mu_d,
            new_cholesky_diag,
            new_cholesky_offdiag,
            new_lambda_t,
            new_lambda_d,
            new_tmp_radii,
        )

    def densify_and_prune(self, max_grad, min_opacity, extent, max_screen_size, radii):
        grads = self.xyz_gradient_accum / self.denom
        grads[grads.isnan()] = 0.0

        self.tmp_radii = radii
        self.densify_and_clone(grads, max_grad, extent)
        self.densify_and_split(grads, max_grad, extent)

        prune_mask = (self.get_opacity < min_opacity).squeeze()
        if max_screen_size:
            big_points_vs = self.max_radii2D > max_screen_size
            big_points_ws = self.get_scaling.max(dim=1).values > 0.1 * extent
            prune_mask = torch.logical_or(torch.logical_or(prune_mask, big_points_vs), big_points_ws)
        self.prune_points(prune_mask)
        self.tmp_radii = None
        torch.cuda.empty_cache()

#***REngine End Modify
