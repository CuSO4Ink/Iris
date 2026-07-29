import json
import unreal


DI_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main:"
    "NiagaraDataInterfaceRenderTarget2D_0"
)


def main():
    target = None
    for value in unreal.ObjectIterator(unreal.NiagaraDataInterfaceRenderTarget2D):
        if value.get_path_name() == DI_PATH:
            target = value
            break
    if target is None:
        raise RuntimeError("Main User.SSPR_SimRT DI is missing")

    result = {"path": target.get_path_name()}
    for name in (
        "mip_map_generation",
        "mip_map_generation_type",
        "inherit_user_parameter_settings",
        "size",
        "override_render_target_filter",
        "override_render_target_format",
    ):
        try:
            result[name] = str(target.get_editor_property(name))
        except Exception as exc:
            result[name] = "ERROR: " + str(exc)
    result["mipGenerationEnum"] = [
        name
        for name in dir(unreal.NiagaraMipMapGeneration)
        if name.isupper()
    ]
    result["mipGenerationTypeEnum"] = [
        name
        for name in dir(unreal.NiagaraMipMapGenerationType)
        if name.isupper()
    ]
    print("M3_SIMRT_MIPS=" + json.dumps(result, sort_keys=True))


main()
