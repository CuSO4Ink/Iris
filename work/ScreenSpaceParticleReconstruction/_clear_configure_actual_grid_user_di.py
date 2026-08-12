import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
RT_DI_PATH = SYSTEM + ":NiagaraDataInterfaceRenderTarget2D_1"


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


grid = find_by_path(unreal.NiagaraDataInterfaceGrid2DCollection, GRID_PATH)
rt_di = find_by_path(unreal.NiagaraDataInterfaceRenderTarget2D, RT_DI_PATH)
if not grid or not rt_di:
    raise RuntimeError(
        f"DI targets missing: grid={bool(grid)} rt={bool(rt_di)}"
    )

binding = rt_di.get_editor_property("render_target_user_parameter")
grid.set_editor_property("render_target_user_parameter", binding)
grid.set_editor_property("num_cells_x", 256)
grid.set_editor_property("num_cells_y", 256)
grid.set_editor_property("num_cells_max_axis", 256)
grid.set_editor_property("set_grid_from_max_axis", False)
grid.set_editor_property("num_attributes", 0)
grid.set_editor_property("clear_before_non_iteration_stage", True)
grid.set_editor_property("override_format", False)

applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(SYSTEM, False)
]
stored_binding = grid.get_editor_property("render_target_user_parameter")
stored_parameter = stored_binding.get_editor_property("parameter")
result = {
    "path": grid.get_path_name(),
    "numCellsX": grid.get_editor_property("num_cells_x"),
    "numCellsY": grid.get_editor_property("num_cells_y"),
    "numCellsMaxAxis": grid.get_editor_property("num_cells_max_axis"),
    "setGridFromMaxAxis": grid.get_editor_property("set_grid_from_max_axis"),
    "numAttributes": grid.get_editor_property("num_attributes"),
    "clearBeforeNonIterationStage": grid.get_editor_property(
        "clear_before_non_iteration_stage"
    ),
    "renderTargetParameterName": str(
        stored_parameter.get_editor_property("name")
    ),
    "applied": applied,
    "compileMessages": messages,
}
print("CLEAR_ACTUAL_GRID=" + json.dumps(result, sort_keys=True))
if (
    result["numCellsX"] != 256
    or result["numCellsY"] != 256
    or not result["clearBeforeNonIterationStage"]
    or result["renderTargetParameterName"] != "User.OccupancyRTParam"
    or not applied
    or messages
):
    raise RuntimeError("Actual Grid DI configuration verification failed")
