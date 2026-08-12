import json
import unreal


SOURCE = "/NiagaraFluids/Materials/Grid2D/Instances/M_2D_GasBase_Inst"
DESTINATION = (
    "/Game/SSPR_Validation/M2/GridTrails/MI_SSPR_GridTrails_Display"
)

created = False
if not unreal.EditorAssetLibrary.does_asset_exist(DESTINATION):
    created = bool(unreal.EditorAssetLibrary.duplicate_asset(SOURCE, DESTINATION))
    if not created:
        raise RuntimeError("Failed to duplicate Grid2D display material")

material = unreal.load_asset(DESTINATION)
if not isinstance(material, unreal.MaterialInstanceConstant):
    raise RuntimeError("GridTrails display material is invalid")

lib = unreal.MaterialEditingLibrary
for parameter_name, value in {
    "DensityGain": 1.8,
    "DensityOffset": 0.0,
    "ConstantExtinction": 1.0,
    "FireGain": 0.0,
    "FireOpacityGain": 0.0,
}.items():
    lib.set_material_instance_scalar_parameter_value(
        material, parameter_name, float(value)
    )
lib.set_material_instance_vector_parameter_value(
    material,
    "Smoke Color",
    unreal.LinearColor(0.64, 0.72, 0.82, 1.0),
)

saved = bool(unreal.EditorAssetLibrary.save_asset(DESTINATION, False))
print(
    "GRIDMAIN_DISPLAY_MATERIAL="
    + json.dumps(
        {
            "source": SOURCE,
            "destination": DESTINATION,
            "created": created,
            "saved": saved,
            "class": material.get_class().get_path_name(),
        },
        sort_keys=True,
    )
)
if not saved:
    raise RuntimeError("Failed to save GridTrails display material")
