import json
import unreal


SOURCE_FOLDER = "/Game/SSPR_Validation/M2"
ARCHIVE_FOLDER = "/Game/SSPR_Validation/Archive/PingPong_M2_20260728"
LEGACY_ASSETS = [
    "BP_SSPR_TemporalOrchestrator",
    "RT_SSPR_HistoryB",
    "M_SSPR_TemporalCombine",
    "RT_SSPR_HistoryA",
    "RT_SSPR_Current",
    "NS_SSPR_ProjTest_M2",
    "M_SSPR_DensityCombine",
    "M_SSPR_BlurLarge",
    "M_SSPR_BlurSmall",
    "M_SSPR_CoreExtract",
    "RT_SSPR_Density",
    "RT_SSPR_BlurLarge",
    "RT_SSPR_BlurSmall",
    "RT_SSPR_Core",
    "MI_SSPR_Smoke_DensityDebug",
    "MI_SSPR_Smoke_Default",
    "M_SSPR_SmokeResolve",
    "RT_SSPR_Smoke",
    "MI_SSPR_SmokeCard_Default",
    "M_SSPR_SmokeCard",
]

unreal.EditorAssetLibrary.make_directory(ARCHIVE_FOLDER)
results = []
for asset_name in LEGACY_ASSETS:
    source = SOURCE_FOLDER + "/" + asset_name
    destination = ARCHIVE_FOLDER + "/" + asset_name
    source_exists = unreal.EditorAssetLibrary.does_asset_exist(source)
    destination_exists = unreal.EditorAssetLibrary.does_asset_exist(destination)
    moved = False
    if source_exists and not destination_exists:
        moved = bool(unreal.EditorAssetLibrary.rename_asset(source, destination))
    results.append(
        {
            "name": asset_name,
            "sourceExisted": source_exists,
            "destinationExistedBefore": destination_exists,
            "moved": moved,
            "sourceExistsAfter": unreal.EditorAssetLibrary.does_asset_exist(source),
            "destinationExistsAfter": unreal.EditorAssetLibrary.does_asset_exist(
                destination
            ),
        }
    )

failures = [
    row
    for row in results
    if row["sourceExisted"]
    and not row["destinationExistedBefore"]
    and not row["moved"]
]
print(
    "GRIDMAIN_ARCHIVE="
    + json.dumps(
        {
            "archiveFolder": ARCHIVE_FOLDER,
            "results": results,
            "failureCount": len(failures),
        },
        sort_keys=True,
    )
)
if failures:
    raise RuntimeError("Failed to archive: " + repr(failures))
