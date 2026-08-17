"""Delete the temporary G37/SVT cold-start maps."""

import unreal


assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
for path in (
    "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_Empty",
    "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_SVT",
    "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_G37_GS",
):
    if unreal.EditorAssetLibrary.does_asset_exist(path) and not assets.delete_asset(path):
        raise RuntimeError(f"failed to delete {path}")
unreal.log("VRAM_MAP_CLEANUP_COMPLETE")
