import json
import unreal


SOURCE = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
actor = next(
    item for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
asset = unreal.load_asset(SOURCE)
component.set_asset(asset)
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(300, 1.0 / 60.0)
unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
).editor_invalidate_viewports()
print("V2_AB_SOURCE=" + json.dumps({
    "asset": component.get_asset().get_path_name(),
    "active": bool(component.is_active()),
    "tick": bool(component.is_component_tick_enabled()),
}, sort_keys=True))
