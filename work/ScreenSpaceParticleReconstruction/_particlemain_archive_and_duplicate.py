import json
import unreal

WRONG_LABEL = "SSPR_GridTrails_Main"
WRONG_ROOT = "/Game/SSPR_Validation/M2/GridTrails"
ARCHIVE_ROOT = "/Game/SSPR_Validation/Archive/IncorrectGasBootstrap_20260728"
SOURCE = "/Game/SSPR_Validation/M2/NewNiagaraSystem2"
DESTINATION = "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main"

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
removed_actors = []
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() != WRONG_LABEL:
        continue
    removed_actors.append(actor.get_path_name())
    actor_subsystem.destroy_actor(actor)

unreal.EditorAssetLibrary.make_directory(ARCHIVE_ROOT)
archived_assets = {}
for name in (
    "BP_SSPR_GridTrails_Main",
    "MI_SSPR_GridTrails_Display",
    "NS_SSPR_GridTrails_Main",
):
    source_path = WRONG_ROOT + "/" + name
    destination_path = ARCHIVE_ROOT + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(destination_path):
        archived_assets[source_path] = destination_path
        continue
    if unreal.EditorAssetLibrary.does_asset_exist(source_path):
        if not unreal.EditorAssetLibrary.rename_asset(source_path, destination_path):
            raise RuntimeError("Failed to archive " + source_path)
        archived_assets[source_path] = destination_path

unreal.EditorAssetLibrary.make_directory("/Game/SSPR_Validation/M2/ParticleTrails")
duplicated = False
if not unreal.EditorAssetLibrary.does_asset_exist(DESTINATION):
    duplicated = bool(unreal.EditorAssetLibrary.duplicate_asset(SOURCE, DESTINATION))
    if not duplicated:
        raise RuntimeError("Failed to duplicate white-particle Niagara system")

asset = unreal.load_asset(DESTINATION)
if not isinstance(asset, unreal.NiagaraSystem):
    raise RuntimeError("White-particle mainline asset is missing or invalid")

saved = bool(unreal.EditorAssetLibrary.save_asset(DESTINATION, False))
if not saved:
    raise RuntimeError("Failed to save white-particle mainline asset")

print(
    "PARTICLE_MAINLINE_CREATED="
    + json.dumps(
        {
            "removedWrongActors": removed_actors,
            "archivedWrongAssets": archived_assets,
            "source": SOURCE,
            "destination": asset.get_path_name(),
            "duplicated": duplicated,
            "saved": saved,
        },
        sort_keys=True,
    )
)
