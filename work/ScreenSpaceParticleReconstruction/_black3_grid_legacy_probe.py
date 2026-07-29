import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

probe_code = r"""
int W = 256;
int H = 256;
int IgnoreValue = 0;
for (int OffsetY = -8; OffsetY <= 8; ++OffsetY)
{
    for (int OffsetX = -8; OffsetX <= 8; ++OffsetX)
    {
        int WriteX = W / 2 + OffsetX;
        int WriteY = H / 2 + OffsetY;
        OccupancyGrid.SetGridValue(
            WriteX, WriteY, 0, 1.0f, IgnoreValue);
    }
}
OutDummy = (float)(IgnoreValue + 1);
""".strip()

if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE, probe_code
):
    raise RuntimeError("Failed to install legacy Grid2D probe")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
print(
    "LEGACY_GRID_PROBE="
    + json.dumps(
        {"applied": applied, "messages": messages}, sort_keys=True
    )
)
if not applied or messages:
    raise RuntimeError("Legacy Grid2D probe compile failed")
