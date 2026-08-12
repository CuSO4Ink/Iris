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
LOCAL_OUTPUT = "Output.SSPR_RasterizeWhiteParticles.OutMark"
SERVICE = unreal.NiagaraScratchPadService

nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, MODULE))
hlsl_id = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "CustomHlsl"
)
map_set_ids = [
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapSet"
]
if not map_set_ids:
    raise RuntimeError("Raster module has no MapSet to replace")

# The old MapSet contains Particles.SSPR_WriteMark. Merely disconnecting that
# pin is insufficient because its presence still classifies the stage as a
# particle writer. Recreate the MapSet with a module-local output instead.
for node_id in map_set_ids:
    if not SERVICE.delete_node(SYSTEM, EMITTER, MODULE, node_id):
        raise RuntimeError("Failed to delete particle-writing MapSet " + node_id)

result = SERVICE.add_module_output(
    SYSTEM, EMITTER, MODULE, LOCAL_OUTPUT, "float"
)
if not result.success:
    raise RuntimeError("Create local raster output: " + str(result.message))
map_set_id = str(result.node_id)
if not SERVICE.connect_pins(
    SYSTEM, EMITTER, MODULE,
    hlsl_id, "OutMark", map_set_id, LOCAL_OUTPUT
):
    raise RuntimeError("Connect raster OutMark to local output failed")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_RASTER_STAGE_DI_ONLY=" + json.dumps({
    "applied": applied,
    "compileMessages": messages,
    "deletedMapSets": map_set_ids,
    "localOutput": LOCAL_OUTPUT,
    "newMapSet": map_set_id,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Raster DI-only stage conversion failed")
