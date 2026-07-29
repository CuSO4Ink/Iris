import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
STAGE_NAME = "SSPR Rasterize Trails"
MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService

nodes = list(
    SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
)
input_node = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "Input"
)
raster_map_get = next(
    str(node.node_id)
    for node in nodes
    if str(node.node_type) == "MapGet"
    and any(
        str(pin.pin_name) == "Particles.Position"
        for pin in SERVICE.get_node_pins(
            SYSTEM,
            EMITTER,
            MODULE,
            str(node.node_id),
        )
    )
)
if not SERVICE.connect_pins(
    SYSTEM,
    EMITTER,
    MODULE,
    input_node,
    "Input",
    raster_map_get,
    "Source",
):
    raise RuntimeError("Failed to connect InputMap to raster MapGet")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))

stage_rows = []
for stage in unreal.ObjectIterator(
    unreal.NiagaraSimulationStageBase
):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    if str(
        stage.get_editor_property("simulation_stage_name")
    ) != STAGE_NAME:
        continue
    stage_rows.append(
        {
            "path": path,
            "iterationSource": str(
                stage.get_editor_property("iteration_source")
            ),
            "script": stage.get_editor_property(
                "script"
            ).get_path_name(),
        }
    )

result = {
    "stage": STAGE_NAME,
    "module": MODULE,
    "stageObjects": stage_rows,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
}
print(
    "PARTICLE_RASTER_STAGE_REPAIRED="
    + json.dumps(result, sort_keys=True)
)
if (
    not applied
    or not saved
    or messages
    or not stage_rows
):
    raise RuntimeError(
        "Raster stage repair did not validate: " + repr(result)
    )
