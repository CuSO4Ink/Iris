import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService

nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, MODULE))
input_id = next(
    str(node.node_id) for node in nodes if str(node.node_type) == "Input"
)
output_id = next(
    str(node.node_id) for node in nodes if str(node.node_type) == "Output"
)
map_set_id = next(
    str(node.node_id) for node in nodes if str(node.node_type) == "MapSet"
)

connections = {
    (
        str(item.from_node_id), str(item.from_pin),
        str(item.to_node_id), str(item.to_pin),
    )
    for item in SERVICE.list_connections(SYSTEM, EMITTER, MODULE)
}
wanted = (
    (input_id, "Input", map_set_id, "Source"),
    (map_set_id, "Dest", output_id, "OutputMap"),
)
added = []
for edge in wanted:
    if edge in connections:
        continue
    if not SERVICE.connect_pins(
        SYSTEM, EMITTER, MODULE,
        edge[0], edge[1], edge[2], edge[3]
    ):
        raise RuntimeError("Failed to connect parameter-map edge " + repr(edge))
    added.append(edge)

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_RASTER_PARAMETER_MAP_REPAIRED=" + json.dumps({
    "added": added,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Raster parameter-map repair failed: " + repr(messages))
