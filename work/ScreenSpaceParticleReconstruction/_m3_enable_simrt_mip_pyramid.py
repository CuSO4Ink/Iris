import json
import unreal


SYSTEM_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
DI_PATH = SYSTEM_PATH + ":NiagaraDataInterfaceRenderTarget2D_0"


def main():
    system = unreal.load_asset(SYSTEM_PATH)
    if not isinstance(system, unreal.NiagaraSystem):
        raise RuntimeError("Main ParticleTrails Niagara system is missing")

    target = None
    for value in unreal.ObjectIterator(unreal.NiagaraDataInterfaceRenderTarget2D):
        if value.get_path_name() == DI_PATH:
            target = value
            break
    if target is None:
        raise RuntimeError("User.SSPR_SimRT data interface is missing")

    target.set_editor_property(
        "mip_map_generation", unreal.NiagaraMipMapGeneration.POST_SIMULATE
    )
    target.set_editor_property(
        "mip_map_generation_type", unreal.NiagaraMipMapGenerationType.BLUR4
    )
    target.set_editor_property(
        "override_render_target_filter", unreal.TextureFilter.TF_TRILINEAR
    )

    applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM_PATH))
    messages = [
        str(value)
        for value in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM_PATH, False
        )
    ]
    saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PATH, False))
    result = {
        "path": target.get_path_name(),
        "mipGeneration": str(target.get_editor_property("mip_map_generation")),
        "mipType": str(target.get_editor_property("mip_map_generation_type")),
        "filter": str(target.get_editor_property("override_render_target_filter")),
        "applied": applied,
        "compileMessages": messages,
        "saved": saved,
    }
    print("M3_SIMRT_MIP_PYRAMID=" + json.dumps(result, sort_keys=True))
    if not applied or messages or not saved:
        raise RuntimeError("Failed to enable clean SimRT mip pyramid: " + repr(result))


main()
