import json
import unreal


def main():
    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    rows = []

    for actor in actor_subsystem.get_all_level_actors():
        components = actor.get_components_by_class(unreal.NiagaraComponent)
        if not components:
            continue

        location = actor.get_actor_location()
        for component in components:
            asset = component.get_asset()
            rows.append(
                {
                    "label": actor.get_actor_label(),
                    "actor": actor.get_path_name(),
                    "component": component.get_path_name(),
                    "asset": asset.get_path_name() if asset else None,
                    "active": bool(component.is_active()),
                    "visible": bool(component.is_visible()),
                    "location": [location.x, location.y, location.z],
                }
            )

    print("NIAGARA_LEVEL_ACTORS=" + json.dumps(rows, sort_keys=True))


main()
