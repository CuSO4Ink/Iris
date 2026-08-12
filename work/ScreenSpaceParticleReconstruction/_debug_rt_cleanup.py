import json
import unreal

DEBUG_PACKAGE = (
    "/Game/SSPR_Validation/Debug/"
    "NS_SSPR_RTWriteProbe_1785243895228"
)
LABEL = "SSPR_RTWriteProbe_Temporary"

level_editor = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
if level_editor.is_in_play_in_editor():
    raise RuntimeError("PIE is still active; cleanup deferred")

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
removed_actors = []
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() != LABEL:
        continue
    removed_actors.append(actor.get_path_name())
    actor_subsystem.destroy_actor(actor)

asset_existed = bool(
    unreal.EditorAssetLibrary.does_asset_exist(DEBUG_PACKAGE)
)
asset_deleted = True
if asset_existed:
    asset_deleted = bool(
        unreal.EditorAssetLibrary.delete_asset(DEBUG_PACKAGE)
    )

print(
    "RT_DEBUG_CLEANUP="
    + json.dumps(
        {
            "removedActors": removed_actors,
            "debugPackage": DEBUG_PACKAGE,
            "assetExisted": asset_existed,
            "assetDeleted": asset_deleted,
        },
        sort_keys=True,
    )
)
if not asset_deleted:
    raise RuntimeError("Failed to delete isolated debug asset")
