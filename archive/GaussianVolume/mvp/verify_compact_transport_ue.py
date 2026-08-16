"""Load the compact WDAS transport asset in TechLab without saving the level."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
PLY = (
    "Plugins/GaussianSplattingForUnrealEngine/Content/Data/"
    "WDAS_Cloud_Quarter_B4_HQ_CompactTransportGS.ply"
)
POINTS = 404_524


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
        if candidate.get_editor_property("gs7d_component").get_point_count() == 2_427_144
    ),
    actors[0],
)
component = actor.get_editor_property("gs7d_component")
old_count = component.get_point_count()
if not component.load_from_file(PLY):
    raise RuntimeError(f"Failed to load {PLY}")
if component.get_point_count() != POINTS:
    raise RuntimeError(f"Loaded {component.get_point_count()} points, expected {POINTS}")
component.refresh_rendering_parameters()

unreal.log(
    "COMPACT_TRANSPORT_VERIFY\n"
    + json.dumps(
        {
            "actor": actor.get_actor_label(),
            "old_records": old_count,
            "compact_records": component.get_point_count(),
            "ply": PLY,
            "saved": False,
        },
        indent=2,
    )
)
