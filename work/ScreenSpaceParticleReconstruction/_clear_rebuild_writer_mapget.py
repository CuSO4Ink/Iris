import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
INPUT_NODE = "2B45B5F243A8A69A63BBD0B999312CF7"
OLD_MAP_GET = "F14AAFE54D15241C4D7D1CB3D77D2761"
HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService


def pin_exists(node_id, direction, name, type_fragment=None):
    for pin in SERVICE.get_node_pins(SYSTEM, EMITTER, MODULE, node_id):
        if str(pin.direction) != direction or str(pin.pin_name) != name:
            continue
        if type_fragment and type_fragment not in str(pin.type_name):
            continue
        return True
    return False


if not pin_exists(OLD_MAP_GET, "Output", "Module.OccupancyRT", "RenderTarget2D"):
    raise RuntimeError("Old OccupancyRT MapGet pin missing")
if not pin_exists(OLD_MAP_GET, "Output", "Module.OccupancyGrid", "Grid2DCollection"):
    raise RuntimeError("Old OccupancyGrid MapGet pin missing")
if not SERVICE.delete_node(SYSTEM, EMITTER, MODULE, OLD_MAP_GET):
    raise RuntimeError("Failed to delete old writer MapGet")

rt_result = SERVICE.add_module_input(
    SYSTEM, EMITTER, MODULE, "OccupancyRT", "RenderTarget2D"
)
grid_result = SERVICE.add_module_input(
    SYSTEM, EMITTER, MODULE, "OccupancyGrid", "Grid2D"
)
if not rt_result.b_success or not grid_result.b_success:
    raise RuntimeError(
        f"Failed to rebuild inputs: rt={rt_result.message} "
        f"grid={grid_result.message}"
    )
new_map_get = str(rt_result.node_id)
if new_map_get != str(grid_result.node_id):
    raise RuntimeError("Rebuilt inputs landed on different MapGet nodes")

connections = [
    (INPUT_NODE, "Input", new_map_get, "Source"),
    (new_map_get, "Module.OccupancyRT", HLSL, "OccupancyRT"),
    (new_map_get, "Module.OccupancyGrid", HLSL, "OccupancyGrid"),
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
result = {
    "newMapGet": new_map_get,
    "applied": applied,
    "compileMessages": messages,
    "pins": [
        (str(pin.pin_name), str(pin.direction), str(pin.type_name))
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, MODULE, new_map_get
        )
    ],
    "connections": [
        (
            str(item.from_node_id), str(item.from_pin),
            str(item.to_node_id), str(item.to_pin)
        )
        for item in SERVICE.list_connections(SYSTEM, EMITTER, MODULE)
        if (
            str(item.from_node_id) == new_map_get
            or str(item.to_node_id) == new_map_get
        )
    ],
}
print("CLEAR_MAPGET_REBUILD=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("MapGet rebuild/apply failed: " + " | ".join(messages))
