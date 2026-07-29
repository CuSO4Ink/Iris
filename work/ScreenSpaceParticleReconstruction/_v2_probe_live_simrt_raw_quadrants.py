import gc
import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
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
    raise RuntimeError("Validation actor is not using V2")
component.advance_simulation(120, 1.0 / 60.0)

rows = []
quadrants = (
    (0, 0, 1024, 1024),
    (1024, 0, 1024, 1024),
    (0, 1024, 1024, 1024),
    (1024, 1024, 1024, 1024),
)
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(target.get_editor_property("render_target_format"))
    except Exception:
        continue
    if width != 2048 or height != 2048 or "RGBA16F" not in fmt:
        continue

    total_count = 0
    total_nonzero = 0
    red_min = 0.0
    red_max = 0.0
    red_sum = 0.0
    for x, y, read_width, read_height in quadrants:
        colors = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
            world, target, x, y, read_width, read_height, False
        )
        red = [float(color.r) for color in colors]
        if red:
            red_min = min(red_min, min(red))
            red_max = max(red_max, max(red))
        total_count += len(red)
        total_nonzero += sum(1 for value in red if abs(value) > 1.0e-8)
        red_sum += sum(red)
        del red
        del colors
        gc.collect()
    rows.append({
        "path": target.get_path_name(),
        "pixelCount": total_count,
        "nonzero": total_nonzero,
        "redMin": red_min,
        "redMax": red_max,
        "redSum": red_sum,
    })

rows.sort(key=lambda row: int(row.get("nonzero", 0)), reverse=True)
print("V2_LIVE_SIMRT_RAW_QUADRANTS=" + json.dumps({
    "active": bool(component.is_active()),
    "candidates": rows,
}, sort_keys=True))
