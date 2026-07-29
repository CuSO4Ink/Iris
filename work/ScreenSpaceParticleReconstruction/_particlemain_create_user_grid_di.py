import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
GRID_PATH = SYSTEM + ":SSPR_TrajectoryGridDI"
REFERENCE_GRID_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest."
    "NS_SSPR_ProjTest:NiagaraDataInterfaceGrid2DCollection_0"
)


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


system = unreal.load_object(None, SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("White-particle main system is missing")

grid = find_by_path(
    unreal.NiagaraDataInterfaceGrid2DCollection,
    GRID_PATH,
)
created = False
if grid is None:
    reference_grid = find_by_path(
        unreal.NiagaraDataInterfaceGrid2DCollection,
        REFERENCE_GRID_PATH,
    )
    if reference_grid is None:
        raise RuntimeError("Reference Grid2D user DI is missing")

    binding = reference_grid.get_editor_property(
        "render_target_user_parameter"
    )
    parameter = binding.get_editor_property("parameter")
    parameter.set_editor_property(
        "name", "User.SSPR_TrajectoryRT"
    )
    binding.set_editor_property("parameter", parameter)

    grid = unreal.new_object(
        unreal.NiagaraDataInterfaceGrid2DCollection,
        outer=system,
        name="SSPR_TrajectoryGridDI",
    )
    grid.set_editor_property(
        "render_target_user_parameter",
        binding,
    )
    created = True

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

stored_binding = grid.get_editor_property(
    "render_target_user_parameter"
)
stored_parameter = stored_binding.get_editor_property("parameter")
result = {
    "path": grid.get_path_name(),
    "created": created,
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
}
print("PARTICLE_USER_GRID_DI=" + json.dumps(result, sort_keys=True))
if (
    result["path"] != GRID_PATH
    or result["numCells"] != [2048, 2048]
    or result["numAttributes"] != 1
    or not result["clear"]
    or result["targetParameter"] != "User.SSPR_TrajectoryRT"
):
    raise RuntimeError("Trajectory Grid2D DI verification failed")
