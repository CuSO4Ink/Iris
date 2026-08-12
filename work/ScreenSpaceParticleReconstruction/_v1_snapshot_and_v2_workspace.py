import json
import unreal


SOURCE = "/Game/SSPR_Validation/M2/ParticleTrails"
V1 = "/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729"
V2 = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"

RENAMES = (
    (
        V2 + "/NS_SSPR_ParticleTrails_Main",
        V2 + "/NS_SSPR_AnisotropicSplat_Main",
    ),
    (
        V2 + "/M_SSPR_ParticleTrails_FluidV2",
        V2 + "/M_SSPR_AnisotropicSplat_Display",
    ),
    (
        V2 + "/MI_SSPR_ParticleTrails_FluidV2_HQ",
        V2 + "/MI_SSPR_AnisotropicSplat_HQ",
    ),
    (
        V2 + "/L_SSPR_ParticleTrails_Validation",
        V2 + "/L_SSPR_AnisotropicSplat_Validation",
    ),
)


def list_assets(path):
    return sorted(
        unreal.EditorAssetLibrary.list_assets(
            path, recursive=True, include_folder=False
        )
    )


def main():
    source_assets = list_assets(SOURCE)
    if not source_assets:
        raise RuntimeError("ParticleTrails source folder is empty")
    for destination in (V1, V2):
        existing = list_assets(destination)
        if existing:
            raise RuntimeError(
                "Refusing to overwrite existing version folder: " + destination
            )

    unreal.EditorAssetLibrary.save_directory(SOURCE, False, True)
    if not unreal.EditorAssetLibrary.duplicate_directory(SOURCE, V1):
        raise RuntimeError("Failed to create frozen V1 snapshot")
    if not unreal.EditorAssetLibrary.duplicate_directory(V1, V2):
        raise RuntimeError("Failed to create V2 anisotropic workspace")

    rename_results = []
    for old_path, new_path in RENAMES:
        if not unreal.EditorAssetLibrary.does_asset_exist(old_path):
            raise RuntimeError("Expected duplicated asset is missing: " + old_path)
        renamed = bool(unreal.EditorAssetLibrary.rename_asset(old_path, new_path))
        rename_results.append(
            {"from": old_path, "to": new_path, "renamed": renamed}
        )
        if not renamed:
            raise RuntimeError("Failed to rename V2 workspace asset: " + old_path)

    unreal.EditorAssetLibrary.save_directory(V1, False, True)
    unreal.EditorAssetLibrary.save_directory(V2, False, True)
    v1_assets = list_assets(V1)
    v2_assets = list_assets(V2)
    result = {
        "source": SOURCE,
        "v1": V1,
        "v2": V2,
        "sourceAssetCount": len(source_assets),
        "v1AssetCount": len(v1_assets),
        "v2AssetCount": len(v2_assets),
        "renames": rename_results,
        "v1Assets": v1_assets,
        "v2Assets": v2_assets,
    }
    print("SSPR_V1_SNAPSHOT_V2_WORKSPACE=" + json.dumps(result, sort_keys=True))
    if len(v1_assets) != len(source_assets) or len(v2_assets) != len(source_assets):
        raise RuntimeError("Version folder asset counts do not match source")


main()
