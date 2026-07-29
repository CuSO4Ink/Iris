import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
INPUT_NODE = "2B45B5F243A8A69A63BBD0B999312CF7"
MAP_GET = "106A7EB74D8B6A80A3E3DFAC68C4BFA8"
HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

connections = [
    (INPUT_NODE, "Input", MAP_GET, "Source"),
    (MAP_GET, "Module.OccupancyRT", HLSL, "OccupancyRT"),
    (MAP_GET, "Module.OccupancyGrid", HLSL, "OccupancyGrid"),
]
for from_node, from_pin, to_node, to_pin in connections:
    if not SERVICE.connect_pins(
        SYSTEM, EMITTER, MODULE,
        from_node, from_pin, to_node, to_pin
    ):
        raise RuntimeError(
            f"Failed connection {from_node}.{from_pin} -> {to_node}.{to_pin}"
        )

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
stored_connections = [
    (
        str(item.from_node_id), str(item.from_pin),
        str(item.to_node_id), str(item.to_pin)
    )
    for item in SERVICE.list_connections(SYSTEM, EMITTER, MODULE)
]
for expected in connections:
    if expected not in stored_connections:
        raise RuntimeError("Connection readback missing: " + repr(expected))

result = {
    "mapGet": MAP_GET,
    "applied": applied,
    "compileMessages": messages,
    "storedConnections": [
        item for item in stored_connections
        if item[0] == MAP_GET or item[2] == MAP_GET
    ],
}
print("CLEAR_MAPGET_CONTINUE=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("MapGet continuation failed: " + " | ".join(messages))
