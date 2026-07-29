import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService

result = {}
for module in ("SSPR_RasterizeWhiteParticles", "SSPR_ResolveGridToSimRT"):
    nodes = []
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, module):
        node_id = str(node.node_id)
        nodes.append({
            "id": node_id,
            "type": str(node.node_type),
            "title": str(node.title),
            "pins": [
                {
                    "name": str(pin.pin_name),
                    "direction": str(pin.direction),
                    "type": str(pin.type_name),
                    "connected": bool(pin.is_connected),
                }
                for pin in SERVICE.get_node_pins(
                    SYSTEM, EMITTER, module, node_id
                )
            ],
        })
    connections = [
        {
            "fromNode": str(item.from_node_id),
            "fromPin": str(item.from_pin),
            "toNode": str(item.to_node_id),
            "toPin": str(item.to_pin),
        }
        for item in SERVICE.list_connections(SYSTEM, EMITTER, module)
    ]
    result[module] = {"nodes": nodes, "connections": connections}

print("V2_RASTER_GRAPH_FULL=" + json.dumps(result, sort_keys=True))
