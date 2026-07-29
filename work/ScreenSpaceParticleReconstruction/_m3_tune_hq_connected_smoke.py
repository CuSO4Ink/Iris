import json
import unreal


INSTANCE_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "MI_SSPR_ParticleTrails_HQ_Default"
)


def main():
    instance = unreal.load_asset(INSTANCE_PATH)
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("M3 HQ material instance is missing")

    # High-quality connectivity baseline.  The source grid remains untouched;
    # these overrides only reconstruct a continuous density field for display.
    scalar_values = {
        "SmallRadiusPx": 6.0,
        "LargeRadiusPx": 12.0,
        "CoreWeight": 0.12,
        "SmallWeight": 0.50,
        "LargeWeight": 0.38,
        "DetailStrength": 0.05,
        "EdgeStrength": 0.02,
        "BlackPoint": 0.0,
        "TrajectoryGain": 4.0,
        "Contrast": 0.55,
        "Extinction": 3.2,
        "OpacityScale": 0.86,
        "EmissiveStrength": 0.82,
        "DebugRaw": 0.0,
    }
    for name, value in scalar_values.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )

    smoke_color = unreal.LinearColor(0.64, 0.70, 0.80, 1.0)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        instance, "SmokeColor", smoke_color
    )

    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save tuned M3 HQ material instance")

    stored_scalars = {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        float(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("scalar_parameter_values")
    }
    stored_vectors = {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        str(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("vector_parameter_values")
    }
    missing = sorted(set(scalar_values) - set(stored_scalars))
    if missing:
        raise RuntimeError("Material instance overrides were not stored: " + repr(missing))

    print(
        "M3_HQ_CONNECTED_SMOKE="
        + json.dumps(
            {
                "path": instance.get_path_name(),
                "scalarOverrides": stored_scalars,
                "vectorOverrides": stored_vectors,
            },
            sort_keys=True,
        )
    )


main()
