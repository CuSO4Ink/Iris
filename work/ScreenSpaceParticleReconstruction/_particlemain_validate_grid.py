import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
GRID_SIZE = 2048

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
actor = next(
    (
        item
        for item in actor_subsystem.get_all_level_actors()
        if item.get_actor_label() == ACTOR_LABEL
    ),
    None,
)
if actor is None:
    raise RuntimeError("White-particle mainline actor is missing")
components = actor.get_components_by_class(unreal.NiagaraComponent)
if not components:
    raise RuntimeError("White-particle mainline component is missing")
component = components[0]

grid = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.NiagaraDataInterfaceGrid2DCollection
        )
        if SYSTEM in item.get_path_name()
        and ":Fountain.GPUComputeScript." in item.get_path_name()
        and "Invalidated_" not in item.get_path_name()
        and int(item.get_editor_property("num_cells_x")) == GRID_SIZE
        and int(item.get_editor_property("num_cells_y")) == GRID_SIZE
        and int(item.get_editor_property("num_attributes")) == 1
    ),
    None,
)
if grid is None:
    raise RuntimeError("Active 2048 Grid2D data interface is missing")

component.reinitialize_system()
component.activate(True)
component.advance_simulation(180, 1.0 / 60.0)

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
target = unreal.RenderingLibrary.create_render_target2d(
    world,
    GRID_SIZE,
    GRID_SIZE,
    unreal.TextureRenderTargetFormat.RTF_R32F,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)
if target is None:
    raise RuntimeError("Failed to create transient Grid readback target")
copied = bool(grid.fill_texture2d(component, target, 0))
if not copied:
    raise RuntimeError("Grid2D FillTexture2D rejected the readback")

raw = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
    world,
    target,
    GRID_SIZE // 4,
    GRID_SIZE // 4,
    GRID_SIZE * 3 // 4 - 1,
    GRID_SIZE * 3 // 4 - 1,
    False,
)
values = [float(color.r) for color in raw] if raw else []
threshold = 0.001
stats = {
    "samples": len(values),
    "min": min(values) if values else None,
    "max": max(values) if values else None,
    "mean": sum(values) / len(values) if values else None,
    "nonzero": sum(value > threshold for value in values),
    "full": sum(value > 0.99 for value in values),
}
result = {
    "system": component.get_asset().get_path_name(),
    "actor": actor.get_path_name(),
    "active": bool(component.is_active()),
    "grid": grid.get_path_name(),
    "gridSize": [
        int(grid.get_editor_property("num_cells_x")),
        int(grid.get_editor_property("num_cells_y")),
    ],
    "clearBeforeWrite": bool(
        grid.get_editor_property("clear_before_non_iteration_stage")
    ),
    "copied": copied,
    "stats": stats,
    "sampleArea": [
        GRID_SIZE // 4,
        GRID_SIZE // 4,
        GRID_SIZE * 3 // 4 - 1,
        GRID_SIZE * 3 // 4 - 1,
    ],
}
print("PARTICLE_GRID_VALIDATION=" + json.dumps(result, sort_keys=True))
if not values or stats["nonzero"] <= 0 or stats["max"] <= threshold:
    raise RuntimeError("White-particle trajectory Grid is empty: " + repr(result))
