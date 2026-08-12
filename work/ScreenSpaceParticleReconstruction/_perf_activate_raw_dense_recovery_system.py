import gc
import json
import math
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
PROBE_LABEL = "SSPR_RawDenseRecoveryProbe"
SAMPLE_RECTS = (
    (512, 512, 512, 512),
    (256, 768, 256, 256),
    (1280, 768, 256, 256),
)


def fresh_stats():
    return {
        "min": 0.0,
        "max": 0.0,
        "nonzero": 0,
        "negative": 0,
        "nonfinite": 0,
    }


def update(stats, values):
    finite = [value for value in values if math.isfinite(value)]
    stats["nonfinite"] += len(values) - len(finite)
    if not finite:
        return
    stats["min"] = min(stats["min"], min(finite))
    stats["max"] = max(stats["max"], max(finite))
    stats["nonzero"] += sum(
        1 for value in finite if abs(value) > 1.0e-7
    )
    stats["negative"] += sum(
        1 for value in finite if value < -1.0e-7
    )


def matching_targets():
    result = {}
    for target in unreal.ObjectIterator(
        unreal.TextureRenderTarget2D
    ):
        try:
            width = int(target.get_editor_property("size_x"))
            height = int(target.get_editor_property("size_y"))
            fmt = str(
                target.get_editor_property("render_target_format")
            )
        except Exception:
            continue
        if (
            width == 2048
            and height == 2048
            and "RGBA16F" in fmt
        ):
            result[target.get_path_name()] = target
    return result


asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_registry.scan_paths_synchronous(
    [RECOVERY_PATH], True, True
)
system = unreal.load_asset(RECOVERY_SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError(
        "Raw Dense recovery System did not load: "
        + RECOVERY_SYSTEM
    )

level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
if not level_subsystem.load_level(V2_LEVEL):
    raise RuntimeError("Failed to reload V2 validation level")
actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
matches = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label() == MAIN_LABEL
]
if len(matches) != 1:
    raise RuntimeError(
        "Expected one blank V2 main actor, got "
        + str(len(matches))
    )
old_actor = matches[0]
old_component = old_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
old_actor_path = old_actor.get_path_name()
old_transform = old_actor.get_actor_transform()
probe_actor = actor_subsystem.spawn_actor_from_class(
    unreal.NiagaraActor,
    old_transform.translation,
)
if not isinstance(probe_actor, unreal.NiagaraActor):
    raise RuntimeError("Failed to spawn raw Dense recovery actor")
probe_actor.set_actor_label(PROBE_LABEL)
probe_actor.set_actor_transform(old_transform, False, False)
probe_component = probe_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
probe_component.set_asset(system)
probe_component.set_auto_activate(True)
probe_component.set_visibility(True, True)
probe_component.set_component_tick_enabled(True)
probe_component.set_force_solo(True)

raster_count = 0
render_target_count = 0
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterface
):
    if not data_interface.get_path_name().startswith(
        probe_component.get_path_name() + "."
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
    actor_subsystem.destroy_actor(probe_actor)
    raise RuntimeError(
        "Raw Dense recovery did not instantiate strict DIs: "
        + repr(
            {
                "raster": raster_count,
                "renderTargets": render_target_count,
            }
        )
    )

probe_component.reinitialize_system()
probe_component.activate(True)
probe_component.advance_simulation(300, 1.0 / 60.0)

after_targets = matching_targets()
level_target_prefix = (
    world.get_path_name() + ":TextureRenderTarget2D_"
)
new_targets = [
    target
    for path, target in after_targets.items()
    if path.startswith(level_target_prefix)
]
rows = []
for target in new_targets:
    channels = {
        name: fresh_stats() for name in ("r", "g", "b", "a")
    }
    pixel_count = 0
    for x, y, width, height in SAMPLE_RECTS:
        colors = (
            unreal.RenderingLibrary
            .read_render_target_raw_pixel_area(
                world,
                target,
                x,
                y,
                width,
                height,
                False,
            )
        )
        pixel_count += len(colors)
        for name in ("r", "g", "b", "a"):
            values = [
                float(getattr(color, name))
                for color in colors
            ]
            update(channels[name], values)
            del values
        del colors
        gc.collect()
    main_signature = (
        channels["r"]["nonzero"] > 0
        and channels["a"]["nonzero"] > 0
        and (
            channels["g"]["negative"] > 0
            or channels["b"]["negative"] > 0
        )
        and sum(
            item["nonfinite"] for item in channels.values()
        )
        == 0
    )
    aux_signature = (
        channels["r"]["nonzero"] > 0
        and channels["g"]["nonzero"] > 0
        and channels["a"]["max"] > 0.5
        and channels["b"]["nonzero"] == 0
        and sum(
            item["nonfinite"] for item in channels.values()
        )
        == 0
    )
    rows.append(
        {
            "path": target.get_path_name(),
            "pixelCount": pixel_count,
            "channels": channels,
            "mainSignature": main_signature,
            "auxSignature": aux_signature,
        }
    )

main_candidates = [
    row for row in rows if row["mainSignature"]
]
aux_candidates = [
    row for row in rows if row["auxSignature"]
]
if (
    not probe_component.is_active()
    or not main_candidates
    or not aux_candidates
):
    actor_subsystem.destroy_actor(probe_actor)
    raise RuntimeError(
        "Raw Dense recovery RT Gate failed: "
        + repr(
            {
                "newTargetCount": len(new_targets),
                "rows": rows,
            }
        )
    )

old_component.deactivate()
old_component.set_component_tick_enabled(False)
if not actor_subsystem.destroy_actor(old_actor):
    actor_subsystem.destroy_actor(probe_actor)
    raise RuntimeError("Failed to remove blank V2 actor")
probe_actor.set_actor_label(MAIN_LABEL)
saved = bool(level_subsystem.save_current_level())
if not saved:
    raise RuntimeError("Failed to save recovered V2 level")

result = {
    "oldActor": old_actor_path,
    "newActor": probe_actor.get_path_name(),
    "recoverySystem": probe_component.get_asset().get_path_name(),
    "active": bool(probe_component.is_active()),
    "rasterCount": raster_count,
    "renderTargetCount": render_target_count,
    "mainCandidates": [
        row["path"] for row in main_candidates
    ],
    "auxCandidates": [
        row["path"] for row in aux_candidates
    ],
    "rows": rows,
    "saved": saved,
}
print(
    "PERF_ACTIVATE_RAW_DENSE_RECOVERY_SYSTEM="
    + json.dumps(result, sort_keys=True)
)
