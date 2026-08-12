import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULES = ("SSPR_InitAttrs", "SSPR_Projection", "SSPR_WriteOccupancy")
SERVICE = unreal.NiagaraScratchPadService

result = {}
for module in MODULES:
    nodes = SERVICE.list_nodes(SYSTEM, EMITTER, module)
    module_data = {
        "scriptPath": str(
            SERVICE.get_scratch_script_path(SYSTEM, EMITTER, module)
        ),
        "nodes": [],
        "connections": [
            {
                "fromNodeId": str(item.from_node_id),
                "fromPin": str(item.from_pin),
                "toNodeId": str(item.to_node_id),
                "toPin": str(item.to_pin),
            }
            for item in SERVICE.list_connections(SYSTEM, EMITTER, module)
        ],
    }
    for node in nodes:
        node_data = {
            "nodeId": str(node.node_id),
            "nodeType": str(node.node_type),
            "title": str(node.title),
            "position": [int(node.pos_x), int(node.pos_y)],
            "pins": [
                {
                    "name": str(pin.pin_name),
                    "direction": str(pin.direction),
                    "type": str(pin.type_name),
                    "connected": bool(pin.is_connected),
                    "default": str(pin.default_value),
                }
                for pin in SERVICE.get_node_pins(
                    SYSTEM, EMITTER, module, str(node.node_id)
                )
            ],
        }
        if str(node.node_type) == "CustomHlsl":
            node_data["hlsl"] = str(
                SERVICE.get_custom_hlsl_code(
                    SYSTEM, EMITTER, module, str(node.node_id)
                )
            )
        module_data["nodes"].append(node_data)
    result[module] = module_data

print("M1_SCRATCH=" + json.dumps(result, sort_keys=True))
