import gc
import json
import math
import unreal


V2_LEVEL = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "L_SSPR_AnisotropicSplat_Validation"
)
V3_LEVEL = (
    "/Game/SSPR_Validation/Versions/"
    "V3_AnisotropicSplat_20260730/"
    "L_SSPR_AnisotropicSplat_V3_Validation"
)
V3_SYSTEM = (
    "/Game/SSPR_Validation/Versions/"
    "V3_AnisotropicSplat_20260730/"
    "NS_SSPR_AnisotropicSplat_V3."
    "NS_SSPR_AnisotropicSplat_V3"
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


level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
try:
    if not level_subsystem.load_level(V3_LEVEL):
        raise RuntimeError("Failed to load V3 frozen level")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    matches = [
        actor
        for actor in actors
        if actor.get_actor_label() == LABEL
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "V3 level does not contain exactly one main actor"
        )
    component = matches[0].get_components_by_class(
        unreal.NiagaraComponent
    )[0]
    if component.get_asset().get_path_name() != V3_SYSTEM:
        raise RuntimeError("V3 level actor is not using V3 System")

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
        elif class_name == "NiagaraDataInterfaceRenderTarget2D":
            render_target_count += 1

    component.reinitialize_system()
    component.activate(True)
    component.set_force_solo(True)
    component.advance_simulation(300, 1.0 / 60.0)

    level_target_prefix = V3_LEVEL + "." + V3_LEVEL.rsplit(
        "/", 1
    )[-1] + ":TextureRenderTarget2D_"
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
                item["nonfinite"]
                for item in channels.values()
            )
            == 0
        )
        aux_signature = (
            channels["r"]["nonzero"] > 0
            and channels["g"]["nonzero"] > 0
            and channels["a"]["max"] > 0.5
            and channels["b"]["nonzero"] == 0
            and sum(
                item["nonfinite"]
                for item in channels.values()
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
        not component.is_active()
        or not main_candidates
        or not aux_candidates
    ):
        raise RuntimeError(
            "V3 frozen level raw Gate failed: "
            + repr(
                {
                    "rasterCount": raster_count,
                    "renderTargetCount": render_target_count,
                    "rows": rows,
                }
            )
        )

    result = {
        "level": world.get_path_name(),
        "system": component.get_asset().get_path_name(),
        "active": bool(component.is_active()),
        "rasterCount": raster_count,
        "renderTargetCount": render_target_count,
        "mainCandidates": [
            row["path"] for row in main_candidates
        ],
        "auxCandidates": [
            row["path"] for row in aux_candidates
        ],
        "rows": rows,
    }
    print(
        "PERF_LOAD_V3_RECOVERY_LEVEL="
        + json.dumps(result, sort_keys=True)
    )
except Exception:
    level_subsystem.load_level(V2_LEVEL)
    raise
