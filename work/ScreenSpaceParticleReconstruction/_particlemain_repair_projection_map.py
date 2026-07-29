import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_Projection"
SERVICE = unreal.NiagaraScratchPadService

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
input_node = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "Input"
)
unconnected_mapget = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
    and any(
        str(pin.pin_name) == "Particles.Position"
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, MODULE, str(node.node_id)
        )
    )
)

connected = bool(
    SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        input_node,
        "Input",
        unconnected_mapget,
        "Source",
    )
)
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
grids = []
for grid in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceGrid2DCollection
):
    path = grid.get_path_name()
    if "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main" in path:
        grids.append(path)

print(
    "PROJECTION_MAP_REPAIRED="
    + json.dumps(
        {
            "connected": connected,
            "applied": applied,
            "messages": messages,
            "grids": grids,
        },
        sort_keys=True,
    )
)
if not connected or not applied or messages:
    raise RuntimeError(
        "Projection map repair failed: " + repr(messages)
    )
