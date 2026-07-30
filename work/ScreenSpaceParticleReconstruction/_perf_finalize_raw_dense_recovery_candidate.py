import gc
import json
import math
import unreal


MAIN_LABEL = "SSPR_ParticleTrails_Main"
CANDIDATE_LABEL = "SSPR_RawDenseRecoveryCandidate"
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
        "Expected one blank actor and one recovery candidate"
    )
old_actor = main_matches[0]
candidate_actor = candidate_matches[0]
candidate_component = candidate_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
candidate_component.advance_simulation(300, 1.0 / 60.0)

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
if (
    not candidate_component.is_active()
    or not main_candidates
    or not aux_candidates
):
    raise RuntimeError(
        "Separated Dense recovery RT Gate failed: "
        + repr(rows)
    )

old_component = old_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
old_actor_path = old_actor.get_path_name()
old_component.deactivate()
old_component.set_component_tick_enabled(False)
if not actor_subsystem.destroy_actor(old_actor):
    raise RuntimeError("Failed to remove blank V2 actor")
candidate_actor.set_actor_label(MAIN_LABEL)
saved = bool(level_subsystem.save_current_level())
if not saved:
    raise RuntimeError("Failed to save Dense recovery actor")

result = {
    "oldActor": old_actor_path,
    "newActor": candidate_actor.get_path_name(),
    "system": candidate_component.get_asset().get_path_name(),
    "active": bool(candidate_component.is_active()),
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
    "PERF_FINALIZE_RAW_DENSE_RECOVERY_CANDIDATE="
    + json.dumps(result, sort_keys=True)
)
