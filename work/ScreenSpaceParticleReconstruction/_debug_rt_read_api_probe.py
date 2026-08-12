import json
import unreal

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
result = {}
for label, clear in (
    ("black", unreal.LinearColor(0.0, 0.0, 0.0, 0.0)),
    ("quarter", unreal.LinearColor(0.25, 0.0, 0.0, 0.0)),
    ("white", unreal.LinearColor(1.0, 0.0, 0.0, 0.0)),
):
    target = unreal.RenderingLibrary.create_render_target2d(
        world,
        64,
        64,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        clear,
        False,
        False,
    )
    unreal.RenderingLibrary.clear_render_target2d(world, target, clear)
    raw = unreal.RenderingLibrary.read_render_target_raw_pixel(
        world, target, 32, 32, False
    )
    color = unreal.RenderingLibrary.read_render_target_pixel(
        world, target, 32, 32
    )
    result[label] = {
        "raw": [float(raw.r), float(raw.g), float(raw.b), float(raw.a)],
        "color": [int(color.r), int(color.g), int(color.b), int(color.a)],
    }
print("RT_READ_API_PROBE=" + json.dumps(result, sort_keys=True))
