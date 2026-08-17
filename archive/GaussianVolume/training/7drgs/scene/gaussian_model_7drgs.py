#***REngine Begin Modify added by tuckersu. [Add 7DRGS relightable model: light-direction slicing + init-ply lifting]
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

"""7DRGS (Relightable 7DGS) model.

Built on top of GaussianModel7D. The ONLY semantic changes are:
  1. The slicing direction condition `d` is the (global) virtual LIGHT direction
     instead of the per-gaussian camera view direction. The rasterization camera
     is fully decoupled from `d` (it only provides the projection matrices).
  2. The SH color channels encode light-conditioned transmittance / J.
  3. A second SH bank (SH_T, single-channel) encodes T_view (view-dependent
     transmittance). Shares slice geometry with J SH; evaluated with the same
     camera view direction; J is evaluated separately against light direction.

Everything else (7x7 covariance, Cholesky, conditional slicing, dual-factor
opacity modulation, native CUDA rasterization, densify/prune, PLY IO) is inherited
unchanged from GaussianModel7D.
"""

import os
import torch
import numpy as np
from torch import nn
from plyfile import PlyData, PlyElement

from utils.system_utils import mkdir_p
from utils.graphics_utils import BasicPointCloud
from utils.sh_utils import RGB2SH, eval_sh
from utils.general_utils import build_rotation
from scene.gaussian_model_7d import GaussianModel7D
from utils.slicing_utils import slice_gaussian_dynamic


class GaussianModel7DRGS(GaussianModel7D):

    def __init__(self, sh_degree, sh_degree_t=0, optimizer_type="default",
                 is_dynamic=False, lambda_t_init=0.35, lambda_d_init=0.35):
        """
        Args:
            sh_degree: SH degree for J (RGB, 3-channel).
            sh_degree_t: SH degree for T_view (scalar, 1-channel replicated to 3ch).
                         0 = DC only (1 coeff), 1 = 4 coeffs. Default 0.
        """
        super().__init__(sh_degree, optimizer_type=optimizer_type,
                         is_dynamic=is_dynamic, lambda_t_init=lambda_t_init,
                         lambda_d_init=lambda_d_init)
        #***REngine Begin Modify added by tuckersu. [T_view dual SH: add SH_T parameters]
        self.max_sh_degree_t = int(sh_degree_t)
        self.active_sh_degree_t = 0
        # T_view SH stored as 3-channel (replicated scalar) so the standard
        # 3DGS rasterizer (NUM_CHANNELS=3) can be reused without modification.
        self._features_dc_t = torch.empty(0)     # [N, 1, 3]
        self._features_rest_t = torch.empty(0)   # [N, K_t-1, 3]
        self.training_stage = "relight"
        self._teacher_anchor = None
        #***REngine End Modify

    @property
    def get_features_t(self):
        """Return T_view SH coefficients [N, K_t, 3] for the rasterizer."""
        return torch.cat((self._features_dc_t, self._features_rest_t), dim=1)

    def oneupSHdegree(self):
        """Promote both J and T_view SH active degree."""
        super().oneupSHdegree()
        if self.active_sh_degree_t < self.max_sh_degree_t:
            self.active_sh_degree_t += 1

    def slice_for_light(self, viewpoint_camera, light_dir):
        """Slice the 7D gaussians to 3D under a GLOBAL light direction condition.

        Args:
            viewpoint_camera: camera providing (only) the timestamp for the time
                condition. Its view direction is intentionally NOT used here.
            light_dir: world-space light direction, tensor of shape [3] (or [1,3]).
                Same coordinate frame as the gaussians/cameras.

        Returns:
            (means3d, cov3d, opacity) ready for the standard 3DGS rasterizer.
        """
        n_points = self.get_xyz.shape[0]
        if n_points == 0:
            raise RuntimeError("No gaussian points to render")

        device = self.get_xyz.device
        dtype = self.get_xyz.dtype

        light_dir = light_dir.to(device=device, dtype=dtype).reshape(1, 3)
        d = torch.nn.functional.normalize(light_dir, dim=1).expand(n_points, 3)

        timestamp = float(getattr(viewpoint_camera, "timestamp", 0.0))
        if not self.is_dynamic:
            timestamp = 0.0
        t = torch.full((n_points, 1), timestamp, dtype=dtype, device=device)

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

    def evaluate_j_for_light(self, light_dir):
        """Evaluate the J SH bank against light direction, not camera direction."""
        direction = torch.nn.functional.normalize(
            light_dir.to(device=self.get_xyz.device, dtype=self.get_xyz.dtype).reshape(1, 3),
            dim=1,
        ).expand(self.get_xyz.shape[0], 3)
        coefficients = self.get_features.transpose(1, 2).reshape(
            -1, 3, (self.max_sh_degree + 1) ** 2
        )
        return eval_sh(self.active_sh_degree, coefficients, direction) + 0.5

    def create_from_init_ply(
        self,
        ply_path,
        light_dirs,
        spatial_lr_scale,
        j_init=0.02,
        warmup_geometry=True,
    ):
        """Lift an init PLY and preserve any aggregated B2 teacher fields.

        Args:
            ply_path: path to init_points.ply.
            light_dirs: [L,3] world-space light directions (tensor or array).
            spatial_lr_scale: scene extent used by the base initializer / LR.
            j_init: cold-start magnitude for the J (transmittance) DC channel.
                Measured GT J ~ 0.02, so features_dc is initialized to
                RGB2SH(j_init) by feeding `colors=j_init` into create_from_pcd.
            warmup_geometry: if True, overwrite scale/rotation and spatial
                Cholesky from the PLY.
        """
        ply = PlyData.read(ply_path)
        v = ply.elements[0]
        names = set(v.data.dtype.names)
        xyz = np.stack([np.asarray(v[c]) for c in ("x", "y", "z")], axis=1).astype(np.float32)
        n = xyz.shape[0]

        # features_dc cold-starts at the J magnitude (create_from_pcd applies RGB2SH).
        colors = np.full((n, 3), float(j_init), dtype=np.float32)
        normals = np.zeros((n, 3), dtype=np.float32)
        pcd = BasicPointCloud(points=xyz, colors=colors, normals=normals)

        # Reuse the full lifting (3DGS fields via distCUDA2 + all 7D fields).
        GaussianModel7D.create_from_pcd(self, pcd, [], spatial_lr_scale)
        self._init_features_t()

        device = self.get_xyz.device
        dtype = self.get_xyz.dtype

        def columns(prefix, count):
            return np.stack(
                [np.asarray(v[f"{prefix}{index}"]) for index in range(count)],
                axis=1,
            ).astype(np.float32)

        with torch.no_grad():
            if "f_dc_j" in names:
                values = torch.as_tensor(
                    np.asarray(v["f_dc_j"], dtype=np.float32),
                    device=device,
                    dtype=dtype,
                )
                self._features_dc.data[:] = values[:, None, None]
                rest_count = min(self._features_rest.shape[1], 15)
                for index in range(rest_count):
                    name = f"f_rest_j_{index}"
                    if name in names:
                        values = torch.as_tensor(
                            np.asarray(v[name], dtype=np.float32),
                            device=device,
                            dtype=dtype,
                        )
                        self._features_rest.data[:, index, :] = values[:, None]
                if rest_count:
                    self.active_sh_degree = min(1, self.max_sh_degree)

            if "opacity" in names:
                self._opacity.data[:] = torch.as_tensor(
                    np.asarray(v["opacity"], dtype=np.float32)[:, None],
                    device=device,
                    dtype=dtype,
                )

            if {"mu_d_0", "mu_d_1", "mu_d_2"}.issubset(names):
                self._mu_d.data[:] = torch.as_tensor(
                    columns("mu_d_", 3), device=device, dtype=dtype
                )
            else:
                if not torch.is_tensor(light_dirs):
                    light_dirs = torch.tensor(np.asarray(light_dirs), dtype=torch.float32)
                light_dirs = light_dirs.to(device=device, dtype=dtype)
                mean_l = light_dirs.mean(dim=0)
                mu_d0 = (
                    torch.tensor([0.0, 0.0, 1.0], device=device, dtype=dtype)
                    if mean_l.norm() < 0.2
                    else torch.nn.functional.normalize(mean_l, dim=0)
                )
                self._mu_d.data[:] = mu_d0.view(1, 3)
            if "mu_t" in names:
                self._mu_t.data[:] = torch.as_tensor(
                    np.asarray(v["mu_t"], dtype=np.float32)[:, None],
                    device=device,
                    dtype=dtype,
                )
            if all(f"chol_diag_{index}" in names for index in range(7)):
                self._cholesky_diag.data[:] = torch.as_tensor(
                    columns("chol_diag_", 7), device=device, dtype=dtype
                )
            if all(f"chol_offdiag_{index}" in names for index in range(21)):
                self._cholesky_offdiag.data[:] = torch.as_tensor(
                    columns("chol_offdiag_", 21), device=device, dtype=dtype
                )
            for name, parameter in (
                ("lambda_t", self._lambda_t),
                ("lambda_d", self._lambda_d),
            ):
                if name in names:
                    parameter.data[:] = torch.as_tensor(
                        np.asarray(v[name], dtype=np.float32)[:, None],
                        device=device,
                        dtype=dtype,
                    )

            if warmup_geometry:
                scale = np.stack([np.asarray(v[f"scale_{i}"]) for i in range(3)], axis=1).astype(np.float32)
                rot = np.stack([np.asarray(v[f"rot_{i}"]) for i in range(4)], axis=1).astype(np.float32)
                self._scaling.data[:] = torch.tensor(scale, device=device, dtype=dtype)
                self._rotation.data[:] = torch.tensor(rot, device=device, dtype=dtype)
                if {"chol_diag_0", "chol_diag_1", "chol_diag_2"}.issubset(names):
                    chol_diag = np.stack(
                        [np.asarray(v[f"chol_diag_{i}"]) for i in range(3)], axis=1
                    ).astype(np.float32)
                    chol_offdiag = np.stack(
                        [np.asarray(v[f"chol_offdiag_{i}"]) for i in range(3)], axis=1
                    ).astype(np.float32)
                    self._cholesky_diag.data[:, :3] = torch.tensor(
                        chol_diag, device=device, dtype=dtype
                    )
                    self._cholesky_offdiag.data[:, :3] = torch.tensor(
                        chol_offdiag, device=device, dtype=dtype
                    )
                else:
                    rotations = build_rotation(self._rotation)
                    scales = torch.exp(self._scaling)
                    covariance = rotations @ torch.diag_embed(scales.square()) @ rotations.transpose(1, 2)
                    cholesky = torch.linalg.cholesky(
                        covariance + torch.eye(3, device=device, dtype=dtype).unsqueeze(0) * 1e-10
                    )
                    spatial_diag = torch.diagonal(cholesky, dim1=1, dim2=2)
                    self._cholesky_diag.data[:, :3] = torch.log(spatial_diag)
                    self._cholesky_offdiag.data[:, 0] = cholesky[:, 1, 0] / spatial_diag[:, 1]
                    self._cholesky_offdiag.data[:, 1] = cholesky[:, 2, 0] / spatial_diag[:, 2]
                    self._cholesky_offdiag.data[:, 2] = cholesky[:, 2, 1] / spatial_diag[:, 2]

            if "f_dc_t" in names:
                values = torch.as_tensor(
                    np.asarray(v["f_dc_t"], dtype=np.float32),
                    device=device,
                    dtype=dtype,
                )
                self._features_dc_t.data[:] = values[:, None, None]
                rest_count = min(self._features_rest_t.shape[1], 15)
                for index in range(rest_count):
                    name = f"f_rest_t_{index}"
                    if name in names:
                        values = torch.as_tensor(
                            np.asarray(v[name], dtype=np.float32),
                            device=device,
                            dtype=dtype,
                        )
                        self._features_rest_t.data[:, index, :] = values[:, None]
                if rest_count:
                    self.active_sh_degree_t = min(1, self.max_sh_degree_t)
        self.load_teacher_anchors_from_ply(ply_path)

    def _init_features_t(self):
        """Initialize T_view SH parameters (DC + rest) for all current points."""
        n_points = self.get_xyz.shape[0]
        device = self.get_xyz.device
        dtype = self.get_xyz.dtype
        K_t = (self.max_sh_degree_t + 1) ** 2

        # DC init: T_view ~ 0.5 (mid-range transmittance) -> SH DC = RGB2SH(0.5)
        # Replicate to 3 channels for rasterizer compatibility.
        dc_val = float(RGB2SH(torch.tensor(0.5)).item())
        features_dc_t = torch.full((n_points, 1, 3), dc_val, dtype=dtype, device=device)
        features_rest_t = torch.zeros((n_points, K_t - 1, 3), dtype=dtype, device=device)

        self._features_dc_t = nn.Parameter(features_dc_t.requires_grad_(True))
        self._features_rest_t = nn.Parameter(features_rest_t.requires_grad_(True))

    def training_setup(self, training_args):
        """Extend parent training_setup with T_view SH optimizer groups."""
        super().training_setup(training_args)

        #***REngine Begin Modify added by tuckersu. [T_view dual SH: register SH_T optimizer groups]
        lr_t = training_args.feature_lr
        self.optimizer.add_param_group(
            {"params": [self._features_dc_t], "lr": lr_t, "name": "f_dc_t"}
        )
        self.optimizer.add_param_group(
            {"params": [self._features_rest_t], "lr": lr_t / 20.0, "name": "f_rest_t"}
        )
        allowed = {
            "smoke": {
                "f_dc", "f_rest",
            },
            "relight": {
                "f_dc", "f_rest",
            },
            "geometry": {
                "f_dc", "f_rest", "opacity", "scaling", "rotation", "mu_d",
                "cholesky_diag", "cholesky_offdiag", "lambda_d",
                "f_dc_t", "f_rest_t",
            },
            "recover": {
                "f_dc", "f_rest", "opacity", "scaling", "rotation", "mu_d",
                "cholesky_diag", "cholesky_offdiag", "lambda_d",
                "f_dc_t", "f_rest_t",
            },
        }[self.training_stage]
        groups = []
        for group in self.optimizer.param_groups:
            trainable = group["name"] in allowed
            for parameter in group["params"]:
                parameter.requires_grad_(trainable)
            if trainable:
                groups.append({
                    "params": group["params"],
                    "lr": group["lr"],
                    "name": group["name"],
                })
        self.optimizer = torch.optim.Adam(groups, lr=0.0, eps=1e-15)
        #***REngine End Modify

    def restore_spatial_cholesky_from_ply(self, ply_path):
        """Restore the fixed B2 spatial block before a frozen-geometry stage."""
        vertex = PlyData.read(ply_path).elements[0]
        values = (
            (
                self._cholesky_diag,
                np.stack([np.asarray(vertex[f"chol_diag_{i}"]) for i in range(3)], axis=1),
            ),
            (
                self._cholesky_offdiag,
                np.stack([np.asarray(vertex[f"chol_offdiag_{i}"]) for i in range(3)], axis=1),
            ),
        )
        with torch.no_grad():
            for parameter, source in values:
                parameter[:, :3].copy_(
                    torch.as_tensor(source, dtype=parameter.dtype, device=parameter.device)
                )
                state = self.optimizer.state.get(parameter, {})
                for key in ("exp_avg", "exp_avg_sq", "max_exp_avg_sq"):
                    if key in state:
                        state[key][:, :3].zero_()

    def load_teacher_anchors_from_ply(self, ply_path):
        """Load the coefficient prefix present in the anchor PLY."""
        vertex = PlyData.read(ply_path).elements[0]
        names = set(vertex.data.dtype.names)
        n_points = self.get_xyz.shape[0]
        if len(vertex.data) != n_points or "opacity" not in names:
            self._teacher_anchor = None
            return

        def scalar(name):
            return torch.as_tensor(
                np.asarray(vertex[name], dtype=np.float32),
                device=self.get_xyz.device,
                dtype=self.get_xyz.dtype,
            )

        rest_j_count = next(
            (
                index
                for index in range(self._features_rest.shape[1])
                if f"f_rest_j_{index}" not in names
            ),
            self._features_rest.shape[1],
        )
        rest_t_count = next(
            (
                index
                for index in range(self._features_rest_t.shape[1])
                if f"f_rest_t_{index}" not in names
            ),
            self._features_rest_t.shape[1],
        )
        rest_j = (
            torch.stack(
                [scalar(f"f_rest_j_{index}") for index in range(rest_j_count)],
                dim=1,
            )[:, :, None].expand(-1, -1, 3)
            if rest_j_count
            else self._features_rest.new_empty((n_points, 0, 3))
        )
        rest_t = (
            torch.stack(
                [scalar(f"f_rest_t_{index}") for index in range(rest_t_count)],
                dim=1,
            )[:, :, None].expand(-1, -1, 3)
            if rest_t_count
            else self._features_rest_t.new_empty((n_points, 0, 3))
        )
        self._teacher_anchor = (
            torch.sigmoid(scalar("opacity"))[:, None],
            scalar("f_dc_j")[:, None, None].expand_as(self._features_dc).clone(),
            rest_j,
            scalar("f_dc_t")[:, None, None].expand_as(self._features_dc_t).clone(),
            rest_t,
        )

    def teacher_anchor_loss(self):
        if self._teacher_anchor is None:
            return self.get_xyz.new_zeros(())
        current = (
            self.get_opacity,
            self._features_dc,
            self._features_rest,
            self._features_dc_t,
            self._features_rest_t,
        )
        terms = [
            (
                value[tuple(slice(0, size) for size in anchor.shape)] - anchor
            ).square().mean()
            for value, anchor in zip(current, self._teacher_anchor)
            if anchor.numel()
        ]
        return torch.stack(terms).mean()

    def capture(self):
        """Include T_view SH in checkpoint."""
        base = super().capture()
        return base + (
            self.max_sh_degree_t,
            self.active_sh_degree_t,
            self._features_dc_t,
            self._features_rest_t,
        )

    def restore(self, model_args, training_args):
        """Restore T_view SH from checkpoint."""
        # Last 4 entries are ours
        base_args = model_args[:-4]
        (
            self.max_sh_degree_t,
            self.active_sh_degree_t,
            self._features_dc_t,
            self._features_rest_t,
        ) = model_args[-4:]
        super().restore(base_args, training_args)
        # Re-add T_view SH optimizer groups (super().restore calls training_setup,
        # which already adds them via our override).

    #***REngine Begin Modify added by tuckersu. [PLY IO: J and T_view stored as single channel]
    def construct_list_of_attributes(self):
        """Build PLY attribute name list.

        J and T_view are both scalar signals stored as single-channel in PLY
        (replicated to 3ch in memory for rasterizer compatibility).
        """
        l = ['x', 'y', 'z', 'nx', 'ny', 'nz']

        # J SH (single channel in PLY)
        K_j = (self.max_sh_degree + 1) ** 2
        l.append('f_dc_j')
        for i in range(K_j - 1):
            l.append(f'f_rest_j_{i}')

        l.append('opacity')
        for i in range(self._scaling.shape[1]):
            l.append(f'scale_{i}')
        for i in range(self._rotation.shape[1]):
            l.append(f'rot_{i}')

        # 7D params
        l.extend(["mu_t", "mu_d_0", "mu_d_1", "mu_d_2"])
        for idx in range(7):
            l.append(f"chol_diag_{idx}")
        for idx in range(21):
            l.append(f"chol_offdiag_{idx}")
        l.append("lambda_t")
        l.append("lambda_d")

        # T_view SH (single channel in PLY)
        K_t = (self.max_sh_degree_t + 1) ** 2
        l.append('f_dc_t')
        for i in range(K_t - 1):
            l.append(f'f_rest_t_{i}')

        return l
    #***REngine End Modify

    #***REngine Begin Modify added by tuckersu. [PLY IO: save J and T_view as single channel]
    def save_ply(self, path):
        """Save model with J and T_view as single-channel SH in PLY."""
        mkdir_p(os.path.dirname(path))

        xyz = self._xyz.detach().cpu().numpy()
        normals = np.zeros_like(xyz)

        # J SH: _features_dc shape [N, 1, 3] → take channel 0 → [N, 1]
        f_dc_j = self._features_dc.detach()[:, :, 0:1].cpu().numpy().reshape(-1, 1)
        #***REngine Begin Modify added by tuckersu. [Robust reshape for zero-sized SH-rest tensors when saving PLY]
        # _features_rest shape [N, K-1, 3] → take channel 0 → [N, K-1]
        n_points = int(xyz.shape[0])
        k_rest_j = int(self._features_rest.shape[1]) if self._features_rest.ndim >= 2 else 0
        if k_rest_j > 0:
            f_rest_j = self._features_rest.detach()[:, :, 0:1].cpu().numpy().reshape(n_points, k_rest_j)
        else:
            f_rest_j = np.zeros((n_points, 0), dtype=np.float32)
        #***REngine End Modify


        opacities = self._opacity.detach().cpu().numpy()
        scale = self._scaling.detach().cpu().numpy()
        rotation = self._rotation.detach().cpu().numpy()

        # 7D params
        mu_t = self._mu_t.detach().cpu().numpy()
        mu_d = self._mu_d.detach().cpu().numpy()
        chol_diag = self._cholesky_diag.detach().cpu().numpy()
        chol_offdiag = self._cholesky_offdiag.detach().cpu().numpy()
        lambda_t = self._lambda_t.detach().cpu().numpy()
        lambda_d = self._lambda_d.detach().cpu().numpy()

        # T_view SH: same as J, take channel 0
        f_dc_t = self._features_dc_t.detach()[:, :, 0:1].cpu().numpy().reshape(-1, 1)
        #***REngine Begin Modify added by tuckersu. [Handle sh_degree_t=0 when exporting PLY]
        k_rest_t = int(self._features_rest_t.shape[1]) if self._features_rest_t.ndim >= 2 else 0
        if k_rest_t > 0:
            f_rest_t = self._features_rest_t.detach()[:, :, 0:1].cpu().numpy().reshape(n_points, k_rest_t)
        else:
            f_rest_t = np.zeros((n_points, 0), dtype=np.float32)
        #***REngine End Modify


        dtype_full = [(attribute, "f4") for attribute in self.construct_list_of_attributes()]
        elements = np.empty(xyz.shape[0], dtype=dtype_full)

        attributes = np.concatenate(
            [
                xyz,
                normals,
                f_dc_j,
                f_rest_j,
                opacities,
                scale,
                rotation,
                mu_t,
                mu_d,
                chol_diag,
                chol_offdiag,
                lambda_t,
                lambda_d,
                f_dc_t,
                f_rest_t,
            ],
            axis=1,
        )
        elements[:] = list(map(tuple, attributes))
        el = PlyElement.describe(elements, "vertex")
        PlyData([el]).write(path)
    #***REngine End Modify

    #***REngine Begin Modify added by tuckersu. [Revert load_ply to base-class behavior]
    def load_ply(self, path, use_train_test_exp=False):
        """Reuse base 3DGS PLY loader directly."""
        super().load_ply(path, use_train_test_exp=use_train_test_exp)
    #***REngine End Modify

    def prune_points(self, mask):
        """Prune including T_view SH tensors."""
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
        #***REngine Begin Modify added by tuckersu. [T_view dual SH: prune SH_T]
        self._features_dc_t = optimizable_tensors["f_dc_t"]
        self._features_rest_t = optimizable_tensors["f_rest_t"]
        #***REngine End Modify

        self.xyz_gradient_accum = self.xyz_gradient_accum[valid_points_mask]
        self.denom = self.denom[valid_points_mask]
        self.max_radii2D = self.max_radii2D[valid_points_mask]
        #***REngine Begin Modify added by tuckersu. [Guard tmp_radii for RAP-only prune path]
        if self.tmp_radii is not None:
            self.tmp_radii = self.tmp_radii[valid_points_mask]
        #***REngine End Modify


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
        new_features_dc_t=None,
        new_features_rest_t=None,
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
            #***REngine Begin Modify added by tuckersu. [T_view dual SH: densify SH_T]
            "f_dc_t": new_features_dc_t if new_features_dc_t is not None else self._features_dc_t[:0],
            "f_rest_t": new_features_rest_t if new_features_rest_t is not None else self._features_rest_t[:0],
            #***REngine End Modify
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
        self._features_dc_t = optimizable_tensors["f_dc_t"]
        self._features_rest_t = optimizable_tensors["f_rest_t"]

        self.tmp_radii = torch.cat((self.tmp_radii, new_tmp_radii))
        self.xyz_gradient_accum = torch.zeros((self.get_xyz.shape[0], 1), device="cuda")
        self.denom = torch.zeros((self.get_xyz.shape[0], 1), device="cuda")
        self.max_radii2D = torch.zeros((self.get_xyz.shape[0]), device="cuda")

    def densify_and_split(self, grads, grad_threshold, scene_extent, n_split=2):
        from utils.general_utils import build_rotation

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
        #***REngine Begin Modify added by tuckersu. [T_view dual SH: split SH_T]
        new_features_dc_t = self._features_dc_t[selected_pts_mask].repeat(n_split, 1, 1)
        new_features_rest_t = self._features_rest_t[selected_pts_mask].repeat(n_split, 1, 1)
        #***REngine End Modify

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
        #***REngine Begin Modify added by tuckersu. [T_view dual SH: clone SH_T]
        new_features_dc_t = self._features_dc_t[selected_pts_mask]
        new_features_rest_t = self._features_rest_t[selected_pts_mask]
        #***REngine End Modify

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
            new_features_dc_t,
            new_features_rest_t,
        )

#***REngine End Modify
