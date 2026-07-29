import json
import unreal


MATERIAL_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "MI_SSPR_ParticleTrails_HQ_Default.MI_SSPR_ParticleTrails_HQ_Default"
)


def main():
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    material = unreal.load_asset(MATERIAL_PATH)
    if world is None or not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError("Live target validation inputs are missing")

    preview = unreal.RenderingLibrary.create_render_target2d(
        world,
        512,
        512,
        unreal.TextureRenderTargetFormat.RTF_RGBA8,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, material)
    if preview is None or mid is None:
        raise RuntimeError("Live target validation resources failed")

    rows = []
    best_nonzero = -1
    export_base = unreal.Paths.project_saved_dir() + "SSPR_M3_LiveProcessed"
    raw_export_base = unreal.Paths.project_saved_dir() + "SSPR_M3_LiveRaw"
    for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
        try:
            size_x = int(target.get_editor_property("size_x"))
            size_y = int(target.get_editor_property("size_y"))
            target_format = str(target.get_editor_property("render_target_format"))
        except Exception:
            continue
        if size_x != 2048 or size_y != 2048 or "RGBA16F" not in target_format:
            continue
        try:
            mid.set_texture_parameter_value("TrajectoryTexture", target)
            mid.set_scalar_parameter_value("DebugRaw", 0.0)
            unreal.RenderingLibrary.clear_render_target2d(
                world, preview, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
            )
            unreal.RenderingLibrary.draw_material_to_render_target(
                world, preview, mid
            )
            colors = unreal.RenderingLibrary.read_render_target(
                world, preview, True
            )
            if colors is None:
                continue
            red = [int(color.r) for color in colors]
            green = [int(color.g) for color in colors]
            blue = [int(color.b) for color in colors]
            nonzero = sum(
                1
                for r, g, b in zip(red, green, blue)
                if r > 0 or g > 0 or b > 0
            )
            mid.set_scalar_parameter_value("DebugRaw", 1.0)
            unreal.RenderingLibrary.clear_render_target2d(
                world, preview, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
            )
            unreal.RenderingLibrary.draw_material_to_render_target(
                world, preview, mid
            )
            raw_colors = unreal.RenderingLibrary.read_render_target(
                world, preview, True
            )
            raw_nonzero = sum(
                1
                for color in raw_colors
                if int(color.r) > 0
                or int(color.g) > 0
                or int(color.b) > 0
            )
            rows.append(
                {
                    "target": target.get_path_name(),
                    "nonzero": nonzero,
                    "rawNonzero": raw_nonzero,
                    "redMax": max(red) if red else 0,
                    "greenMax": max(green) if green else 0,
                    "blueMax": max(blue) if blue else 0,
                }
            )
            if nonzero > best_nonzero:
                best_nonzero = nonzero
                unreal.RenderingLibrary.export_render_target(
                    world,
                    preview,
                    unreal.Paths.project_saved_dir(),
                    "SSPR_M3_LiveRaw",
                )
                mid.set_scalar_parameter_value("DebugRaw", 0.0)
                unreal.RenderingLibrary.clear_render_target2d(
                    world, preview, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
                )
                unreal.RenderingLibrary.draw_material_to_render_target(
                    world, preview, mid
                )
                unreal.RenderingLibrary.export_render_target(
                    world,
                    preview,
                    unreal.Paths.project_saved_dir(),
                    "SSPR_M3_LiveProcessed",
                )
        except Exception as exc:
            rows.append(
                {
                    "target": target.get_path_name(),
                    "error": str(exc),
                    "nonzero": 0,
                }
            )
    rows.sort(key=lambda row: int(row.get("nonzero", 0)), reverse=True)
    result = {
        "candidateCount": len(rows),
        "candidates": rows,
        "exportBase": export_base,
        "rawExportBase": raw_export_base,
    }
    print("M3_LIVE_INTERNAL_TARGETS=" + json.dumps(result, sort_keys=True))
    if not rows or int(rows[0].get("nonzero", 0)) == 0:
        raise RuntimeError("No live SimRT produced M3 material output: " + repr(result))


main()
