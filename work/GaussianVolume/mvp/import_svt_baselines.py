"""Import the two smoke2 SVT baselines and create matching material instances."""

import json

import unreal


DESTINATION = "/Game/GaussianVolume/Baselines"
PARENT = "/Engine/EngineMaterials/SparseVolumeMaterial.SparseVolumeMaterial"
VARIANTS = (
    (
        r"D:\Work\AI\Iris\tmp\openvdb_samples\svt_baselines\smoke2_density_u8.vdb",
        "SVT_Smoke2_Density_U8",
    ),
    (
        r"D:\Work\AI\Iris\tmp\openvdb_samples\svt_baselines\smoke2_density_f16.vdb",
        "SVT_Smoke2_Density_F16",
    ),
)


def import_svt(filename, name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", DESTINATION)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", True)
    task.set_editor_property("factory", unreal.SparseVolumeTextureFactory())
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(f"{DESTINATION}/{name}")
    if not asset or asset.get_class().get_name() != "StaticSparseVolumeTexture":
        raise RuntimeError(f"failed to import {filename}")
    return asset


def material_for(svt, suffix):
    path = f"{DESTINATION}/MI_Smoke2_SVT_{suffix}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        material = unreal.EditorAssetLibrary.load_asset(path)
    else:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            path.rsplit("/", 1)[1],
            DESTINATION,
            unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew(),
        )
    parent = unreal.load_asset(PARENT)
    material.set_editor_property("parent", parent)
    unreal.MaterialEditingLibrary.update_material_instance(material)
    # UE 5.8 writes these parameters but its Python setters currently always
    # return false. Validate assignments through the getters below instead.
    unreal.MaterialEditingLibrary.set_material_instance_sparse_volume_texture_parameter_value(
        material, "SparseVolumeTexture", svt
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        material, "Density Scale", 0.02
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        material, "Albedo Scale", 1.0
    )
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        material, "Albedo", unreal.LinearColor(0.9, 0.9, 0.9, 1.0)
    )
    unreal.MaterialEditingLibrary.update_material_instance(material)
    if (
        unreal.MaterialEditingLibrary.get_material_instance_sparse_volume_texture_parameter_value(
            material, "SparseVolumeTexture"
        )
        != svt
    ):
        raise RuntimeError("SVT material readback mismatch")
    if abs(
        unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            material, "Density Scale"
        )
        - 0.02
    ) > 1e-6:
        raise RuntimeError("Density Scale material readback mismatch")
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    return material


def main():
    unreal.EditorAssetLibrary.make_directory(DESTINATION)
    report = []
    for filename, asset_name in VARIANTS:
        suffix = asset_name.rsplit("_", 1)[1]
        svt = import_svt(filename, asset_name)
        material = material_for(svt, suffix)
        report.append(
            {
                "asset": svt.get_path_name(),
                "material": material.get_path_name(),
                "resolution": str(svt.get_editor_property("volume_resolution")),
                "frames": svt.get_editor_property("num_frames"),
                "mips": svt.get_editor_property("num_mip_levels"),
                "frame_transform": str(svt.get_frame_transform()),
                "format_a": str(svt.get_editor_property("format_a")),
                "format_b": str(svt.get_editor_property("format_b")),
            }
        )
    unreal.log("SVT_BASELINE_REPORT\n" + json.dumps(report, indent=2))


main()
