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


def require(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))
    return str(result.node_id)


def add_pin(node_id, direction, type_name, pin_name):
    require(
        SERVICE.add_pin(
            SYSTEM,
            EMITTER,
            MODULE,
            node_id,
            direction,
            type_name,
            pin_name,
        ),
        "Add pin " + pin_name,
    )


def connect(from_node, from_pin, to_node, to_pin):
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
            "Connect failed: {} -> {}".format(from_pin, to_pin)
        )


stage_result = SERVICE.create_simulation_stage(
    SYSTEM, EMITTER, STAGE_NAME
)
if not stage_result.success:
    raise RuntimeError(
        "Create simulation stage failed: " + str(stage_result.message)
    )

existing = {
    str(name)
    for name in SERVICE.list_scratch_modules(SYSTEM, EMITTER)
}
if MODULE in existing:
    raise RuntimeError(
        "Raster module already exists; refusing a partial duplicate build"
    )

module_result = SERVICE.create_scratch_module(
    SYSTEM,
    EMITTER,
    "SimulationStage:" + STAGE_NAME,
    MODULE,
)
if not module_result.success:
    raise RuntimeError(
        "Create raster module failed: " + str(module_result.message)
    )
MODULE = str(module_result.module_name)

map_get = require(
    SERVICE.add_node(
        SYSTEM, EMITTER, MODULE, "MapGet", 0, 0
    ),
    "Create MapGet",
)
add_pin(map_get, "Output", "Position", "Particles.Position")
add_pin(
    map_get,
    "Output",
    "Grid2D",
    "User.SSPR_TrajectoryGrid",
)

hlsl_code = r"""// One current-frame splat per alive white source particle.
// Particle age distribution and particle count form the visible trajectory.
float4 clip = mul(float4(WorldPos, 1.0f), View.WorldToClip);
bool inFront = clip.w > 0.0001f;
float2 ndc = inFront ? clip.xy / clip.w : float2(0.0f, 0.0f);
float2 uv = ndc * float2(0.5f, -0.5f) + 0.5f;
bool validUV =
    inFront &&
    uv.x >= 0.0f && uv.x < 1.0f &&
    uv.y >= 0.0f && uv.y < 1.0f;

int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
bool validGrid = W > 0 && H > 0;
int safeW = max(W, 1);
int safeH = max(H, 1);
int2 centerPx = int2(floor(uv * float2(safeW, safeH)));

const int RadiusPx = 1;
for (int y = -RadiusPx; y <= RadiusPx; ++y)
{
    for (int x = -RadiusPx; x <= RadiusPx; ++x)
    {
        int2 p = centerPx + int2(x, y);
        bool insideDisk = x * x + y * y <= RadiusPx * RadiusPx;
        bool insideGrid =
            p.x >= 0 && p.x < safeW &&
            p.y >= 0 && p.y < safeH;
        if (validUV && validGrid && insideDisk && insideGrid)
        {
            TrajectoryGrid.SetValueAtIndex(p.x, p.y, 0, 1.0f);
        }
    }
}
OutMark = validUV && validGrid ? 1.0f : 0.0f;
"""
hlsl = require(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        MODULE,
        hlsl_code,
        360,
        0,
    ),
    "Create raster HLSL",
)
for direction, type_name, pin_name in (
    ("Input", "Position", "WorldPos"),
    ("Input", "Grid2D", "TrajectoryGrid"),
    ("Output", "float", "OutMark"),
):
    add_pin(hlsl, direction, type_name, pin_name)

map_set = require(
    SERVICE.add_module_output(
        SYSTEM,
        EMITTER,
        MODULE,
        "Particles.SSPR_WriteMark",
        "float",
    ),
    "Create particle mark output",
)
connect(map_get, "Particles.Position", hlsl, "WorldPos")
connect(
    map_get,
    "User.SSPR_TrajectoryGrid",
    hlsl,
    "TrajectoryGrid",
)
connect(
    hlsl,
    "OutMark",
    map_set,
    "Particles.SSPR_WriteMark",
)

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
            "enabled": bool(
                stage.get_editor_property("enabled")
            ),
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
    "PARTICLE_RASTER_STAGE="
    + json.dumps(result, sort_keys=True)
)
if (
    not applied
    or not saved
    or messages
    or not stage_rows
):
    raise RuntimeError(
        "Raster stage build did not validate: " + repr(result)
    )
