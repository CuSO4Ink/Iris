import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
INPUT_NODE = "2B45B5F243A8A69A63BBD0B999312CF7"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
old_map_gets = [
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
]
if len(old_map_gets) != 1:
    raise RuntimeError("Expected one old MapGet: " + repr(old_map_gets))
old_map_get = old_map_gets[0]

writer_code = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))
if "OccupancyGrid.SetValueAtIndex" not in writer_code:
    raise RuntimeError("Expected Grid2D writer before MapGet rebuild")
if not SERVICE.delete_node(SYSTEM, EMITTER, MODULE, old_map_get):
    raise RuntimeError("Failed to delete old MapGet")

rt_input = SERVICE.add_module_input(
    SYSTEM, EMITTER, MODULE, "OccupancyRT", "RenderTarget2D"
)
grid_input = SERVICE.add_module_input(
    SYSTEM, EMITTER, MODULE, "OccupancyGrid", "Grid2D"
)
if not rt_input.success or not grid_input.success:
    raise RuntimeError(
        "Failed module inputs: rt=" + str(rt_input.message) +
        " grid=" + str(grid_input.message)
    )
new_map_get = str(rt_input.node_id)
if new_map_get != str(grid_input.node_id):
    raise RuntimeError("Module inputs landed on different MapGet nodes")

uv_input = SERVICE.add_pin(
    SYSTEM, EMITTER, MODULE, new_map_get,
    "Output", "vec2", "Particles.SSPR_ScreenUV"
)
velocity_input = SERVICE.add_pin(
    SYSTEM, EMITTER, MODULE, new_map_get,
    "Output", "vec2", "Particles.SSPR_ScreenVelocityUV"
)
if not uv_input.success or not velocity_input.success:
    raise RuntimeError(
        "Failed particle reads: uv=" + str(uv_input.message) +
        " velocity=" + str(velocity_input.message)
    )

expected_connections = [
    (INPUT_NODE, "Input", new_map_get, "Source"),
    (new_map_get, "Module.OccupancyRT", HLSL_NODE, "OccupancyRT"),
    (new_map_get, "Module.OccupancyGrid", HLSL_NODE, "OccupancyGrid"),
    (new_map_get, "Particles.SSPR_ScreenUV", HLSL_NODE, "ScreenUV"),
    (
        new_map_get, "Particles.SSPR_ScreenVelocityUV",
        HLSL_NODE, "ScreenVelocityUV"
    ),
]
for from_node, from_pin, to_node, to_pin in expected_connections:
    if not SERVICE.connect_pins(
            SYSTEM, EMITTER, MODULE,
            from_node, from_pin, to_node, to_pin):
        raise RuntimeError(
            "Failed connection " + from_node + "." + from_pin +
            " -> " + to_node + "." + to_pin
        )

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
pins = [
    (str(pin.pin_name), str(pin.direction), str(pin.type_name))
    for pin in SERVICE.get_node_pins(
        SYSTEM, EMITTER, MODULE, new_map_get
    )
]
connections = [
    (
        str(item.from_node_id), str(item.from_pin),
        str(item.to_node_id), str(item.to_pin)
    )
    for item in SERVICE.list_connections(SYSTEM, EMITTER, MODULE)
]
missing = [item for item in expected_connections if item not in connections]
result = {
    "oldMapGet": old_map_get,
    "newMapGet": new_map_get,
    "applied": applied,
    "messages": messages,
    "pins": pins,
    "missingConnections": missing,
}
print("FIXED_MAPGET_REBUILD=" + json.dumps(result, sort_keys=True))
if not applied or messages or missing:
    raise RuntimeError("Fixed MapGet rebuild verification failed")
