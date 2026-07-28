"""Load an exact-budget directional-shadow preview without changing SVT visibility."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
TARGET_COUNT = globals().get("TARGET_COUNT_OVERRIDE", 50_000)
JSON_PATH = globals().get(
    "JSON_PATH_OVERRIDE",
    (
        r"D:\Work\AI\Iris\work\GaussianVolume\artifacts\hero_tau_recovered50k_h9_directional"
        r"\GaussianVolume_Hero_TauRecovered50K_Directional.json"
    ),
)
LABEL = globals().get(
    "LABEL_OVERRIDE", "GaussianVolume Hero Directional Tau 50K H9 PREVIEW"
)
LIGHT_ROTATION = globals().get(
    "LIGHT_ROTATION_OVERRIDE", (54.5518787, 51.8930809, 115.9061271)
)


with open(JSON_PATH, encoding="utf-8") as stream:
    payload = json.load(stream)
if (
    payload.get("primitive_count") != TARGET_COUNT
    or len(payload.get("gaussians", ())) != TARGET_COUNT
):
    raise RuntimeError(f"preview source is not exactly {TARGET_COUNT} primitives")

unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_actors = actors.get_all_level_actors()
svt_before = {
    actor.get_actor_label(): (
        actor.is_hidden_ed(),
        actor.get_editor_property("hidden"),
        actor.get_editor_property("root_component").is_visible(),
    )
    for actor in level_actors
    if isinstance(actor, unreal.HeterogeneousVolume)
}
reference_class = getattr(unreal, "GaussianSplatting7DActor", None)
reference = next(
    (actor for actor in level_actors if reference_class and isinstance(actor, reference_class)),
    None,
)
preview = next(
    (
        actor
        for actor in level_actors
        if isinstance(actor, unreal.GaussianVolumeActor)
        and actor.get_actor_label() == LABEL
    ),
    None,
)
if preview is None:
    preview = actors.spawn_actor_from_class(
        unreal.GaussianVolumeActor,
        unreal.Vector(-80.0, 90.0, 350.0),
        unreal.Rotator(0.0, 180.0, 90.0),
    )
preview.set_actor_label(LABEL)
preview.set_actor_location(unreal.Vector(-80.0, 90.0, 350.0), False, False)
preview.set_actor_rotation(unreal.Rotator(0.0, 180.0, 90.0), False)
preview.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
preview.set_actor_hidden_in_game(False)

source = unreal.FilePath()
source.file_path = JSON_PATH
preview.set_editor_property("gaussian_json_file", source)
component = preview.get_editor_property("gaussian_volume_component")
component.set_editor_property("enable_screen_size_lod", False)
component.set_editor_property("support_tau_min", 0.0)
component.set_editor_property("density_multiplier", 1.0)
component.set_editor_property("density_gamma", 1.515627)
component.set_editor_property("directional_shadow_density_scale", 0.3)
lights = [actor for actor in level_actors if isinstance(actor, unreal.DirectionalLight)]
sky_lights = [actor for actor in level_actors if isinstance(actor, unreal.SkyLight)]
if lights:
    light = next(
        (actor for actor in lights if actor.get_actor_label() == "Light Source"),
        lights[0],
    )
    light.set_actor_location(unreal.Vector(0.0, 0.0, 200.0), False, False)
    light.set_actor_rotation(unreal.Rotator(*LIGHT_ROTATION), False)
    light.set_actor_scale3d(unreal.Vector(2.5, 2.5, 2.5))
    component.set_editor_property("directional_light_actor", light)
if sky_lights:
    component.set_editor_property(
        "sky_light_actor",
        next(
            (actor for actor in sky_lights if actor.get_actor_label() == "SkyLight"),
            sky_lights[0],
        ),
    )
component.set_editor_property("use_scene_lights", True)
component.set_editor_property("use_scene_depth", True)
component.set_editor_property("directional_light_intensity_scale", 0.2)
component.set_editor_property("sky_light_intensity_scale", 0.3)
if not preview.import_gaussian_json():
    raise RuntimeError(f"contracted {TARGET_COUNT} JSON import failed")
component.set_editor_property("enable_rendering", True)

for actor in level_actors:
    if isinstance(actor, unreal.GaussianVolumeActor) and actor != preview:
        actor.get_editor_property("gaussian_volume_component").set_editor_property(
            "enable_rendering", False
        )
if reference:
    reference_component = reference.get_editor_property("gs7d_component")
    reference_component.set_editor_property("opacity_multiplier", 0.0)
    reference_component.set_visibility(False, True)
svt_after = {
    actor.get_actor_label(): (
        actor.is_hidden_ed(),
        actor.get_editor_property("hidden"),
        actor.get_editor_property("root_component").is_visible(),
    )
    for actor in level_actors
    if isinstance(actor, unreal.HeterogeneousVolume)
}
if svt_after != svt_before:
    raise RuntimeError(f"SVT visibility changed: before={svt_before}, after={svt_after}")

unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
    unreal.Vector(38.3243586, 354.1205275, 593.3889062),
    unreal.Rotator(-16.1999015, 976.8000234, 0.0),
)
unreal.log(
    "CONTRACTED_PREVIEW_REPORT\n"
    + json.dumps(
        {
            "label": LABEL,
            "primitive_count": TARGET_COUNT,
            "saved": False,
            "reference_7drgs_hidden_for_preview": reference is not None,
            "svt_states_unchanged": svt_after,
        },
        indent=2,
    )
)
