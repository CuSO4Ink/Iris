import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)

rows = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        SYSTEM not in path
        or data_interface.get_class().get_name()
        != "NiagaraDataInterfaceRasterizationGrid3D"
    ):
        continue
    try:
        data_interface.modify()
    except Exception:
        pass
    data_interface.set_editor_property(
        "num_cells", unreal.IntVector(2048, 2048, 1)
    )
    data_interface.set_editor_property(
        "clear_before_non_iteration_stage", True
    )
    value = data_interface.get_editor_property("num_cells")
    rows.append({
        "path": path,
        "numCells": [int(value.x), int(value.y), int(value.z)],
        "clear": bool(data_interface.get_editor_property(
            "clear_before_non_iteration_stage"
        )),
    })

if not rows:
    raise RuntimeError("No RasterizationGrid3D objects found")

saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_FINAL_RASTER_DI=" + json.dumps({
    "rows": rows,
    "saved": saved,
}, sort_keys=True))
if not saved or any(row["numCells"] != [2048, 2048, 1] for row in rows):
    raise RuntimeError("Final raster DI gate failed")
