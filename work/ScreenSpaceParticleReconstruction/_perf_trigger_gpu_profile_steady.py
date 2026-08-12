import json
import unreal

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
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
asset = component.get_asset()
if asset is None:
    raise RuntimeError("Active Niagara component has no System")

level_subsystem.editor_invalidate_viewports()
unreal.SystemLibrary.execute_console_command(
    world, "r.ProfileGPU.ShowUI 0"
)
unreal.SystemLibrary.execute_console_command(
    world, "ProfileGPU"
)
level_subsystem.editor_invalidate_viewports()
print(
    "PERF_GPU_PROFILE_STEADY="
    + json.dumps(
        {
            "world": world.get_path_name(),
            "system": asset.get_path_name(),
            "active": bool(component.is_active()),
            "manualAdvance": False,
        },
        sort_keys=True,
    )
)
