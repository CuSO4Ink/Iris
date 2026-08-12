import json
import unreal


SYSTEM = "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
EMITTER = "Fountain"
MODULE = "SSPR_ResolveGridToSimRT"
SERVICE = unreal.NiagaraScratchPadService

nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, MODULE))
input_node = next(
    str(node.node_id) for node in nodes if str(node.node_type) == "Input"
)
map_get = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
    and any(
        str(pin.pin_name) == "User.SSPR_SimRT"
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, MODULE, str(node.node_id)
        )
    )
)
hlsl_node = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "CustomHlsl"
)
code = str(
    SERVICE.get_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, hlsl_node
    )
)
if "TrajectoryGrid.GetValue(" in code:
    code = code.replace(
        "TrajectoryGrid.GetValue(",
        "TrajectoryGrid.GetGridValue(",
    )
    if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, hlsl_node, code
    ):
        raise RuntimeError("Failed to update Grid2D read function")
connected = bool(
    SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        MODULE,
        input_node,
        "Input",
        map_get,
        "Source",
    )
)
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(x) for x in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
result = {
    "connected": connected,
    "applied": applied,
    "messages": messages,
    "saved": saved,
}
print("PARTICLE_RESOLVE_REPAIR=" + json.dumps(result, sort_keys=True))
