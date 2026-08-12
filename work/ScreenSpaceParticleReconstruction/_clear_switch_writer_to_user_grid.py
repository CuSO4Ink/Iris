import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
INPUT_NODE = "2B45B5F243A8A69A63BBD0B999312CF7"
OLD_MAP_GET = "106A7EB74D8B6A80A3E3DFAC68C4BFA8"
HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"
USER_GRID_PIN = "User.SSPR_OccupancyGrid"
SERVICE = unreal.NiagaraScratchPadService


def pins(node_id):
    return SERVICE.get_node_pins(SYSTEM, EMITTER, MODULE, node_id)


old_names = [str(pin.pin_name) for pin in pins(OLD_MAP_GET)]
if "Module.OccupancyGrid" not in old_names:
    raise RuntimeError("Expected old Module.OccupancyGrid pin is missing")
if not SERVICE.delete_node(SYSTEM, EMITTER, MODULE, OLD_MAP_GET):
    raise RuntimeError("Failed to delete old MapGet")

rt_result = SERVICE.add_module_input(
    SYSTEM, EMITTER, MODULE, "OccupancyRT", "RenderTarget2D"
)
if not rt_result.success:
    raise RuntimeError("Failed to recreate OccupancyRT: " + str(rt_result.message))
map_get = str(rt_result.node_id)
grid_result = SERVICE.add_pin(
    SYSTEM, EMITTER, MODULE, map_get,
    "Output", "Grid2D", USER_GRID_PIN
)
if not grid_result.success:
    raise RuntimeError("Failed to add user Grid2D pin: " + str(grid_result.message))

expected_pins = {
    "Module.OccupancyRT": "NiagaraDataInterfaceRenderTarget2D",
    USER_GRID_PIN: "NiagaraDataInterfaceGrid2DCollection",
}
stored_pins = {
    str(pin.pin_name): str(pin.type_name)
    for pin in pins(map_get)
}
for name, type_name in expected_pins.items():
    if type_name not in stored_pins.get(name, ""):
        raise RuntimeError(f"Pin readback failed: {name} -> {stored_pins.get(name)}")

expected_connections = [
    (INPUT_NODE, "Input", map_get, "Source"),
    (map_get, "Module.OccupancyRT", HLSL, "OccupancyRT"),
    (map_get, USER_GRID_PIN, HLSL, "OccupancyGrid"),
]
for from_node, from_pin, to_node, to_pin in expected_connections:
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
for expected in expected_connections:
    if expected not in stored_connections:
        raise RuntimeError("Connection readback missing: " + repr(expected))

result = {
    "mapGet": map_get,
    "applied": applied,
    "compileMessages": messages,
    "pins": stored_pins,
    "connections": [
        item for item in stored_connections
        if item[0] == map_get or item[2] == map_get
    ],
}
print("CLEAR_USER_GRID_SWITCH=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("User grid switch failed: " + " | ".join(messages))
