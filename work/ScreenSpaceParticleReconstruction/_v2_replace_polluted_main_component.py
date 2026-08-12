import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
LABEL = "SSPR_ParticleTrails_Main"


def safe_property(obj, name):
    try:
        return str(obj.get_editor_property(name))
    except Exception:
        return None


system = unreal.load_asset(SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Missing V2 Niagara system")
actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
level_subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
matches = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label() == LABEL
]
if len(matches) != 1:
    raise RuntimeError(
        "Expected exactly one polluted main actor, got "
        + str(len(matches))
    )
old_actor = matches[0]
old_component = old_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
old_path = old_actor.get_path_name()
old_component_path = old_component.get_path_name()
old_transform = old_actor.get_actor_transform()

new_actor = actor_subsystem.spawn_actor_from_class(
    unreal.NiagaraActor,
    old_transform.translation,
)
if not isinstance(new_actor, unreal.NiagaraActor):
    raise RuntimeError("Failed to spawn replacement NiagaraActor")
new_actor.set_actor_label(LABEL + "_CleanCandidate")
new_actor.set_actor_transform(old_transform, False, False)
new_component = new_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
new_component.set_asset(system)
new_component.set_auto_activate(True)
new_component.set_visibility(True, True)
new_component.set_component_tick_enabled(True)
new_component.set_force_solo(True)

raster_interfaces = []
render_target_interfaces = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if not path.startswith(new_component.get_path_name() + "."):
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
        cells = data_interface.get_editor_property("num_cells")
        raster_interfaces.append(
            {
                "path": path,
                "cells": [
                    int(cells.x),
                    int(cells.y),
                    int(cells.z),
                ],
                "precision": safe_property(
                    data_interface, "precision"
                ),
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

if not raster_interfaces or len(render_target_interfaces) < 2:
    actor_subsystem.destroy_actor(new_actor)
    raise RuntimeError(
        "Replacement component did not create required DIs: "
        + repr(
            {
                "raster": raster_interfaces,
                "renderTargets": render_target_interfaces,
            }
        )
    )

new_component.reinitialize_system()
new_component.activate(True)
new_component.advance_simulation(300, 1.0 / 60.0)
if not new_component.is_active():
    actor_subsystem.destroy_actor(new_actor)
    raise RuntimeError("Replacement component failed to activate")

old_component.deactivate()
old_component.set_component_tick_enabled(False)
destroyed = bool(actor_subsystem.destroy_actor(old_actor))
if not destroyed:
    actor_subsystem.destroy_actor(new_actor)
    raise RuntimeError("Failed to destroy the polluted main actor")
new_actor.set_actor_label(LABEL)
saved = bool(level_subsystem.save_current_level())
result = {
    "oldActor": old_path,
    "oldComponent": old_component_path,
    "oldActorDestroyed": destroyed,
    "newActor": new_actor.get_path_name(),
    "newComponent": new_component.get_path_name(),
    "newAsset": new_component.get_asset().get_path_name(),
    "active": bool(new_component.is_active()),
    "rasterInterfaces": raster_interfaces,
    "renderTargetInterfaces": render_target_interfaces,
    "saved": saved,
}
print(
    "V2_REPLACE_POLLUTED_MAIN_COMPONENT="
    + json.dumps(result, sort_keys=True)
)
if not saved:
    raise RuntimeError("Failed to save clean replacement actor")
