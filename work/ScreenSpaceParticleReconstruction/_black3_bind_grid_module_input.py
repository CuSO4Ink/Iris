import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

writer_code = r"""
// Binary velocity-aligned capsule mask, written into an auto-cleared Grid2D.
const float TrailTime = 0.040f;
const float MaxTrailPx = 12.0f;
const float RadiusPx = 1.5f;
const int MaxTrailSteps = 12;
const int RadiusSteps = 2;

int W = 1;
int H = 1;
OccupancyGrid.GetNumCells(W, H);

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
    bool activeStep = validSize && validUV && (stepIndex <= activeSteps);
    float stepDistance = min((float)stepIndex, trailPx);
    float2 centerPxF = headPx - tangent * stepDistance;
    int2 centerPx = int2(floor(centerPxF));

    for (int offsetY = -RadiusSteps; offsetY <= RadiusSteps; ++offsetY)
    {
        for (int offsetX = -RadiusSteps; offsetX <= RadiusSteps; ++offsetX)
        {
            float2 offset = float2(offsetX, offsetY);
            bool insideDisc = dot(offset, offset) <= (RadiusPx * RadiusPx);
            int2 writePx = centerPx + int2(offsetX, offsetY);
            bool inBounds = (writePx.x >= 0 && writePx.x < safeW &&
                             writePx.y >= 0 && writePx.y < safeH);
            bool shouldWrite = activeStep && insideDisc && inBounds;
            if (shouldWrite)
            {
                OccupancyGrid.SetValueAtIndex(
                    writePx.x, writePx.y, 0, 1.0f);
            }
        }
    }
}

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;
""".strip()

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
map_gets = [str(node.node_id) for node in nodes if str(node.node_type) == "MapGet"]
if len(map_gets) != 1:
    raise RuntimeError("Expected exactly one MapGet: " + repr(map_gets))
map_get = map_gets[0]

pin_names = {
    str(pin.pin_name)
    for pin in SERVICE.get_node_pins(SYSTEM, EMITTER, MODULE, map_get)
}
if "Module.OccupancyGrid" not in pin_names:
    added = SERVICE.add_module_input(
        SYSTEM, EMITTER, MODULE, "OccupancyGrid", "Grid2D"
    )
    if not added.success:
        raise RuntimeError("Failed to add Module.OccupancyGrid: " + str(added.message))
    map_get = str(added.node_id)

if not SERVICE.disconnect_pin(
        SYSTEM, EMITTER, MODULE, HLSL_NODE, "OccupancyGrid"):
    raise RuntimeError("Failed to disconnect old OccupancyGrid binding")
if not SERVICE.connect_pins(
        SYSTEM, EMITTER, MODULE,
        map_get, "Module.OccupancyGrid", HLSL_NODE, "OccupancyGrid"):
    raise RuntimeError("Failed to bind Module.OccupancyGrid")
if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL_NODE, writer_code):
    raise RuntimeError("Failed to restore Grid2D writer HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
connections = [
    (str(item.from_node_id), str(item.from_pin),
     str(item.to_node_id), str(item.to_pin))
    for item in SERVICE.list_connections(SYSTEM, EMITTER, MODULE)
]
expected = (map_get, "Module.OccupancyGrid", HLSL_NODE, "OccupancyGrid")
result = {
    "applied": applied,
    "messages": messages,
    "mapGet": map_get,
    "moduleGridConnected": expected in connections,
    "storedWriter": str(SERVICE.get_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL_NODE
    )) == writer_code,
}
print("GRID_MODULE_INPUT=" + json.dumps(result, sort_keys=True))
if (not applied or messages or not result["moduleGridConnected"] or
        not result["storedWriter"]):
    raise RuntimeError("Grid module input patch verification failed")
