import json
import unreal

PACKAGE_TOKEN = "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main"
rows = []
for grid in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceGrid2DCollection
):
    path = grid.get_path_name()
    if PACKAGE_TOKEN not in path:
        continue
    rows.append(
        {
            "path": path,
            "outer": grid.get_outer().get_path_name()
            if grid.get_outer()
            else None,
            "numCells": [
                int(grid.get_editor_property("num_cells_x")),
                int(grid.get_editor_property("num_cells_y")),
            ],
            "numAttributes": int(
                grid.get_editor_property("num_attributes")
            ),
            "clear": bool(
                grid.get_editor_property(
                    "clear_before_non_iteration_stage"
                )
            ),
        }
    )

modules = [
    str(name)
    for name in unreal.NiagaraScratchPadService.list_scratch_modules(
        PACKAGE_TOKEN, "Fountain"
    )
]
print(
    "NEW_MAIN_DI_STATE="
    + json.dumps({"grids": rows, "modules": modules}, sort_keys=True)
)
