import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

writer_code = r"""
// M2-A current-frame writer. This stage is intentionally stateless:
// it only writes current velocity-aligned capsules into the render target.
// Clear, temporal reprojection, decay and ping-pong are owned by the
// orchestrator and the temporal material pass.
const float TrailTime = 0.040f;
const float MaxTrailPx = 12.0f;
const float RadiusPx = 1.5f;
const int MaxTrailSteps = 12;
const int RadiusSteps = 2;

int W = 1;
int H = 1;
OccupancyRT.GetRenderTargetSize(W, H);

bool validSize = (W > 0 && H > 0);
bool validUV = (ScreenUV.x >= 0.0f && ScreenUV.x < 1.0f &&
                ScreenUV.y >= 0.0f && ScreenUV.y < 1.0f);
int safeW = max(W, 1);
int safeH = max(H, 1);
float2 rtSize = float2(safeW, safeH);
float2 headPx = saturate(ScreenUV) * rtSize;
float2 velocityPx = ScreenVelocityUV * rtSize;
float speedPx = length(velocityPx);
float2 tangent = (speedPx > 0.001f)
    ? (velocityPx / speedPx)
    : float2(0.0f, 0.0f);
float trailPx = clamp(speedPx * TrailTime, 0.0f, MaxTrailPx);
int activeSteps = min((int)ceil(trailPx), MaxTrailSteps);

for (int stepIndex = 0; stepIndex <= MaxTrailSteps; ++stepIndex)
{
    bool activeStep =
        validSize && validUV && (stepIndex <= activeSteps);
    float stepDistance = min((float)stepIndex, trailPx);
    int2 centerPx = int2(floor(headPx - tangent * stepDistance));

    for (int offsetY = -RadiusSteps; offsetY <= RadiusSteps; ++offsetY)
    {
        for (int offsetX = -RadiusSteps; offsetX <= RadiusSteps; ++offsetX)
        {
            float2 offset = float2(offsetX, offsetY);
            int2 writePx = centerPx + int2(offsetX, offsetY);
            bool shouldDraw = activeStep &&
                (dot(offset, offset) <= RadiusPx * RadiusPx) &&
                (writePx.x >= 0 && writePx.x < safeW &&
                 writePx.y >= 0 && writePx.y < safeH);
            OccupancyRT.SetRenderTargetValue(
                shouldDraw,
                writePx.x,
                writePx.y,
                float4(1.0f, 0.0f, 0.0f, 1.0f));
        }
    }
}

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;
""".strip()

if not SERVICE.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    MODULE,
    HLSL_NODE,
    writer_code,
):
    raise RuntimeError("Failed to install the M2-A Current writer")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
stored = str(
    SERVICE.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
result = {
    "applied": applied,
    "messages": messages,
    "saved": saved,
    "stored": stored == writer_code,
    "containsLoad": "LoadRenderTargetValue" in stored,
    "containsDecay": "Decay" in stored,
}
print("M2A_CURRENT_WRITER=" + json.dumps(result, sort_keys=True))
if (
    not applied
    or messages
    or not result["stored"]
    or result["containsLoad"]
    or result["containsDecay"]
):
    raise RuntimeError("M2-A Current writer verification failed: " + repr(result))
