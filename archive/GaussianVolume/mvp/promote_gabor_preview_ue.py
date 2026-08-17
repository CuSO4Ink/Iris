"""Add the step-720 Gabor checkpoint to TechLab without removing the Q2 base."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
JSON_PATH = (
    r"D:\Work\Personal\Project\Abyss\Plugins\GaussianVolume\Content\Data"
    r"\Smoke2_GFields_Q2_Gabor_10K_4K_Step0720.json"
)
BASE_LABEL = "Smoke2 GFields Q2 10K High Fidelity"
PREVIEW_LABEL = "Smoke2 GFields Q2 10K + 4K Gabor Preview Step 0720"

with open(JSON_PATH, encoding="utf-8") as stream:
    payload = json.load(stream)
if payload["primitive_count"] != 14040 or payload["gabor_count"] != 4096:
    raise RuntimeError("Unexpected step-720 Gabor payload")

unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = editor_actors.get_all_level_actors()
base = next(
    (
        actor
        for actor in actors
        if isinstance(actor, unreal.GaussianVolumeActor)
        and actor.get_actor_label() == BASE_LABEL
    ),
    None,
)
if base is None:
    raise RuntimeError("Q2 base actor is missing")

preview = next(
    (
        actor
        for actor in actors
        if isinstance(actor, unreal.GaussianVolumeActor)
        and actor.get_actor_label() == PREVIEW_LABEL
    ),
    None,
)
if preview is None:
    preview = editor_actors.spawn_actor_from_class(
        unreal.GaussianVolumeActor,
        base.get_actor_location(),
        base.get_actor_rotation(),
    )
if preview is None:
    raise RuntimeError("Failed to create Gabor preview actor")

preview.modify()
preview.set_actor_label(PREVIEW_LABEL)
preview.set_actor_location(base.get_actor_location(), False, False)
preview.set_actor_rotation(base.get_actor_rotation(), False)
preview.set_actor_scale3d(base.get_actor_scale3d())

base_component = base.get_editor_property("gaussian_volume_component")
preview_component = preview.get_editor_property("gaussian_volume_component")
for property_name in (
    "density_multiplier",
    "density_gamma",
    "use_scene_lights",
    "directional_light_actor",
    "sky_light_actor",
    "directional_light_intensity_scale",
    "sky_light_intensity_scale",
    "light_direction",
    "light_color",
    "ambient_color",
    "powder_factor",
    "max_ray_distance",
    "use_scene_depth",
    "debug_view",
):
    preview_component.set_editor_property(
        property_name, base_component.get_editor_property(property_name)
    )
preview_component.set_editor_property("enable_screen_size_lod", False)
preview_component.set_editor_property("support_tau_min", 0.0)

source = unreal.FilePath()
source.file_path = JSON_PATH
preview.set_editor_property("gaussian_json_file", source)
if not preview.import_gaussian_json():
    raise RuntimeError("ImportGaussianJson returned false")

for actor in editor_actors.get_all_level_actors():
    if isinstance(actor, unreal.GaussianVolumeActor):
        actor.get_editor_property("gaussian_volume_component").set_editor_property(
            "enable_rendering", actor == preview
        )

if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    raise RuntimeError("Failed to save TechLab")
unreal.log(
    "GAUSSIAN_VOLUME_GABOR_PREVIEW_READY "
    f"label={PREVIEW_LABEL} primitives={payload['primitive_count']} "
    f"gabors={payload['gabor_count']} base_enabled=False preview_enabled=True"
)
