import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
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
TrajectoryGrid.GetNumCells(W, H);
bool Valid = W > 0 && H > 0;
if (Valid)
{
    TrajectoryGrid.SetValueAtIndex(W / 2, H / 2, 0, 1.0f);
}
OutMark = Valid ? 1.0f : 0.0f;"""

resolve = r"""int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int X = 0;
int Y = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(X, Y);
float Density = 0.0f;
bool Valid = W > 0 && H > 0 && X >= 0 && X < W && Y >= 0 && Y < H;
if (Valid)
{
    TrajectoryGrid.GetGridValue(X, Y, 0, Density);
}
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = Valid && ValidRT ? clamp((int)(((float)X + 0.5f) * RTW / W), 0, RTW - 1) : 0;
int DstY = Valid && ValidRT ? clamp((int)(((float)Y + 0.5f) * RTH / H), 0, RTH - 1) : 0;
SimRT.SetRenderTargetValue(Valid && ValidRT, DstX, DstY, float4(Density, Density, Density, Density));
OutMark = Density;"""

if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, "SSPR_RasterizeWhiteParticles",
    hlsl_node("SSPR_RasterizeWhiteParticles"), writer,
):
    raise RuntimeError("Failed to install Grid particle-stage probe")
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, "SSPR_ResolveGridToSimRT",
    hlsl_node("SSPR_ResolveGridToSimRT"), resolve,
):
    raise RuntimeError("Failed to install Grid resolve probe")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
print("V2_PARTICLE_STAGE_GRID_PROBE=" + json.dumps({
    "applied": applied,
    "messages": messages,
}, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Particle-stage Grid probe failed")
