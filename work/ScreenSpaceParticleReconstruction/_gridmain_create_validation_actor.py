import json
import unreal


FOLDER = "/Game/SSPR_Validation/M2/GridTrails"
BP_PATH = FOLDER + "/BP_SSPR_GridTrails_Main"
SYSTEM_PATH = (
    FOLDER + "/NS_SSPR_GridTrails_Main.NS_SSPR_GridTrails_Main"
)
ACTOR_LABEL = "SSPR_GridTrails_Main"

created = False
bp = unreal.load_asset(BP_PATH)
if bp is None:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "BP_SSPR_GridTrails_Main",
        FOLDER,
        unreal.Blueprint,
        factory,
    )
    created = bp is not None
if not isinstance(bp, unreal.Blueprint):
    raise RuntimeError("Failed to create GridTrails validation Blueprint")

service = unreal.BlueprintService
hierarchy = service.get_component_hierarchy(BP_PATH)
component_names = {str(item.component_name) for item in hierarchy}
if "GridTrailsNiagara" not in component_names:
    if not service.add_component(
        BP_PATH,
        "NiagaraComponent",
        "GridTrailsNiagara",
        "",
    ):
        raise RuntimeError("Failed to add Niagara component")

if not service.set_component_property(
    BP_PATH,
    "GridTrailsNiagara",
    "Asset",
    SYSTEM_PATH,
):
    raise RuntimeError("Failed to assign GridTrails Niagara system")
service.set_component_property(
    BP_PATH,
    "GridTrailsNiagara",
    "bAutoActivate",
    "true",
)

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
status = str(bp.get_editor_property("status"))
saved = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))
if "ERROR" in status.upper() or not saved:
    raise RuntimeError("GridTrails validation Blueprint did not compile/save")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matching = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label() == ACTOR_LABEL
]
removed = []
for existing in matching:
    removed.append(existing.get_path_name())
    actor_subsystem.destroy_actor(existing)

blueprint_class = unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH)
actor = actor_subsystem.spawn_actor_from_class(
    blueprint_class,
    unreal.Vector(0.0, 0.0, 0.0),
    unreal.Rotator(0.0, 0.0, 0.0),
)
if actor is None:
    raise RuntimeError("Failed to spawn GridTrails validation actor")
actor.set_actor_label(ACTOR_LABEL)

components = actor.get_components_by_class(unreal.NiagaraComponent)
if not components:
    raise RuntimeError("GridTrails validation actor has no Niagara component")
component = components[0]
component.set_force_solo(True)
component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME)
component.set_component_tick_enabled(True)
component.reinitialize_system()
component.activate(True)

print(
    "GRIDMAIN_VALIDATION_ACTOR="
    + json.dumps(
        {
            "blueprint": BP_PATH,
            "blueprintCreated": created,
            "blueprintStatus": status,
            "blueprintSaved": saved,
            "actor": actor.get_path_name(),
            "actorLabel": actor.get_actor_label(),
            "removedPreviousActors": removed,
            "component": component.get_path_name(),
            "system": component.get_asset().get_path_name(),
            "active": bool(component.is_active()),
            "forceSolo": bool(component.get_force_solo()),
        },
        sort_keys=True,
    )
)
