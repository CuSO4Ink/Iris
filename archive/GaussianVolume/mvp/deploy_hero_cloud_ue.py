"""Deploy CGHEVEN Hero Congestus 50 as a visible 7DRGS/SVT A/B."""

import json

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
DESTINATION = "/Game/GaussianVolume/Baselines"
VDB_SOURCE = (
    r"D:\Work\AI\Iris\tmp\cgheven_hero50"
    r"\Hero_Cloud_02_v50_density_only.vdb"
)
SVT_PATH = f"{DESTINATION}/SVT_CGHEVEN_HeroCongestus50_U8"
MATERIAL_PATH = f"{DESTINATION}/MI_CGHEVEN_HeroCongestus50_SVT_U8"
PLY_PATH = (
    "Plugins/GaussianSplattingForUnrealEngine/Content/Data/"
    "CGHEVEN_HeroCongestus50_B2_Ultra_6Light_7DRGS.ply"
)
POINT_COUNT = 6_676_044
TARGET_CENTER = unreal.Vector(-390.0, 0.0, 300.0)
TARGET_LONGEST_SIZE_CM = 1000.0
RELIGHT_INTENSITY_SCALE = 0.06892181
RELIGHT_COLOR_TINT = unreal.LinearColor(1.0655021, 1.0150508, 0.9194471, 1.0)
AMBIENT_LIGHT_INTENSITY_SCALE = 0.0866097


def import_svt():
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", VDB_SOURCE)
    task.set_editor_property("destination_path", DESTINATION)
    task.set_editor_property("destination_name", SVT_PATH.rsplit("/", 1)[1])
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", True)
    task.set_editor_property("factory", unreal.SparseVolumeTextureFactory())
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    svt = unreal.load_asset(SVT_PATH)
    if not svt or svt.get_class().get_name() != "StaticSparseVolumeTexture":
        raise RuntimeError(f"failed to import {VDB_SOURCE}")
    return svt


def make_material(svt):
    material = unreal.load_asset(MATERIAL_PATH)
    if not material:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_PATH.rsplit("/", 1)[1],
            DESTINATION,
            unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew(),
        )
    material.set_editor_property(
        "parent", unreal.load_asset("/Engine/EngineMaterials/SparseVolumeMaterial")
    )
    unreal.MaterialEditingLibrary.set_material_instance_sparse_volume_texture_parameter_value(
        material, "SparseVolumeTexture", svt
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        material, "Density Scale", 0.04
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        material, "Albedo Scale", 1.0
    )
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        material, "Albedo", unreal.LinearColor(1.0, 1.0, 1.0, 1.0)
    )
    unreal.MaterialEditingLibrary.update_material_instance(material)
    if (
        unreal.MaterialEditingLibrary.get_material_instance_sparse_volume_texture_parameter_value(
            material, "SparseVolumeTexture"
        )
        != svt
    ):
        raise RuntimeError("SVT material readback mismatch")
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    return material


def align_svt_actor(actor, svt, material):
    component = actor.get_editor_property("root_component")
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
    uniform_scale = TARGET_LONGEST_SIZE_CM / max(
        voxel_extent.x, voxel_extent.y, voxel_extent.z
    )
    actor.set_actor_scale3d(unreal.Vector(uniform_scale, uniform_scale, uniform_scale))
    local_center = frame_transform.translation + voxel_extent * 0.5
    actor.set_actor_location(TARGET_CENTER - local_center * uniform_scale, False, False)
    actor.set_actor_hidden_in_game(False)
    component.set_visibility(True, True)
    return uniform_scale


def main():
    unreal.EditorAssetLibrary.make_directory(DESTINATION)
    svt = import_svt()
    material = make_material(svt)
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
    actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    level_actors = actor_system.get_all_level_actors()

    for actor in level_actors:
        if isinstance(actor, (unreal.GaussianVolumeActor, unreal.HeterogeneousVolume)):
            actor.set_actor_hidden_in_game(True)
            actor.get_editor_property("root_component").set_visibility(False, True)

    svt_label = "CGHEVEN Hero Congestus 50 UE SVT U8 A-B"
    svt_matches = [a for a in level_actors if a.get_actor_label() == svt_label]
    svt_actor = svt_matches[0] if svt_matches else actor_system.spawn_actor_from_class(
        unreal.HeterogeneousVolume, unreal.Vector(), unreal.Rotator()
    )
    svt_actor.set_actor_label(svt_label)
    svt_scale = align_svt_actor(svt_actor, svt, material)

    actor_class = getattr(unreal, "GaussianSplatting7DActor")
    gs_matches = [a for a in level_actors if isinstance(a, actor_class)]
    gs_actor = gs_matches[0] if gs_matches else actor_system.spawn_actor_from_class(
        actor_class, TARGET_CENTER, unreal.Rotator()
    )
    gs_actor.set_actor_label("7DRGS CGHEVEN Hero Congestus 50 B2 Ultra 6.68M")
    gs_actor.set_actor_location(TARGET_CENTER, False, False)
    gs_actor.set_actor_rotation(unreal.Rotator(), False)
    gs_actor.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    component = gs_actor.get_editor_property("gs7d_component")
    component.set_editor_property("use_synthetic_cloud_when_ply_missing", False)
    if component.get_point_count() != POINT_COUNT and not component.load_from_file(PLY_PATH):
        raise RuntimeError(f"failed to load {PLY_PATH}")
    if component.get_point_count() != POINT_COUNT:
        raise RuntimeError(
            f"7DRGS point count {component.get_point_count()} != {POINT_COUNT}"
        )

    lights = [a for a in level_actors if isinstance(a, unreal.DirectionalLight)]
    if not lights:
        raise RuntimeError("TechLab has no DirectionalLight for relighting")
    light = lights[0]
    light_component = light.get_editor_property("light_component")
    light_intensity = max(float(light_component.get_editor_property("intensity")), 1e-6)
    sky_lights = [a for a in level_actors if isinstance(a, unreal.SkyLight)]
    if not sky_lights:
        raise RuntimeError("TechLab has no SkyLight for ambient relighting")
    sky_light = sky_lights[0]
    component.set_editor_property("directional_light", light)
    component.set_editor_property("use_manual_light_direction", False)
    component.set_editor_property("relight_intensity_scale", RELIGHT_INTENSITY_SCALE)
    component.set_editor_property("relight_color_tint", RELIGHT_COLOR_TINT)
    component.set_editor_property("sky_light", sky_light)
    component.set_editor_property(
        "ambient_light_intensity_scale", AMBIENT_LIGHT_INTENSITY_SCALE
    )
    component.set_editor_property("dual_sh", True)
    component.set_editor_property("opacity_multiplier", 1.0)
    component.set_editor_property("opacity_power", 1.0)
    component.set_editor_property("phase_mode", 0)
    component.set_editor_property("phase_g", 0.65)
    component.set_editor_property("phase_g2", -0.2)
    component.set_editor_property("phase_blend", 0.1)
    component.set_editor_property("phase_intensity", 0.0)
    component.refresh_rendering_parameters()

    unreal.SystemLibrary.execute_console_command(
        unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),
        "r.GaussianSplatting.Enable 1",
    )
    if not unreal.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError(f"failed to save {LEVEL}")
    unreal.log(
        "HERO_CLOUD_7DRGS_DEPLOY_REPORT\n"
        + json.dumps(
            {
                "level": LEVEL,
                "7drgs_actor": gs_actor.get_actor_label(),
                "points": component.get_point_count(),
                "light": light.get_actor_label(),
                "light_intensity": light_intensity,
                "relight_scale": RELIGHT_INTENSITY_SCALE,
                "relight_tint": str(RELIGHT_COLOR_TINT),
                "direct_energy": light_intensity * RELIGHT_INTENSITY_SCALE,
                "sky_light": sky_light.get_actor_label(),
                "ambient_scale": AMBIENT_LIGHT_INTENSITY_SCALE,
                "svt_actor": svt_actor.get_actor_label(),
                "svt_scale": svt_scale,
                "svt_resolution": str(svt.get_editor_property("volume_resolution")),
                "svt_visible": True,
            },
            indent=2,
        )
    )


main()
