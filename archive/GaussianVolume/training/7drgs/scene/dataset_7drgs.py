#***REngine Begin Modify added by tuckersu. [Add 7DRGS dataset adapter: OpenCV c2w -> 3DGS camera + per (view,light) RGSCamera]
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

"""7DRGS dataset adapter.

Reuses RelightDataset for all EXR/mask/depth/json IO, then wraps every
(view, light) pair into a lightweight RGSCamera whose fields are compatible
with the 3DGS rasterizer (render_7drgs / train_7drgs):

    image_height / image_width / FoVx / FoVy
    world_view_transform / full_proj_transform / camera_center  (cuda)
    timestamp                                                    (0, single frame)
    light_dir                                                    (cuda [3])
    original_image = J (J_TView RGB, linear)                     ([3,H,W])
    alpha_mask     = foreground mask                             ([1,H,W])
    invdepthmap    = 1 / clamp(depth_m, eps_near)                ([1,H,W])
    depth_mask     = foreground mask                             ([1,H,W])
    depth_reliable = True

Coordinate convention: transforms_train.json stores OpenCV c2w (x-right, y-down,
z-forward, meters), which matches the 3DGS projection convention (camera looks
+z) -> no y/z flip needed (unlike Blender/OpenGL).
"""

import numpy as np
import torch

from utils.graphics_utils import getWorld2View2, getProjectionMatrix, focal2fov
from scene.relight_dataset import RelightDataset


class RGSCamera:
    """Lightweight camera compatible with the 3DGS rasterizer for one (view, light)."""

    def __init__(self, uid, image_name, R, T, FoVx, FoVy, width, height,
                 light_dir, image, alpha_mask, invdepthmap, depth_mask,
                 tview_gt=None, timestamp=0.0, znear=0.01, zfar=100.0):
        self.uid = uid
        self.image_name = image_name
        self.R = R
        self.T = T
        self.FoVx = float(FoVx)
        self.FoVy = float(FoVy)
        self.image_width = int(width)
        self.image_height = int(height)
        self.timestamp = float(timestamp)
        self.znear = float(znear)
        self.zfar = float(zfar)

        # GT signals (kept on CPU; .cuda() at use site like the standard Camera).
        self.original_image = image          # [3,H,W] linear J
        self.alpha_mask = alpha_mask         # [1,H,W] 0/1
        self.invdepthmap = invdepthmap       # [1,H,W]
        self.depth_mask = depth_mask         # [1,H,W]
        self.depth_reliable = True
        #***REngine Begin Modify added by tuckersu. [T_view dual SH: store T_view GT from EXR alpha]
        self.tview_gt = tview_gt             # [1,H,W] T_view (transmittance), or None
        #***REngine End Modify

        # Direction condition for slicing (small tensor kept on cuda).
        self.light_dir = light_dir.cuda() if torch.is_tensor(light_dir) else \
            torch.tensor(np.asarray(light_dir), dtype=torch.float32, device="cuda")

        # Projection matrices (same construction as scene/cameras.py Camera).
        self.world_view_transform = torch.tensor(getWorld2View2(R, T)).transpose(0, 1).cuda()
        self.projection_matrix = getProjectionMatrix(
            znear=self.znear, zfar=self.zfar, fovX=self.FoVx, fovY=self.FoVy
        ).transpose(0, 1).cuda()
        self.full_proj_transform = (
            self.world_view_transform.unsqueeze(0).bmm(self.projection_matrix.unsqueeze(0))
        ).squeeze(0)
        self.camera_center = self.world_view_transform.inverse()[3, :3]


class Dataset7DRGS:
    """Multi-view x multi-light dataset producing RGSCamera lists for 7DRGS."""

    def __init__(self, source_path, sh_degree=2, val_ratio=0.2, eps_near=None,
                 znear=0.01, zfar=100.0, device="cuda"):
        self.source_path = source_path

        self._rd_train = RelightDataset(source_path, split="train", sh_degree=sh_degree,
                                        device=device, val_ratio=val_ratio)
        self._rd_val = RelightDataset(source_path, split="val", sh_degree=sh_degree,
                                      device=device, val_ratio=val_ratio)

        self.light_dirs = self._rd_train.light_dirs            # [L,3] cuda
        self.num_lights = self._rd_train.num_lights()
        n_val_lights = max(1, int(self.num_lights * val_ratio))
        self.train_light_indices = list(range(max(1, self.num_lights - n_val_lights)))
        self.val_light_indices = list(range(self.num_lights - n_val_lights, self.num_lights))
        self.eps_near = float(eps_near) if eps_near is not None else float(self._rd_train.eps_near)
        self.bbox_min = self._rd_train.bbox_min
        self.bbox_max = self._rd_train.bbox_max
        self.sh_degree = sh_degree
        self.znear = znear
        self.zfar = zfar

        self.train_cameras = self._build_cameras(self._rd_train, self.train_light_indices)
        self.test_cameras = self._build_cameras(self._rd_val, self.val_light_indices)

        # Free EXR caches now that pixels live inside RGSCamera tensors.
        self._rd_train._j_tview_cache.clear()
        self._rd_val._j_tview_cache.clear()

        self.cameras_extent = self._compute_extent(self._rd_train)
        print(f"[Dataset7DRGS] train (v,l)={len(self.train_cameras)}, "
              f"test (v,l)={len(self.test_cameras)}, lights={self.num_lights}, "
              f"extent={self.cameras_extent:.4f}")

    def _build_cameras(self, rd, light_indices):
        depth_scale = 1.0 if rd._use_legacy_format else 0.01
        cams = []
        for vi in range(rd.num_views()):
            cam = rd.cameras[vi]
            c2w = np.asarray(cam.c2w, dtype=np.float64)
            R_c2w = c2w[:3, :3]
            cam_pos = c2w[:3, 3]
            R = R_c2w                              # getWorld2View2 will transpose -> R_w2c
            T = (-R_c2w.T @ cam_pos).astype(np.float64)

            FoVx = focal2fov(cam.fl_x, cam.w)
            FoVy = focal2fov(cam.fl_y, cam.h)

            mask_np = rd._get_mask(vi)             # [H,W] in [0,1]
            depth_np = rd._get_depth(vi) * depth_scale  # [H,W] meters
            mask_t = torch.from_numpy(mask_np.astype(np.float32))[None]      # [1,H,W]
            fg = (mask_np > 0.5).astype(np.float32)
            inv_depth = 1.0 / np.clip(depth_np, self.eps_near, None)
            inv_depth = inv_depth * fg             # zero out background
            inv_depth_t = torch.from_numpy(inv_depth.astype(np.float32))[None]  # [1,H,W]
            depth_mask_t = torch.from_numpy(fg)[None]                            # [1,H,W]

            for li in light_indices:
                j_tview = rd._get_j_tview(vi, li)  # [H,W,4], RGB=J, A=T_view
                J = np.ascontiguousarray(np.transpose(j_tview[:, :, :3], (2, 0, 1)))  # [3,H,W]
                J_t = torch.from_numpy(J.astype(np.float32))
                #***REngine Begin Modify added by tuckersu. [T_view dual SH: extract T_view GT from alpha]
                tview_np = j_tview[:, :, 3]  # [H,W] transmittance
                tview_t = torch.from_numpy(tview_np.astype(np.float32))[None]  # [1,H,W]
                #***REngine End Modify

                cams.append(RGSCamera(
                    uid=len(cams),
                    image_name=f"view{cam.uid:04d}_light{li:04d}",
                    R=R, T=T, FoVx=FoVx, FoVy=FoVy, width=cam.w, height=cam.h,
                    light_dir=rd.light_dirs[li].detach().cpu(),
                    image=J_t, alpha_mask=mask_t, invdepthmap=inv_depth_t,
                    depth_mask=depth_mask_t, tview_gt=tview_t, timestamp=0.0,
                    znear=self.znear, zfar=self.zfar,
                ))
            # release per-view caches as we go to bound memory
            rd._j_tview_cache = {k: v for k, v in rd._j_tview_cache.items() if k[0] != vi}
        return cams

    def _compute_extent(self, rd):
        """getNerfppNorm-style scene extent from camera centers."""
        centers = []
        for vi in range(rd.num_views()):
            c2w = np.asarray(rd.cameras[vi].c2w, dtype=np.float64)
            centers.append(c2w[:3, 3])
        centers = np.stack(centers, axis=0)
        center = centers.mean(axis=0, keepdims=True)
        diagonal = np.linalg.norm(centers - center, axis=1).max()
        return float(diagonal * 1.1)

    def getTrainCameras(self):
        return self.train_cameras

    def getTestCameras(self):
        return self.test_cameras
#***REngine End Modify
