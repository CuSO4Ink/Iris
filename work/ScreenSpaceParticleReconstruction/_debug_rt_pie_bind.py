import json
import unreal

DEBUG_PREFIX = (
    "/Game/SSPR_Validation/Debug/"
    "NS_SSPR_RTWriteProbe_"
)
TARGET_NAME = "SSPR_RTWriteProbeSource"
GRID_SIZE = 2048

level_editor = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
if not level_editor.is_in_play_in_editor():
    raise RuntimeError("PIE is not active")

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
    raise RuntimeError("PIE Niagara probe component was not found")

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
created = False
if target is None:
    target = unreal.RenderingLibrary.create_render_target2d(
        component.get_world(),
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    if target is None:
        raise RuntimeError("Failed to create PIE R32F target")
    if not target.rename(TARGET_NAME, component):
        raise RuntimeError("Failed to uniquely own PIE target")
    created = True

component.set_variable_texture_render_target(
    "User.SSPR_TrajectoryRT", target
)
component.set_force_solo(True)
component.reinitialize_system()
component.activate(True)
print(
    "RT_PIE_BOUND="
    + json.dumps(
        {
            "system": component.get_asset().get_path_name(),
            "component": component.get_path_name(),
            "target": target.get_path_name(),
            "created": created,
            "active": bool(component.is_active()),
        },
        sort_keys=True,
    )
)
