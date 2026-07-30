import gc
import json
import math
import unreal

MAIN_LABEL = "SSPR_ParticleTrails_Main"
CANDIDATE_LABEL = "SSPR_PerfSparseV2_Candidate"
CANDIDATE_SYSTEM = (
    "/Game/SSPR_Validation/Performance/DenseG5SparseV2/"
    "NS_SSPR_AnisotropicSplat_Main."
    "NS_SSPR_AnisotropicSplat_Main"
)
SPAWN_OUTPUT = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_perf_spawn_sparse_v2_candidate_out.json"
)
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


with open(SPAWN_OUTPUT, encoding="utf-8-sig") as handle:
    spawn_wrapper = json.load(handle)
spawn_line = spawn_wrapper["data"]["output"]
spawn_data = json.loads(spawn_line.split("=", 1)[1])
baseline_targets = set(spawn_data["baselineTargets"])

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
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
if len(main_matches) != 1 or len(candidate_matches) != 1:
    raise RuntimeError(
        "Expected one Dense baseline and one Sparse V2 candidate"
    )
old_actor = main_matches[0]
candidate_actor = candidate_matches[0]
old_component = old_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
candidate_component = candidate_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
candidate_asset = candidate_component.get_asset()
if (
    candidate_asset is None
    or candidate_asset.get_path_name() != CANDIDATE_SYSTEM
):
    raise RuntimeError("Sparse V2 candidate System binding changed")

candidate_component.advance_simulation(300, 1.0 / 60.0)

component_counts = {
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
        or outer.get_path_name()
        != candidate_component.get_path_name()
    ):
        continue
    class_name = data_interface.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        component_counts["raster"] += 1
    elif class_name == "NiagaraDataInterfaceRenderTarget2D":
        component_counts["renderTargets"] += 1
    elif class_name == "NiagaraDataInterfaceGrid2DCollection":
        component_counts["grid2D"] += 1

level_target_prefix = (
    world.get_path_name() + ":TextureRenderTarget2D_"
)
targets = []
for target in unreal.ObjectIterator(
    unreal.TextureRenderTarget2D
):
    path = target.get_path_name()
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(
            target.get_editor_property("render_target_format")
        )
    except Exception:
        continue
    if (
        path.startswith(level_target_prefix)
        and path not in baseline_targets
        and width == 2048
        and height == 2048
        and "RGBA16F" in fmt
    ):
        targets.append(target)

rows = []
for target in targets:
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
gate_passed = (
    candidate_component.is_active()
    and component_counts
    == {"raster": 1, "renderTargets": 2, "grid2D": 1}
    and len(targets) == 2
    and len(main_candidates) == 1
    and len(aux_candidates) == 1
)
if not gate_passed:
    candidate_component.deactivate()
    candidate_component.set_component_tick_enabled(False)
    actor_subsystem.destroy_actor(candidate_actor)
    old_component.set_component_tick_enabled(True)
    old_component.set_visibility(True, True)
    old_component.activate(True)
    level_subsystem.save_current_level()
    raise RuntimeError(
        "Separated Sparse V2 RT Gate failed; Dense restored: "
        + repr(
            {
                "newTargets": [
                    target.get_path_name() for target in targets
                ],
                "rows": rows,
                "componentCounts": component_counts,
            }
        )
    )

old_actor_path = old_actor.get_path_name()
old_component.deactivate()
old_component.set_component_tick_enabled(False)
if not actor_subsystem.destroy_actor(old_actor):
    raise RuntimeError("Failed to remove Dense baseline actor")
candidate_actor.set_actor_label(MAIN_LABEL)
saved = bool(level_subsystem.save_current_level())
if not saved:
    raise RuntimeError("Failed to save Sparse V2 candidate actor")

result = {
    "oldActor": old_actor_path,
    "newActor": candidate_actor.get_path_name(),
    "system": candidate_component.get_asset().get_path_name(),
    "active": bool(candidate_component.is_active()),
    "newTargetCount": len(targets),
    "componentCounts": component_counts,
    "main": main_candidates[0],
    "aux": aux_candidates[0],
    "saved": saved,
}
print(
    "PERF_FINALIZE_SPARSE_V2_CANDIDATE="
    + json.dumps(result, sort_keys=True)
)
