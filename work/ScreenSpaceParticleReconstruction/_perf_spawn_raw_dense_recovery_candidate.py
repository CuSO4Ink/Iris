import json
import unreal


V2_LEVEL = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "L_SSPR_AnisotropicSplat_Validation"
)
RECOVERY_PATH = (
    "/Game/SSPR_Validation/Recovery/DenseG5_20260730"
)
RECOVERY_SYSTEM = (
    RECOVERY_PATH
    + "/NS_SSPR_AnisotropicSplat_Main."
    + "NS_SSPR_AnisotropicSplat_Main"
)
MAIN_LABEL = "SSPR_ParticleTrails_Main"
CANDIDATE_LABEL = "SSPR_RawDenseRecoveryCandidate"


asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_registry.scan_paths_synchronous(
    [RECOVERY_PATH], True, True
)
system = unreal.load_asset(RECOVERY_SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Raw Dense recovery System did not load")

level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
current_world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
if not current_world.get_path_name().startswith(V2_LEVEL + "."):
    if not level_subsystem.load_level(V2_LEVEL):
        raise RuntimeError("Failed to load V2 validation level")

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
        "Unexpected recovery actor state: "
        + repr(
            {
                "main": len(main_matches),
                "candidate": len(candidate_matches),
            }
        )
    )
old_actor = main_matches[0]
old_transform = old_actor.get_actor_transform()

candidate_actor = actor_subsystem.spawn_actor_from_class(
    unreal.NiagaraActor,
    old_transform.translation,
)
if not isinstance(candidate_actor, unreal.NiagaraActor):
    raise RuntimeError("Failed to spawn Dense recovery candidate")
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

if raster_count != 1 or render_target_count != 2:
    actor_subsystem.destroy_actor(candidate_actor)
    raise RuntimeError(
        "Dense recovery candidate has unexpected DIs: "
        + repr(
            {
                "raster": raster_count,
                "renderTargets": render_target_count,
            }
        )
    )

component.reinitialize_system()
component.activate(True)
result = {
    "candidateActor": candidate_actor.get_path_name(),
    "candidateComponent": component.get_path_name(),
    "system": component.get_asset().get_path_name(),
    "active": bool(component.is_active()),
    "rasterCount": raster_count,
    "renderTargetCount": render_target_count,
}
print(
    "PERF_SPAWN_RAW_DENSE_RECOVERY_CANDIDATE="
    + json.dumps(result, sort_keys=True)
)
