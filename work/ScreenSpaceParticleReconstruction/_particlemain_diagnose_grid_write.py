import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_WriteParticleTrails"
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
TARGET_NAME = "SSPR_TrajectoryRT_Runtime"
PREVIEW_NAME = "SSPR_TrajectoryValidationPreview"
MATERIAL_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)
SERVICE = unreal.NiagaraScratchPadService

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
hlsl = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "CustomHlsl"
    and "TrajectoryGrid"
    in {
        str(pin.pin_name)
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, MODULE, str(node.node_id)
        )
    }
)
original_code = SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl
)
diagnostic_code = r"""
int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int centerX = max(W / 2, 0);
int centerY = max(H / 2, 0);
for (int y = -32; y <= 32; ++y)
{
    for (int x = -32; x <= 32; ++x)
    {
        int px = centerX + x;
        int py = centerY + y;
        if (px >= 0 && px < W && py >= 0 && py < H)
        {
            TrajectoryGrid.SetValueAtIndex(px, py, 0, 1.0f);
        }
    }
}
OutDummy = 1.0f;
"""

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
system = unreal.load_object(None, SYSTEM)
grid = next(
    item
    for item in unreal.ObjectIterator(
        unreal.NiagaraDataInterfaceGrid2DCollection
    )
    if item.get_path_name() == GRID_PATH
)
target = next(
    item
    for item in unreal.ObjectIterator(
        unreal.TextureRenderTarget2D
    )
    if item.get_name() == TARGET_NAME
    and component.get_path_name() in item.get_path_name()
)
preview = next(
    item
    for item in unreal.ObjectIterator(
        unreal.TextureRenderTarget2D
    )
    if item.get_name() == PREVIEW_NAME
    and component.get_path_name() in item.get_path_name()
)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
material = unreal.load_object(None, MATERIAL_PATH)
result = {}

try:
    if not SERVICE.set_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        hlsl,
        diagnostic_code,
    ):
        raise RuntimeError("Failed to install diagnostic grid writer")
    if not SERVICE.apply_changes(SYSTEM):
        raise RuntimeError("Diagnostic grid writer did not apply")

    component.deactivate()
    component.set_asset(None)
    component.set_asset(system)
    component.set_variable_texture_render_target(
        "User.SSPR_TrajectoryRT", target
    )
    component.set_force_solo(True)
    component.reinitialize_system()
    component.activate(True)
    component.advance_simulation(60, 1.0 / 60.0)

    copied = bool(grid.fill_texture2d(component, target, 0))
    mid = unreal.MaterialLibrary.create_dynamic_material_instance(
        world, material
    )
    mid.set_texture_parameter_value(
        "TrajectoryTexture", target
    )
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
    result = {
        "copied": copied,
        "samples": len(colors),
        "nonzero": nonzero,
        "redMax": max(int(color.r) for color in colors),
    }
finally:
    SERVICE.set_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        hlsl,
        original_code,
    )
    restored = bool(SERVICE.apply_changes(SYSTEM))
    saved = bool(
        unreal.EditorAssetLibrary.save_asset(SYSTEM, False)
    )
    component.deactivate()
    component.set_asset(None)
    component.set_asset(system)
    component.set_variable_texture_render_target(
        "User.SSPR_TrajectoryRT", target
    )
    component.set_force_solo(True)
    component.reinitialize_system()
    component.activate(True)
    result["restored"] = restored
    result["saved"] = saved

print(
    "PARTICLE_GRID_WRITE_DIAGNOSIS="
    + json.dumps(result, sort_keys=True)
)
if (
    not result.get("restored")
    or not result.get("saved")
):
    raise RuntimeError(
        "Diagnostic writer restoration failed: " + repr(result)
    )
