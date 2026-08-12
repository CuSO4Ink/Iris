import unreal

target = next(
    item
    for item in unreal.ObjectIterator(unreal.TextureRenderTarget2D)
    if item.get_name() == "SSPR_R32ClearProbe"
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
raw = unreal.RenderingLibrary.read_render_target_raw_pixel(
    world, target, 32, 32, False
)
color = unreal.RenderingLibrary.read_render_target_pixel(
    world, target, 32, 32
)
print(
    "R32_CLEAR_PROBE="
    + repr(
        {
            "raw": [raw.r, raw.g, raw.b, raw.a],
            "color": [color.r, color.g, color.b, color.a],
        }
    )
)
