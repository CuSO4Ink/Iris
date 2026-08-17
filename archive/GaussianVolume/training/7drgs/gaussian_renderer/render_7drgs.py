#***REngine Begin Modify added by tuckersu. [Add 7DRGS renderer: light-direction slicing + linear J + optional coverage]
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

"""7DRGS renderer.

99% identical to render_7d. Differences:
  1. Slicing uses a global LIGHT direction (pc.slice_for_light) instead of the
     camera view direction.
  2. SH is kept (color channels = transmittance / J).
  3. The output J is LINEAR and may exceed 1 -> clamp(0,1) is OFF by default
     (only clamp for visualization).
  4. Optional `coverage` output = sum of per-gaussian weights (1 - T_final),
     rendered with override_color=ones and bg=0, for the mask BCE term.
"""

import math
import torch
from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer
from scene.gaussian_model_7drgs import GaussianModel7DRGS


def render_7drgs(
    viewpoint_camera,
    pc: GaussianModel7DRGS,
    pipe,
    bg_color: torch.Tensor,
    light_dir,
    scaling_modifier=1.0,
    separate_sh=False,
    override_color=None,
    clamp_image=False,
    need_coverage=False,
    render_tview=False,
    track_gradients=True,
    pixel_weights=None,
    return_accum_weights=False,
):
    """Render relightable transmittance J for a (camera, light_dir) pair.

    When render_tview=True, additionally renders T_view using the second SH bank
    (SH_T) with identical geometry (means/cov/opacity). J uses light direction;
    T_view uses rasterizer campos/view direction.
    """
    if pixel_weights is not None or return_accum_weights:
        raise RuntimeError(
            "EAS accumulation needs the private REngine rasterizer; use --no_eas "
            "with the official 3DGS backend."
        )
    if separate_sh:
        raise RuntimeError("separate_sh is unsupported by the official 3DGS backend")

    screenspace_points = torch.zeros_like(
        pc.get_xyz,
        dtype=pc.get_xyz.dtype,
        requires_grad=track_gradients,
        device="cuda",
    ) + 0
    if track_gradients:
        try:
            screenspace_points.retain_grad()
        except RuntimeError:
            pass

    tanfovx = math.tan(viewpoint_camera.FoVx * 0.5)
    tanfovy = math.tan(viewpoint_camera.FoVy * 0.5)

    raster_settings = GaussianRasterizationSettings(
        image_height=int(viewpoint_camera.image_height),
        image_width=int(viewpoint_camera.image_width),
        tanfovx=tanfovx,
        tanfovy=tanfovy,
        bg=bg_color,
        scale_modifier=scaling_modifier,
        viewmatrix=viewpoint_camera.world_view_transform,
        projmatrix=viewpoint_camera.full_proj_transform,
        sh_degree=pc.active_sh_degree,
        campos=viewpoint_camera.camera_center,
        prefiltered=False,
        debug=pipe.debug,
        antialiasing=pipe.antialiasing,
    )

    rasterizer = GaussianRasterizer(raster_settings=raster_settings)

    # 7DRGS: direction condition is the global light direction (decoupled from camera).
    means3d, cov3d_precomp, opacity = pc.slice_for_light(viewpoint_camera, light_dir)
    means2d = screenspace_points

    shs = None
    dc = None
    colors_precomp = None

    if override_color is None:
        # J is light transport. T_view remains the view-dependent SH bank below.
        j_values = pc.evaluate_j_for_light(light_dir)
        colors_precomp = torch.clamp_min(j_values, 0.0)
    else:
        j_values = override_color
        colors_precomp = override_color

    rendered_image, radii, depth_image = rasterizer(
        means3D=means3d,
        means2D=means2d,
        shs=shs,
        colors_precomp=colors_precomp,
        opacities=opacity,
        scales=None,
        rotations=None,
        cov3D_precomp=cov3d_precomp,
    )

    # J is LINEAR transmittance — do NOT clamp during training (would cut gradients).
    if clamp_image:
        rendered_image = rendered_image.clamp(0, 1)

    out = {
        "render": rendered_image,
        "viewspace_points": screenspace_points,
        "visibility_filter": (radii > 0),
        "radii": radii,
        "depth": depth_image,
        "j_values": j_values,
    }
    if need_coverage:
        # Object Mask Constraint (Relightable 3D Gaussians):
        #   L_O = -M*log(O) - (1-M)*log(1-O), where O = 1 - T_final.
        #
        # Reuse the SAME (means3d, cov3d, opacity) produced by slice_for_light.
        # In 7DRGS semantics there is no view-conditioned slice — the d-dim is
        # the light direction, not the view direction. f_dir(d_light) is part
        # of the physical opacity (dual-factor modulation), so coverage under
        # the current light is the geometrically meaningful silhouette signal.
        # Across all training lights this becomes an aggregate silhouette
        # constraint without coupling artifacts.
        zero_bg = torch.zeros(3, dtype=bg_color.dtype, device=bg_color.device)
        cov_settings = GaussianRasterizationSettings(
            image_height=int(viewpoint_camera.image_height),
            image_width=int(viewpoint_camera.image_width),
            tanfovx=tanfovx,
            tanfovy=tanfovy,
            bg=zero_bg,
            scale_modifier=scaling_modifier,
            viewmatrix=viewpoint_camera.world_view_transform,
            projmatrix=viewpoint_camera.full_proj_transform,
            sh_degree=pc.active_sh_degree,
            campos=viewpoint_camera.camera_center,
            prefiltered=False,
            debug=pipe.debug,
            antialiasing=pipe.antialiasing,
        )
        cov_rasterizer = GaussianRasterizer(raster_settings=cov_settings)
        ones_color = torch.ones_like(means3d)
        coverage_image, _, _ = cov_rasterizer(
            means3D=means3d,
            means2D=torch.zeros_like(means3d, requires_grad=False),
            shs=None,
            colors_precomp=ones_color,
            opacities=opacity,
            scales=None,
            rotations=None,
            cov3D_precomp=cov3d_precomp,
        )
        out["coverage"] = coverage_image[0:1]  # all channels equal; keep one

    #***REngine Begin Modify added by tuckersu. [T_view dual SH: second rasterizer pass with SH_T]
    if render_tview:
        # T_view uses the SAME (means3d, cov3d, opacity) from slice_for_light.
        # SH = SH_T (3-channel replicated scalar), campos = same camera center
        # → SH evaluation direction = view direction (identical to J path).
        # Background for T_view: 1.0 (rays that miss the volume have T=1).
        tview_bg = torch.ones(3, dtype=bg_color.dtype, device=bg_color.device)
        tview_settings = GaussianRasterizationSettings(
            image_height=int(viewpoint_camera.image_height),
            image_width=int(viewpoint_camera.image_width),
            tanfovx=tanfovx,
            tanfovy=tanfovy,
            bg=tview_bg,
            scale_modifier=scaling_modifier,
            viewmatrix=viewpoint_camera.world_view_transform,
            projmatrix=viewpoint_camera.full_proj_transform,
            sh_degree=pc.active_sh_degree_t,
            campos=viewpoint_camera.camera_center,
            prefiltered=False,
            debug=pipe.debug,
            antialiasing=pipe.antialiasing,
        )
        tview_rasterizer = GaussianRasterizer(raster_settings=tview_settings)
        tview_image, _, _ = tview_rasterizer(
            means3D=means3d,
            means2D=torch.zeros_like(means3d, requires_grad=False),
            shs=pc.get_features_t,
            colors_precomp=None,
            opacities=opacity,
            scales=None,
            rotations=None,
            cov3D_precomp=cov3d_precomp,
        )
        # All 3 channels are identical (replicated scalar); take channel 0.
        out["tview"] = tview_image[0:1]  # [1, H, W]
    #***REngine End Modify

    return out
#***REngine End Modify
