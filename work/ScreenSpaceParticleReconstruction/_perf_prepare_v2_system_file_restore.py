import json
import unreal


V2_SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main."
    "NS_SSPR_AnisotropicSplat_Main"
)
NEUTRAL_LEVEL = "/Engine/Maps/Entry"


system = unreal.load_asset(V2_SYSTEM)
closed_editors = False
if isinstance(system, unreal.NiagaraSystem):
    asset_editor_subsystem = unreal.get_editor_subsystem(
        unreal.AssetEditorSubsystem
    )
    closed_editors = bool(
        asset_editor_subsystem.close_all_editors_for_asset(system)
    )

level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
loaded = bool(level_subsystem.load_level(NEUTRAL_LEVEL))
if not loaded:
    raise RuntimeError("Failed to load neutral Engine Entry map")
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "obj gc")
print(
    "PERF_PREPARE_V2_SYSTEM_FILE_RESTORE="
    + json.dumps(
        {
            "closedEditors": closed_editors,
            "neutralLevelLoaded": loaded,
            "world": world.get_path_name(),
        },
        sort_keys=True,
    )
)
