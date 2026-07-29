import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"


def main():
    material = unreal.load_asset(MATERIAL_PATH)
    instance = unreal.load_asset(INSTANCE_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing V2 display material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Missing V2 display material instance")

    instance.modify()

    # First continuity baseline: keep the anisotropic raw field as fine
    # structure, but make the reconstructed medium/body field responsible for
    # most of the visible smoke mass. Neutral lighting isolates density quality
    # from the old high-contrast gradient-lighting experiment.
    scalar_values = {
        "AS_InputGain": 1.0,
        "AS_MediumRadiusPx": 14.0,
        "AS_BodyRadiusPx": 48.0,
        "AS_MediumMipBias": -0.15,
        "AS_BodyMipBias": 0.35,
        "AS_RidgeStrength": 0.25,
        "AS_FilamentWeight": 0.18,
        "AS_MediumWeight": 0.50,
        "AS_BodyWeight": 0.32,
        "AS_DetailStrength": 0.03,
        "AS_EdgeStrength": 0.0,
        "AS_BlackPoint": 0.0,
        "AS_DensityGain": 2.0,
        "AS_Contrast": 0.48,
        "AS_EdgeFadeWidthPx": 20.0,
        "AS_LightingMipLevel": 4.0,
        "AS_LightingGradientRadius": 1.0,
        "AS_LightingGradientStrength": 2.0,
        "AS_AmbientLight": 1.0,
        "AS_LightStrength": 0.0,
        "AS_Extinction": 2.4,
        "AS_OpacityScale": 0.82,
        "AS_EmissiveStrength": 1.0,
        "AS_DebugRaw": 0.0,
    }
    for name, value in scalar_values.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )

    smoke_color = unreal.LinearColor(0.72, 0.78, 0.88, 1.0)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        instance, "AS_SmokeColor", smoke_color
    )

    try:
        instance.post_edit_change()
    except Exception:
        pass
    saved_loaded = bool(
        unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    )
    saved_path = False
    if not saved_loaded:
        saved_path = bool(
            unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False)
        )

    stored_scalars = {
        str(row.get_editor_property("parameter_info").get_editor_property("name")):
        float(row.get_editor_property("parameter_value"))
        for row in instance.get_editor_property("scalar_parameter_values")
    }
    stored_vectors = {
        str(row.get_editor_property("parameter_info").get_editor_property("name")):
        str(row.get_editor_property("parameter_value"))
        for row in instance.get_editor_property("vector_parameter_values")
    }
    missing = sorted(set(scalar_values) - set(stored_scalars))
    mismatched = {
        name: {"expected": value, "stored": stored_scalars.get(name)}
        for name, value in scalar_values.items()
        if name in stored_scalars and abs(stored_scalars[name] - value) > 1.0e-5
    }
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    result = {
        "instance": instance.get_path_name(),
        "parent": instance.get_editor_property("parent").get_path_name(),
        "scalarValues": scalar_values,
        "storedVectors": stored_vectors,
        "missing": missing,
        "mismatched": mismatched,
        "materialCompiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [str(value) for value in diagnostics.compile_errors],
        "savedLoaded": saved_loaded,
        "savedPath": saved_path,
    }
    print("V2_CONTINUITY_NEUTRAL_LIGHTING=" + json.dumps(result, sort_keys=True))
    if (
        missing or mismatched or
        not diagnostics.is_compiled_ok or diagnostics.compile_errors or
        not (saved_loaded or saved_path)
    ):
        raise RuntimeError("Continuity baseline validation failed: " + repr(result))


main()
