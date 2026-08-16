"""Promote the compact WDAS transport asset in TechLab without touching A/B visibility."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
PLY = (
    "Plugins/GaussianSplattingForUnrealEngine/Content/Data/"
    "WDAS_Cloud_Half_B8_Sigma038_Aniso115_CompactTransportGS_404K.ply"
)
POINTS = 404_524
LABEL = "Compact Transport GS + DGSM | WDAS G2 Sigma038 Aniso115 / 404K"


unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
actors = [
    actor
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if isinstance(actor, unreal.GaussianSplatting7DActor)
]
if not actors:
    raise RuntimeError("TechLab has no GaussianSplatting7DActor")

actor = next(
    (
        candidate
        for candidate in actors
        if candidate.get_editor_property("gs7d_component").get_point_count()
        in (2_427_144, POINTS)
    ),
    actors[0],
)
component = actor.get_editor_property("gs7d_component")
old_count = component.get_point_count()
component.set_editor_property("use_synthetic_cloud_when_ply_missing", False)
if not component.load_from_file(PLY):
    raise RuntimeError(f"Failed to load {PLY}")
if component.get_point_count() != POINTS:
    raise RuntimeError(f"Loaded {component.get_point_count()} points, expected {POINTS}")

actor.set_actor_label(LABEL)
component.set_editor_property("dual_sh", True)
component.refresh_rendering_parameters()
if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    raise RuntimeError(f"Failed to save {LEVEL}")

unreal.log(
    "COMPACT_TRANSPORT_DEPLOY\n"
    + json.dumps(
        {
            "actor": actor.get_actor_label(),
            "old_records": old_count,
            "compact_records": component.get_point_count(),
            "ply": PLY,
            "saved": True,
        },
        indent=2,
    )
)
