import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest"
GRID_OBJECT_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest:"
    "SSPR_OccupancyGridDI"
)
RT_DI_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest:"
    "NiagaraDataInterfaceRenderTarget2D_1"
)


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


system = unreal.load_asset(SYSTEM_PATH)
if not system:
    raise RuntimeError("Niagara system not found")
if find_by_path(unreal.NiagaraDataInterfaceGrid2DCollection, GRID_OBJECT_PATH):
    raise RuntimeError("Grid user DI object already exists")

rt_di = find_by_path(unreal.NiagaraDataInterfaceRenderTarget2D, RT_DI_PATH)
if not rt_di:
    raise RuntimeError("Existing RT2D DI not found")
render_target_binding = rt_di.get_editor_property("render_target_user_parameter")

grid = unreal.new_object(
    unreal.NiagaraDataInterfaceGrid2DCollection,
    outer=system,
    name="SSPR_OccupancyGridDI",
)
grid.set_editor_property("render_target_user_parameter", render_target_binding)
grid.set_editor_property("num_cells_x", 256)
grid.set_editor_property("num_cells_y", 256)
grid.set_editor_property("num_cells_max_axis", 256)
grid.set_editor_property("set_grid_from_max_axis", False)
grid.set_editor_property("num_attributes", 0)
grid.set_editor_property("clear_before_non_iteration_stage", True)
grid.set_editor_property("override_format", False)

result = {
    "path": grid.get_path_name(),
    "numCellsX": grid.get_editor_property("num_cells_x"),
    "numCellsY": grid.get_editor_property("num_cells_y"),
    "clearBeforeNonIterationStage": grid.get_editor_property(
        "clear_before_non_iteration_stage"
    ),
    "renderTargetBinding": str(
        grid.get_editor_property("render_target_user_parameter")
    ),
}
print("CLEAR_GRID_DI=" + json.dumps(result, sort_keys=True))
if result["path"] != GRID_OBJECT_PATH:
    raise RuntimeError("Unexpected Grid DI object path")
