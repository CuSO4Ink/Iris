#***REngine Begin Modify added by tuckersu. [Add multi-view multi-light relight dataset for RGS training]
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
from torch import Tensor
from typing import Dict, List, Optional, Tuple


class RelightCamera:
    """Lightweight camera info for relight dataset."""

    def __init__(self, uid: int, c2w: np.ndarray, fl_x: float, fl_y: float,
                 cx: float, cy: float, w: int, h: int, near: float, far: float):
        self.uid = uid
        self.c2w = c2w  # [4, 4] OpenCV c2w, meters
        self.fl_x = fl_x
        self.fl_y = fl_y
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.near = near
        self.far = far


class RelightDataset:
    """
    Multi-view × multi-light dataset for relightable GS training.

    Loads data following RGS_Data_Format.md:
      - transforms_train.json (cameras)
      - lights.json (light directions)
      - scene.json (bbox, phase function, etc.)
      - J_TView/*.exr (RGB=J, A=T_view) — primary training signal
      - depth/*.exr (R=depth) — per-view depth
      - mask/*.png (binary foreground mask)
    """

    def __init__(
        self,
        source_path: str,
        split: str = "train",
        sh_degree: int = 2,
        device: str = "cuda",
        val_ratio: float = 0.2,
    ):
        self.source_path = source_path
        self.split = split
        self.device = device
        self.sh_degree = sh_degree

        # Load metadata
        self._load_transforms(source_path)
        self._load_lights(source_path)
        self._load_scene(source_path)

        # Split by view index (80/20 train/val)
        n_views = len(self._all_cameras)
        indices = list(range(n_views))
        n_val = max(1, int(n_views * val_ratio))
        # Deterministic split: last n_val views are val
        if split == "val":
            self._view_indices = indices[-n_val:]
        else:
            self._view_indices = indices[:-n_val] if n_val < n_views else indices

        self.cameras = [self._all_cameras[i] for i in self._view_indices]

        # Detect data format: new (J_TView/*.exr) vs legacy (J/*.npy + trans_view/*.npy)
        self._use_legacy_format = not os.path.isdir(os.path.join(source_path, "J_TView"))
        if self._use_legacy_format:
            # Legacy format: J/*.npy (RGB=J, A=1) + trans_view/*.npy (R=T_view)
            assert os.path.isdir(os.path.join(source_path, "J")), \
                f"Neither J_TView/ nor J/ found in {source_path}"
            assert os.path.isdir(os.path.join(source_path, "trans_view")), \
                f"Legacy format requires trans_view/ in {source_path}"
            print("[RelightDataset] Using LEGACY format: J/*.npy + trans_view/*.npy + depth/*.npy")
        else:
            print("[RelightDataset] Using NEW format: J_TView/*.exr + depth/*.exr")

        # Lazy-load caches
        self._j_tview_cache = {}
        self._depth_cache = {}
        self._mask_cache = {}
        self._trans_view_cache = {}

        print(f"[RelightDataset] split={split}, views={len(self.cameras)}, "
              f"lights={self.num_lights()}, bbox_diag={self.bbox_diag:.4f}m")

    def _load_transforms(self, path: str):
        """Load cameras from transforms_train.json.

        Supports two formats:
          - Global intrinsics: fl_x/fl_y/cx/cy/w/h at top-level
          - Per-frame intrinsics: fl_x/fl_y/cx/cy/w/h inside each frame
        """
        tf_path = os.path.join(path, "transforms_train.json")
        with open(tf_path, 'r') as f:
            data = json.load(f)

        # Check if intrinsics are at top level or per-frame
        has_global_intrinsics = "fl_x" in data

        if has_global_intrinsics:
            self.fl_x = float(data["fl_x"])
            self.fl_y = float(data["fl_y"])
            self.cx = float(data["cx"])
            self.cy = float(data["cy"])
            self.img_w = int(data["w"])
            self.img_h = int(data["h"])

        self._all_cameras = []
        for i, frame in enumerate(data["frames"]):
            c2w = np.array(frame["transform_matrix"], dtype=np.float64)
            near = float(frame.get("near", 0.1))
            far = float(frame.get("far", 100.0))

            # Per-frame intrinsics take priority
            fl_x = float(frame.get("fl_x", self.fl_x if has_global_intrinsics else 0))
            fl_y = float(frame.get("fl_y", self.fl_y if has_global_intrinsics else 0))
            cx = float(frame.get("cx", self.cx if has_global_intrinsics else 0))
            cy = float(frame.get("cy", self.cy if has_global_intrinsics else 0))
            w = int(frame.get("w", self.img_w if has_global_intrinsics else 0))
            h = int(frame.get("h", self.img_h if has_global_intrinsics else 0))

            cam = RelightCamera(
                uid=i, c2w=c2w,
                fl_x=fl_x, fl_y=fl_y,
                cx=cx, cy=cy,
                w=w, h=h,
                near=near, far=far,
            )
            self._all_cameras.append(cam)

        # Set global intrinsics from first frame if not at top level
        if not has_global_intrinsics and len(self._all_cameras) > 0:
            first = self._all_cameras[0]
            self.fl_x = first.fl_x
            self.fl_y = first.fl_y
            self.cx = first.cx
            self.cy = first.cy
            self.img_w = first.w
            self.img_h = first.h

    def _load_lights(self, path: str):
        """Load light directions from lights.json.

        Supports two formats:
          - New: {"L": n, "light_dirs": [[x,y,z], ...]}
          - Legacy: {"directions": [[x,y,z], ...]}
        """
        lights_path = os.path.join(path, "lights.json")
        with open(lights_path, 'r') as f:
            data = json.load(f)

        # Support both key names
        if "light_dirs" in data:
            light_dirs = np.array(data["light_dirs"], dtype=np.float32)
        elif "directions" in data:
            light_dirs = np.array(data["directions"], dtype=np.float32)
        else:
            raise RuntimeError(f"lights.json missing 'light_dirs' or 'directions' key")

        self.n_lights = int(data.get("L", len(light_dirs)))
        # Normalize
        norms = np.linalg.norm(light_dirs, axis=1, keepdims=True)
        light_dirs = light_dirs / np.clip(norms, 1e-8, None)
        self.light_dirs = torch.tensor(light_dirs, device=self.device)

    def _load_scene(self, path: str):
        """Load scene metadata from scene.json.

        Supports two formats:
          - New: {"bbox_min":[], "bbox_max":[], "phase_function":{"type":"hg","g":0.3},
                  "depth_thresholds":{"eps_near":0.01}, ...}
          - Legacy: {"bbox_min":[], "bbox_max":[], "phase_g":0.0, "eps_near":0.01, ...}
        """
        scene_path = os.path.join(path, "scene.json")
        with open(scene_path, 'r') as f:
            data = json.load(f)

        self.bbox_min = torch.tensor(data["bbox_min"], dtype=torch.float32, device=self.device)
        self.bbox_max = torch.tensor(data["bbox_max"], dtype=torch.float32, device=self.device)
        self.bbox_diag = (self.bbox_max - self.bbox_min).norm().item()

        # Phase function — support both nested dict and flat key
        pf = data.get("phase_function", None)
        if pf is not None:
            if isinstance(pf, str):
                self.phase_meta = {"type": pf, "g": 0.0}
            else:
                self.phase_meta = {"type": pf.get("type", "isotropic"), "g": float(pf.get("g", 0.0))}
        else:
            # Legacy: phase_g at top level
            g_val = float(data.get("phase_g", 0.0))
            ptype = "hg" if abs(g_val) > 1e-6 else "isotropic"
            self.phase_meta = {"type": ptype, "g": g_val}

        # Depth thresholds — support both nested and flat
        dt = data.get("depth_thresholds", None)
        if dt is not None:
            self.eps_near = float(dt.get("eps_near", 0.01))
        else:
            # Legacy: eps_near at top level
            self.eps_near = float(data.get("eps_near", 0.01))

        # Background value
        bg = data.get("background_value", {"J": 0, "depth_near": 0, "depth_far": 0, "trans_view": 1})
        if isinstance(bg, dict):
            self.bg_J = float(bg.get("J", 0.0))
            self.bg_trans_view = float(bg.get("trans_view", 1.0))
            self.bg_depth_near = float(bg.get("depth_near", 0.0))
            self.bg_depth_far = float(bg.get("depth_far", 0.0))
        else:
            # Legacy: list format [r, g, b]
            self.bg_J = 0.0
            self.bg_trans_view = 1.0
            self.bg_depth_near = 0.0
            self.bg_depth_far = 0.0
        self.bg_value = torch.tensor([self.bg_J, self.bg_J, self.bg_J], dtype=torch.float32, device=self.device)

    def get_camera(self, vi: int) -> RelightCamera:
        return self.cameras[vi]

    def num_views(self) -> int:
        return len(self.cameras)

    def num_lights(self) -> int:
        return self.n_lights

    def get_j_tview(self, vi: int, li: int) -> np.ndarray:
        """Public accessor for J_TView data: [H, W, 4] with RGB=J, A=T_view."""
        return self._get_j_tview(vi, li)

    def _load_exr(self, path: str) -> np.ndarray:
        """Load EXR file as float32 numpy array [H, W, C]."""
        try:
            import OpenEXR
            import Imath
            exr_file = OpenEXR.InputFile(path)
            header = exr_file.header()
            dw = header['dataWindow']
            w = dw.max.x - dw.min.x + 1
            h = dw.max.y - dw.min.y + 1

            pt = Imath.PixelType(Imath.PixelType.FLOAT)
            channels = []
            for ch_name in ['R', 'G', 'B', 'A']:
                if ch_name in header['channels']:
                    raw = exr_file.channel(ch_name, pt)
                    arr = np.frombuffer(raw, dtype=np.float32).reshape(h, w)
                    channels.append(arr)
                else:
                    channels.append(np.zeros((h, w), dtype=np.float32))
            return np.stack(channels, axis=-1)  # [H, W, 4]
        except ImportError:
            # Fallback: try imageio
            import imageio
            img = imageio.imread(path)
            if img.dtype != np.float32:
                img = img.astype(np.float32)
            if img.ndim == 2:
                img = img[:, :, np.newaxis]
            return img

    def _get_j_tview(self, vi: int, li: int) -> np.ndarray:
        """Load J+T_view data: [H, W, 4] with RGB=J, A=T_view.

        Supports two formats:
          - New: J_TView/*.exr (RGBA where A=T_view)
          - Legacy: J/*.npy (RGBA, RGB=J) + trans_view/*.npy (RGBA, R=T_view)
        """
        key = (vi, li)
        if key not in self._j_tview_cache:
            cam = self.cameras[vi]
            if self._use_legacy_format:
                # Load J from npy
                j_fname = f"view{cam.uid:04d}_light{li:04d}.npy"
                j_path = os.path.join(self.source_path, "J", j_fname)
                j_data = np.load(j_path)  # [H, W, 4] RGB=J, A=1

                # Load T_view from trans_view
                t_view = self._get_trans_view(vi)  # [H, W]

                # Combine: RGB from J, A from T_view
                result = np.copy(j_data)
                result[:, :, 3] = t_view
                self._j_tview_cache[key] = result
            else:
                fname = f"view{cam.uid:04d}_light{li:04d}.exr"
                path = os.path.join(self.source_path, "J_TView", fname)
                self._j_tview_cache[key] = self._load_exr(path)
        return self._j_tview_cache[key]

    def _get_trans_view(self, vi: int) -> np.ndarray:
        """Load trans_view npy (legacy format): [H, W] float32, R channel = T_view."""
        if vi not in self._trans_view_cache:
            cam = self.cameras[vi]
            fname = f"view{cam.uid:04d}.npy"
            path = os.path.join(self.source_path, "trans_view", fname)
            data = np.load(path)  # [H, W, 4]
            self._trans_view_cache[vi] = data[:, :, 0]  # R channel = T_view
        return self._trans_view_cache[vi]

    def _get_depth(self, vi: int) -> np.ndarray:
        """Load depth: [H, W] float32.

        Supports two formats:
          - New: depth/*.exr (R channel, UE units cm)
          - Legacy: depth/*.npy (RGBA, R channel, meters)
        """
        if vi not in self._depth_cache:
            cam = self.cameras[vi]
            if self._use_legacy_format:
                fname = f"view{cam.uid:04d}.npy"
                path = os.path.join(self.source_path, "depth", fname)
                data = np.load(path)  # [H, W, 4]
                self._depth_cache[vi] = data[:, :, 0]  # R channel, already meters
            else:
                fname = f"view{cam.uid:04d}.exr"
                path = os.path.join(self.source_path, "depth", fname)
                depth_rgba = self._load_exr(path)  # [H, W, 4]
                self._depth_cache[vi] = depth_rgba[:, :, 0]  # R channel only
        return self._depth_cache[vi]

    def _get_mask(self, vi: int) -> np.ndarray:
        """Load mask PNG: [H, W] float32 in [0,1]. Binary foreground mask."""
        if vi not in self._mask_cache:
            cam = self.cameras[vi]
            fname = f"view{cam.uid:04d}.png"
            path = os.path.join(self.source_path, "mask", fname)
            from PIL import Image
            img = np.array(Image.open(path)).astype(np.float32)
            if img.max() > 1.0:
                img = img / 255.0
            # Take first channel if multi-channel
            if img.ndim == 3:
                img = img[:, :, 0]
            self._mask_cache[vi] = img
        return self._mask_cache[vi]

    def sample_batch(
        self,
        B_v: int = 4,
        B_l: int = 1,
        B_p: int = 2048,
        mask_only: bool = False,
        need_J: bool = True,
    ) -> Dict[str, Tensor]:
        """
        Sample a training batch.

        Data sources:
          - mask/*.png — foreground/background pixel sampling
          - depth/*.exr — per-view depth (R channel, UE units cm)
          - J_TView/*.exr — RGB=J (radiance), A=T_view (transmittance)

        Args:
            B_v: number of views to sample.
            B_l: number of lights per view.
            B_p: number of pixels per (view, light) pair.
            mask_only: if True, sample only foreground pixels.
            need_J: if True, load J from J_TView (Stage-2).

        Returns:
            dict with keys: view_o, view_d, light_d, J_gt, T_view_gt, depth_gt, mask, cam_idx
        """
        device = self.device
        n_views = len(self.cameras)
        n_lights = self.n_lights

        # Sample views
        view_indices = torch.randint(0, n_views, (B_v,))
        # Sample lights
        light_indices = torch.randint(0, n_lights, (B_v, B_l))

        all_view_o = []
        all_view_d = []
        all_light_d = []
        all_J_gt = []
        all_T_view_gt = []
        all_depth_gt = []
        all_mask = []
        all_cam_idx = []

        for bv in range(B_v):
            vi = view_indices[bv].item()
            cam = self.cameras[vi]
            c2w_tensor = torch.tensor(cam.c2w, dtype=torch.float32, device=device)

            # Load mask and depth for this view
            mask_map = self._get_mask(vi)    # [H, W] float32 in [0,1]
            depth_map = self._get_depth(vi)  # [H, W] float32 in UE cm

            for bl in range(B_l):
                li = light_indices[bv, bl].item()

                # Sample pixels
                if mask_only:
                    fg_coords = np.argwhere(mask_map > 0.5)  # [N_fg, 2] (row, col)
                    if len(fg_coords) < B_p:
                        chosen = np.arange(len(fg_coords))
                    else:
                        chosen = np.random.choice(len(fg_coords), B_p, replace=False)
                    pixel_rows = fg_coords[chosen, 0]
                    pixel_cols = fg_coords[chosen, 1]
                else:
                    # Mixed sampling: 70% foreground, 30% background
                    n_fg = int(B_p * 0.7)
                    n_bg = B_p - n_fg

                    fg_coords = np.argwhere(mask_map > 0.5)
                    bg_coords = np.argwhere(mask_map <= 0.5)

                    if len(fg_coords) >= n_fg:
                        fg_idx = np.random.choice(len(fg_coords), n_fg, replace=False)
                    else:
                        fg_idx = np.random.choice(len(fg_coords), n_fg, replace=True) if len(fg_coords) > 0 else np.array([], dtype=int)

                    if len(bg_coords) >= n_bg:
                        bg_idx = np.random.choice(len(bg_coords), n_bg, replace=False)
                    else:
                        bg_idx = np.random.choice(len(bg_coords), n_bg, replace=True) if len(bg_coords) > 0 else np.array([], dtype=int)

                    if len(fg_idx) > 0 and len(bg_idx) > 0:
                        all_coords = np.concatenate([fg_coords[fg_idx], bg_coords[bg_idx]], axis=0)
                    elif len(fg_idx) > 0:
                        all_coords = fg_coords[fg_idx]
                    else:
                        all_coords = bg_coords[bg_idx]

                    pixel_rows = all_coords[:, 0]
                    pixel_cols = all_coords[:, 1]

                actual_B_p = len(pixel_rows)

                # Pixel centers: (col + 0.5, row + 0.5)
                pixel_xy = torch.tensor(
                    np.stack([pixel_cols + 0.5, pixel_rows + 0.5], axis=1),
                    dtype=torch.float32, device=device,
                )  # [B_p, 2]

                # Generate rays
                from utils.ray_utils import pixels_to_world_rays
                rays_o, rays_d = pixels_to_world_rays(
                    c2w_tensor, cam.fl_x, cam.fl_y, cam.cx, cam.cy, pixel_xy
                )

                # Light direction (same for all pixels in this sample)
                ld = self.light_dirs[li].unsqueeze(0).expand(actual_B_p, -1)  # [B_p, 3]

                # Ground truth: mask
                mask_vals = torch.tensor(
                    mask_map[pixel_rows, pixel_cols], dtype=torch.float32, device=device
                )

                # Ground truth: depth
                # Legacy format: already in meters; New format: cm -> m
                depth_scale = 1.0 if self._use_legacy_format else 0.01
                depth_vals = torch.tensor(
                    depth_map[pixel_rows, pixel_cols] * depth_scale,
                    dtype=torch.float32, device=device
                )

                # Ground truth: J and T_view from J_TView
                if need_J:
                    j_tview = self._get_j_tview(vi, li)  # [H, W, 4]
                    J_vals = torch.tensor(
                        j_tview[pixel_rows, pixel_cols, :3],
                        dtype=torch.float32, device=device,
                    )  # [B_p, 3]
                    T_view_vals = torch.tensor(
                        j_tview[pixel_rows, pixel_cols, 3],
                        dtype=torch.float32, device=device,
                    )  # [B_p]
                    all_J_gt.append(J_vals)
                else:
                    # Stage-1: T_view also from J_TView alpha, use light=0
                    j_tview = self._get_j_tview(vi, 0)  # [H, W, 4]
                    T_view_vals = torch.tensor(
                        j_tview[pixel_rows, pixel_cols, 3],
                        dtype=torch.float32, device=device,
                    )
                    all_J_gt.append(torch.zeros(actual_B_p, 3, device=device))

                all_view_o.append(rays_o)
                all_view_d.append(rays_d)
                all_light_d.append(ld)
                all_T_view_gt.append(T_view_vals)
                all_depth_gt.append(depth_vals)
                all_mask.append(mask_vals)
                all_cam_idx.append(torch.full((actual_B_p,), vi, dtype=torch.long, device=device))

        batch = {
            "view_o": torch.cat(all_view_o, dim=0),         # [B, 3]
            "view_d": torch.cat(all_view_d, dim=0),         # [B, 3]
            "light_d": torch.cat(all_light_d, dim=0),       # [B, 3]
            "J_gt": torch.cat(all_J_gt, dim=0),             # [B, 3]
            "T_view_gt": torch.cat(all_T_view_gt, dim=0),   # [B]
            "depth_gt": torch.cat(all_depth_gt, dim=0),     # [B]
            "mask": torch.cat(all_mask, dim=0),             # [B]
            "cam_idx": torch.cat(all_cam_idx, dim=0),       # [B]
        }

        return batch

    #***REngine Begin Modify added by tuckersu. [Fix 2: patch sampling for depth-gradient consistency]
    def sample_patch_batch(
        self,
        B_v: int = 2,
        patch_size: int = 8,
        n_patches: int = 16,
        need_J: bool = False,
    ) -> Dict[str, Tensor]:
        """
        Sample a training batch as KxK image patches (instead of scattered pixels).

        Patch sampling lets the loss compare PREDICTED vs GT depth GRADIENTS within a
        local neighbourhood, injecting a lateral (perpendicular-to-view) shape signal
        that per-ray T_view / first-hit depth cannot provide. This is the mechanism
        used to break the spherical-symmetry collapse (Fix (2)).

        Rays are laid out patch-major and row-major within each patch, so the returned
        tensors of length B = B_v * n_patches * patch_size^2 can be reshaped to
        [n_patches_total, patch_size, patch_size] for gradient computation.

        Returns the same keys as sample_batch() PLUS:
            patch_size:       int K
            n_patches_total:  int P = B_v * n_patches
        """
        device = self.device
        K = int(patch_size)
        n_views = len(self.cameras)

        view_indices = torch.randint(0, n_views, (B_v,))

        all_view_o, all_view_d, all_light_d = [], [], []
        all_J_gt, all_T_view_gt, all_depth_gt, all_mask, all_cam_idx = [], [], [], [], []

        n_patches_total = 0
        for bv in range(B_v):
            vi = view_indices[bv].item()
            cam = self.cameras[vi]
            c2w_tensor = torch.tensor(cam.c2w, dtype=torch.float32, device=device)

            mask_map = self._get_mask(vi)    # [H, W]
            depth_map = self._get_depth(vi)  # [H, W] (UE cm for new format)
            H, W = mask_map.shape[:2]
            depth_scale = 1.0 if self._use_legacy_format else 0.01

            # Foreground pixels to centre patches on (fall back to whole image)
            fg_coords = np.argwhere(mask_map > 0.5)
            li = 0  # Stage-1 uses light 0 for T_view
            j_tview = self._get_j_tview(vi, li)  # [H, W, 4], always needed for T_view

            for _ in range(n_patches):
                # Choose a top-left corner so the KxK patch stays inside the image
                if len(fg_coords) > 0:
                    cidx = np.random.randint(len(fg_coords))
                    cr, cc = int(fg_coords[cidx, 0]), int(fg_coords[cidx, 1])
                    r0 = int(np.clip(cr - K // 2, 0, max(H - K, 0)))
                    c0 = int(np.clip(cc - K // 2, 0, max(W - K, 0)))
                else:
                    r0 = np.random.randint(0, max(H - K, 1))
                    c0 = np.random.randint(0, max(W - K, 1))

                rows = np.arange(r0, r0 + K)
                cols = np.arange(c0, c0 + K)
                gc, gr = np.meshgrid(cols, rows)  # [K, K] row-major
                pixel_rows = gr.reshape(-1)
                pixel_cols = gc.reshape(-1)

                pixel_xy = torch.tensor(
                    np.stack([pixel_cols + 0.5, pixel_rows + 0.5], axis=1),
                    dtype=torch.float32, device=device,
                )  # [K*K, 2]

                from utils.ray_utils import pixels_to_world_rays
                rays_o, rays_d = pixels_to_world_rays(
                    c2w_tensor, cam.fl_x, cam.fl_y, cam.cx, cam.cy, pixel_xy
                )

                ld = self.light_dirs[li].unsqueeze(0).expand(K * K, -1)

                mask_vals = torch.tensor(
                    mask_map[pixel_rows, pixel_cols], dtype=torch.float32, device=device
                )
                depth_vals = torch.tensor(
                    depth_map[pixel_rows, pixel_cols] * depth_scale,
                    dtype=torch.float32, device=device
                )
                T_view_vals = torch.tensor(
                    j_tview[pixel_rows, pixel_cols, 3], dtype=torch.float32, device=device
                )
                if need_J:
                    J_vals = torch.tensor(
                        j_tview[pixel_rows, pixel_cols, :3], dtype=torch.float32, device=device
                    )
                else:
                    J_vals = torch.zeros(K * K, 3, device=device)

                all_view_o.append(rays_o)
                all_view_d.append(rays_d)
                all_light_d.append(ld)
                all_J_gt.append(J_vals)
                all_T_view_gt.append(T_view_vals)
                all_depth_gt.append(depth_vals)
                all_mask.append(mask_vals)
                all_cam_idx.append(torch.full((K * K,), vi, dtype=torch.long, device=device))
                n_patches_total += 1

        batch = {
            "view_o": torch.cat(all_view_o, dim=0),
            "view_d": torch.cat(all_view_d, dim=0),
            "light_d": torch.cat(all_light_d, dim=0),
            "J_gt": torch.cat(all_J_gt, dim=0),
            "T_view_gt": torch.cat(all_T_view_gt, dim=0),
            "depth_gt": torch.cat(all_depth_gt, dim=0),
            "mask": torch.cat(all_mask, dim=0),
            "cam_idx": torch.cat(all_cam_idx, dim=0),
            "patch_size": K,
            "n_patches_total": n_patches_total,
        }
        return batch
    #***REngine End Modify
#***REngine End Modify
