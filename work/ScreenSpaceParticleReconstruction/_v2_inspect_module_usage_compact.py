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
    nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, module))
    node_rows = []
    for node in nodes:
        node_id = str(node.node_id)
        pins = []
        for pin in SERVICE.get_node_pins(SYSTEM, EMITTER, module, node_id):
            pins.append({
                "name": str(pin.pin_name),
                "direction": str(pin.direction),
                "type": str(pin.type_name),
                "connected": bool(pin.is_connected),
            })
        node_rows.append({
            "id": node_id,
            "type": str(node.node_type),
            "title": str(node.title),
            "pins": pins,
        })
    connections = [{
        "fromNode": str(item.from_node_id),
        "fromPin": str(item.from_pin),
        "toNode": str(item.to_node_id),
        "toPin": str(item.to_pin),
    } for item in SERVICE.list_connections(SYSTEM, EMITTER, module)]
    result[module] = {"nodes": node_rows, "connections": connections}

print("V2_MODULE_USAGE=" + json.dumps(result, sort_keys=True))
