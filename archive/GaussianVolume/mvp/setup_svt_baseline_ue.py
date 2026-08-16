"""Create isolated U8/F16 SVT copies of the Gaussian TechLab level."""

import unreal


SOURCE_LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
TARGET_CENTER = unreal.Vector(-390.0, 0.0, 300.0)
TARGET_LONGEST_SIZE_CM = 1000.0
VARIANTS = (
    ("U8", "/Game/GaussianVolume/Baselines/MI_Smoke2_SVT_U8"),
    ("F16", "/Game/GaussianVolume/Baselines/MI_Smoke2_SVT_F16"),
)


assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
empty_level = "/Game/GaussianVolume/Maps/L_GaussianVolume_EmptyBaseline"
if not unreal.EditorAssetLibrary.does_asset_exist(empty_level):
    if not assets.duplicate_asset(SOURCE_LEVEL, empty_level):
        raise RuntimeError(f"failed to duplicate {empty_level}")
unreal.EditorLoadingAndSavingUtils.load_map(empty_level)
for actor in actors.get_all_level_actors():
    if isinstance(actor, (unreal.GaussianVolumeActor, unreal.HeterogeneousVolume)):
        actors.destroy_actor(actor)
if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    raise RuntimeError(f"failed to save {empty_level}")
unreal.log(f"SVT_BASELINE_READY level={empty_level} actor=none")

for suffix, material_path in VARIANTS:
    level = f"/Game/GaussianVolume/Maps/L_GaussianVolume_SVT_{suffix}"
    if not unreal.EditorAssetLibrary.does_asset_exist(level):
        if not assets.duplicate_asset(SOURCE_LEVEL, level):
            raise RuntimeError(f"failed to duplicate {level}")
    unreal.EditorLoadingAndSavingUtils.load_map(level)

    for actor in actors.get_all_level_actors():
        if isinstance(actor, (unreal.GaussianVolumeActor, unreal.HeterogeneousVolume)):
            actors.destroy_actor(actor)

    material = unreal.load_asset(material_path)
    svt = unreal.MaterialEditingLibrary.get_material_instance_sparse_volume_texture_parameter_value(
        material, "SparseVolumeTexture"
    )
    volume = actors.spawn_actor_from_class(
        unreal.HeterogeneousVolume, unreal.Vector(), unreal.Rotator()
    )
    component = volume.get_editor_property("root_component")
    component.set_material(0, material)
    component.set_editor_property("volume_resolution", svt.get_editor_property("volume_resolution"))
    component.set_editor_property("frame", 0.0)
    component.set_editor_property("playing", False)
    component.set_editor_property("issue_blocking_requests", True)
    component.set_editor_property("streaming_mip_bias", 0.0)

    resolution = svt.get_editor_property("volume_resolution")
    frame_transform = svt.get_frame_transform()
    frame_scale = frame_transform.scale3d
    longest_voxel_extent = max(
        resolution.x * frame_scale.x,
        resolution.y * frame_scale.y,
        resolution.z * frame_scale.z,
    )
    uniform_scale = TARGET_LONGEST_SIZE_CM / longest_voxel_extent
    volume.set_actor_scale3d(unreal.Vector(uniform_scale, uniform_scale, uniform_scale))
    local_center = frame_transform.translation + unreal.Vector(
        resolution.x * frame_scale.x,
        resolution.y * frame_scale.y,
        resolution.z * frame_scale.z,
    ) * 0.5
    volume.set_actor_location(TARGET_CENTER - local_center * uniform_scale, False, False)
    volume.set_actor_label(f"Smoke2 UE SVT {suffix} Baseline")

    bounds_extent = unreal.Vector(
        resolution.x * frame_scale.x,
        resolution.y * frame_scale.y,
        resolution.z * frame_scale.z,
    ) * (uniform_scale * 0.5)
    if abs(max(bounds_extent.x, bounds_extent.y, bounds_extent.z) * 2.0 - TARGET_LONGEST_SIZE_CM) > 1.0:
        raise RuntimeError(f"unexpected {suffix} extent {bounds_extent}")
    if not unreal.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError(f"failed to save {level}")
    unreal.log(
        f"SVT_BASELINE_READY level={level} actor={volume.get_actor_label()} "
        f"scale={uniform_scale:.6f} extent={bounds_extent}"
    )
