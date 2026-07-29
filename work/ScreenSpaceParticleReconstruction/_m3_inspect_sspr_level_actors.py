import json
import unreal


def main():
    rows = []
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    for actor in actors:
        label = actor.get_actor_label()
        class_path = actor.get_class().get_path_name()
        path = actor.get_path_name()
        # Do not include the full actor path here: the project/map package name
        # contains "precisefluid", which made every level actor match.
        text = (label + " " + class_path).lower()
        if not any(token in text for token in ("sspr", "orchestrator", "pingpong")):
            continue
        components = [
            component.get_class().get_path_name()
            for component in actor.get_components_by_class(unreal.ActorComponent)
        ]
        try:
            hidden_editor = bool(actor.is_hidden_ed())
        except Exception:
            hidden_editor = None
        try:
            hidden_game = bool(actor.get_editor_property("hidden"))
        except Exception:
            hidden_game = None
        try:
            tick_enabled = bool(actor.is_actor_tick_enabled())
        except Exception:
            tick_enabled = None
        rows.append(
            {
                "label": label,
                "path": path,
                "class": class_path,
                "hiddenEditor": hidden_editor,
                "hiddenGame": hidden_game,
                "tickEnabled": tick_enabled,
                "components": components,
            }
        )
    print("M3_SSPR_LEVEL_ACTORS=" + json.dumps(rows, sort_keys=True))


main()
