import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
REFERENCE_GRID_PATH = SYSTEM + ":SSPR_TrajectoryGridDI"


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


grid = find_by_path(
    unreal.NiagaraDataInterfaceGrid2DCollection,
    GRID_PATH,
)
reference_grid = find_by_path(
    unreal.NiagaraDataInterfaceGrid2DCollection,
    REFERENCE_GRID_PATH,
)
if grid is None or reference_grid is None:
    raise RuntimeError(
        "Actual/reference Grid2D DI is missing: "
        + repr(
            {
                "grid": bool(grid),
                "reference": bool(reference_grid),
            }
        )
    )

binding = reference_grid.get_editor_property(
    "render_target_user_parameter"
)
grid.set_editor_property("render_target_user_parameter", binding)
grid.set_editor_property("num_cells_x", 2048)
grid.set_editor_property("num_cells_y", 2048)
grid.set_editor_property("num_cells_max_axis", 2048)
grid.set_editor_property("set_grid_from_max_axis", False)
grid.set_editor_property("num_attributes", 1)
grid.set_editor_property("clear_before_non_iteration_stage", True)
grid.set_editor_property("override_format", True)
grid.set_editor_property(
    "override_buffer_format",
    unreal.NiagaraGpuBufferFormat.FLOAT,
)

applied = bool(
    unreal.NiagaraScratchPadService.apply_changes(SYSTEM)
)
messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(
        SYSTEM, False
    )
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
stored_binding = grid.get_editor_property(
    "render_target_user_parameter"
)
stored_parameter = stored_binding.get_editor_property("parameter")
result = {
    "path": grid.get_path_name(),
    "numCells": [
        grid.get_editor_property("num_cells_x"),
        grid.get_editor_property("num_cells_y"),
    ],
    "numAttributes": grid.get_editor_property("num_attributes"),
    "clear": bool(
        grid.get_editor_property(
            "clear_before_non_iteration_stage"
        )
    ),
    "targetParameter": str(
        stored_parameter.get_editor_property("name")
    ),
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print(
    "PARTICLE_ACTUAL_USER_GRID="
    + json.dumps(result, sort_keys=True)
)
if (
    result["numCells"] != [2048, 2048]
    or result["numAttributes"] != 1
    or not result["clear"]
    or result["targetParameter"] != "User.SSPR_TrajectoryRT"
    or not applied
    or messages
    or not saved
):
    raise RuntimeError(
        "Actual trajectory Grid2D configuration failed: "
        + repr(result)
    )
