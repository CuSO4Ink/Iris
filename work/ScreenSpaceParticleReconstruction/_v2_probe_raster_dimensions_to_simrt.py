import json
import unreal

SYSTEM = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
EMITTER = "Fountain"
MODULE = "SSPR_ResolveGridToSimRT"
SERVICE = unreal.NiagaraScratchPadService
node_id = next(str(node.node_id) for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE) if str(node.node_type) == "CustomHlsl")
code = r"""int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int X = 0;
int Y = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(X, Y);
int RW = 0;
int RH = 0;
int RD = 0;
DensityRaster.GetNumCells(RW, RH, RD);
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = ValidRT ? clamp((int)(((float)X + 0.5f) * RTW / max(W, 1)), 0, RTW - 1) : 0;
int DstY = ValidRT ? clamp((int)(((float)Y + 0.5f) * RTH / max(H, 1)), 0, RTH - 1) : 0;
float IsConfigured = (RW == 2048 && RH == 2048 && RD == 1) ? 1.0f : 0.0f;
float IsAllocated = (RW > 0 && RH > 0 && RD > 0) ? 1.0f : 0.0f;
SimRT.SetRenderTargetValue(ValidRT, DstX, DstY, float4(IsConfigured, IsAllocated, 0.0f, 1.0f));
OutMark = (float)RW;"""
if not SERVICE.set_custom_hlsl_code(SYSTEM, EMITTER, MODULE, node_id, code):
    raise RuntimeError("Failed to install raster dimensions probe")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
print("V2_RASTER_DIMENSIONS_PROBE=" + json.dumps({"applied": applied, "messages": messages}, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Raster dimensions probe failed")
