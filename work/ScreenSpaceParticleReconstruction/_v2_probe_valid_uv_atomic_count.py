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
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService

node_id = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
    if str(node.node_type) == "CustomHlsl"
)
writer = r"""int W = 1;
int H = 1;
int D = 1;
DensityRaster.GetNumCells(W, H, D);
bool ValidUV =
    W > 0 && H > 0 && D > 0 &&
    ScreenUV.x >= 0.0f && ScreenUV.x < 1.0f &&
    ScreenUV.y >= 0.0f && ScreenUV.y < 1.0f;
int PreviousValue = 0;
if (ValidUV)
{
    DensityRaster.InterlockedAddIntGridValue(
        W / 2, H / 2, 0, 0, 1024, PreviousValue);
}
OutMark = ValidUV ? 1.0f : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, node_id, writer
):
    raise RuntimeError("Install valid-UV counter failed")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        data_interface.get_class().get_name()
        == "NiagaraDataInterfaceRasterizationGrid3D"
        and (SYSTEM in path or path.startswith(component.get_path_name() + "."))
    ):
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(120, 1.0 / 60.0)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_VALID_UV_ATOMIC_COUNT=" + json.dumps({
    "active": bool(component.is_active()),
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Valid-UV atomic probe failed")
