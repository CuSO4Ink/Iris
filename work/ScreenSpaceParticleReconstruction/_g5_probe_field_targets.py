import gc
import json
import math
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)


def fresh_stats():
    return {
        "min": 0.0,
        "max": 0.0,
        "sum": 0.0,
        "sumAbs": 0.0,
        "nonzero": 0,
        "negative": 0,
        "nonfinite": 0,
    }


def update(stats, values):
    finite = [value for value in values if math.isfinite(value)]
    stats["nonfinite"] += len(values) - len(finite)
    if finite:
        stats["min"] = min(stats["min"], min(finite))
        stats["max"] = max(stats["max"], max(finite))
        stats["sum"] += sum(finite)
        stats["sumAbs"] += sum(abs(value) for value in finite)
        stats["nonzero"] += sum(
            1 for value in finite if abs(value) > 1.0e-7
        )
        stats["negative"] += sum(
            1 for value in finite if value < -1.0e-7
        )


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Validation actor is not using the V2 system")
component.advance_simulation(120, 1.0 / 60.0)

quadrants = (
    (0, 0, 1024, 1024),
    (1024, 0, 1024, 1024),
    (0, 1024, 1024, 1024),
    (1024, 1024, 1024, 1024),
)
rows = []
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(target.get_editor_property("render_target_format"))
    except Exception:
        continue
    if width != 2048 or height != 2048 or "RGBA16F" not in fmt:
        continue

    channels = {
        "r": fresh_stats(),
        "g": fresh_stats(),
        "b": fresh_stats(),
        "a": fresh_stats(),
    }
    pixel_count = 0
    for x, y, read_width, read_height in quadrants:
        colors = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
            world, target, x, y, read_width, read_height, False
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
        channels["r"]["max"] > 1.0e-4
        and channels["r"]["nonzero"] > 0
        and channels["b"]["nonzero"] > 0
        and (
            channels["g"]["negative"] > 0
            or channels["b"]["negative"] > 0
        )
        and channels["a"]["max"] > 1.0e-5
        and channels["a"]["max"] <= 1.01
        and sum(
            channel["nonfinite"] for channel in channels.values()
        ) == 0
    )
    aux_signature = (
        channels["a"]["max"] > 0.5
        and channels["g"]["max"] > 1.0e-5
        and channels["g"]["min"] >= -1.0e-5
        and channels["g"]["max"] <= 1.01
        and channels["b"]["nonzero"] == 0
        and channels["r"]["max"] > 1.0e-6
        and channels["r"]["min"] >= -1.0e-5
        and sum(
            channel["nonfinite"] for channel in channels.values()
        ) == 0
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
    "targets": rows,
    "mainCandidateCount": len(main_candidates),
    "auxCandidateCount": len(aux_candidates),
    "mainCandidates": [
        row["path"] for row in main_candidates
    ],
    "auxCandidates": [
        row["path"] for row in aux_candidates
    ],
}
print("G5_FIELD_TARGETS=" + json.dumps(result, sort_keys=True))
if not result["active"] or not main_candidates or not aux_candidates:
    raise RuntimeError("G5 raw field target gate failed: " + repr(result))
