import unreal

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
target = unreal.RenderingLibrary.create_render_target2d(
    world,
    64,
    64,
    unreal.TextureRenderTargetFormat.RTF_R32F,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)
target.rename("SSPR_R32ClearProbe", component)
component.set_variable_texture_render_target(
    "User.SSPR_R32ClearProbe", target
)
unreal.RenderingLibrary.clear_render_target2d(
    world, target, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
)
print("R32_CLEAR_PROBE_PREPARED=" + target.get_path_name())
