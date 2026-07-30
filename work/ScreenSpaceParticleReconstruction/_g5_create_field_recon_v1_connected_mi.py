import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
SOURCE = ROOT + "/MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ"
TARGET = ROOT + "/MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ"

SCALARS = {
    "FR_GuideRadiusPx": 4.5,
    "FR_StepPx": 2.25,
    "FR_ActiveSteps": 8.0,
    "FR_MediumCrossPx": 2.75,
    "FR_BodyCrossPx": 8.5,
    "FR_CoherenceMin": 0.08,
    "FR_DepthFalloff": 48.0,
    "FR_DepthSigmaScale": 58.0,
    "FR_FilamentTaper": 1.65,
    "FR_MediumTaper": 0.80,
    "FR_BodyTaper": 0.48,
    "FR_OneSidedBlend": 0.46,
    "FR_SupportGain": 0.85,
    "FR_FilamentGain": 0.90,
    "FR_MediumGain": 1.20,
    "FR_BodyGain": 1.05,
    "FR_FilamentWeight": 0.18,
    "FR_MediumWeight": 0.54,
    "FR_BodyWeight": 0.28,
    "FR_DetailStrength": 0.0,
    "FR_EdgeStrength": 0.0,
    "FR_BlackPoint": 0.001,
    "FR_DensityGain": 1.25,
    "FR_Contrast": 0.78,
    "FR_EdgeFadeWidthPx": 20.0,
    "FR_Extinction": 1.45,
    "FR_OpacityScale": 0.82,
    "FR_EmissiveStrength": 0.82,
    "FR_DepthRegularizationPx": 4.0,
    "FR_DepthGradientPx": 3.0,
    "FR_DepthRangeScale": 12.0,
    "FR_ThicknessAbsorption": 4.6,
    "FR_Ambient": 0.68,
    "FR_DirectionalStrength": 0.42,
    "FR_NearFarContrast": 0.12,
    "FR_DepthCueStrength": 1.0,
}
VECTORS = {
    "FR_SmokeColor": unreal.LinearColor(0.56, 0.61, 0.69, 1.0),
    "FR_NearTint": unreal.LinearColor(1.04, 1.00, 0.96, 1.0),
    "FR_FarTint": unreal.LinearColor(0.78, 0.87, 1.02, 1.0),
    "FR_ThickTint": unreal.LinearColor(0.70, 0.78, 0.90, 1.0),
}


if unreal.EditorAssetLibrary.does_asset_exist(TARGET):
    raise RuntimeError("Refusing to overwrite existing MI: " + TARGET)
instance = unreal.EditorAssetLibrary.duplicate_asset(SOURCE, TARGET)
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Failed to duplicate connected FieldRecon MI")

library = unreal.MaterialEditingLibrary
for name, value in SCALARS.items():
    library.set_material_instance_scalar_parameter_value(
        instance, name, float(value)
    )
for name, value in VECTORS.items():
    library.set_material_instance_vector_parameter_value(
        instance, name, value
    )
try:
    instance.post_edit_change()
except Exception:
    pass
saved = bool(unreal.EditorAssetLibrary.save_asset(TARGET, False))

stored_scalars = {
    str(
        row.get_editor_property("parameter_info").get_editor_property("name")
    ): float(row.get_editor_property("parameter_value"))
    for row in instance.get_editor_property("scalar_parameter_values")
}
missing = sorted(set(SCALARS) - set(stored_scalars))
mismatched = {
    name: {
        "expected": value,
        "stored": stored_scalars.get(name),
    }
    for name, value in SCALARS.items()
    if name in stored_scalars
    and abs(stored_scalars[name] - value) > 1.0e-5
}
result = {
    "source": SOURCE,
    "target": TARGET,
    "saved": saved,
    "scalars": SCALARS,
    "vectors": {
        name: [value.r, value.g, value.b, value.a]
        for name, value in VECTORS.items()
    },
    "missing": missing,
    "mismatched": mismatched,
}
print("G5_FIELD_RECON_V1_CONNECTED_MI=" + json.dumps(
    result, sort_keys=True
))
if not saved or missing or mismatched:
    raise RuntimeError(
        "Connected FieldRecon MI gate failed: " + repr(result)
    )
