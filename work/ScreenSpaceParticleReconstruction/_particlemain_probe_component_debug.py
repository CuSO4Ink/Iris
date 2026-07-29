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
names = [
    name
    for name in dir(component)
    if any(
        token in name.lower()
        for token in (
            "particle",
            "debug",
            "simulation",
            "age",
            "desired",
            "active",
            "tick",
        )
    )
]
print(
    "PARTICLE_COMPONENT_DEBUG="
    + json.dumps(
        {
            "component": component.get_path_name(),
            "active": bool(component.is_active()),
            "methods": sorted(names),
        },
        sort_keys=True,
    )
)
