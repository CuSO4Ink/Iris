import json
import unreal


SOURCE = "/Game/SSPR_Validation/M2/NewNiagaraSystem"
FOLDER = "/Game/SSPR_Validation/M2/GridTrails"
DESTINATION = FOLDER + "/NS_SSPR_GridTrails_Main"

unreal.EditorAssetLibrary.make_directory(FOLDER)
created = False
if not unreal.EditorAssetLibrary.does_asset_exist(DESTINATION):
    created = bool(unreal.EditorAssetLibrary.duplicate_asset(SOURCE, DESTINATION))
    if not created:
        raise RuntimeError("Failed to duplicate Grid2D Niagara scaffold")

asset = unreal.load_asset(DESTINATION)
if not isinstance(asset, unreal.NiagaraSystem):
    raise RuntimeError("Main GridTrails asset is invalid")

saved = bool(unreal.EditorAssetLibrary.save_asset(DESTINATION, False))
print(
    "GRIDMAIN_CREATE="
    + json.dumps(
        {
            "source": SOURCE,
            "destination": DESTINATION,
            "created": created,
            "saved": saved,
            "asset": asset.get_path_name(),
        },
        sort_keys=True,
    )
)
if not saved:
    raise RuntimeError("Failed to save GridTrails main system")
