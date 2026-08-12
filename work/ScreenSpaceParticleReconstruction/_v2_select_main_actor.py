import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
actors = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors()
actor = next(
    item for item in actors
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
system = unreal.load_asset(SYSTEM)
# The V2 RasterizationGrid user parameter was added after this level component
# already existed. Reattaching through None forces the component override store
# to adopt the current system data-interface layout instead of retaining the
# old store with a null DensityRaster slot.
component.deactivate()
component.set_asset(None)
component.set_asset(system)

# Niagara clones data interfaces into each component override store. Configure
# the live component clone as well as the authored/compiled system copies.
raster_data_interfaces = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        path.startswith(component.get_path_name() + ".")
        and data_interface.get_class().get_name()
        == "NiagaraDataInterfaceRasterizationGrid3D"
    ):
        data_interface.set_editor_property(
            "num_cells", unreal.IntVector(2048, 2048, 1)
        )
        # Diagnostic probes may override this immediately. The production
        # selection path starts from deterministic current-frame clearing.
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
        raster_data_interfaces.append(path)
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(300, 1.0 / 60.0)
unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).set_selected_level_actors([actor])
level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.editor_invalidate_viewports()
location = actor.get_actor_location()
print("V2_SELECT_MAIN=" + json.dumps({
    "actor": actor.get_path_name(),
    "location": [location.x, location.y, location.z],
    "active": bool(component.is_active()),
    "visible": bool(component.is_visible()),
    "tickEnabled": bool(component.is_component_tick_enabled()),
    "forceSolo": bool(component.get_force_solo()),
    "rasterDataInterfaces": raster_data_interfaces,
}, sort_keys=True))
