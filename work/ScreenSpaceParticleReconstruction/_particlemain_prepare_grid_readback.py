import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
GRID_SIZE = 2048
TARGET_NAME = "SSPR_ParticleGridReadback"

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
actor = next(
    item
    for item in actor_subsystem.get_all_level_actors()
    if item.get_actor_label() == ACTOR_LABEL
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
grid = next(
    item
    for item in unreal.ObjectIterator(
        unreal.NiagaraDataInterfaceGrid2DCollection
    )
    if SYSTEM in item.get_path_name()
    and ":Fountain.GPUComputeScript." in item.get_path_name()
    and "Invalidated_" not in item.get_path_name()
    and int(item.get_editor_property("num_cells_x")) == GRID_SIZE
)

component.reinitialize_system()
component.activate(True)
component.advance_simulation(5, 1.0 / 60.0)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()

target = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.TextureRenderTarget2D
        )
        if item.get_name() == TARGET_NAME
        and component.get_path_name() in item.get_path_name()
    ),
    None,
)
if target is None:
    target = unreal.RenderingLibrary.create_render_target2d(
        world,
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    target.rename(TARGET_NAME, component)

component.set_variable_texture_render_target(
    "User.SSPR_DebugGridReadback", target
)
unreal.RenderingLibrary.clear_render_target2d(
    world, target, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
)
copied = bool(grid.fill_texture2d(component, target, 0))
print(
    "GRID_READBACK_PREPARED="
    + json.dumps(
        {
            "component": component.get_path_name(),
            "grid": grid.get_path_name(),
            "target": target.get_path_name(),
            "copied": copied,
        },
        sort_keys=True,
    )
)
if not copied:
    raise RuntimeError("Grid readback copy was rejected")
