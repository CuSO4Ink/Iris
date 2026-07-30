import json
import unreal


SOURCE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
TARGET = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance/"
    "NS_SSPR_AnisotropicSplat_DuplicateControlV1"
)

if unreal.EditorAssetLibrary.does_asset_exist(TARGET):
    raise RuntimeError("Duplicate control already exists")
duplicated = unreal.EditorAssetLibrary.duplicate_asset(SOURCE, TARGET)
if not isinstance(duplicated, unreal.NiagaraSystem):
    raise RuntimeError("Failed to create duplicate control")
saved = bool(unreal.EditorAssetLibrary.save_asset(TARGET, False))
result = {
    "source": SOURCE,
    "target": TARGET,
    "saved": saved,
    "fixedTick": bool(
        duplicated.get_editor_property("fixed_tick_delta")
    ),
}
print(
    "PERF_DUPLICATE_CONTROL_V1="
    + json.dumps(result, sort_keys=True)
)
if not saved or not result["fixedTick"]:
    raise RuntimeError("Duplicate control creation gate failed")
