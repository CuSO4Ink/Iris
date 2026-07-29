import json
import unreal


SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
MAP_GET = "BFD8FBC24B2DA1BEE89AF2889F618A0A"
HLSL = "1877D2CA4F034875E12FFB8B17F65DEE"
SERVICE = unreal.NiagaraScratchPadService


def pins(node_id):
    return SERVICE.get_node_pins(SYSTEM, EMITTER, MODULE, node_id)


def connections():
    return SERVICE.list_connections(SYSTEM, EMITTER, MODULE)


def has_pin(node_id, direction, pin_name):
    return any(
        str(pin.direction) == direction and str(pin.pin_name) == pin_name
        for pin in pins(node_id)
    )


def ensure_pin(node_id, direction, type_name, pin_name):
    if has_pin(node_id, direction, pin_name):
        return False
    result = SERVICE.add_pin(
        SYSTEM, EMITTER, MODULE, node_id, direction, type_name, pin_name
    )
    if not result.success:
        raise RuntimeError(
            "AddPin failed for {}: {}".format(pin_name, result.message)
        )
    if not has_pin(node_id, direction, pin_name):
        raise RuntimeError("Pin readback failed for " + pin_name)
    return True


def has_connection(from_node, from_pin, to_node, to_pin):
    return any(
        str(item.from_node_id) == from_node
        and str(item.from_pin) == from_pin
        and str(item.to_node_id) == to_node
        and str(item.to_pin) == to_pin
        for item in connections()
    )


def ensure_connection(from_node, from_pin, to_node, to_pin):
    if has_connection(from_node, from_pin, to_node, to_pin):
        return False
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        from_node,
        from_pin,
        to_node,
        to_pin,
    ):
        raise RuntimeError("ConnectPins failed for {} -> {}".format(from_pin, to_pin))
    if not has_connection(from_node, from_pin, to_node, to_pin):
        raise RuntimeError(
            "Connection readback failed for {} -> {}".format(from_pin, to_pin)
        )
    return True


code = str(SERVICE.get_custom_hlsl_code(SYSTEM, EMITTER, MODULE, HLSL))
if "OccupancyGrid.SetValueAtIndex" not in code:
    raise RuntimeError("Grid writer HLSL is not the expected anonymous-channel version")

added_pins = 0
added_connections = 0
for source_pin, target_pin in (
    ("Particles.SSPR_ScreenUV", "ScreenUV"),
    ("Particles.SSPR_ScreenVelocityUV", "ScreenVelocityUV"),
):
    added_pins += int(ensure_pin(MAP_GET, "Output", "vec2", source_pin))
    added_connections += int(
        ensure_connection(MAP_GET, source_pin, HLSL, target_pin)
    )

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]

expected = [
    (MAP_GET, "Particles.SSPR_ScreenUV", HLSL, "ScreenUV"),
    (
        MAP_GET,
        "Particles.SSPR_ScreenVelocityUV",
        HLSL,
        "ScreenVelocityUV",
    ),
]
stored = [
    (
        str(item.from_node_id),
        str(item.from_pin),
        str(item.to_node_id),
        str(item.to_pin),
    )
    for item in connections()
]
missing = [item for item in expected if item not in stored]

result = {
    "addedPins": added_pins,
    "addedConnections": added_connections,
    "applied": applied,
    "compileMessages": messages,
    "missingConnections": missing,
    "expectedConnections": expected,
}
print("WRITER_UV_RECONNECT=" + json.dumps(result, sort_keys=True))

if not applied or messages or missing:
    raise RuntimeError("Writer UV reconnect verification failed")
