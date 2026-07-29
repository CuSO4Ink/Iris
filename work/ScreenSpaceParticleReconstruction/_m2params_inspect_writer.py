import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/"
    "NS_SSPR_ProjTest_M2.NS_SSPR_ProjTest_M2"
)
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
service = unreal.NiagaraScratchPadService

KNOWN_NODES = (
    ("MapGet", "F14AAFE54D15241C4D7D1CB3D77D2761"),
    ("CustomHLSL", "1877D2CA4F034875E12FFB8B17F65DEE"),
)
nodes = service.list_nodes(SYSTEM, EMITTER, MODULE)
result = {"nodes": [], "connections": [], "hlsl": {}}
node_specs = [
    (
        str(node.node_id),
        str(node.title),
        str(node.node_type),
    )
    for node in nodes
]
if not node_specs:
    node_specs = [(node_id, label, "known") for label, node_id in KNOWN_NODES]
for node_id, node_title, node_class in node_specs:
    pins = []
    for pin in service.get_node_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        node_id,
    ):
        pins.append(
            {
                "name": str(pin.pin_name),
                "type": str(pin.type_name),
                "direction": str(pin.direction),
            }
        )
    result["nodes"].append(
        {
            "id": node_id,
            "title": node_title,
            "class": node_class,
            "pins": pins,
        }
    )
    try:
        code = str(
            service.get_custom_hlsl_code(
                SYSTEM,
                EMITTER,
                MODULE,
                node_id,
            )
        )
        if code:
            result["hlsl"][node_id] = code
    except Exception:
        pass
for connection in service.list_connections(SYSTEM, EMITTER, MODULE):
    result["connections"].append(
        {
            "fromNode": str(connection.from_node_id),
            "fromPin": str(connection.from_pin),
            "toNode": str(connection.to_node_id),
            "toPin": str(connection.to_pin),
        }
    )
print("M2PARAMS_WRITER=" + json.dumps(result, sort_keys=True))
