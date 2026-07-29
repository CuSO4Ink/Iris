import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/"
    "NS_SSPR_ProjTest_M2.NS_SSPR_ProjTest_M2"
)
SYSTEM_PACKAGE = "/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
service = unreal.NiagaraScratchPadService


def pin_names(node_id):
    return {
        str(pin.pin_name)
        for pin in service.get_node_pins(
            SYSTEM,
            EMITTER,
            MODULE,
            node_id,
        )
    }


def connection_tuples():
    return {
        (
            str(item.from_node_id),
            str(item.from_pin),
            str(item.to_node_id),
            str(item.to_pin),
        )
        for item in service.list_connections(SYSTEM, EMITTER, MODULE)
    }


nodes = service.list_nodes(SYSTEM, EMITTER, MODULE)
map_gets = [
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
]
if len(map_gets) != 1:
    raise RuntimeError("Expected exactly one Writer MapGet: " + repr(map_gets))
map_get = map_gets[0]

parameter_specs = (
    ("RadiusPx", 0.75),
    ("TrailTime", 0.075),
    ("MaxTrailPx", 20.0),
)
changes = {"moduleInputs": [], "hlslPins": [], "connections": []}
for name, _ in parameter_specs:
    module_pin = "Module." + name
    if module_pin not in pin_names(map_get):
        added = service.add_module_input(
            SYSTEM,
            EMITTER,
            MODULE,
            name,
            "float",
        )
        if not added.success:
            raise RuntimeError(
                "Failed to add module input "
                + name
                + ": "
                + str(added.message)
            )
        map_get = str(added.node_id)
        changes["moduleInputs"].append(name)
    if name not in pin_names(HLSL_NODE):
        added_pin = service.add_pin(
            SYSTEM,
            EMITTER,
            MODULE,
            HLSL_NODE,
            "Input",
            "float",
            name,
        )
        if not added_pin.success:
            raise RuntimeError(
                "Failed to add HLSL input "
                + name
                + ": "
                + str(added_pin.message)
            )
        changes["hlslPins"].append(name)
    expected_connection = (
        map_get,
        module_pin,
        HLSL_NODE,
        name,
    )
    if expected_connection not in connection_tuples():
        if not service.connect_pins(
            SYSTEM,
            EMITTER,
            MODULE,
            map_get,
            module_pin,
            HLSL_NODE,
            name,
        ):
            raise RuntimeError("Failed Writer parameter connection " + name)
        changes["connections"].append(name)

code = str(
    service.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
for old_line in (
    "const float TrailTime = 0.075f;",
    "const float MaxTrailPx = 20.0f;",
    "const float RadiusPx = 1.5f;",
):
    code = code.replace(old_line + "\n", "")
code = code.replace(
    "const int RadiusSteps = 2;",
    "const int RadiusSteps = 4;",
)
code = code.replace(
    "float trailPx = clamp(speedPx * TrailTime, 0.0f, MaxTrailPx);",
    (
        "float trailPx = clamp(\n"
        "    speedPx * max(TrailTime, 0.0f),\n"
        "    0.0f,\n"
        "    min(max(MaxTrailPx, 0.0f), (float)MaxTrailSteps));"
    ),
)
code = code.replace(
    "(dot(offset, offset) <= RadiusPx * RadiusPx)",
    (
        "(dot(offset, offset) <= "
        "clamp(RadiusPx, 0.0f, (float)RadiusSteps) * "
        "clamp(RadiusPx, 0.0f, (float)RadiusSteps))"
    ),
)
required_fragments = (
    "max(TrailTime, 0.0f)",
    "max(MaxTrailPx, 0.0f)",
    "clamp(RadiusPx, 0.0f, (float)RadiusSteps)",
    "const int RadiusSteps = 4;",
)
missing = [item for item in required_fragments if item not in code]
if missing:
    raise RuntimeError(
        "Writer parameterization precondition failed: " + repr(missing)
    )
if not service.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    MODULE,
    HLSL_NODE,
    code,
):
    raise RuntimeError("Failed to install parameterized M2 Writer HLSL")

applied = bool(service.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in service.get_compile_messages(SYSTEM, False)
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False)
)
stored = str(
    service.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
verified_connections = connection_tuples()
result = {
    "changes": changes,
    "mapGet": map_get,
    "applied": applied,
    "messages": messages,
    "saved": saved,
    "parameters": {
        name: (
            "Module." + name in pin_names(map_get)
            and name in pin_names(HLSL_NODE)
            and (map_get, "Module." + name, HLSL_NODE, name)
            in verified_connections
        )
        for name, _ in parameter_specs
    },
    "storedParameterizedCode": all(
        fragment in stored for fragment in required_fragments
    ),
}
print("M2PARAMS_WRITER=" + json.dumps(result, sort_keys=True))
if (
    not applied
    or messages
    or not saved
    or not all(result["parameters"].values())
    or not result["storedParameterizedCode"]
):
    raise RuntimeError("M2 Writer parameterization failed: " + repr(result))
