import unreal


ROOT = r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
SERVICE = unreal.NiagaraScratchPadService

# A non-zero reset distinguishes "stage is a Raster output destination" from
# particle-count and atomic-kernel issues. PreStage should fill the whole grid.
result = SERVICE.create_rasterization_grid3d_user_parameter(
    SYSTEM, "User.SSPR_DensityRaster",
    2048, 2048, 1, 1, 1024.0, 1024, True,
)
if not result.success:
    raise RuntimeError(str(result.message))
exec(open(ROOT + "\\_v2_probe_fixed_atomic_writer.py", encoding="utf-8").read(), {
    "__name__": "__main__",
})
exec(open(ROOT + "\\_v2_select_main_actor.py", encoding="utf-8").read(), {
    "__name__": "__main__",
})
