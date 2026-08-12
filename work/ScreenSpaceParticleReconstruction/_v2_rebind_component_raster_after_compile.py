import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)

system = unreal.load_asset(SYSTEM)
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]

# Rebuild the component override store first. Recompiling the Niagara System
# creates new user-DI templates; configuring older component clones before this
# step leaves the live RasterizationGrid at its 1x1x1 class default.
component.deactivate()
component.set_asset(None)
component.set_asset(system)

configured = []
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
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
        value = data_interface.get_editor_property("num_cells")
        configured.append({
            "path": path,
            "numCells": [int(value.x), int(value.y), int(value.z)],
        })

if not configured:
    raise RuntimeError("No current component RasterizationGrid3D clone found")

component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(120, 1.0 / 60.0)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_REBIND_COMPONENT_RASTER=" + json.dumps({
    "active": bool(component.is_active()),
    "configured": configured,
    "saved": saved,
}, sort_keys=True))
if not saved:
    raise RuntimeError("Failed to save V2 system after component rebind")
