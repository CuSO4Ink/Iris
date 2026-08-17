"""Load the rejected Q2 scout through the UE actor importer without saving the level."""

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
JSON_PATH = (
    r"D:\Work\Personal\Project\Abyss\Plugins\GaussianVolume\Content\Data"
    r"\Smoke2_GFields_Q2_10K.json"
)
EXPECTED_COUNT = 9944


unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = actors.spawn_actor_from_class(
    unreal.GaussianVolumeActor, unreal.Vector(), unreal.Rotator()
)
if actor is None:
    raise RuntimeError("Failed to spawn GaussianVolumeActor")

try:
    source = unreal.FilePath()
    source.file_path = JSON_PATH
    actor.set_editor_property("gaussian_json_file", source)
    if not actor.import_gaussian_json():
        raise RuntimeError("ImportGaussianJson returned false")
    unreal.log(f"GAUSSIAN_VOLUME_Q2_IMPORT_OK expected_count={EXPECTED_COUNT}")
finally:
    actors.destroy_actor(actor)
