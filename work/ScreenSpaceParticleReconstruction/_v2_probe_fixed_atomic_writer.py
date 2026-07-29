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
SERVICE = unreal.NiagaraScratchPadService


def hlsl_node(module):
    return next(
        str(node.node_id)
        for node in SERVICE.list_nodes(SYSTEM, EMITTER, module)
        if str(node.node_type) == "CustomHlsl"
    )


writer = r"""int W = 1;
int H = 1;
int D = 1;
DensityRaster.GetNumCells(W, H, D);
bool Valid = W > 0 && H > 0 && D > 0;
int PreviousValue = 0;
if (Valid)
{
    DensityRaster.InterlockedAddIntGridValue(
        W / 2, H / 2, 0, 0, 1024, PreviousValue);
}
OutMark = Valid ? 1.0f : 0.0f;"""

resolve = r"""int DispatchW = 1;
int DispatchH = 1;
TrajectoryGrid.GetNumCells(DispatchW, DispatchH);
int CellX = 0;
int CellY = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(CellX, CellY);
int RasterW = 1;
int RasterH = 1;
int RasterD = 1;
DensityRaster.GetNumCells(RasterW, RasterH, RasterD);
bool ValidRaster = RasterW > 0 && RasterH > 0 && RasterD > 0 &&
    CellX >= 0 && CellX < RasterW && CellY >= 0 && CellY < RasterH;
int DensityInt = 0;
if (ValidRaster)
{
    DensityRaster.GetIntGridValue(CellX, CellY, 0, 0, DensityInt);
}
float Density = (float)DensityInt / 1024.0f;
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = ValidRaster && ValidRT
    ? clamp((int)(((float)CellX + 0.5f) * RTW / RasterW), 0, RTW - 1) : 0;
int DstY = ValidRaster && ValidRT
    ? clamp((int)(((float)CellY + 0.5f) * RTH / RasterH), 0, RTH - 1) : 0;
SimRT.SetRenderTargetValue(
    ValidRaster && ValidRT, DstX, DstY,
    float4(Density, Density, Density, Density));
OutMark = Density;"""

if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, "SSPR_RasterizeWhiteParticles",
    hlsl_node("SSPR_RasterizeWhiteParticles"), writer
):
    raise RuntimeError("Failed to install fixed atomic writer")
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, "SSPR_ResolveGridToSimRT",
    hlsl_node("SSPR_ResolveGridToSimRT"), resolve
):
    raise RuntimeError("Failed to restore raster resolve")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]

# ApplyChanges constructs the final executable DI clones. Configure that final
# set after compilation, then save without triggering another compile.
configured = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        SYSTEM in path
        and data_interface.get_class().get_name()
        == "NiagaraDataInterfaceRasterizationGrid3D"
    ):
        data_interface.set_editor_property(
            "num_cells", unreal.IntVector(2048, 2048, 1)
        )
        data_interface.set_editor_property(
            "clear_before_non_iteration_stage", True
        )
        configured.append(path)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_FIXED_ATOMIC=" + json.dumps({
    "applied": applied,
    "configured": configured,
    "messages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Fixed atomic probe failed")
