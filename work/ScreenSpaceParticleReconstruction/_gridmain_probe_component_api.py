import json
import unreal


actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    (
        candidate
        for candidate in actor_subsystem.get_all_level_actors()
        if candidate.get_actor_label() == "SSPR_GridTrails_Main"
    ),
    None,
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
names = [
    name
    for name in dir(component)
    if any(
        token in name.lower()
        for token in (
            "variable",
            "texture",
            "render",
            "emitter",
            "debug",
            "parameter",
        )
    )
]
print("GRIDMAIN_COMPONENT_API=" + json.dumps(sorted(names)))
