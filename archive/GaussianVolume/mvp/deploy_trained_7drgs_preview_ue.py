"""Load the selected H4 pointwise-light preview without saving."""

import json

import unreal


LEVEL_NAME = "L_GaussianVolume_TechLab"
PLY_PATH = (
    "Plugins/GaussianSplattingForUnrealEngine/Content/Data/"
    "CGHEVEN_HeroCongestus50_7DRGS_PointwiseLight24_Degree2_1p112M.ply"
)
POINT_COUNT = 1_112_674
ACTOR_LABEL = "H12 | H4 PointwiseLight24 D2 1.112M"


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_name() != LEVEL_NAME:
    raise RuntimeError(f"Open {LEVEL_NAME} before deploying the trained preview")

actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor_class = unreal.GaussianSplatting7DActor
actors = [actor for actor in actor_system.get_all_level_actors() if isinstance(actor, actor_class)]
if len(actors) != 1:
    raise RuntimeError(f"Expected one 7DRGS actor in TechLab, found {len(actors)}")

actor = actors[0]
component = actor.get_editor_property("gs7d_component")
component.set_editor_property("use_synthetic_cloud_when_ply_missing", False)
if not component.load_from_file(PLY_PATH):
    raise RuntimeError(f"Failed to load {PLY_PATH}")
if component.get_point_count() != POINT_COUNT:
    raise RuntimeError(f"Loaded {component.get_point_count()} points, expected {POINT_COUNT}")

actor.set_actor_label(ACTOR_LABEL)
actor.set_actor_hidden_in_game(False)
component.set_visibility(True, True)
component.set_editor_property("dual_sh", True)
component.set_editor_property("t_view_sh_degree", 1)
component.set_editor_property("opacity_multiplier", 1.0)
component.set_editor_property("opacity_power", 1.35)
component.set_editor_property("phase_mode", 1)
component.set_editor_property("phase_g", 0.65)
component.set_editor_property("phase_g2", -0.2)
component.set_editor_property("phase_blend", 0.1)
component.set_editor_property("phase_intensity", 0.35)
component.refresh_rendering_parameters()

unreal.log(
    "TRAINED_7DRGS_PREVIEW_REPORT\n"
    + json.dumps(
        {
            "level": world.get_name(),
            "actor": actor.get_actor_label(),
            "points": component.get_point_count(),
            "ply": PLY_PATH,
            "saved": False,
        },
        indent=2,
    )
)
