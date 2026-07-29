import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
SOURCE_LABEL = "NewNiagaraSystem2"
MAIN_LABEL = "SSPR_ParticleTrails_Main"

def main():
    system = unreal.load_object(None, SYSTEM)
    if not isinstance(system, unreal.NiagaraSystem):
        raise RuntimeError("White-particle mainline system is missing")

    applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM))
    messages = [
        str(item)
        for item in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM, False
        )
    ]
    saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
    if not applied or messages or not saved:
        raise RuntimeError(
            "White-particle mainline is not clean: "
            + repr(
                {
                    "applied": applied,
                    "messages": messages,
                    "saved": saved,
                }
            )
        )

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    matching_actors = []
    for item in actor_subsystem.get_all_level_actors():
        item_components = item.get_components_by_class(
            unreal.NiagaraComponent
        )
        if not item_components:
            continue
        if item.get_actor_label() in (SOURCE_LABEL, MAIN_LABEL) or any(
            item_component.get_asset() is not None
            and item_component.get_asset().get_path_name() == SYSTEM
            for item_component in item_components
        ):
            matching_actors.append(item)

    actor = next(
        (
            item
            for item in matching_actors
            if item.get_actor_label() == MAIN_LABEL
        ),
        None,
    )
    if actor is None:
        actor = next(
            (
                item
                for item in matching_actors
                if item.get_actor_label() == SOURCE_LABEL
            ),
            None,
        )
    if actor is None and matching_actors:
        actor = matching_actors[0]
    if actor is None:
        actor = actor_subsystem.spawn_actor_from_class(
            unreal.NiagaraActor,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
        )
    if actor is None:
        raise RuntimeError("Failed to locate or spawn white-particle actor")

    components = actor.get_components_by_class(unreal.NiagaraComponent)
    if not components:
        raise RuntimeError("White-particle actor has no Niagara component")
    component = components[0]
    component.set_asset(system)
    component.set_auto_activate(True)
    component.set_force_solo(True)
    component.set_age_update_mode(
        unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME
    )
    component.set_component_tick_enabled(True)
    component.set_visibility(True, True)
    component.reinitialize_system()
    component.activate(True)
    actor.set_actor_label(MAIN_LABEL)
    actor.set_actor_hidden_in_game(False)
    try:
        actor.set_is_temporarily_hidden_in_editor(False)
    except Exception:
        pass

    disabled_duplicates = []
    for duplicate_actor in matching_actors:
        if duplicate_actor == actor:
            continue
        duplicate_components = duplicate_actor.get_components_by_class(
            unreal.NiagaraComponent
        )
        disabled_any = False
        for duplicate_component in duplicate_components:
            duplicate_asset = duplicate_component.get_asset()
            if (
                duplicate_asset is None
                or duplicate_asset.get_path_name() != SYSTEM
            ):
                continue
            duplicate_component.set_auto_activate(False)
            duplicate_component.set_active(False, True)
            duplicate_component.deactivate()
            duplicate_component.set_component_tick_enabled(False)
            duplicate_component.set_visibility(False, True)
            disabled_any = True
        if disabled_any:
            duplicate_actor.set_actor_hidden_in_game(True)
            try:
                duplicate_actor.set_is_temporarily_hidden_in_editor(True)
            except Exception:
                pass
            disabled_duplicates.append(
                {
                    "actor": duplicate_actor.get_path_name(),
                    "label": duplicate_actor.get_actor_label(),
                }
            )

    print(
        "WHITE_MAIN_ACTIVATED="
        + json.dumps(
            {
                "system": system.get_path_name(),
                "actor": actor.get_path_name(),
                "actorLabel": actor.get_actor_label(),
                "component": component.get_path_name(),
                "active": bool(component.is_active()),
                "forceSolo": bool(component.get_force_solo()),
                "applied": applied,
                "saved": saved,
                "compileMessages": messages,
                "disabledDuplicates": disabled_duplicates,
            },
            sort_keys=True,
        )
    )


main()
