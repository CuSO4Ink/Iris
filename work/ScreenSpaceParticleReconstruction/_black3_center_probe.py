import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

old_code = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))
probe_code = r"""
int W = 1;
int H = 1;
OccupancyGrid.GetNumCells(W, H);
int2 center = int2(max(W / 2, 0), max(H / 2, 0));
for (int offsetY = -8; offsetY <= 8; ++offsetY)
{
    for (int offsetX = -8; offsetX <= 8; ++offsetX)
    {
        int2 writePx = center + int2(offsetX, offsetY);
        if (writePx.x >= 0 && writePx.x < W &&
            writePx.y >= 0 && writePx.y < H)
        {
            OccupancyGrid.SetValueAtIndex(
                writePx.x, writePx.y, 0, 1.0f);
        }
    }
}
OutDummy = 1.0f;
""".strip()

if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL_NODE, probe_code):
    raise RuntimeError("Failed to install center probe HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
stored = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))
print("CENTER_PROBE=" + json.dumps({
    "applied": applied,
    "messages": messages,
    "oldLength": len(old_code),
    "stored": stored == probe_code,
}, sort_keys=True))
if not applied or messages or stored != probe_code:
    raise RuntimeError("Center probe verification failed")
