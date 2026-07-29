import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"

blueprint_class = unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH)
if blueprint_class is None:
    raise RuntimeError("Unable to load orchestrator Blueprint class")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
removed = []
for existing_actor in actor_subsystem.get_all_level_actors():
    if (
        existing_actor.get_actor_label() == ACTOR_LABEL
        and existing_actor.get_class().get_path_name() == blueprint_class.get_path_name()
    ):
        removed.append(existing_actor.get_path_name())
        actor_subsystem.destroy_actor(existing_actor)

actor = actor_subsystem.spawn_actor_from_class(
    blueprint_class,
    unreal.Vector(0.0, 0.0, 0.0),
    unreal.Rotator(0.0, 0.0, 0.0),
)
if actor is None:
    raise RuntimeError("Failed to spawn orchestrator actor")
actor.set_actor_label(ACTOR_LABEL)

disabled_m1 = []
for level_actor in actor_subsystem.get_all_level_actors():
    if level_actor == actor:
        continue
    for component in level_actor.get_components_by_class(unreal.NiagaraComponent):
        asset = component.get_editor_property("asset")
        if (
            asset
            and asset.get_path_name()
            == (
                "/Game/SSPR_Validation/"
                "NS_SSPR_ProjTest.NS_SSPR_ProjTest"
            )
        ):
            component.modify()
            component.set_editor_property("auto_activate", False)
            component.deactivate()
            component.set_component_tick_enabled(False)
            disabled_m1.append(
                {
                    "actor": level_actor.get_path_name(),
                    "actorLabel": level_actor.get_actor_label(),
                    "component": component.get_path_name(),
                }
            )

components = []
for component in actor.get_components_by_class(unreal.NiagaraComponent):
    asset = component.get_editor_property("asset")
    components.append(
        {
            "name": component.get_name(),
            "asset": asset.get_path_name() if asset else None,
            "auto_activate": component.get_editor_property("auto_activate"),
            "active": component.is_active(),
            "tick_enabled": component.is_component_tick_enabled(),
        }
    )

result = {
    "actor": actor.get_path_name(),
    "class": actor.get_class().get_path_name(),
    "removed_previous": removed,
    "disabled_standalone_m1": disabled_m1,
    "niagara_components": components,
}
print("M2A_SPAWN " + json.dumps(result, ensure_ascii=False, default=str))
