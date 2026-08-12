import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)

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
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Validation actor is not using V2")

component.advance_simulation(120, 1.0 / 60.0)

rows = []
for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        width = int(target.get_editor_property("size_x"))
        height = int(target.get_editor_property("size_y"))
        fmt = str(target.get_editor_property("render_target_format"))
    except Exception:
        continue
    if width != 2048 or height != 2048 or "RGBA16F" not in fmt:
        continue
    try:
        colors = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
            world, target, 1016, 1016, 1032, 1032, False
        )
        red = [float(color.r) for color in colors]
        rows.append({
            "path": target.get_path_name(),
            "centerAreaCount": len(red),
            "centerNonzero": sum(1 for value in red if abs(value) > 1.0e-8),
            "centerRedMax": max(red) if red else 0.0,
            "centerRedSum": sum(red),
        })
    except Exception as error:
        rows.append({"path": target.get_path_name(), "error": str(error)})

rows.sort(key=lambda row: float(row.get("centerRedSum", 0.0)), reverse=True)
print("V2_LIVE_SIMRT_RAW_CENTER=" + json.dumps({
    "active": bool(component.is_active()),
    "candidates": rows,
}, sort_keys=True))
