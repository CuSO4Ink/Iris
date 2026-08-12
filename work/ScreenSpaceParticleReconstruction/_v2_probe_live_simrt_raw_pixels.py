import json
import unreal


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
rows = []
positions = ((0, 0), (128, 128), (1024, 1024), (2047, 2047))
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(target.get_editor_property("render_target_format"))
    except Exception:
        continue
    if width != 2048 or height != 2048 or "RGBA16F" not in fmt:
        continue
    samples = []
    for x, y in positions:
        color = unreal.RenderingLibrary.read_render_target_raw_pixel(
            world, target, x, y, False
        )
        samples.append({
            "x": x,
            "y": y,
            "rgba": [
                float(color.r), float(color.g),
                float(color.b), float(color.a),
            ],
        })
    rows.append({"path": target.get_path_name(), "samples": samples})
print("V2_LIVE_SIMRT_RAW_PIXELS=" + json.dumps(rows, sort_keys=True))
