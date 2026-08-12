import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
INSTANCE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "MI_SSPR_G5_FieldDebugV2"
)

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Validation actor is not using V2")
instance = unreal.load_asset(INSTANCE)
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("G5 debug MI is missing")

debug_mode = None
for row in instance.get_editor_property("scalar_parameter_values"):
    info = row.get_editor_property("parameter_info")
    if str(info.get_editor_property("name")) == "G5_DebugMode":
        debug_mode = float(row.get_editor_property("parameter_value"))
        break
if debug_mode != 6.0:
    raise RuntimeError("G5 debug MI is not in four-panel mode")

component.deactivate()
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(120, 1.0 / 60.0)
result = {
    "active": bool(component.is_active()),
    "asset": component.get_asset().get_path_name(),
    "debugInstance": instance.get_path_name(),
    "debugMode": debug_mode,
    "advancedFrames": 120,
}
print("G5_FOUR_PANEL_ACTIVE=" + json.dumps(result, sort_keys=True))
if not result["active"]:
    raise RuntimeError("G5 four-panel activation failed")
