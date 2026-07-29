import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

probe_code = r"""
int W = 1;
int H = 1;
OccupancyRT.GetRenderTargetSize(W, H);
for (int offsetY = -8; offsetY <= 8; ++offsetY)
{
    for (int offsetX = -8; offsetX <= 8; ++offsetX)
    {
        int writeX = W / 2 + offsetX;
        int writeY = H / 2 + offsetY;
        bool inBounds = writeX >= 0 && writeX < W &&
                        writeY >= 0 && writeY < H;
        OccupancyRT.SetRenderTargetValue(
            inBounds, writeX, writeY,
            float4(1.0f, 0.0f, 0.0f, 1.0f));
    }
}
OutDummy = 1.0f;
""".strip()

if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL_NODE, probe_code):
    raise RuntimeError("Failed to install direct RT probe HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
stored = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))
print("DIRECT_RT_PROBE=" + json.dumps({
    "applied": applied,
    "messages": messages,
    "stored": stored == probe_code,
}, sort_keys=True))
if not applied or messages or stored != probe_code:
    raise RuntimeError("Direct RT probe verification failed")
