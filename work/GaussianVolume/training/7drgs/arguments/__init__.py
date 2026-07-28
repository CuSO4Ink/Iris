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

from argparse import ArgumentParser, Namespace
import sys
import os

class GroupParams:
    pass

class ParamGroup:
    def __init__(self, parser: ArgumentParser, name : str, fill_none = False):
        group = parser.add_argument_group(name)
        for key, value in vars(self).items():
            shorthand = False
            if key.startswith("_"):
                shorthand = True
                key = key[1:]
            t = type(value)
            value = value if not fill_none else None 
            if shorthand:
                if t == bool:
                    group.add_argument("--" + key, ("-" + key[0:1]), default=value, action="store_true")
                else:
                    group.add_argument("--" + key, ("-" + key[0:1]), default=value, type=t)
            else:
                if t == bool:
                    group.add_argument("--" + key, default=value, action="store_true")
                else:
                    group.add_argument("--" + key, default=value, type=t)

    def extract(self, args):
        group = GroupParams()
        for arg in vars(args).items():
            if arg[0] in vars(self) or ("_" + arg[0]) in vars(self):
                setattr(group, arg[0], arg[1])
        return group

class ModelParams(ParamGroup): 
    def __init__(self, parser, sentinel=False):
        self.sh_degree = 3
        self._source_path = ""
        self._model_path = ""
        self._images = "images"
        self._depths = ""
        self._resolution = -1
        self._white_background = False
        self.train_test_exp = False
        self.data_device = "cuda"
        self.eval = False
        #***REngine Begin Modify added by tuckersu. [Add 7DGS runtime flags in model params]
        self.use_7dgs = False
        self.is_dynamic = False
        self.lambda_t_init = 0.35
        self.lambda_d_init = 0.35
        #***REngine End Modify
        super().__init__(parser, "Loading Parameters", sentinel)


    def extract(self, args):
        g = super().extract(args)
        g.source_path = os.path.abspath(g.source_path)
        return g

class PipelineParams(ParamGroup):
    def __init__(self, parser):
        self.convert_SHs_python = False
        self.compute_cov3D_python = False
        self.debug = False
        self.antialiasing = False
        super().__init__(parser, "Pipeline Parameters")

class OptimizationParams(ParamGroup):
    def __init__(self, parser):
        self.iterations = 30_000
        self.position_lr_init = 0.00016
        self.position_lr_final = 0.0000016
        self.position_lr_delay_mult = 0.01
        self.position_lr_max_steps = 30_000
        self.feature_lr = 0.0025
        self.opacity_lr = 0.025
        self.scaling_lr = 0.005
        self.rotation_lr = 0.001
        self.exposure_lr_init = 0.01
        self.exposure_lr_final = 0.001
        self.exposure_lr_delay_steps = 0
        self.exposure_lr_delay_mult = 0.0
        self.percent_dense = 0.01
        self.lambda_dssim = 0.2
        self.densification_interval = 100
        self.opacity_reset_interval = 3000
        self.densify_from_iter = 500
        self.densify_until_iter = 15_000
        self.densify_grad_threshold = 0.0002
        self.depth_l1_weight_init = 1.0
        self.depth_l1_weight_final = 0.01
        self.random_background = False
        self.optimizer_type = "default"
        #***REngine Begin Modify added by tuckersu. [Add optional 7DGS-specific optimization controls]
        self.lambda_lr = 0.001
        self.enable_7d_densification = False
        #***REngine End Modify
        #***REngine Begin Modify added by tuckersu. [Add Relightable GS training hyperparameters]
        # --- Relight loss weights ---
        self.lambda_J = 100.0
        self.lambda_depth = 1.0
        self.lambda_mask_bce = 0.05
        self.lambda_T_view = 50.0
        self.lambda_T_view_s2 = 0.1
        self.lambda_sh_reg = 1e-4
        self.lambda_sigma_reg = 1e-5
        # --- Relight loss form ---
        # J loss: "l1" (raw L1), "scale_invariant" (L1 / mean(|J_gt|)), "log" (log-space L1)
        # NOTE: "scale_invariant" normalizes away absolute magnitude (single global
        # scalar per batch), so it does NOT penalize per-pixel absolute radiance error
        # -> bad for relighting where J must recover ABSOLUTE radiance. Use "l1"/"log".
        self.j_loss_form = "l1"
        # --- Relight depth / phase ---
        self.eps_near = 0.01
        self.t_view_loss_form = "log"
        self.phase_train_type = "isotropic"
        self.phase_train_g = 0.0
        # --- Relight model ---
        self.relight_sh_degree = 1
        self.tau_channels = 3
        self.tau00_init = 1.0
        # --- Two-stage training schedule ---
        self.stage1_iters = 15000
        self.stage2_iters = 15000
        self.stage2_sigma_finetune_iters = 1000
        # --- Relight densify / prune ---
        self.relight_densify_until = 12000
        self.relight_prune_threshold = 0.005
        # 3D gradient-norm threshold for densify. 1e-6 was effectively "no threshold"
        # (almost every point cloned every interval -> point explosion). 2e-4 matches
        # the 3DGS 2D-viewspace default order of magnitude; tune via grad percentiles.
        self.densify_grad_threshold_3d = 2e-4
        # Hard cap on point count to prevent runaway clone explosion (<=0 = unlimited).
        self.relight_max_points = 600000
        # --- Relight LR ---
        self.sigma_t_lr = 0.01
        self.tau_sh_lr = 0.002
        self.scaling_lr_relight = 0.02
        self.rotation_lr_relight = 0.003
        #***REngine Begin Modify added by tuckersu. [Anisotropy fixes: stage2 geom finetune + patch depth-grad + anisotropic split]
        # --- Fix (1): Stage-2 unfreeze scale/rotation with small lr ---
        # The J (radiance) loss is the only dense appearance signal; letting it
        # finetune scale/rotation at a small lr allows anisotropic detail to emerge
        # without destroying Stage-1 geometry. NOTE: bool defaults use store_true,
        # so to DISABLE flip the default here (cannot be turned off from CLI).
        self.stage2_geom_finetune = True
        self.scaling_lr_stage2 = 0.002    # ~ scaling_lr_relight * 0.1
        self.rotation_lr_stage2 = 0.0003  # ~ rotation_lr_relight * 0.1
        # --- Fix (2): Stage-1 patch sampling + depth-gradient consistency ---
        # Random per-pixel T_view/depth only constrains geometry ALONG the view ray.
        # Sampling small KxK patches and matching predicted vs GT depth GRADIENTS adds
        # a lateral (perpendicular-to-view) shape signal that breaks spherical symmetry.
        self.use_patch_sampling = True
        self.patch_size = 8
        self.n_patches_per_view = 16
        self.patch_B_v = 2
        self.lambda_depth_grad = 5.0
        # --- Fix (3): anisotropic densify split ---
        # Instead of shrinking all 3 axes equally (isotropic /2), shrink ONLY the
        # dominant (largest) axis -> oblate / disk-like children that can fit surfaces.
        self.anisotropic_split = True
        #***REngine End Modify
        # --- TensorBoard ---
        self.tb_scalar_every = 100
        self.tb_image_every = 500
        self.val_every = -1
        self.tb_val_image_samples = 2
        #***REngine End Modify
        super().__init__(parser, "Optimization Parameters")


def get_combined_args(parser : ArgumentParser):
    cmdlne_string = sys.argv[1:]
    cfgfile_string = "Namespace()"
    args_cmdline = parser.parse_args(cmdlne_string)

    try:
        cfgfilepath = os.path.join(args_cmdline.model_path, "cfg_args")
        print("Looking for config file in", cfgfilepath)
        with open(cfgfilepath) as cfg_file:
            print("Config file found: {}".format(cfgfilepath))
            cfgfile_string = cfg_file.read()
    except TypeError:
        print("Config file not found at")
        pass
    args_cfgfile = eval(cfgfile_string)

    merged_dict = vars(args_cfgfile).copy()
    for k,v in vars(args_cmdline).items():
        if v != None:
            merged_dict[k] = v
    return Namespace(**merged_dict)
