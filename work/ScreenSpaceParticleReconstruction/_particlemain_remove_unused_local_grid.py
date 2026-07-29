import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_WriteParticleTrails"
SERVICE = unreal.NiagaraScratchPadService

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
old_map_get = None
hlsl = None
input_map = None
for node in nodes:
    node_id = str(node.node_id)
    pins = SERVICE.get_node_pins(
        SYSTEM, EMITTER, MODULE, node_id
    )
    pin_names = {str(pin.pin_name) for pin in pins}
    if str(node.node_type) == "MapGet" and (
        "Module.TrajectoryGrid" in pin_names
    ):
        old_map_get = node_id
    elif str(node.node_type) == "CustomHlsl" and (
        "TrajectoryGrid" in pin_names
    ):
        hlsl = node_id
    elif str(node.node_type) == "Input":
        input_map = node_id

if old_map_get is None or hlsl is None or input_map is None:
    raise RuntimeError(
        "Writer nodes could not be resolved for local-grid cleanup"
    )
if not SERVICE.delete_node(
    SYSTEM, EMITTER, MODULE, old_map_get
):
    raise RuntimeError("Failed to delete old writer MapGet")

new_result = SERVICE.add_node(
    SYSTEM, EMITTER, MODULE, "MapGet", 0, 0
)
if not new_result.success:
    raise RuntimeError(
        "Failed to create clean writer MapGet: "
        + str(new_result.message)
    )
new_map_get = str(new_result.node_id)
for type_name, pin_name in (
    ("Grid2D", "User.SSPR_TrajectoryGrid"),
    ("vec2", "Particles.SSPR_ScreenUV"),
    ("vec2", "Particles.SSPR_ScreenVelocityUV"),
):
    pin_result = SERVICE.add_pin(
        SYSTEM,
        EMITTER,
        MODULE,
        new_map_get,
        "Output",
        type_name,
        pin_name,
    )
    if not pin_result.success:
        raise RuntimeError(
            "Failed to add clean writer pin "
            + pin_name
            + ": "
            + str(pin_result.message)
        )

connections = (
    (input_map, "Input", new_map_get, "Source"),
    (
        new_map_get,
        "User.SSPR_TrajectoryGrid",
        hlsl,
        "TrajectoryGrid",
    ),
    (
        new_map_get,
        "Particles.SSPR_ScreenUV",
        hlsl,
        "ScreenUV",
    ),
    (
        new_map_get,
        "Particles.SSPR_ScreenVelocityUV",
        hlsl,
        "ScreenVelocityUV",
    ),
)
for from_node, from_pin, to_node, to_pin in connections:
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        from_node,
        from_pin,
        to_node,
        to_pin,
    ):
        raise RuntimeError(
            "Failed clean writer connection: "
            + from_pin
            + " -> "
            + to_pin
        )

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
stored_pins = [
    str(pin.pin_name)
    for pin in SERVICE.get_node_pins(
        SYSTEM, EMITTER, MODULE, new_map_get
    )
]
result = {
    "oldMapGet": old_map_get,
    "newMapGet": new_map_get,
    "pins": stored_pins,
    "hasLocalGridPin": "Module.TrajectoryGrid" in stored_pins,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print(
    "PARTICLE_LOCAL_GRID_REMOVED="
    + json.dumps(result, sort_keys=True)
)
if (
    result["hasLocalGridPin"]
    or not applied
    or messages
    or not saved
):
    raise RuntimeError(
        "Unused local Grid2D cleanup failed: " + repr(result)
    )
