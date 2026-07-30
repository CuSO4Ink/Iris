import json
import math
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
LABEL = "SSPR_ParticleTrails_Main"
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


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == LABEL
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Active actor is not using the V2 System")
component.advance_simulation(60, 1.0 / 60.0)

rows = []
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(
            target.get_editor_property("render_target_format")
        )
    except Exception:
        continue
    if width != 2048 or height != 2048 or "RGBA16F" not in fmt:
        continue

    channels = {
        name: fresh_stats() for name in ("r", "g", "b", "a")
    }
    pixel_count = 0
    for x, y, read_width, read_height in SAMPLE_RECTS:
        colors = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
            world,
            target,
            x,
            y,
            read_width,
            read_height,
            False,
        )
        pixel_count += len(colors)
        for color in colors:
            for name in ("r", "g", "b", "a"):
                value = float(getattr(color, name))
                stats = channels[name]
                if not math.isfinite(value):
                    stats["nonfinite"] += 1
                    continue
                stats["min"] = min(stats["min"], value)
                stats["max"] = max(stats["max"], value)
                stats["nonzero"] += int(abs(value) > 1.0e-7)
                stats["negative"] += int(value < -1.0e-7)

    main_signature = (
        channels["r"]["max"] > 1.0e-4
        and channels["r"]["nonzero"] > 100
        and channels["r"]["nonzero"] < pixel_count
        and channels["g"]["nonzero"] > 100
        and channels["b"]["nonzero"] > 100
        and (
            channels["g"]["negative"] > 0
            or channels["b"]["negative"] > 0
        )
        and sum(
            value["nonfinite"] for value in channels.values()
        )
        == 0
    )
    aux_signature = (
        channels["a"]["max"] > 0.5
        and channels["a"]["nonzero"] > 100
        and channels["a"]["nonzero"] < pixel_count
        and channels["g"]["max"] > 1.0e-5
        and channels["g"]["max"] <= 1.01
        and channels["b"]["nonzero"] == 0
        and channels["r"]["max"] > 1.0e-6
        and channels["r"]["min"] >= -1.0e-5
        and sum(
            value["nonfinite"] for value in channels.values()
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
result = {
    "active": bool(component.is_active()),
    "sampleRects": SAMPLE_RECTS,
    "rows": rows,
    "mainCandidates": [
        row["path"] for row in main_candidates
    ],
    "auxCandidates": [
        row["path"] for row in aux_candidates
    ],
}
print(
    "PERF_FAST_ACTIVE_RAW_GATE="
    + json.dumps(result, sort_keys=True)
)
if (
    not result["active"]
    or not main_candidates
    or not aux_candidates
):
    raise RuntimeError(
        "Fast active raw gate failed: " + repr(result)
    )
