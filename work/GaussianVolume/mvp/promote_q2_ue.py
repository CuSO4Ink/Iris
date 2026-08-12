"""Promote the validated Q2 Gaussian fit to the saved TechLab hero actor."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
JSON_PATH = (
    r"D:\Work\Personal\Project\Abyss\Plugins\GaussianVolume\Content\Data"
    r"\Smoke2_GFields_Q2_10K.json"
)
TARGET_LABEL = "Smoke2 GFields Q2 10K High Fidelity"
SOURCE_LABEL = "Smoke2 GFields Q0 1K (Scout)"
EXPECTED_COUNT = 9944


with open(JSON_PATH, encoding="utf-8") as stream:
    if json.load(stream)["primitive_count"] != EXPECTED_COUNT:
        raise RuntimeError("Unexpected Q2 primitive count")

unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = editor_actors.get_all_level_actors()
hero = next(
    (
        actor
        for actor in actors
        if isinstance(actor, unreal.GaussianVolumeActor)
        and actor.get_actor_label() in (TARGET_LABEL, SOURCE_LABEL)
    ),
    None,
)
if hero is None:
    hero = editor_actors.spawn_actor_from_class(
        unreal.GaussianVolumeActor,
        unreal.Vector(-390.0, 0.0, 300.0),
        unreal.Rotator(),
    )
if hero is None:
    raise RuntimeError("Failed to create the Q2 hero actor")

hero.modify()
hero.set_actor_label(TARGET_LABEL)
component = hero.get_editor_property("gaussian_volume_component")
component.set_editor_property("enable_rendering", True)
component.set_editor_property("enable_screen_size_lod", False)
component.set_editor_property("support_tau_min", 0.0)
source = unreal.FilePath()
source.file_path = JSON_PATH
hero.set_editor_property("gaussian_json_file", source)
if not hero.import_gaussian_json():
    raise RuntimeError("ImportGaussianJson returned false")

for actor in actors:
    if isinstance(actor, unreal.GaussianVolumeActor) and actor != hero:
        actor.get_editor_property("gaussian_volume_component").set_editor_property(
            "enable_rendering", False
        )

if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    raise RuntimeError("Failed to save TechLab")
unreal.log(
    f"GAUSSIAN_VOLUME_Q2_PROMOTED label={TARGET_LABEL} count={EXPECTED_COUNT}"
)
