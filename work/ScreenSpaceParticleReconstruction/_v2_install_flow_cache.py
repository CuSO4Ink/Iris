import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
SYSTEM_PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService


def require(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))
    return str(result.node_id)


def node_ids(module):
    nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, module))
    return {
        "hlsl": next(
            str(node.node_id)
            for node in nodes
            if str(node.node_type) == "CustomHlsl"
        ),
        "map_get": next(
            str(node.node_id)
            for node in nodes
            if str(node.node_type) == "MapGet"
        ),
    }


def pin_names(module, node_id):
    return {
        str(pin.pin_name)
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, module, node_id
        )
    }


def ensure_pin(module, node_id, direction, type_name, pin_name):
    if pin_name in pin_names(module, node_id):
        return False
    require(
        SERVICE.add_pin(
            SYSTEM,
            EMITTER,
            module,
            node_id,
            direction,
            type_name,
            pin_name,
        ),
        "Add pin {}/{}".format(module, pin_name),
    )
    return True


def connections(module):
    return {
        (
            str(item.from_node_id),
            str(item.from_pin),
            str(item.to_node_id),
            str(item.to_pin),
        )
        for item in SERVICE.list_connections(SYSTEM, EMITTER, module)
    }


def ensure_connection(module, from_node, from_pin, to_node, to_pin):
    wanted = (from_node, from_pin, to_node, to_pin)
    if wanted in connections(module):
        return False
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        module,
        from_node,
        from_pin,
        to_node,
        to_pin,
    ):
        raise RuntimeError(
            "Connect failed in {}: {} -> {}".format(
                module, from_pin, to_pin
            )
        )
    return True


changes = []

# Spawn initializes every custom attribute used by the GPU layout.
init_module = "SSPR_InitAttrs"
init_nodes = node_ids(init_module)
init_hlsl = init_nodes["hlsl"]
for type_name, pin_name in (
    ("Vector", "OutFlowDelta"),
    ("Vector", "OutFlowVelocity"),
    ("vec2", "OutScreenDeltaUV"),
):
    if ensure_pin(init_module, init_hlsl, "Output", type_name, pin_name):
        changes.append("init-pin:" + pin_name)

init_map_set = None
for output_name, type_name, hlsl_pin in (
    ("Particles.SSPR_FlowDelta", "Vector", "OutFlowDelta"),
    ("Particles.SSPR_FlowVelocity", "Vector", "OutFlowVelocity"),
    ("Particles.SSPR_ScreenDeltaUV", "vec2", "OutScreenDeltaUV"),
):
    init_map_set = require(
        SERVICE.add_module_output(
            SYSTEM,
            EMITTER,
            init_module,
            output_name,
            type_name,
        ),
        "Add init output " + output_name,
    )
    if ensure_connection(
        init_module, init_hlsl, hlsl_pin, init_map_set, output_name
    ):
        changes.append("init-output:" + output_name)

init_code = """// Stable defaults for custom particle attributes.
OutUV = float2(-1.0f, -1.0f);
OutDepth = 0.0f;
OutMark = 0.0f;
OutScreenVelocityUV = float2(0.0f, 0.0f);
OutFlowDelta = float3(0.0f, 0.0f, 0.0f);
OutFlowVelocity = float3(0.0f, 0.0f, 0.0f);
OutScreenDeltaUV = float2(0.0f, 0.0f);"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, init_module, init_hlsl, init_code
):
    raise RuntimeError("Failed to update SSPR_InitAttrs HLSL")

# This module already runs after Solve Forces and Velocity and before the
# dedicated velocity reset. Cache motion here so later stages never read the
# zeroed Particles.Velocity.
projection_module = "SSPR_Projection"
projection_nodes = node_ids(projection_module)
projection_hlsl = projection_nodes["hlsl"]
projection_map_get = projection_nodes["map_get"]

if ensure_pin(
    projection_module,
    projection_map_get,
    "Output",
    "float",
    "Engine.DeltaTime",
):
    changes.append("projection-mapget:Engine.DeltaTime")
if ensure_pin(
    projection_module,
    projection_hlsl,
    "Input",
    "float",
    "DeltaSeconds",
):
    changes.append("projection-pin:DeltaSeconds")
for type_name, pin_name in (
    ("Vector", "OutFlowDelta"),
    ("Vector", "OutFlowVelocity"),
    ("vec2", "OutScreenDeltaUV"),
):
    if ensure_pin(
        projection_module,
        projection_hlsl,
        "Output",
        type_name,
        pin_name,
    ):
        changes.append("projection-pin:" + pin_name)

ensure_connection(
    projection_module,
    projection_map_get,
    "Engine.DeltaTime",
    projection_hlsl,
    "DeltaSeconds",
)

projection_map_set = None
for output_name, type_name, hlsl_pin in (
    ("Particles.SSPR_FlowDelta", "Vector", "OutFlowDelta"),
    ("Particles.SSPR_FlowVelocity", "Vector", "OutFlowVelocity"),
    ("Particles.SSPR_ScreenDeltaUV", "vec2", "OutScreenDeltaUV"),
):
    projection_map_set = require(
        SERVICE.add_module_output(
            SYSTEM,
            EMITTER,
            projection_module,
            output_name,
            type_name,
        ),
        "Add projection output " + output_name,
    )
    ensure_connection(
        projection_module,
        projection_hlsl,
        hlsl_pin,
        projection_map_set,
        output_name,
    )

projection_code = r"""// Cache post-solver motion before the following reset module.
float SafeDt = max(DeltaSeconds, 0.00001f);
OutFlowVelocity = WorldVelocity;
OutFlowDelta = WorldVelocity * SafeDt;

float4 clip0 = mul(float4(WorldPos, 1.0f), View.WorldToClip);
OutDepth = clip0.w;
bool inFront0 = clip0.w > 0.0001f;
float2 ndc0 = inFront0 ? clip0.xy / clip0.w : float2(0.0f, 0.0f);
float2 uv0 = ndc0 * float2(0.5f, -0.5f) + 0.5f;
bool onScreen = inFront0 &&
    uv0.x >= 0.0f && uv0.x < 1.0f &&
    uv0.y >= 0.0f && uv0.y < 1.0f;

float3 previousWorldPos = WorldPos - OutFlowDelta;
float4 clipPrev = mul(float4(previousWorldPos, 1.0f), View.WorldToClip);
bool inFrontPrev = clipPrev.w > 0.0001f;
float2 ndcPrev = inFrontPrev
    ? clipPrev.xy / clipPrev.w
    : ndc0;
float2 uvPrev = ndcPrev * float2(0.5f, -0.5f) + 0.5f;

OutUV = onScreen ? uv0 : float2(-1.0f, -1.0f);
OutScreenDeltaUV = (onScreen && inFrontPrev)
    ? (uv0 - uvPrev)
    : float2(0.0f, 0.0f);
OutScreenVelocityUV = OutScreenDeltaUV / SafeDt;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    projection_module,
    projection_hlsl,
    projection_code,
):
    raise RuntimeError("Failed to update SSPR_Projection HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False))

result = {
    "changes": changes,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
    "projectionHlsl": str(
        SERVICE.get_custom_hlsl_code(
            SYSTEM, EMITTER, projection_module, projection_hlsl
        )
    ),
}
print("V2_FLOW_CACHE=" + json.dumps(result, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("V2 flow cache gate failed: " + repr(result))
