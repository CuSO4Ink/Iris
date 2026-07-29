import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
TARGET_NAME = "SSPR_TrajectoryRT_Runtime"
GRID_SIZE = 2048


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


system = unreal.load_object(None, SYSTEM)
grid = find_by_path(
    unreal.NiagaraDataInterfaceGrid2DCollection,
    GRID_PATH,
)
actor = next(
    (
        item
        for item in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        if item.get_actor_label() == ACTOR_LABEL
    ),
    None,
)
if (
    not isinstance(system, unreal.NiagaraSystem)
    or grid is None
    or actor is None
):
    raise RuntimeError(
        "Runtime binding inputs are missing: "
        + repr(
            {
                "system": bool(system),
                "grid": bool(grid),
                "actor": bool(actor),
            }
        )
    )

components = actor.get_components_by_class(
    unreal.NiagaraComponent
)
if not components:
    raise RuntimeError("White-particle actor has no Niagara component")
component = components[0]
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
if world is None:
    raise RuntimeError("Editor world is unavailable")

target = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.TextureRenderTarget2D
        )
        if item.get_name() == TARGET_NAME
        and component.get_path_name() in item.get_path_name()
    ),
    None,
)
if target is None:
    target = unreal.RenderingLibrary.create_render_target2d(
        world,
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    if target is None:
        raise RuntimeError(
            "Failed to create runtime trajectory target"
        )
    target.rename(TARGET_NAME, component)

for property_name in ("address_x", "address_y"):
    try:
        target.set_editor_property(
            property_name, unreal.TextureAddress.TA_CLAMP
        )
    except Exception:
        pass

unreal.RenderingLibrary.clear_render_target2d(
    world,
    target,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
)

# Re-attach the asset so this existing level component rebuilds its
# exposed-parameter store after the new User variables were authored.
component.deactivate()
component.set_asset(None)
component.set_asset(system)
component.set_variable_texture_render_target(
    "User.SSPR_TrajectoryRT", target
)
grid_override = "system-default"
component.set_force_solo(True)
component.set_age_update_mode(
    unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME
)
component.set_component_tick_enabled(True)
component.reinitialize_system()
component.activate(True)
component.advance_simulation(30, 1.0 / 60.0)

live_grids = []
for live_grid in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceGrid2DCollection
):
    path = live_grid.get_path_name()
    if component.get_path_name() not in path:
        continue
    binding = live_grid.get_editor_property(
        "render_target_user_parameter"
    )
    parameter = binding.get_editor_property("parameter")
    live_grids.append(
        {
            "path": path,
            "x": int(
                live_grid.get_editor_property("num_cells_x")
            ),
            "y": int(
                live_grid.get_editor_property("num_cells_y")
            ),
            "attributes": int(
                live_grid.get_editor_property(
                    "num_attributes"
                )
            ),
            "clear": bool(
                live_grid.get_editor_property(
                    "clear_before_non_iteration_stage"
                )
            ),
            "targetParameter": str(
                parameter.get_editor_property("name")
            ),
        }
    )

matching_grid = any(
    item["x"] == GRID_SIZE
    and item["y"] == GRID_SIZE
    and item["attributes"] == 1
    and item["clear"]
    and item["targetParameter"] == "User.SSPR_TrajectoryRT"
    for item in live_grids
)
result = {
    "component": component.get_path_name(),
    "active": bool(component.is_active()),
    "forceSolo": bool(component.get_force_solo()),
    "gridOverride": grid_override,
    "target": target.get_path_name(),
    "targetSize": [
        int(target.get_editor_property("size_x")),
        int(target.get_editor_property("size_y")),
    ],
    "targetFormat": str(
        target.get_editor_property("render_target_format")
    ),
    "liveGrids": live_grids,
    "matchingGrid": matching_grid,
}
print(
    "PARTICLE_RUNTIME_GRID_TARGET="
    + json.dumps(result, sort_keys=True)
)
if (
    not result["active"]
    or result["targetSize"] != [GRID_SIZE, GRID_SIZE]
    or not matching_grid
):
    raise RuntimeError(
        "Runtime trajectory target binding failed: "
        + repr(result)
    )
