import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
SERVICE = unreal.NiagaraScratchPadService

# Re-author the exposed parameter with the real RasterizationGrid3D subclass.
# The former Python-only path could only touch generic NiagaraDataInterface
# wrappers, which left the runtime parameter store with invalid/stale clones.
created = SERVICE.create_rasterization_grid3d_user_parameter(
    SYSTEM,
    "User.SSPR_DensityRaster",
    2048,
    2048,
    1,
    1,
    1024.0,
    0,
    True,
)
if not created.success:
    raise RuntimeError("Raster parameter creation failed: " + str(created.message))

# Restore production anisotropic writer + density resolve after the dimensions
# probe, then rebuild the live component parameter store from the system.
exec(open(
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\_v2_install_atomic_gaussian.py",
    encoding="utf-8",
).read(), {"__name__": "__main__"})
exec(open(
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\_v2_select_main_actor.py",
    encoding="utf-8",
).read(), {"__name__": "__main__"})

messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
print("V2_COMPILED_RASTER_ACTIVATED=" + json.dumps({
    "created": bool(created.success),
    "message": str(created.message),
    "parameter": str(created.module_name),
    "dataInterface": str(created.script_path),
    "compileMessages": messages,
}, sort_keys=True))
if messages:
    raise RuntimeError("V2 compile gate failed: " + repr(messages))
