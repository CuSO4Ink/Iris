import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)

service = unreal.NiagaraScratchPadService
applied = bool(service.apply_changes(SYSTEM))
messages = [str(item) for item in service.get_compile_messages(SYSTEM, False)]

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(120, 1.0 / 60.0)

saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_STAGE_RUNTIME_PROBE=" + json.dumps({
    "active": bool(component.is_active()),
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Applying stage runtime probe failed")
