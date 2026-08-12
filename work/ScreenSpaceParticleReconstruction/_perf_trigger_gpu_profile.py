import json
import unreal


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
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
unreal.SystemLibrary.execute_console_command(
    world, "r.ProfileGPU.ShowUI 0"
)
unreal.SystemLibrary.execute_console_command(
    world, "ProfileGPU"
)
component.advance_simulation(1, 1.0 / 60.0)
print(
    "PERF_GPU_PROFILE_TRIGGERED="
    + json.dumps(
        {
            "showUI": False,
            "command": "ProfileGPU",
            "world": world.get_path_name(),
            "advancedFrames": 1,
        },
        sort_keys=True,
    )
)
