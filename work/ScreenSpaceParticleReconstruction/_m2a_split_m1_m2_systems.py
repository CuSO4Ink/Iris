import json
import unreal

SOURCE_SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest"
M2_SYSTEM = "/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2"
BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

m1_writer = r"""
// M1 standalone preview writer. The persistent external RT has no native
// per-frame clear, so this debug path performs a directionally unbiased
// distributed fade before drawing the current velocity-aligned capsules.
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

m2_writer = r"""
// M2 current-frame writer. This path is deliberately stateless because
// BP_SSPR_TemporalOrchestrator owns Current clear, temporal decay and
// HistoryA/HistoryB ping-pong.
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


def install_writer(system_path, code):
    object_path = system_path + "." + system_path.rsplit("/", 1)[-1]
    if not SERVICE.set_custom_hlsl_code(
        object_path, EMITTER, MODULE, HLSL_NODE, code
    ):
        raise RuntimeError("Failed to set writer code on " + object_path)
    applied = bool(SERVICE.apply_changes(object_path))
    messages = [
        str(item)
        for item in SERVICE.get_compile_messages(object_path, False)
    ]
    saved = bool(unreal.EditorAssetLibrary.save_asset(system_path, False))
    stored = str(
        SERVICE.get_custom_hlsl_code(
            object_path, EMITTER, MODULE, HLSL_NODE
        )
    )
    result = {
        "objectPath": object_path,
        "applied": applied,
        "messages": messages,
        "saved": saved,
        "stored": stored == code,
        "hasLoad": "LoadRenderTargetValue" in stored,
    }
    if not applied or messages or not saved or not result["stored"]:
        raise RuntimeError("Writer install failed: " + repr(result))
    return result


if not unreal.EditorAssetLibrary.does_asset_exist(SOURCE_SYSTEM):
    raise RuntimeError("Source Niagara system is missing")

duplicated = False
if not unreal.EditorAssetLibrary.does_asset_exist(M2_SYSTEM):
    duplicated = bool(
        unreal.EditorAssetLibrary.duplicate_asset(SOURCE_SYSTEM, M2_SYSTEM)
    )
    if not duplicated:
        raise RuntimeError("Failed to duplicate the M2 Niagara system")

m2_result = install_writer(M2_SYSTEM, m2_writer)
m1_result = install_writer(SOURCE_SYSTEM, m1_writer)

component_result = bool(
    unreal.BlueprintService.set_component_property(
        BP_PATH,
        "SSPRNiagara",
        "Asset",
        M2_SYSTEM + ".NS_SSPR_ProjTest_M2",
    )
)
bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("Temporal orchestrator Blueprint is missing")
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
bp_status = str(bp.get_editor_property("status"))
bp_saved = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))

result = {
    "duplicatedM2": duplicated,
    "m1": m1_result,
    "m2": m2_result,
    "componentAssetSet": component_result,
    "blueprintStatus": bp_status,
    "blueprintSaved": bp_saved,
}
print("M1_M2_SPLIT=" + json.dumps(result, sort_keys=True))

if not component_result or not bp_saved or "ERROR" in bp_status.upper():
    raise RuntimeError("Blueprint update failed: " + repr(result))
