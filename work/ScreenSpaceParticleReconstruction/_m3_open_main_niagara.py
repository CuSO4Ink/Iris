import json
import unreal


SYSTEM_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)


def main():
    system = unreal.load_asset(SYSTEM_PATH)
    if system is None:
        raise RuntimeError("Main Niagara system is missing")
    subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    opened = bool(subsystem.open_editor_for_assets([system]))
    print(
        "M3_MAIN_NIAGARA_OPEN="
        + json.dumps(
            {"opened": opened, "asset": system.get_path_name()},
            sort_keys=True,
        )
    )


main()
