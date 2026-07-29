import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/"
    "NS_SSPR_ProjTest_M2.NS_SSPR_ProjTest_M2"
)
SYSTEM_PACKAGE = "/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
service = unreal.NiagaraScratchPadService


def pin_names(node_id):
    return {
        str(pin.pin_name)
        for pin in service.get_node_pins(
            SYSTEM,
            EMITTER,
            MODULE,
            node_id,
        )
    }


def connections():
    return {
        (
            str(item.from_node_id),
            str(item.from_pin),
            str(item.to_node_id),
            str(item.to_pin),
        )
        for item in service.list_connections(SYSTEM, EMITTER, MODULE)
    }


nodes = service.list_nodes(SYSTEM, EMITTER, MODULE)
map_gets = [
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
]
if len(map_gets) != 1:
    raise RuntimeError("Expected one Writer MapGet: " + repr(map_gets))
map_get = map_gets[0]

specs = (
    ("Module.RadiusPx", "User.SSPR_RadiusPx", "RadiusPx"),
    ("Module.TrailTime", "User.SSPR_TrailTime", "TrailTime"),
    ("Module.MaxTrailPx", "User.SSPR_MaxTrailPx", "MaxTrailPx"),
)
changes = {"pins": [], "disconnected": [], "connected": []}

for old_source, user_source, target in specs:
    if user_source not in pin_names(map_get):
        result = service.add_pin(
            SYSTEM,
            EMITTER,
            MODULE,
            map_get,
            "Output",
            "float",
            user_source,
        )
        if not result.success:
            raise RuntimeError(
                "Failed to add " + user_source + ": " + str(result.message)
            )
        changes["pins"].append(user_source)

    current = connections()
    old_connection = (map_get, old_source, HLSL_NODE, target)
    if old_connection in current:
        if not service.disconnect_pin(
            SYSTEM,
            EMITTER,
            MODULE,
            HLSL_NODE,
            target,
        ):
            raise RuntimeError("Failed to disconnect " + target)
        changes["disconnected"].append(target)

    desired = (map_get, user_source, HLSL_NODE, target)
    if desired not in connections():
        if not service.connect_pins(
            SYSTEM,
            EMITTER,
            MODULE,
            map_get,
            user_source,
            HLSL_NODE,
            target,
        ):
            raise RuntimeError("Failed to connect " + user_source)
        changes["connected"].append(target)

applied = bool(service.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in service.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False))
final_connections = connections()
verified = {
    target: (map_get, user_source, HLSL_NODE, target) in final_connections
    for _, user_source, target in specs
}
result = {
    "applied": applied,
    "changes": changes,
    "compileMessages": messages,
    "saved": saved,
    "verified": verified,
}
print("M2PARAMS_WRITER_USERS=" + json.dumps(result, sort_keys=True))
if not applied or messages or not saved or not all(verified.values()):
    raise RuntimeError("Writer User parameter link failed: " + repr(result))
