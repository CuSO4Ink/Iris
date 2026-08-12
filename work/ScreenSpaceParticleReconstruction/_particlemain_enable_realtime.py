import json
import unreal


actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
set_ok = bool(unreal.ViewportService.set_realtime(True))
level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
level_subsystem.editor_set_viewport_realtime(True)
level_subsystem.editor_invalidate_viewports()
component.set_force_solo(False)
component.set_age_update_mode(
    unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME
)
component.set_component_tick_enabled(True)
component.set_auto_activate(True)
component.reinitialize_system()
component.activate(True)
info = unreal.ViewportService.get_viewport_info()
print(
    "PARTICLE_REALTIME="
    + json.dumps(
        {
            "setOk": set_ok,
            "realtime": bool(info.is_realtime),
            "active": bool(component.is_active()),
            "tick": bool(component.is_component_tick_enabled()),
            "forceSolo": bool(component.get_force_solo()),
        },
        sort_keys=True,
    )
)
