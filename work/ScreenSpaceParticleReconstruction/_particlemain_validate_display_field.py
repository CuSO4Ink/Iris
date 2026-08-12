import json
import unreal

ACTOR_LABEL = "SSPR_ParticleTrails_Main"
TARGET_NAME = "SSPR_TrajectoryRT_Runtime"
PREVIEW_NAME = "SSPR_TrajectoryValidationPreview"
MATERIAL_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)
SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"

actor = next(
    (
        item
        for item in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        if item.get_actor_label() == ACTOR_LABEL
    ),
    None,
)
if actor is None:
    raise RuntimeError("White-particle main actor is missing")
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
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
material = unreal.load_object(None, MATERIAL_PATH)
grid = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.NiagaraDataInterfaceGrid2DCollection
        )
        if item.get_path_name() == GRID_PATH
    ),
    None,
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
if (
    target is None
    or not isinstance(material, unreal.MaterialInterface)
    or grid is None
    or world is None
):
    raise RuntimeError(
        "Display-field validation inputs are missing"
    )

preview = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.TextureRenderTarget2D
        )
        if item.get_name() == PREVIEW_NAME
        and component.get_path_name() in item.get_path_name()
    ),
    None,
)
if preview is None:
    preview = unreal.RenderingLibrary.create_render_target2d(
        world,
        256,
        256,
        unreal.TextureRenderTargetFormat.RTF_RGBA8,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    if preview is None:
        raise RuntimeError(
            "Failed to create display validation target"
        )
    preview.rename(PREVIEW_NAME, component)

mid = unreal.MaterialLibrary.create_dynamic_material_instance(
    world, material
)
if mid is None:
    raise RuntimeError("Failed to create validation MID")
mid.set_texture_parameter_value("TrajectoryTexture", target)
mid.set_scalar_parameter_value("TrajectoryGain", 1.0)

component.advance_simulation(30, 1.0 / 60.0)
# Grid2DCollection now publishes into the object user variable every frame.
# Calling the deprecated fill_texture2d on the system-default DI can select a
# different compile clone and overwrite the valid external target with zeroes.
copied_from_grid = "external-object-user-variable"
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
if colors is None:
    raise RuntimeError("RGBA8 validation readback failed")

red_values = [int(color.r) for color in colors]
green_values = [int(color.g) for color in colors]
blue_values = [int(color.b) for color in colors]
nonzero = sum(
    1
    for r, g, b in zip(
        red_values, green_values, blue_values
    )
    if r > 0 or g > 0 or b > 0
)
result = {
    "sourceTarget": target.get_path_name(),
    "preview": preview.get_path_name(),
    "samples": len(colors),
    "copiedFromGrid": copied_from_grid,
    "nonzero": nonzero,
    "redMax": max(red_values) if red_values else 0,
    "greenMax": max(green_values) if green_values else 0,
    "blueMax": max(blue_values) if blue_values else 0,
}
print(
    "PARTICLE_DISPLAY_FIELD_VALIDATION="
    + json.dumps(result, sort_keys=True)
)
if len(colors) != 256 * 256 or nonzero == 0:
    raise RuntimeError(
        "White-particle trajectory field is empty in the display material: "
        + repr(result)
    )
