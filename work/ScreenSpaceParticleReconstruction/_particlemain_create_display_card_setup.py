import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_DisplayCardSetup"
SERVICE = unreal.NiagaraScratchPadService


def require(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))
    return str(result.node_id)


existing = {
    str(name)
    for name in SERVICE.list_scratch_modules(SYSTEM, EMITTER)
}
if MODULE in existing:
    raise RuntimeError(
        "Display card setup already exists; refusing a partial rebuild"
    )

created = SERVICE.create_scratch_module(
    SYSTEM, EMITTER, "EmitterUpdate", MODULE
)
if not created.success:
    raise RuntimeError(
        "Failed to create display-card module: "
        + str(created.message)
    )

nodes = SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
input_map = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "Input"
)

map_get = require(
    SERVICE.add_node(
        SYSTEM, EMITTER, MODULE, "MapGet", 0, 0
    ),
    "Create display-card MapGet",
)
pin = SERVICE.add_pin(
    SYSTEM,
    EMITTER,
    MODULE,
    map_get,
    "Output",
    "Position",
    "Engine.Owner.Position",
)
if not pin.success:
    raise RuntimeError(
        "Failed to add owner-position pin: " + str(pin.message)
    )
if not SERVICE.connect_pins(
    SYSTEM,
    EMITTER,
    MODULE,
    input_map,
    "Input",
    map_get,
    "Source",
):
    raise RuntimeError(
        "Failed to connect display-card parameter map"
    )

hlsl = require(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        MODULE,
        "OutSize = float2(1200.0f, 1200.0f);",
        320,
        0,
    ),
    "Create display-card size HLSL",
)
size_pin = SERVICE.add_pin(
    SYSTEM,
    EMITTER,
    MODULE,
    hlsl,
    "Output",
    "vec2",
    "OutSize",
)
if not size_pin.success:
    raise RuntimeError(
        "Failed to add display-card size pin: "
        + str(size_pin.message)
    )

position_output = SERVICE.add_module_output(
    SYSTEM,
    EMITTER,
    MODULE,
    "Emitter.Position",
    "Position",
)
if not position_output.success:
    raise RuntimeError(
        "Failed to add Emitter.Position: "
        + str(position_output.message)
    )
map_set = str(position_output.node_id)
size_output = SERVICE.add_module_output(
    SYSTEM,
    EMITTER,
    MODULE,
    "Emitter.SpriteSize",
    "vec2",
)
if not size_output.success:
    raise RuntimeError(
        "Failed to add Emitter.SpriteSize: "
        + str(size_output.message)
    )

for from_node, from_pin, to_pin in (
    (map_get, "Engine.Owner.Position", "Emitter.Position"),
    (hlsl, "OutSize", "Emitter.SpriteSize"),
):
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        from_node,
        from_pin,
        map_set,
        to_pin,
    ):
        raise RuntimeError(
            "Failed display-card connection: "
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
result = {
    "module": MODULE,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print(
    "PARTICLE_DISPLAY_CARD_SETUP="
    + json.dumps(result, sort_keys=True)
)
if not applied or messages or not saved:
    raise RuntimeError(
        "Display card setup failed: " + repr(result)
    )
