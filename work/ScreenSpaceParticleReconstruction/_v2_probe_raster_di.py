import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)

rows = []
for obj in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    if obj.get_class().get_name() != "NiagaraDataInterfaceRasterizationGrid3D":
        continue
    path = obj.get_path_name()
    if SYSTEM not in path:
        continue
    props = {}
    for name in (
        "num_cells", "num_attributes", "precision", "reset_value",
        "clear_before_non_iteration_stage"
    ):
        try:
            value = obj.get_editor_property(name)
            if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
                value = [int(value.x), int(value.y), int(value.z)]
            props[name] = str(value) if not isinstance(value, list) else value
        except Exception as error:
            props[name] = "ERROR:" + str(error)
    rows.append({"path": path, "properties": props})

print("V2_RASTER_DI=" + json.dumps(rows, sort_keys=True))
