"""Load the Sigma8 de-grid candidate beside the untouched G2 asset without saving."""

import json

import unreal


PLY = (
    r"D:\Work\AI\Iris\work\GaussianVolume\artifacts\wdas_sigma_points_8\beta050"
    r"\ue_candidate\WDAS_Cloud_Half_Sigma8_Beta050_CompactTransportGS_3236K.ply"
)
POINTS = 3_236_192
LABEL = "TEMP | Sigma8 B050 Degrid / 3.236M"


actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_actors = actors.get_all_level_actors()
reference = next(
    (
        actor
        for actor in level_actors
        if isinstance(actor, unreal.GaussianSplatting7DActor)
        and actor.get_editor_property("gs7d_component").get_point_count() == 404_524
    ),
    None,
)
if reference is None:
    raise RuntimeError("exact G2 reference actor was not found")
for actor in level_actors:
    if isinstance(actor, unreal.GaussianSplatting7DActor) and actor.get_actor_label() == LABEL:
        actors.destroy_actor(actor)

reference_component = reference.get_editor_property("gs7d_component")
preview = actors.spawn_actor_from_class(
    unreal.GaussianSplatting7DActor,
    reference.get_actor_location(),
    reference.get_actor_rotation(),
)
if preview is None:
    raise RuntimeError("failed to spawn Sigma8 preview actor")
preview.set_actor_label(LABEL)
preview.set_actor_scale3d(reference.get_actor_scale3d())
preview_component = preview.get_editor_property("gs7d_component")
preview_component.set_visibility(False, True)

try:
    preview_component.set_editor_property("use_synthetic_cloud_when_ply_missing", False)
    if not preview_component.load_from_file(PLY):
        raise RuntimeError(f"failed to load {PLY}")
    if preview_component.get_point_count() != POINTS:
        raise RuntimeError(
            f"loaded {preview_component.get_point_count()} points, expected {POINTS}"
        )
    for name in (
        "dual_sh",
        "t_view_sh_degree",
        "opacity_multiplier",
        "opacity_power",
        "relight_intensity_scale",
        "relight_color_tint",
        "ambient_light_intensity_scale",
        "deep_shadow_density_scale",
        "phase_mode",
        "phase_g",
        "phase_g2",
        "phase_blend",
        "phase_intensity",
    ):
        preview_component.set_editor_property(
            name, reference_component.get_editor_property(name)
        )
    preview_component.refresh_rendering_parameters()
    reference_component.set_visibility(False, True)
    preview_component.set_visibility(True, True)
except Exception:
    reference_component.set_visibility(True, True)
    actors.destroy_actor(preview)
    raise

unreal.log(
    "SIGMA8_PREVIEW_REPORT\n"
    + json.dumps(
        {
            "label": LABEL,
            "points": preview_component.get_point_count(),
            "reference_points": reference_component.get_point_count(),
            "opacity_multiplier": preview_component.get_editor_property(
                "opacity_multiplier"
            ),
            "opacity_power": preview_component.get_editor_property("opacity_power"),
            "saved": False,
        },
        indent=2,
    )
)
