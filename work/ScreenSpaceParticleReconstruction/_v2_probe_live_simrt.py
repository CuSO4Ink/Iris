import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PROBE_MATERIAL = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "MI_SSPR_ParticleTrails_HQ_Default.MI_SSPR_ParticleTrails_HQ_Default"
)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
material = unreal.load_asset(PROBE_MATERIAL)
actor = next(
    item for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Validation actor is not using V2")
component.advance_simulation(120, 1.0 / 60.0)

preview = unreal.RenderingLibrary.create_render_target2d(
    world, 256, 256, unreal.TextureRenderTargetFormat.RTF_RGBA8,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0), False, False
)
mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, material)
mid.set_scalar_parameter_value("DebugRaw", 1.0)

rows = []
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        sx = int(target.get_editor_property("size_x"))
        sy = int(target.get_editor_property("size_y"))
        fmt = str(target.get_editor_property("render_target_format"))
    except Exception:
        continue
    if sx != 2048 or sy != 2048 or "RGBA16F" not in fmt:
        continue
    try:
        mid.set_texture_parameter_value("TrajectoryTexture", target)
        unreal.RenderingLibrary.clear_render_target2d(
            world, preview, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
        )
        unreal.RenderingLibrary.draw_material_to_render_target(world, preview, mid)
        colors = unreal.RenderingLibrary.read_render_target(world, preview, True)
        red = [int(color.r) for color in colors]
        rows.append({
            "path": target.get_path_name(),
            "outer": target.get_outer().get_path_name() if target.get_outer() else None,
            "nonzero": sum(1 for value in red if value > 0),
            "redMax": max(red) if red else 0,
            "redSum": sum(red),
        })
    except Exception as error:
        rows.append({"path": target.get_path_name(), "error": str(error)})

rows.sort(key=lambda row: int(row.get("redSum", 0)), reverse=True)
print("V2_LIVE_SIMRT=" + json.dumps({
    "active": bool(component.is_active()),
    "candidates": rows,
}, sort_keys=True))
