import json
import unreal

DEBUG_PREFIX = (
    "/Game/SSPR_Validation/Debug/"
    "NS_SSPR_RTWriteProbe_"
)
TARGET_NAME = "SSPR_RTWriteProbeSource"
MATERIAL = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)
GRID_SIZE = 2048

component = next(
    (
        item
        for item in unreal.ObjectIterator(unreal.NiagaraComponent)
        if item.get_asset() is not None
        and item.get_asset().get_path_name().startswith(DEBUG_PREFIX)
        and item.get_world() is not None
        and item.get_world().get_path_name().startswith("/Temp/UEDPIE_")
        and item.get_path_name().startswith("/Memory/UEDPIE_")
    ),
    None,
)
if component is None:
    raise RuntimeError("Live PIE Niagara probe component was not found")
world = component.get_world()
target = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.TextureRenderTarget2D
        )
        if item.get_name() == TARGET_NAME
        and item.get_outer() == component
    ),
    None,
)
if target is None:
    raise RuntimeError("Live PIE source target was not found")

system_path = component.get_asset().get_path_name()
grid = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.NiagaraDataInterfaceGrid2DCollection
        )
        if item.get_path_name()
        == system_path + ":NiagaraDataInterfaceGrid2DCollection_0"
    ),
    None,
)
if grid is None:
    raise RuntimeError("Debug system Grid2D default was not found")

readback = unreal.RenderingLibrary.create_render_target2d(
    world,
    GRID_SIZE,
    GRID_SIZE,
    unreal.TextureRenderTargetFormat.RTF_R32F,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)
copied = bool(grid.fill_texture2d(component, readback, 0))

material = unreal.load_object(None, MATERIAL)
mid = unreal.MaterialLibrary.create_dynamic_material_instance(
    world, material
)
mid.set_scalar_parameter_value("TrajectoryGain", 1.0)
preview = unreal.RenderingLibrary.create_render_target2d(
    world,
    256,
    256,
    unreal.TextureRenderTargetFormat.RTF_RGBA8,
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    False,
    False,
)


def render_stats(texture):
    mid.set_texture_parameter_value("TrajectoryTexture", texture)
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


result = {
    "system": system_path,
    "component": component.get_path_name(),
    "world": world.get_path_name(),
    "active": bool(component.is_active()),
    "tick": bool(component.is_component_tick_enabled()),
    "sourceTarget": target.get_path_name(),
    "copied": copied,
    "sourceStats": render_stats(target),
    "fillStats": render_stats(readback),
}
print("RT_PIE_VALIDATION=" + json.dumps(result, sort_keys=True))
