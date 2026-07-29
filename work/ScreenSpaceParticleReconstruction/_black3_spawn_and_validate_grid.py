import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
RT_PATH = "/Game/SSPR_Validation/RT_SSPR_Occupancy.RT_SSPR_Occupancy"
GRID_PATH = SYSTEM_PATH + ":NiagaraDataInterfaceGrid2DCollection_0"
EXPORT_DIR = unreal.Paths.project_saved_dir()


def find_object(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


def read_stats(world, render_target):
    raw = unreal.RenderingLibrary.read_render_target_raw(world, render_target, True)
    if raw is None:
        colors = unreal.RenderingLibrary.read_render_target(world, render_target, True)
        if colors is None:
            return {"mode": "unavailable"}
        values = [float(color.r) / 255.0 for color in colors]
        mode = "color"
    else:
        values = [float(color.r) for color in raw]
        mode = "raw"
    threshold = 0.001
    return {
        "mode": mode,
        "samples": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "nonzero": sum(1 for value in values if value > threshold),
        "full": sum(1 for value in values if value > 0.99),
    }


system = unreal.load_object(None, SYSTEM_PATH)
render_target = unreal.load_object(None, RT_PATH)
grid = find_object(unreal.NiagaraDataInterfaceGrid2DCollection, GRID_PATH)
world = unreal.EditorLevelLibrary.get_editor_world()
if system is None or render_target is None or grid is None or world is None:
    raise RuntimeError(
        "Missing test inputs: "
        + repr(
            {
                "system": bool(system),
                "renderTarget": bool(render_target),
                "grid": bool(grid),
                "world": bool(world),
            }
        )
    )

matching_components = []
for candidate in unreal.ObjectIterator(unreal.NiagaraComponent):
    try:
        asset = candidate.get_asset()
        if asset is not None and asset.get_path_name() == SYSTEM_PATH:
            matching_components.append(candidate)
    except Exception:
        pass

actor = None
if matching_components:
    component = matching_components[0]
    actor = component.get_owner()
else:
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.NiagaraActor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("Failed to spawn NiagaraActor")
    components = actor.get_components_by_class(unreal.NiagaraComponent)
    if not components:
        raise RuntimeError("Spawned NiagaraActor has no NiagaraComponent")
    component = components[0]
    component.set_asset(system)
    actor.set_actor_label("SSPR_RT_RuntimeValidation")

unreal.RenderingLibrary.clear_render_target2d(
    world, render_target, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
)
component.set_variable_texture_render_target("User.OccupancyRTParam", render_target)
grid_override_result = "not-attempted"
try:
    component.set_variable_object("User.SSPR_OccupancyGrid", grid)
    grid_override_result = "set_variable_object"
except Exception as error:
    grid_override_result = "default-system-grid: " + str(error)

component.set_force_solo(True)
component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME)
component.set_component_tick_enabled(True)
component.reinitialize_system()
component.activate(True)
component.advance_simulation(180, 1.0 / 60.0)

stats_a = read_stats(world, render_target)
unreal.RenderingLibrary.export_render_target(
    component, render_target, EXPORT_DIR, "SSPR_RT_Grid_FrameA"
)

component.advance_simulation(120, 1.0 / 60.0)
stats_b = read_stats(world, render_target)
unreal.RenderingLibrary.export_render_target(
    component, render_target, EXPORT_DIR, "SSPR_RT_Grid_FrameB"
)

live_grids = []
for live_grid in unreal.ObjectIterator(unreal.NiagaraDataInterfaceGrid2DCollection):
    path = live_grid.get_path_name()
    if "NS_SSPR_ProjTest" not in path and "NiagaraComponent" not in path:
        continue
    binding = live_grid.get_editor_property("render_target_user_parameter")
    parameter = binding.get_editor_property("parameter")
    live_grids.append(
        {
            "path": path,
            "x": live_grid.get_editor_property("num_cells_x"),
            "y": live_grid.get_editor_property("num_cells_y"),
            "attributes": live_grid.get_editor_property("num_attributes"),
            "clear": bool(
                live_grid.get_editor_property("clear_before_non_iteration_stage")
            ),
            "renderTargetParameter": str(parameter.get_editor_property("name")),
        }
    )

result = {
    "actor": actor.get_path_name() if actor is not None else None,
    "component": component.get_path_name(),
    "active": bool(component.is_active()),
    "forceSolo": bool(component.get_force_solo()),
    "gridOverride": grid_override_result,
    "frameA": stats_a,
    "frameB": stats_b,
    "exports": [
        EXPORT_DIR + "SSPR_RT_Grid_FrameA",
        EXPORT_DIR + "SSPR_RT_Grid_FrameB",
    ],
    "liveGrids": live_grids,
}
print("SSPR_GRID_VALIDATION=" + json.dumps(result, sort_keys=True))
