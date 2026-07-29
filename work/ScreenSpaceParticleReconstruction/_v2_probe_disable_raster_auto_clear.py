import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
rows = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        SYSTEM in path
        and data_interface.get_class().get_name()
        == "NiagaraDataInterfaceRasterizationGrid3D"
    ):
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", False
        )
        rows.append(path)
print("V2_RASTER_CLEAR_DISABLED=" + json.dumps(rows, sort_keys=True))
