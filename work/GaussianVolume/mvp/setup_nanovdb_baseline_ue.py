"""Create isolated, aligned NanoVDB Fp8/FpN baseline levels."""

import unreal


SOURCE_LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_EmptyBaseline"
TARGET_CENTER = unreal.Vector(-390.0, 0.0, 300.0)
TARGET_LONGEST_SIZE_CM = 1000.0
RESOLUTION = unreal.IntVector(191, 610, 178)
FRAME_TRANSLATION = unreal.Vector(-6.881570, -1.2, -7.939096)
FRAME_SCALE = unreal.Vector(0.1, 0.1, 0.1)
VARIANTS = (
    (
        "Fp8",
        r"D:\Work\AI\Iris\tmp\openvdb_samples\svt_baselines\smoke2_density_fp8.nvdb",
    ),
    (
        "FpN",
        r"D:\Work\AI\Iris\tmp\openvdb_samples\svt_baselines\smoke2_density_fpn_abs1e-3.nvdb",
    ),
)


assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
local_size = unreal.Vector(
    RESOLUTION.x * FRAME_SCALE.x,
    RESOLUTION.y * FRAME_SCALE.y,
    RESOLUTION.z * FRAME_SCALE.z,
)
uniform_scale = TARGET_LONGEST_SIZE_CM / max(local_size.x, local_size.y, local_size.z)
local_center = FRAME_TRANSLATION + local_size * 0.5

for suffix, filename in VARIANTS:
    level = f"/Game/GaussianVolume/Maps/L_GaussianVolume_NanoVDB_{suffix}"
    if not unreal.EditorAssetLibrary.does_asset_exist(level):
        if not assets.duplicate_asset(SOURCE_LEVEL, level):
            raise RuntimeError(f"failed to duplicate {level}")
    unreal.EditorLoadingAndSavingUtils.load_map(level)

    for actor in actors.get_all_level_actors():
        if isinstance(
            actor,
            (
                unreal.GaussianVolumeActor,
                unreal.HeterogeneousVolume,
                unreal.NanoVdbVolumeActor,
            ),
        ):
            actors.destroy_actor(actor)

    volume = actors.spawn_actor_from_class(
        unreal.NanoVdbVolumeActor, unreal.Vector(), unreal.Rotator()
    )
    component = volume.get_editor_property("nano_vdb_volume_component")
    source = unreal.FilePath()
    source.file_path = filename
    component.set_editor_property("nano_vdb_file", source)
    component.set_editor_property("density_scale", 10.0 / RESOLUTION.y)
    component.set_editor_property("step_size_voxels", 0.75)
    component.set_editor_property("max_steps", 1024)
    component.set_editor_property("use_scene_depth", True)
    component.set_editor_property("enable_rendering", True)
    if not component.reload_nano_vdb():
        raise RuntimeError(f"failed to load {filename}")

    volume.set_actor_scale3d(
        unreal.Vector(uniform_scale, uniform_scale, uniform_scale)
    )
    volume.set_actor_location(TARGET_CENTER - local_center * uniform_scale, False, False)
    volume.set_actor_label(f"Smoke2 NanoVDB {suffix} Baseline")

    if not unreal.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError(f"failed to save {level}")
    unreal.log(
        f"NANOVDB_BASELINE_READY level={level} actor={volume.get_actor_label()} "
        f"scale={uniform_scale:.6f} density_scale={10.0 / RESOLUTION.y:.8f}"
    )
