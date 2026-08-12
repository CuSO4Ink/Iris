import json
import unreal

SYSTEM = "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main"
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService

result = {}
for module in SERVICE.list_scratch_modules(SYSTEM, EMITTER):
    module_name = str(module)
    nodes = SERVICE.list_nodes(SYSTEM, EMITTER, module_name)
    result[module_name] = {
        "nodes": [
            {
                "nodeId": str(node.node_id),
                "nodeType": str(node.node_type),
                "title": str(node.title),
                "pins": [
                    {
                        "name": str(pin.pin_name),
                        "direction": str(pin.direction),
                        "type": str(pin.type_name),
                        "connected": bool(pin.is_connected),
                        "default": str(pin.default_value),
                    }
                    for pin in SERVICE.get_node_pins(
                        SYSTEM,
                        EMITTER,
                        module_name,
                        str(node.node_id),
                    )
                ],
            }
            for node in nodes
        ],
        "connections": [
            {
                "fromNodeId": str(item.from_node_id),
                "fromPin": str(item.from_pin),
                "toNodeId": str(item.to_node_id),
                "toPin": str(item.to_pin),
            }
            for item in SERVICE.list_connections(
                SYSTEM, EMITTER, module_name
            )
        ],
    }

print("NEW_SCRATCH=" + json.dumps(result, sort_keys=True))
