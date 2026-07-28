"""Add the existing smoke2 U8 SVT to the open TechLab for live A/B."""

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
LABEL = "Smoke2 UE SVT U8 Live A-B"
MATERIAL = "/Game/GaussianVolume/Baselines/MI_Smoke2_SVT_U8"
TARGET_CENTER = unreal.Vector(-390.0, 0.0, 300.0)
TARGET_LONGEST_SIZE_CM = 1000.0


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name().split(".")[0] != LEVEL:
    raise RuntimeError("Open L_GaussianVolume_TechLab before running this script")

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matches = [actor for actor in actors.get_all_level_actors() if actor.get_actor_label() == LABEL]
if len(matches) > 1:
    raise RuntimeError(f"Expected at most one {LABEL}, found {len(matches)}")

material = unreal.load_asset(MATERIAL)
if not material:
    raise RuntimeError(f"Missing material {MATERIAL}")
svt = unreal.MaterialEditingLibrary.get_material_instance_sparse_volume_texture_parameter_value(
    material, "SparseVolumeTexture"
)
if not svt:
    raise RuntimeError(f"{MATERIAL} has no SparseVolumeTexture")

volume = matches[0] if matches else actors.spawn_actor_from_class(
    unreal.HeterogeneousVolume, unreal.Vector(), unreal.Rotator()
)
volume.set_actor_label(LABEL)
component = volume.get_editor_property("root_component")
component.set_material(0, material)
resolution = svt.get_editor_property("volume_resolution")
component.set_editor_property("volume_resolution", resolution)
component.set_editor_property("frame", 0.0)
component.set_editor_property("playing", False)
component.set_editor_property("issue_blocking_requests", True)
component.set_editor_property("streaming_mip_bias", 0.0)

frame_transform = svt.get_frame_transform()
frame_scale = frame_transform.scale3d
voxel_extent = unreal.Vector(
    resolution.x * frame_scale.x,
    resolution.y * frame_scale.y,
    resolution.z * frame_scale.z,
)
uniform_scale = TARGET_LONGEST_SIZE_CM / max(voxel_extent.x, voxel_extent.y, voxel_extent.z)
volume.set_actor_scale3d(unreal.Vector(uniform_scale, uniform_scale, uniform_scale))
local_center = frame_transform.translation + voxel_extent * 0.5
volume.set_actor_location(TARGET_CENTER - local_center * uniform_scale, False, False)
volume.set_is_temporarily_hidden_in_editor(True)

if abs(max(voxel_extent.x, voxel_extent.y, voxel_extent.z) * uniform_scale - TARGET_LONGEST_SIZE_CM) > 1.0:
    raise RuntimeError("SVT alignment check failed")
unreal.log(
    f"SVT_LIVE_AB_READY actor='{LABEL}' scale={uniform_scale:.6f} "
    "state=editor-hidden map_not_saved=true"
)
