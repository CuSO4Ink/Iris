import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_ResolveGridToSimRT"
SERVICE = unreal.NiagaraScratchPadService

node_id = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
    if str(node.node_type) == "CustomHlsl"
)
code = r"""int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int X = 0;
int Y = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(X, Y);
int RW = 1;
int RH = 1;
int RD = 1;
DensityRaster.GetNumCells(RW, RH, RD);
bool Valid = RW > 0 && RH > 0 && RD > 0 && X < RW && Y < RH;
int Ignore = 0;
if (Valid)
{
    DensityRaster.InterlockedAddIntGridValue(X, Y, 0, 0, 1024, Ignore);
}
int Value = 0;
if (Valid)
{
    DensityRaster.GetIntGridValue(X, Y, 0, 0, Value);
}
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = Valid && ValidRT ? clamp((int)(((float)X + 0.5f) * RTW / RW), 0, RTW - 1) : 0;
int DstY = Valid && ValidRT ? clamp((int)(((float)Y + 0.5f) * RTH / RH), 0, RTH - 1) : 0;
float Density = (float)Value / 1024.0f;
SimRT.SetRenderTargetValue(
    Valid && ValidRT, DstX, DstY,
    float4(Density, Density, Density, Density));
OutMark = Density;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, node_id, code
):
    raise RuntimeError("Failed to install same-stage atomic probe")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if SYSTEM in path and data_interface.get_class().get_name() == "NiagaraDataInterfaceRasterizationGrid3D":
        data_interface.set_editor_property("num_cells", unreal.IntVector(2048, 2048, 1))
        data_interface.set_editor_property("clear_before_non_iteration_stage", False)
print("V2_SAME_STAGE_ATOMIC=" + json.dumps({
    "applied": applied, "messages": messages
}, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Same-stage atomic probe failed")
