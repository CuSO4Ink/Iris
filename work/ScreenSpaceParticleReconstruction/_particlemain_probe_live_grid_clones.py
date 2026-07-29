import json
import unreal


ACTOR_LABEL = "SSPR_ParticleTrails_Main"
MATERIAL_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == ACTOR_LABEL
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
material = unreal.load_object(None, MATERIAL_PATH)

scratch = unreal.RenderingLibrary.create_render_target2d(
    world,
    2048,
    2048,
    unreal.TextureRenderTargetFormat.RTF_R32F,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)
preview = unreal.RenderingLibrary.create_render_target2d(
    world,
    256,
    256,
    unreal.TextureRenderTargetFormat.RTF_RGBA8,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)
if scratch is None or preview is None:
    raise RuntimeError("Failed to create clone-probe targets")

component.advance_simulation(30, 1.0 / 60.0)
rows = []
for index, grid in enumerate(
    unreal.ObjectIterator(
        unreal.NiagaraDataInterfaceGrid2DCollection
    )
):
    if component.get_path_name() not in grid.get_path_name():
        continue
    unreal.RenderingLibrary.clear_render_target2d(
        world,
        scratch,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    )
    copied = bool(
        grid.fill_texture2d(component, scratch, 0)
    )
    mid = unreal.MaterialLibrary.create_dynamic_material_instance(
        world, material
    )
    mid.set_texture_parameter_value(
        "TrajectoryTexture", scratch
    )
    mid.set_scalar_parameter_value("TrajectoryGain", 1.0)
    unreal.RenderingLibrary.clear_render_target2d(
        world,
        preview,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    )
    unreal.RenderingLibrary.draw_material_to_render_target(
        world, preview, mid
    )
    colors = unreal.RenderingLibrary.read_render_target(
        world, preview, True
    )
    nonzero = sum(
        1
        for color in colors
        if int(color.r) > 0
        or int(color.g) > 0
        or int(color.b) > 0
    )
    rows.append(
        {
            "index": index,
            "grid": grid.get_path_name(),
            "copied": copied,
            "nonzero": nonzero,
            "redMax": max(
                (int(color.r) for color in colors),
                default=0,
            ),
        }
    )

print(
    "PARTICLE_LIVE_GRID_CLONES="
    + json.dumps(rows, sort_keys=True)
)
if not any(row["nonzero"] > 0 for row in rows):
    raise RuntimeError(
        "Every live Grid2D clone is empty: " + repr(rows)
    )
