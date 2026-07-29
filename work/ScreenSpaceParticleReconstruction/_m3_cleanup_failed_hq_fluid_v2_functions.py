import json
import unreal


PATHS = (
    "/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity",
    "/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQFluidV2/MF_SSPR_DensityGradientLighting",
)


def main():
    result = {}
    for path in PATHS:
        existed = unreal.EditorAssetLibrary.does_asset_exist(path)
        deleted = False
        if existed:
            deleted = bool(unreal.EditorAssetLibrary.delete_asset(path))
            if not deleted:
                raise RuntimeError("Failed to remove unreferenced failed V2 asset: " + path)
        result[path] = {"existed": existed, "deleted": deleted}
    print("M3_FAILED_V2_CLEANUP=" + json.dumps(result, sort_keys=True))


main()
