import json
import unreal


INSTANCE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "MI_SSPR_G5_FieldDebugV2"
)
instance = unreal.load_asset(INSTANCE)
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Clean G5 V2 debug MI is missing")

values = {
    "G5_DebugMode": 6.0,
    "G5_DensityDisplayGain": 0.9,
    "G5_DepthDisplayGain": 10.0,
    "G5_SigmaDisplayGain": 32.0,
}
for name, value in values.items():
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, name, value
    )
saved = bool(unreal.EditorAssetLibrary.save_asset(INSTANCE, False))
resolved = {
    name: float(
        unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            instance, name
        )
    )
    for name in values
}
print(
    "G5_DEBUG_V2_TUNE="
    + json.dumps(
        {"values": values, "resolved": resolved, "saved": saved},
        sort_keys=True,
    )
)
if not saved or any(
    abs(resolved[name] - value) > 1.0e-5
    for name, value in values.items()
):
    raise RuntimeError("Failed to save clean G5 V2 debug MI")
