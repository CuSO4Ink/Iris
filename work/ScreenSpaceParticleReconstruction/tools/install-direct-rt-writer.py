import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

writer_code = r"""
// Sparse screen-space occupancy. A frame-rotated, directionally unbiased
// decay pass touches the RT before current velocity-aligned capsules are
// drawn for downstream blur/convolution.
const float DecayMultiplier = 0.78f;
const int DecayPixelsPerParticle = 64;
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

// Spread a cheap whole-image fade across the current particle dispatch.
// The previous implementation decayed 64 consecutive linear addresses per
// particle. On a row-major RT those addresses become visible horizontal
// bands, especially when camera motion shifts the accumulated screen-space
// history. Use a frame-rotated permutation instead: for a 256x256 RT and
// roughly 1000 live particles it covers almost the entire image once per
// frame without a horizontal or vertical preference.
int totalPixels = safeW * safeH;
for (int decayIndex = 0;
     decayIndex < DecayPixelsPerParticle;
     ++decayIndex)
{
    uint sequenceIndex =
        (uint)ExecIndex() * (uint)DecayPixelsPerParticle +
        (uint)decayIndex +
        View.FrameNumber * 7919u;
    uint permutedIndex = sequenceIndex * 40503u;
    int linearPixel = (int)(permutedIndex % (uint)totalPixels);
    int decayX = linearPixel % safeW;
    int decayY = linearPixel / safeW;
    float4 oldValue = float4(0.0f, 0.0f, 0.0f, 0.0f);
    OccupancyRT.LoadRenderTargetValue(decayX, decayY, 0, oldValue);
    OccupancyRT.SetRenderTargetValue(
        validSize, decayX, decayY, oldValue * DecayMultiplier);
}

// Draw the current stamp. The red channel is the occupancy scalar; the
// preview therefore appears red while R16F exports as grayscale for material
// processing.
for (int stepIndex = 0; stepIndex <= MaxTrailSteps; ++stepIndex)
{
    bool activeStep = validSize && validUV && (stepIndex <= activeSteps);
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
                shouldDraw, writePx.x, writePx.y,
                float4(1.0f, 0.0f, 0.0f, 1.0f));
        }
    }
}

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;
""".strip()

if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE, writer_code
):
    raise RuntimeError("Failed to install direct RT occupancy writer")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
stored = str(
    SERVICE.get_custom_hlsl_code(SYSTEM, EMITTER, MODULE, HLSL_NODE)
)
result = {
    "applied": applied,
    "messages": messages,
    "saved": saved,
    "stored": stored == writer_code,
}
print("DIRECT_RT_WRITER=" + json.dumps(result, sort_keys=True))
if not applied or messages or not result["stored"]:
    raise RuntimeError("Direct RT writer verification failed: " + repr(result))
