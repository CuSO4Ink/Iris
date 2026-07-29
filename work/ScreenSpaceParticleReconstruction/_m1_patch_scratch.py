import json

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"

INIT_MODULE = "SSPR_InitAttrs"
INIT_HLSL = "A181B6A4442D33585E77549D8D842E03"
INIT_MAPSET = "AAF4A4F34C72C0DBD9B765B862231DF0"

PROJ_MODULE = "SSPR_Projection"
PROJ_MAPGET = "B47EA575449F2A202ABE6A81F7C87E33"
PROJ_HLSL = "E20AC4B842762D7503A03887C05B7CE8"
PROJ_MAPSET = "AAF4A4F34C72C0DBD9B765B862231DF0"

WRITE_MODULE = "SSPR_WriteOccupancy"
WRITE_MAPGET = "F14AAFE54D15241C4D7D1CB3D77D2761"
WRITE_HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"


def call(tool_name, arguments):
    return execute_tool(tool_name, json.dumps(arguments))


def get_pins(module_name, node_id):
    result = call("VibeUE.NiagaraScratchPadService.GetNodePins", {
        "systemPath": SYSTEM,
        "emitterName": EMITTER,
        "moduleName": module_name,
        "nodeId": node_id,
    })
    return result["returnValue"]


def get_connections(module_name):
    result = call("VibeUE.NiagaraScratchPadService.ListConnections", {
        "systemPath": SYSTEM,
        "emitterName": EMITTER,
        "moduleName": module_name,
    })
    return result["returnValue"]


def has_pin(module_name, node_id, direction, pin_name):
    for pin in get_pins(module_name, node_id):
        if pin["direction"] == direction and pin["pinName"] == pin_name:
            return True
    return False


def ensure_pin(module_name, node_id, direction, type_name, pin_name):
    if has_pin(module_name, node_id, direction, pin_name):
        return False
    call("VibeUE.NiagaraScratchPadService.AddPin", {
        "systemPath": SYSTEM,
        "emitterName": EMITTER,
        "moduleName": module_name,
        "nodeId": node_id,
        "direction": direction,
        "typeName": type_name,
        "pinName": pin_name,
    })
    if not has_pin(module_name, node_id, direction, pin_name):
        raise RuntimeError("Pin was not created: " + module_name + "/" + pin_name)
    return True


def has_connection(module_name, from_node, from_pin, to_node, to_pin):
    for connection in get_connections(module_name):
        if (connection["fromNodeId"] == from_node and
                connection["fromPin"] == from_pin and
                connection["toNodeId"] == to_node and
                connection["toPin"] == to_pin):
            return True
    return False


def ensure_connection(module_name, from_node, from_pin, to_node, to_pin):
    if has_connection(module_name, from_node, from_pin, to_node, to_pin):
        return False
    result = call("VibeUE.NiagaraScratchPadService.ConnectPins", {
        "systemPath": SYSTEM,
        "emitterName": EMITTER,
        "moduleName": module_name,
        "fromNodeId": from_node,
        "fromPin": from_pin,
        "toNodeId": to_node,
        "toPin": to_pin,
    })
    if not result["returnValue"]:
        raise RuntimeError("ConnectPins returned false: " + module_name + "/" + from_pin + " -> " + to_pin)
    if not has_connection(module_name, from_node, from_pin, to_node, to_pin):
        raise RuntimeError("Connection was not created: " + module_name + "/" + from_pin + " -> " + to_pin)
    return True


def set_hlsl(module_name, node_id, code):
    result = call("VibeUE.NiagaraScratchPadService.SetCustomHlslCode", {
        "systemPath": SYSTEM,
        "emitterName": EMITTER,
        "moduleName": module_name,
        "nodeId": node_id,
        "code": code,
    })
    if not result["returnValue"]:
        raise RuntimeError("SetCustomHlslCode returned false: " + module_name)


def run():
    added_pins = 0
    added_connections = 0

    # Spawn initialization keeps the custom particle attribute defined on all paths.
    added_pins += int(ensure_pin(INIT_MODULE, INIT_HLSL, "Output", "vec2", "OutScreenVelocityUV"))
    added_pins += int(ensure_pin(INIT_MODULE, INIT_MAPSET, "Input", "vec2", "Particles.SSPR_ScreenVelocityUV"))
    added_connections += int(ensure_connection(
        INIT_MODULE,
        INIT_HLSL, "OutScreenVelocityUV",
        INIT_MAPSET, "Particles.SSPR_ScreenVelocityUV"))

    # Projection reads solved particle velocity and publishes normalized screen motion per second.
    added_pins += int(ensure_pin(PROJ_MODULE, PROJ_MAPGET, "Output", "vec3", "Particles.Velocity"))
    added_pins += int(ensure_pin(PROJ_MODULE, PROJ_HLSL, "Input", "vec3", "WorldVelocity"))
    added_pins += int(ensure_pin(PROJ_MODULE, PROJ_HLSL, "Output", "vec2", "OutScreenVelocityUV"))
    added_pins += int(ensure_pin(PROJ_MODULE, PROJ_MAPSET, "Input", "vec2", "Particles.SSPR_ScreenVelocityUV"))
    added_connections += int(ensure_connection(
        PROJ_MODULE,
        PROJ_MAPGET, "Particles.Velocity",
        PROJ_HLSL, "WorldVelocity"))
    added_connections += int(ensure_connection(
        PROJ_MODULE,
        PROJ_HLSL, "OutScreenVelocityUV",
        PROJ_MAPSET, "Particles.SSPR_ScreenVelocityUV"))

    # The writer consumes normalized motion and converts it with the live RT dimensions.
    added_pins += int(ensure_pin(WRITE_MODULE, WRITE_MAPGET, "Output", "vec2", "Particles.SSPR_ScreenVelocityUV"))
    added_pins += int(ensure_pin(WRITE_MODULE, WRITE_HLSL, "Input", "vec2", "ScreenVelocityUV"))
    added_connections += int(ensure_connection(
        WRITE_MODULE,
        WRITE_MAPGET, "Particles.SSPR_ScreenVelocityUV",
        WRITE_HLSL, "ScreenVelocityUV"))

    set_hlsl(INIT_MODULE, INIT_HLSL, """OutUV = float2(0.0f, 0.0f);
OutDepth = 0.0f;
OutMark = 0.0f;
OutScreenVelocityUV = float2(0.0f, 0.0f);""")

    set_hlsl(PROJ_MODULE, PROJ_HLSL, """// SSPR world-to-screen projection plus frame-rate-independent particle motion.
const float ReferenceDt = 1.0f / 60.0f;

float4 clip0 = mul(float4(WorldPos, 1.0f), View.WorldToClip);
OutDepth = clip0.w;

bool inFront0 = (clip0.w > 0.0001f);
float2 ndc0 = inFront0 ? (clip0.xy / clip0.w) : float2(0.0f, 0.0f);
float2 uv0 = ndc0 * float2(0.5f, -0.5f) + 0.5f;
bool onScreen = inFront0 &&
    (uv0.x >= 0.0f && uv0.x < 1.0f && uv0.y >= 0.0f && uv0.y < 1.0f);

float3 futureWorldPos = WorldPos + WorldVelocity * ReferenceDt;
float4 clip1 = mul(float4(futureWorldPos, 1.0f), View.WorldToClip);
bool inFront1 = (clip1.w > 0.0001f);
float2 ndc1 = inFront1 ? (clip1.xy / clip1.w) : ndc0;
float2 uv1 = ndc1 * float2(0.5f, -0.5f) + 0.5f;

OutUV = onScreen ? uv0 : float2(-1.0f, -1.0f);
OutScreenVelocityUV = (onScreen && inFront1)
    ? ((uv1 - uv0) / ReferenceDt)
    : float2(0.0f, 0.0f);

float depthN = saturate(clip0.w / 5000.0f);
float dim = onScreen ? 1.0f : 0.25f;
OutColor = float4(saturate(uv0.x) * dim, saturate(uv0.y) * dim, depthN * dim, 1.0f);""")

    set_hlsl(WRITE_MODULE, WRITE_HLSL, """// M1 validation constants for a binary, velocity-aligned capsule mask.
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
            int safeX = clamp(writePx.x, 0, safeW - 1);
            int safeY = clamp(writePx.y, 0, safeH - 1);
            OccupancyRT.SetRenderTargetValue(
                shouldWrite,
                safeX,
                safeY,
                float4(1.0f, 0.0f, 0.0f, 1.0f));
        }
    }
}

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;""")

    return {
        "addedPins": added_pins,
        "addedConnections": added_connections,
        "initPinCount": len(get_pins(INIT_MODULE, INIT_HLSL)),
        "projectionPinCount": len(get_pins(PROJ_MODULE, PROJ_HLSL)),
        "writerPinCount": len(get_pins(WRITE_MODULE, WRITE_HLSL)),
    }
