import json
import unreal


FOLDER = "/Game/SSPR_Validation/M2/ParticleTrails"
PARENT_PATH = FOLDER + "/M_SSPR_ParticleTrails_Display"
INSTANCE_PATH = FOLDER + "/MI_SSPR_ParticleTrails_HQ_Default"


def main():
    parent = unreal.load_asset(PARENT_PATH)
    if not isinstance(parent, unreal.Material):
        raise RuntimeError("M3 parent material is missing")

    instance = unreal.load_asset(INSTANCE_PATH)
    created = False
    if instance is None:
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "MI_SSPR_ParticleTrails_HQ_Default",
            FOLDER,
            unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew(),
        )
        created = True
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("M3 HQ material instance is invalid")

    # The parent material owns the approved HQ defaults. Keep the instance
    # lightweight: artists opt in to overrides only when tuning a look.
    instance.set_editor_property("parent", parent)
    scalar_override_names = sorted(
        str(value.get_editor_property("parameter_info").get_editor_property("name"))
        for value in instance.get_editor_property("scalar_parameter_values")
    )
    vector_override_names = sorted(
        str(value.get_editor_property("parameter_info").get_editor_property("name"))
        for value in instance.get_editor_property("vector_parameter_values")
    )

    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save M3 HQ material instance")

    print(
        "M3_HQ_MATERIAL_INSTANCE="
        + json.dumps(
            {
                "created": created,
                "path": instance.get_path_name(),
                "parent": instance.get_editor_property("parent").get_path_name(),
                "storedScalarOverrideNames": scalar_override_names,
                "storedVectorOverrideNames": vector_override_names,
                "defaultsSource": "parent material",
            },
            sort_keys=True,
        )
    )


main()
