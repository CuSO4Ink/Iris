import json
import unreal

V2_LEVEL = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "L_SSPR_AnisotropicSplat_Validation"
)
CANDIDATE_PATH = (
    "/Game/SSPR_Validation/Performance/DenseG5SparseV2"
)
CANDIDATE_SYSTEM = (
    CANDIDATE_PATH
    + "/NS_SSPR_AnisotropicSplat_Main."
    + "NS_SSPR_AnisotropicSplat_Main"
)
RECOVERY_SYSTEM = (
    "/Game/SSPR_Validation/Recovery/DenseG5_20260730/"
    "NS_SSPR_AnisotropicSplat_Main."
    "NS_SSPR_AnisotropicSplat_Main"
)
MAIN_LABEL = "SSPR_ParticleTrails_Main"
CANDIDATE_LABEL = "SSPR_PerfSparseV2_Candidate"


asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_registry.scan_paths_synchronous(
    [CANDIDATE_PATH], True, False
)
system = unreal.load_asset(CANDIDATE_SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Sparse V2 candidate System did not load")

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
if not world.get_path_name().startswith(V2_LEVEL + "."):
    raise RuntimeError("V2 validation level is not active")

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
actors = actor_subsystem.get_all_level_actors()
main_matches = [
    actor
    for actor in actors
    if actor.get_actor_label() == MAIN_LABEL
]
candidate_matches = [
    actor
    for actor in actors
    if actor.get_actor_label() == CANDIDATE_LABEL
]
if len(main_matches) != 1 or candidate_matches:
    raise RuntimeError(
        "Unexpected Sparse V2 actor state: "
        + repr(
            {
                "main": len(main_matches),
                "candidate": len(candidate_matches),
            }
        )
    )
old_actor = main_matches[0]
old_component = old_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
old_asset = old_component.get_asset()
if old_asset is None or old_asset.get_path_name() not in (
    RECOVERY_SYSTEM,
    CANDIDATE_SYSTEM,
):
    raise RuntimeError(
        "Current visual baseline is neither Dense nor Sparse V2"
    )

level_target_prefix = (
    world.get_path_name() + ":TextureRenderTarget2D_"
)
baseline_targets = sorted(
    target.get_path_name()
    for target in unreal.ObjectIterator(
        unreal.TextureRenderTarget2D
    )
    if target.get_path_name().startswith(level_target_prefix)
)

old_transform = old_actor.get_actor_transform()
candidate_actor = actor_subsystem.spawn_actor_from_class(
    unreal.NiagaraActor,
    old_transform.translation,
)
if not isinstance(candidate_actor, unreal.NiagaraActor):
    raise RuntimeError("Failed to spawn Sparse V2 candidate")
candidate_actor.set_actor_label(CANDIDATE_LABEL)
candidate_actor.set_actor_transform(old_transform, False, False)
component = candidate_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
component.set_asset(system)
component.set_auto_activate(True)
component.set_visibility(True, True)
component.set_component_tick_enabled(True)
component.set_force_solo(True)

raster_count = 0
render_target_count = 0
grid2d_count = 0
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterface
):
    if not data_interface.get_path_name().startswith(
        component.get_path_name() + "."
    ):
        continue
    class_name = data_interface.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        raster_count += 1
        data_interface.set_editor_property(
            "num_cells", unreal.IntVector(2048, 2048, 1)
        )
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
        try:
            data_interface.set_editor_property(
                "precision", 65535.0
            )
        except Exception:
            pass
    elif class_name == "NiagaraDataInterfaceRenderTarget2D":
        render_target_count += 1
        data_interface.set_editor_property(
            "size", unreal.IntPoint(2048, 2048)
        )
        data_interface.set_editor_property(
            "inherit_user_parameter_settings", False
        )
        data_interface.set_editor_property("override_format", True)
        data_interface.set_editor_property(
            "override_render_target_format",
            unreal.TextureRenderTargetFormat.RTF_RGBA16F,
        )
        data_interface.set_editor_property(
            "override_render_target_filter",
            unreal.TextureFilter.TF_BILINEAR,
        )
        data_interface.set_editor_property(
            "mip_map_generation",
            unreal.NiagaraMipMapGeneration.DISABLED,
        )
    elif class_name == "NiagaraDataInterfaceGrid2DCollection":
        grid2d_count += 1

if (
    raster_count != 1
    or render_target_count != 2
    or grid2d_count != 1
):
    actor_subsystem.destroy_actor(candidate_actor)
    raise RuntimeError(
        "Sparse V2 candidate has unexpected DIs: "
        + repr(
            {
                "raster": raster_count,
                "renderTargets": render_target_count,
                "grid2D": grid2d_count,
            }
        )
    )

component.activate(True)
if not component.is_active():
    actor_subsystem.destroy_actor(candidate_actor)
    raise RuntimeError("Sparse V2 candidate failed to activate")

post_counts = {
    "raster": 0,
    "renderTargets": 0,
    "grid2D": 0,
}
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterface
):
    outer = data_interface.get_outer()
    if (
        outer is None
        or outer.get_path_name() != component.get_path_name()
    ):
        continue
    class_name = data_interface.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        post_counts["raster"] += 1
    elif class_name == "NiagaraDataInterfaceRenderTarget2D":
        post_counts["renderTargets"] += 1
    elif class_name == "NiagaraDataInterfaceGrid2DCollection":
        post_counts["grid2D"] += 1
if post_counts != {
    "raster": 1,
    "renderTargets": 2,
    "grid2D": 1,
}:
    component.deactivate()
    actor_subsystem.destroy_actor(candidate_actor)
    old_component.set_component_tick_enabled(True)
    old_component.activate(True)
    raise RuntimeError(
        "Sparse V2 activation duplicated DIs: "
        + repr(post_counts)
    )

old_component.deactivate()
old_component.set_component_tick_enabled(False)
result = {
    "oldActor": old_actor.get_path_name(),
    "oldSystem": old_asset.get_path_name(),
    "candidateActor": candidate_actor.get_path_name(),
    "candidateComponent": component.get_path_name(),
    "candidateSystem": component.get_asset().get_path_name(),
    "active": bool(component.is_active()),
    "rasterCount": raster_count,
    "renderTargetCount": render_target_count,
    "grid2DCount": grid2d_count,
    "postActivateCounts": post_counts,
    "baselineTargets": baseline_targets,
}
print(
    "PERF_SPAWN_SPARSE_V2_CANDIDATE="
    + json.dumps(result, sort_keys=True)
)
