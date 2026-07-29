import json
import unreal


def main():
    rows = []
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    for actor in actors:
        components = actor.get_components_by_class(unreal.NiagaraComponent)
        if not components:
            continue
        component_rows = []
        for component in components:
            asset = component.get_asset()
            component_rows.append(
                {
                    "path": component.get_path_name(),
                    "asset": asset.get_path_name() if asset is not None else None,
                    "active": bool(component.is_active()),
                    "visible": bool(component.is_visible()),
                    "autoActivate": bool(component.get_editor_property("auto_activate")),
                    "tickEnabled": bool(component.is_component_tick_enabled()),
                }
            )
        rows.append(
            {
                "label": actor.get_actor_label(),
                "path": actor.get_path_name(),
                "components": component_rows,
            }
        )
    print("M3_NIAGARA_ACTORS=" + json.dumps(rows, sort_keys=True))


main()
