import unreal

target = next(
    item
    for item in unreal.ObjectIterator(unreal.TextureRenderTarget2D)
    if item.get_name() == "SSPR_ParticleGridReadback"
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
unreal.RenderingLibrary.clear_render_target2d(
    world, target, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
)
print("GRID_READBACK_CLEARED=" + target.get_path_name())
