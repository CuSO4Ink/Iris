import json
import unreal


SYSTEM_FRAGMENT = (
    "/Game/SSPR_Validation/M2/"
    "NS_SSPR_ProjTest_M2"
)
RT_NAMES = (
    "RT_SSPR_Current",
    "RT_SSPR_HistoryA",
    "RT_SSPR_HistoryB",
    "RT_SSPR_Core",
    "RT_SSPR_BlurSmall",
    "RT_SSPR_BlurLarge",
    "RT_SSPR_Density",
    "RT_SSPR_Smoke",
)

grids = []
for grid in unreal.ObjectIterator(unreal.NiagaraDataInterfaceGrid2DCollection):
    path = grid.get_path_name()
    if SYSTEM_FRAGMENT not in path:
        continue
    binding_name = None
    try:
        binding = grid.get_editor_property("render_target_user_parameter")
        parameter = binding.get_editor_property("parameter")
        binding_name = str(parameter.get_editor_property("name"))
    except Exception:
        pass
    grids.append(
        {
            "path": path,
            "numCellsX": int(grid.get_editor_property("num_cells_x")),
            "numCellsY": int(grid.get_editor_property("num_cells_y")),
            "numCellsMaxAxis": int(
                grid.get_editor_property("num_cells_max_axis")
            ),
            "setGridFromMaxAxis": bool(
                grid.get_editor_property("set_grid_from_max_axis")
            ),
            "numAttributes": int(
                grid.get_editor_property("num_attributes")
            ),
            "clear": bool(
                grid.get_editor_property(
                    "clear_before_non_iteration_stage"
                )
            ),
            "renderTargetParameter": binding_name,
        }
    )

rts = {}
for name in RT_NAMES:
    path = "/Game/SSPR_Validation/M2/" + name
    rt = unreal.load_asset(path)
    if not isinstance(rt, unreal.TextureRenderTarget2D):
        rts[name] = {"error": "missing or wrong class"}
        continue
    rts[name] = {
        "size": [
            int(rt.get_editor_property("size_x")),
            int(rt.get_editor_property("size_y")),
        ],
        "format": str(rt.get_editor_property("render_target_format")),
        "filter": str(rt.get_editor_property("filter")),
    }

result = {"grids": grids, "renderTargets": rts}
print("M2HQ_RESOLUTION_STATE=" + json.dumps(result, sort_keys=True))
if not grids:
    raise RuntimeError("No M2 Grid2DCollection data interfaces found")
