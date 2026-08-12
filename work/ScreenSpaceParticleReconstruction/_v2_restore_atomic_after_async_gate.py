import unreal


ROOT = r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)


def run_script(name):
    exec(open(ROOT + "\\" + name, encoding="utf-8").read(), {
        "__name__": "__main__",
    })


restored = unreal.NiagaraScratchPadService.create_rasterization_grid3d_user_parameter(
    SYSTEM, "User.SSPR_DensityRaster",
    2048, 2048, 1, 1, 1024.0, 0, True,
)
if not restored.success:
    raise RuntimeError(str(restored.message))
run_script("_v2_install_atomic_gaussian.py")
run_script("_v2_select_main_actor.py")
