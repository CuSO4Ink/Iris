import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
MATERIAL = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
GRID_SIZE = 2048
SERVICE = unreal.NiagaraScratchPadService

probe_code = r"""
int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int2 center = int2(max(W / 2, 0), max(H / 2, 0));
for (int y = -8; y <= 8; ++y)
{
    for (int x = -8; x <= 8; ++x)
    {
        int2 p = center + int2(x, y);
        if (p.x >= 0 && p.x < W && p.y >= 0 && p.y < H)
        {
            TrajectoryGrid.SetValueAtIndex(p.x, p.y, 0, 1.0f);
        }
    }
}
OutMark = (W > 0 && H > 0) ? 1.0f : 0.0f;
"""

result = {
    "system": SYSTEM,
    "probeInstalled": False,
    "probeCompiled": False,
    "copied": False,
    "restored": False,
    "saved": False,
}
actor = None
original_code = None

try:
    hlsl = next(
        str(node.node_id)
        for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
        if str(node.node_type) == "CustomHlsl"
    )
    original_code = SERVICE.get_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, hlsl
    )
    if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, hlsl, probe_code
    ):
        raise RuntimeError("Failed to install constant Grid2D probe")
    result["probeInstalled"] = bool(SERVICE.apply_changes(SYSTEM))
    compile_messages = [
        str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
    ]
    result["compileMessages"] = compile_messages
    result["probeCompiled"] = not compile_messages
    if compile_messages:
        raise RuntimeError("Probe compile failed: " + repr(compile_messages))

    system = unreal.load_object(None, SYSTEM)
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.NiagaraActor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    actor.set_actor_label("SSPR_RTWriteProbe_Temporary")
    component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
    component.set_asset(system)
    component.set_force_solo(True)

    source_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    readback_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    if source_target is None or readback_target is None:
        raise RuntimeError("Failed to create transient R32F probe targets")
    component.set_variable_texture_render_target(
        "User.SSPR_TrajectoryRT", source_target
    )
    component.reinitialize_system()
    component.activate(True)
    component.advance_simulation(180, 1.0 / 60.0)
    result["componentActive"] = bool(component.is_active())

    grid = next(
        item
        for item in unreal.ObjectIterator(
            unreal.NiagaraDataInterfaceGrid2DCollection
        )
        if item.get_path_name()
        == SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
    )
    result["gridPath"] = grid.get_path_name()
    result["copied"] = bool(
        grid.fill_texture2d(component, readback_target, 0)
    )

    center = GRID_SIZE // 2
    material = unreal.load_object(None, MATERIAL)
    mid = unreal.MaterialLibrary.create_dynamic_material_instance(
        world, material
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
    mid.set_scalar_parameter_value("TrajectoryGain", 1.0)

    def render_stats(texture):
        mid.set_texture_parameter_value(
            "TrajectoryTexture", texture
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
        red = [int(color.r) for color in colors] if colors else []
        green = [int(color.g) for color in colors] if colors else []
        blue = [int(color.b) for color in colors] if colors else []
        return {
            "samples": len(red),
            "nonzero": sum(
                r > 0 or g > 0 or b > 0
                for r, g, b in zip(red, green, blue)
            ),
            "redMax": max(red) if red else 0,
            "center": (
                red[(256 // 2) * 256 + (256 // 2)]
                if red
                else 0
            ),
            "corner": red[0] if red else 0,
        }

    black_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        64,
        64,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    white_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        64,
        64,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(1.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    unreal.RenderingLibrary.clear_render_target2d(
        world,
        black_target,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    )
    unreal.RenderingLibrary.clear_render_target2d(
        world,
        white_target,
        unreal.LinearColor(1.0, 0.0, 0.0, 0.0),
    )
    result["materialCalibrationBlack"] = render_stats(
        black_target
    )
    result["materialCalibrationWhite"] = render_stats(
        white_target
    )
    result["sourceTargetStats"] = render_stats(source_target)
    result["fillTextureStats"] = render_stats(readback_target)
finally:
    if original_code is not None:
        SERVICE.set_custom_hlsl_code(
            SYSTEM, EMITTER, MODULE, hlsl, original_code
        )
        result["restored"] = bool(SERVICE.apply_changes(SYSTEM))
        result["saved"] = bool(
            unreal.EditorAssetLibrary.save_asset(SYSTEM, False)
        )
    if actor is not None:
        unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).destroy_actor(actor)

print("RT_CONSTANT_PROBE=" + json.dumps(result, sort_keys=True))
