import json
import unreal


ROOT = r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)


def run_script(name):
    exec(open(ROOT + "\\" + name, encoding="utf-8").read(), {
        "__name__": "__main__",
    })


created = unreal.NiagaraScratchPadService.create_rasterization_grid3d_user_parameter(
    SYSTEM, "User.SSPR_DensityRaster",
    2048, 2048, 1, 1, 1024.0, 0, False,
)
if not created.success:
    raise RuntimeError(str(created.message))

run_script("_v2_install_atomic_gaussian.py")
run_script("_v2_select_main_actor.py")

actors = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors()
actor = next(
    item for item in actors
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]

configured = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        data_interface.get_class().get_name()
        == "NiagaraDataInterfaceRasterizationGrid3D"
        and (SYSTEM in path or path.startswith(component.get_path_name() + "."))
    ):
        data_interface.set_editor_property(
            "num_cells", unreal.IntVector(2048, 2048, 1)
        )
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", False
        )
        configured.append(path)

component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(60, 1.0 / 60.0)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_FORMAL_CLEAR_DISABLED=" + json.dumps({
    "configured": configured,
    "active": bool(component.is_active()),
    "saved": saved,
}, sort_keys=True))
