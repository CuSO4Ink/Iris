import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730/"
    "NS_SSPR_AnisotropicSplat_V3.NS_SSPR_AnisotropicSplat_V3"
)
SYSTEM_PACKAGE = SYSTEM.split(".", 1)[0]


def safe_property(obj, name):
    try:
        return str(obj.get_editor_property(name))
    except Exception:
        return None


system = unreal.load_asset(SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("V3 Niagara system is missing")

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
component.deactivate()
component.set_asset(None)
component.set_asset(system)

raster_interfaces = []
render_target_interfaces = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if not path.startswith(component.get_path_name() + "."):
        continue
    class_name = data_interface.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        data_interface.set_editor_property(
            "num_cells", unreal.IntVector(2048, 2048, 1)
        )
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
        try:
            data_interface.set_editor_property("precision", 65535.0)
        except Exception:
            pass
        value = data_interface.get_editor_property("num_cells")
        raster_interfaces.append(
            {
                "path": path,
                "numCells": [
                    int(value.x),
                    int(value.y),
                    int(value.z),
                ],
                "precision": safe_property(data_interface, "precision"),
                "clear": safe_property(
                    data_interface,
                    "clear_before_non_iteration_stage",
                ),
            }
        )
    elif class_name == "NiagaraDataInterfaceRenderTarget2D":
        data_interface.set_editor_property(
            "size", unreal.IntPoint(2048, 2048)
        )
        data_interface.set_editor_property(
            "inherit_user_parameter_settings", False
        )
        data_interface.set_editor_property("override_format", True)
        data_interface.set_editor_property(
            "override_render_target_format",
            unreal.TextureRenderTargetFormat.RTF_RGBA16F,
        )
        data_interface.set_editor_property(
            "override_render_target_filter",
            unreal.TextureFilter.TF_BILINEAR,
        )
        data_interface.set_editor_property(
            "mip_map_generation",
            unreal.NiagaraMipMapGeneration.DISABLED,
        )
        data_interface.set_editor_property(
            "mip_map_generation_type",
            unreal.NiagaraMipMapGenerationType.LINEAR,
        )
        size = data_interface.get_editor_property("size")
        render_target_interfaces.append(
            {
                "path": path,
                "size": [int(size.x), int(size.y)],
                "format": safe_property(
                    data_interface,
                    "override_render_target_format",
                ),
                "filter": safe_property(
                    data_interface,
                    "override_render_target_filter",
                ),
                "mips": safe_property(
                    data_interface, "mip_map_generation"
                ),
            }
        )

if not raster_interfaces:
    raise RuntimeError("No live V3 RasterizationGrid3D clone found")
if len(render_target_interfaces) < 2:
    raise RuntimeError("Expected V3 Main and Aux RenderTarget2D clones")

component.reinitialize_system()
component.set_force_solo(True)
component.set_component_tick_enabled(True)
component.activate(True)
component.advance_simulation(180, 1.0 / 60.0)

system_saved = bool(
    unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False)
)
level_saved = bool(
    unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    ).save_current_level()
)
result = {
    "asset": component.get_asset().get_path_name(),
    "active": bool(component.is_active()),
    "forceSolo": bool(component.get_force_solo()),
    "rasterInterfaces": raster_interfaces,
    "renderTargetInterfaces": render_target_interfaces,
    "advancedFrames": 180,
    "fixedDeltaSeconds": 1.0 / 60.0,
    "systemSaved": system_saved,
    "levelSaved": level_saved,
}
print("V3_REBIND_REINITIALIZE=" + json.dumps(result, sort_keys=True))
if (
    result["asset"] != SYSTEM
    or not result["active"]
    or not system_saved
    or not level_saved
):
    raise RuntimeError("V3 rebind/reinitialize gate failed: " + repr(result))
