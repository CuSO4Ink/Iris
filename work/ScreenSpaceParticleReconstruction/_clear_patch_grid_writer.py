import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
MAP_GET = "F14AAFE54D15241C4D7D1CB3D77D2761"
HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService


def pins(node_id):
    return SERVICE.get_node_pins(SYSTEM, EMITTER, MODULE, node_id)


def pin_exists(node_id, direction, pin_name, type_fragment=None):
    for pin in pins(node_id):
        if str(pin.direction) != direction or str(pin.pin_name) != pin_name:
            continue
        if type_fragment and type_fragment not in str(pin.type_name):
            continue
        return True
    return False


def connections():
    return SERVICE.list_connections(SYSTEM, EMITTER, MODULE)


def connection_exists(from_node, from_pin, to_node, to_pin):
    for connection in connections():
        if (str(connection.from_node_id) == from_node and
                str(connection.from_pin) == from_pin and
                str(connection.to_node_id) == to_node and
                str(connection.to_pin) == to_pin):
            return True
    return False


# Preconditions: this is the visually verified M1 writer, not an unknown graph.
old_code = str(SERVICE.get_custom_hlsl_code(SYSTEM, EMITTER, MODULE, HLSL))
if "OccupancyRT.SetRenderTargetValue" not in old_code:
    raise RuntimeError("Writer precondition failed: expected RenderTarget2D scatter code")
if not pin_exists(HLSL, "Input", "OccupancyRT", "RenderTarget2D"):
    raise RuntimeError("Writer precondition failed: OccupancyRT HLSL input missing")
if not pin_exists(MAP_GET, "Output", "Particles.SSPR_ScreenUV"):
    raise RuntimeError("Writer precondition failed: ScreenUV MapGet output missing")
if not pin_exists(MAP_GET, "Output", "Particles.SSPR_ScreenVelocityUV"):
    raise RuntimeError("Writer precondition failed: ScreenVelocityUV MapGet output missing")

added_module_input = False
if not pin_exists(MAP_GET, "Output", "Module.OccupancyGrid", "Grid2DCollection"):
    result = SERVICE.add_module_input(
        SYSTEM, EMITTER, MODULE, "OccupancyGrid", "Grid2D")
    if not result.success:
        raise RuntimeError("AddModuleInput failed: " + str(result.message))
    added_module_input = True

added_hlsl_pin = False
if not pin_exists(HLSL, "Input", "OccupancyGrid", "Grid2DCollection"):
    result = SERVICE.add_pin(
        SYSTEM, EMITTER, MODULE, HLSL, "Input", "Grid2D", "OccupancyGrid")
    if not result.success:
        raise RuntimeError("AddPin failed: " + str(result.message))
    added_hlsl_pin = True

added_connection = False
if not connection_exists(MAP_GET, "Module.OccupancyGrid", HLSL, "OccupancyGrid"):
    if not SERVICE.connect_pins(
            SYSTEM, EMITTER, MODULE,
            MAP_GET, "Module.OccupancyGrid", HLSL, "OccupancyGrid"):
        raise RuntimeError("ConnectPins failed for OccupancyGrid")
    added_connection = True

writer_code = r"""// M1 binary velocity-aligned capsule mask, written into an auto-cleared Grid2D.
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
                OccupancyGrid.SetFloatValue<Attribute=Occupancy>(
                    writePx.x, writePx.y, 1.0f);
            }
        }
    }
}

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;"""

if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL, writer_code):
    raise RuntimeError("SetCustomHlslCode failed")

stored_code = str(SERVICE.get_custom_hlsl_code(SYSTEM, EMITTER, MODULE, HLSL))
if stored_code.strip() != writer_code.strip():
    raise RuntimeError("HLSL readback mismatch")
if not connection_exists(MAP_GET, "Module.OccupancyGrid", HLSL, "OccupancyGrid"):
    raise RuntimeError("OccupancyGrid connection readback failed")

applied = SERVICE.apply_changes(SYSTEM)
messages = [str(x) for x in SERVICE.get_compile_messages(SYSTEM, False)]

summary = {
    "addedModuleInput": added_module_input,
    "addedHlslPin": added_hlsl_pin,
    "addedConnection": added_connection,
    "applied": bool(applied),
    "compileMessages": messages,
    "hlslPinCount": len(pins(HLSL)),
}
print("CLEAR_GRID_PATCH=" + json.dumps(summary, sort_keys=True))

if not applied or messages:
    raise RuntimeError("Grid writer compile failed: " + " | ".join(messages))
