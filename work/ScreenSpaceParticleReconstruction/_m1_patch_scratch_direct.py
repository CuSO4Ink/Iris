import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
SERVICE = unreal.NiagaraScratchPadService

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


def pins(module_name, node_id):
    return SERVICE.get_node_pins(SYSTEM, EMITTER, module_name, node_id)


def connections(module_name):
    return SERVICE.list_connections(SYSTEM, EMITTER, module_name)


def has_pin(module_name, node_id, direction, pin_name):
    for pin in pins(module_name, node_id):
        if str(pin.direction) == direction and str(pin.pin_name) == pin_name:
            return True
    return False


def ensure_pin(module_name, node_id, direction, type_name, pin_name):
    if has_pin(module_name, node_id, direction, pin_name):
        return False
    result = SERVICE.add_pin(
        SYSTEM, EMITTER, module_name, node_id, direction, type_name, pin_name)
    if not result.success:
        raise RuntimeError("AddPin failed for {}/{}: {}".format(
            module_name, pin_name, result.message))
    if not has_pin(module_name, node_id, direction, pin_name):
        raise RuntimeError("Pin readback failed for {}/{}".format(module_name, pin_name))
    return True


def has_connection(module_name, from_node, from_pin, to_node, to_pin):
    for connection in connections(module_name):
        if (str(connection.from_node_id) == from_node and
                str(connection.from_pin) == from_pin and
                str(connection.to_node_id) == to_node and
                str(connection.to_pin) == to_pin):
            return True
    return False


def ensure_connection(module_name, from_node, from_pin, to_node, to_pin):
    if has_connection(module_name, from_node, from_pin, to_node, to_pin):
        return False
    if not SERVICE.connect_pins(
            SYSTEM, EMITTER, module_name,
            from_node, from_pin, to_node, to_pin):
        raise RuntimeError("ConnectPins failed for {}/{} -> {}".format(
            module_name, from_pin, to_pin))
    if not has_connection(module_name, from_node, from_pin, to_node, to_pin):
        raise RuntimeError("Connection readback failed for {}/{} -> {}".format(
            module_name, from_pin, to_pin))
    return True


def set_hlsl(module_name, node_id, code):
    if not SERVICE.set_custom_hlsl_code(
            SYSTEM, EMITTER, module_name, node_id, code):
        raise RuntimeError("SetCustomHlslCode failed for " + module_name)
    stored = SERVICE.get_custom_hlsl_code(
        SYSTEM, EMITTER, module_name, node_id)
    if str(stored).strip() != code.strip():
        raise RuntimeError("HLSL readback mismatch for " + module_name)


added_pins = 0
added_connections = 0

# Spawn initialization defines the custom screen-velocity attribute on every path.
added_pins += int(ensure_pin(
    INIT_MODULE, INIT_HLSL, "Output", "vec2", "OutScreenVelocityUV"))
added_pins += int(ensure_pin(
    INIT_MODULE, INIT_MAPSET, "Input", "vec2", "Particles.SSPR_ScreenVelocityUV"))
added_connections += int(ensure_connection(
    INIT_MODULE,
    INIT_HLSL, "OutScreenVelocityUV",
    INIT_MAPSET, "Particles.SSPR_ScreenVelocityUV"))

# Projection reads solved velocity and publishes normalized screen motion per second.
added_pins += int(ensure_pin(
    PROJ_MODULE, PROJ_MAPGET, "Output", "vec3", "Particles.Velocity"))
added_pins += int(ensure_pin(
    PROJ_MODULE, PROJ_HLSL, "Input", "vec3", "WorldVelocity"))
added_pins += int(ensure_pin(
    PROJ_MODULE, PROJ_HLSL, "Output", "vec2", "OutScreenVelocityUV"))
added_pins += int(ensure_pin(
    PROJ_MODULE, PROJ_MAPSET, "Input", "vec2", "Particles.SSPR_ScreenVelocityUV"))
added_connections += int(ensure_connection(
    PROJ_MODULE,
    PROJ_MAPGET, "Particles.Velocity",
    PROJ_HLSL, "WorldVelocity"))
added_connections += int(ensure_connection(
    PROJ_MODULE,
    PROJ_HLSL, "OutScreenVelocityUV",
    PROJ_MAPSET, "Particles.SSPR_ScreenVelocityUV"))

# Writer converts normalized motion with the live RT dimensions.
added_pins += int(ensure_pin(
    WRITE_MODULE, WRITE_MAPGET, "Output", "vec2", "Particles.SSPR_ScreenVelocityUV"))
added_pins += int(ensure_pin(
    WRITE_MODULE, WRITE_HLSL, "Input", "vec2", "ScreenVelocityUV"))
added_connections += int(ensure_connection(
    WRITE_MODULE,
    WRITE_MAPGET, "Particles.SSPR_ScreenVelocityUV",
    WRITE_HLSL, "ScreenVelocityUV"))

INIT_CODE = """OutUV = float2(0.0f, 0.0f);
OutDepth = 0.0f;
OutMark = 0.0f;
OutScreenVelocityUV = float2(0.0f, 0.0f);"""

PROJECTION_CODE = """// SSPR world-to-screen projection plus frame-rate-independent particle motion.
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
OutColor = float4(saturate(uv0.x) * dim, saturate(uv0.y) * dim, depthN * dim, 1.0f);"""

WRITER_CODE = """// M1 validation constants for a binary, velocity-aligned capsule mask.
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

OutDummy = (validSize && validUV) ? 1.0f : 0.0f;"""

set_hlsl(INIT_MODULE, INIT_HLSL, INIT_CODE)
set_hlsl(PROJ_MODULE, PROJ_HLSL, PROJECTION_CODE)
set_hlsl(WRITE_MODULE, WRITE_HLSL, WRITER_CODE)

summary = {
    "addedPins": added_pins,
    "addedConnections": added_connections,
    "initHlslPins": len(pins(INIT_MODULE, INIT_HLSL)),
    "projectionHlslPins": len(pins(PROJ_MODULE, PROJ_HLSL)),
    "writerHlslPins": len(pins(WRITE_MODULE, WRITE_HLSL)),
}
print("M1_PATCH_RESULT=" + json.dumps(summary, sort_keys=True))
