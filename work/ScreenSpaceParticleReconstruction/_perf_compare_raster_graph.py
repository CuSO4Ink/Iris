import json
import unreal


SOURCE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
CANDIDATE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance/"
    "NS_SSPR_AnisotropicSplat_PerfSparseV1."
    "NS_SSPR_AnisotropicSplat_PerfSparseV1"
)
EMITTER = "Fountain"
MODULES = (
    "SSPR_RasterizeWhiteParticles",
    "SSPR_Projection",
    "SSPR_InitAttrs",
)
SERVICE = unreal.NiagaraScratchPadService


def graph(system_path, module_name):
    nodes = []
    for node in SERVICE.list_nodes(
        system_path, EMITTER, module_name
    ):
        node_id = str(node.node_id)
        nodes.append(
            {
                "id": node_id,
                "type": str(node.node_type),
                "pins": sorted(
                    str(pin.pin_name)
                    for pin in SERVICE.get_node_pins(
                        system_path,
                        EMITTER,
                        module_name,
                        node_id,
                    )
                ),
            }
        )
    connections = sorted(
        (
            str(item.from_node_id),
            str(item.from_pin),
            str(item.to_node_id),
            str(item.to_pin),
        )
        for item in SERVICE.list_connections(
            system_path, EMITTER, module_name
        )
    )
    return {"nodes": nodes, "connections": connections}


result = {
    "source": {
        module: graph(SOURCE, module) for module in MODULES
    },
    "candidate": {
        module: graph(CANDIDATE, module) for module in MODULES
    },
}
print(
    "PERF_RASTER_GRAPH_COMPARE="
    + json.dumps(result, sort_keys=True)
)
