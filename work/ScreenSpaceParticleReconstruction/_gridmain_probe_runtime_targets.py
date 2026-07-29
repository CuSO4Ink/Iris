import json
import unreal


SYSTEM_PATH = (
    "/Game/SSPR_Validation/M2/GridTrails/"
    "NS_SSPR_GridTrails_Main.NS_SSPR_GridTrails_Main"
)
ACTOR_LABEL = "SSPR_GridTrails_Main"

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    (
        candidate
        for candidate in actor_subsystem.get_all_level_actors()
        if candidate.get_actor_label() == ACTOR_LABEL
    ),
    None,
)
if actor is None:
    raise RuntimeError("GridTrails validation actor is missing")
components = actor.get_components_by_class(unreal.NiagaraComponent)
if not components:
    raise RuntimeError("GridTrails Niagara component is missing")
component = components[0]
asset = component.get_asset()
if asset is None or asset.get_path_name() != SYSTEM_PATH:
    raise RuntimeError("GridTrails validation actor uses the wrong system")

component.advance_simulation(10, 1.0 / 30.0)

targets = []
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        size_x = int(target.get_editor_property("size_x"))
        size_y = int(target.get_editor_property("size_y"))
    except Exception:
        continue
    path = target.get_path_name()
    if size_x < 128 or size_y < 128:
        continue
    targets.append(
        {
            "path": path,
            "sizeX": size_x,
            "sizeY": size_y,
            "format": str(target.get_editor_property("render_target_format")),
            "outer": target.get_outer().get_path_name()
            if target.get_outer()
            else None,
            "transient": not path.startswith("/Game/"),
        }
    )

render_target_dis = []
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceRenderTarget2D
):
    path = data_interface.get_path_name()
    if (
        "NS_SSPR_GridTrails_Main" not in path
        and "GridTrailsNiagara" not in path
    ):
        continue
    render_target_dis.append(
        {
            "path": path,
            "preview": bool(
                data_interface.get_editor_property("preview_render_target")
            ),
            "inheritUserSettings": bool(
                data_interface.get_editor_property(
                    "inherit_user_parameter_settings"
                )
            ),
        }
    )

print(
    "GRIDMAIN_RUNTIME_TARGETS="
    + json.dumps(
        {
            "actor": actor.get_path_name(),
            "component": component.get_path_name(),
            "active": bool(component.is_active()),
            "targets": targets,
            "renderTargetDataInterfaces": render_target_dis,
        },
        sort_keys=True,
    )
)
