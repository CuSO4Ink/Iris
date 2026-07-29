import json
import unreal


LEGACY_LABEL = "SSPR_M2A_TemporalOrchestrator"
EXPECTED_CLASS = (
    "/Game/SSPR_Validation/Archive/PingPong_M2_20260728/"
    "BP_SSPR_TemporalOrchestrator.BP_SSPR_TemporalOrchestrator_C"
)


def main():
    editor_actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    matches = [
        actor
        for actor in editor_actor_subsystem.get_all_level_actors()
        if actor.get_actor_label() == LEGACY_LABEL
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {LEGACY_LABEL!r} actor, found {len(matches)}"
        )

    actor = matches[0]
    class_path = actor.get_class().get_path_name()
    actor_path = actor.get_path_name()
    if class_path != EXPECTED_CLASS:
        raise RuntimeError(
            f"Refusing to remove unexpected class {class_path!r} at {actor_path!r}"
        )

    if not editor_actor_subsystem.destroy_actor(actor):
        raise RuntimeError(f"Failed to remove legacy actor {actor_path!r}")

    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Legacy actor was removed, but the current level did not save")

    remaining = [
        current.get_actor_label()
        for current in editor_actor_subsystem.get_all_level_actors()
        if current.get_actor_label() == LEGACY_LABEL
    ]
    print(
        "M3_LEGACY_ORCHESTRATOR_REMOVED="
        + json.dumps(
            {
                "label": LEGACY_LABEL,
                "class": class_path,
                "formerPath": actor_path,
                "remainingInstances": len(remaining),
                "archiveAssetPreserved": True,
            },
            sort_keys=True,
        )
    )


main()
