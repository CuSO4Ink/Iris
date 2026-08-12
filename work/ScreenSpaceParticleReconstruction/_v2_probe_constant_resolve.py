import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_ResolveGridToSimRT"
SERVICE = unreal.NiagaraScratchPadService

hlsl_node = next(
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
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool Valid = W > 0 && H > 0 && RTW > 0 && RTH > 0;
int DstX = Valid ? clamp((int)(((float)X + 0.5f) * RTW / W), 0, RTW - 1) : 0;
int DstY = Valid ? clamp((int)(((float)Y + 0.5f) * RTH / H), 0, RTH - 1) : 0;
SimRT.SetRenderTargetValue(Valid, DstX, DstY, float4(1.0f, 1.0f, 1.0f, 1.0f));
OutMark = Valid ? 1.0f : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl_node, code
):
    raise RuntimeError("Failed to install constant resolve probe")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
print("V2_CONSTANT_RESOLVE=" + json.dumps({
    "applied": applied,
    "messages": messages,
}, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Constant resolve probe failed")
