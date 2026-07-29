import json
import unreal

MATERIAL_DEFAULTS = {
    "/Game/SSPR_Validation/M2/M_SSPR_BlurLarge": {
        "RadiusPx": 7.0,
    },
    "/Game/SSPR_Validation/M2/M_SSPR_DensityCombine": {
        "CoreWeight": 0.60,
        "SmallBlurWeight": 1.00,
        "LargeBlurWeight": 0.65,
        "DensityGain": 1.0,
        "DensityLow": 0.002,
        "DensityHigh": 0.18,
        "EdgeBreakStrength": 0.04,
        "NoiseScale": 18.0,
    },
}

results = {}
for material_path, defaults in MATERIAL_DEFAULTS.items():
    material = unreal.load_asset(material_path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Material missing: " + material_path)
    changed = {}
    for expression in unreal.MaterialEditingLibrary.get_material_expressions(
        material
    ):
        if not isinstance(
            expression, unreal.MaterialExpressionScalarParameter
        ):
            continue
        name = str(expression.get_editor_property("parameter_name"))
        if name not in defaults:
            continue
        expression.set_editor_property("default_value", float(defaults[name]))
        changed[name] = float(defaults[name])
    missing = sorted(set(defaults) - set(changed))
    if missing:
        raise RuntimeError(
            "Missing scalar parameters on "
            + material_path
            + ": "
            + repr(missing)
        )
    unreal.MaterialEditingLibrary.recompile_material(material)
    saved = bool(
        unreal.EditorAssetLibrary.save_asset(material_path, False)
    )
    results[material_path] = {"changed": changed, "saved": saved}
    if not saved:
        raise RuntimeError("Failed to save " + material_path)

print("M2B_TUNING=" + json.dumps(results, sort_keys=True))
