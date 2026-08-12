import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_WriteParticleTrails"
USER_GRID = "User.SSPR_TrajectoryGrid"
SERVICE = unreal.NiagaraScratchPadService

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
map_get = None
hlsl = None
for node in nodes:
    node_id = str(node.node_id)
    pins = SERVICE.get_node_pins(
        SYSTEM, EMITTER, MODULE, node_id
    )
    pin_names = {str(pin.pin_name) for pin in pins}
    if str(node.node_type) == "MapGet" and (
        "Module.TrajectoryGrid" in pin_names
    ):
        map_get = node_id
    if str(node.node_type) == "CustomHlsl" and (
        "TrajectoryGrid" in pin_names
    ):
        hlsl = node_id

if map_get is None or hlsl is None:
    raise RuntimeError(
        "Writer MapGet/HLSL nodes could not be resolved"
    )

stored_names = {
    str(pin.pin_name)
    for pin in SERVICE.get_node_pins(
        SYSTEM, EMITTER, MODULE, map_get
    )
}
if USER_GRID not in stored_names:
    add_result = SERVICE.add_pin(
        SYSTEM,
        EMITTER,
        MODULE,
        map_get,
        "Output",
        "Grid2D",
        USER_GRID,
    )
    if not add_result.success:
        raise RuntimeError(
            "Failed to add User Grid pin: "
            + str(add_result.message)
        )

if not SERVICE.connect_pins(
    SYSTEM,
    EMITTER,
    MODULE,
    map_get,
    USER_GRID,
    hlsl,
    "TrajectoryGrid",
):
    raise RuntimeError("Failed to link User Grid to writer HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
connections = [
    (
        str(item.from_node_id),
        str(item.from_pin),
        str(item.to_node_id),
        str(item.to_pin),
    )
    for item in SERVICE.list_connections(
        SYSTEM, EMITTER, MODULE
    )
]
expected = (map_get, USER_GRID, hlsl, "TrajectoryGrid")
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
result = {
    "mapGet": map_get,
    "hlsl": hlsl,
    "expectedConnection": expected,
    "connectionPresent": expected in connections,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
}
print(
    "PARTICLE_WRITER_USER_GRID="
    + json.dumps(result, sort_keys=True)
)
if (
    not result["connectionPresent"]
    or not applied
    or not saved
    or messages
):
    raise RuntimeError(
        "User Grid writer link failed: " + repr(result)
    )
