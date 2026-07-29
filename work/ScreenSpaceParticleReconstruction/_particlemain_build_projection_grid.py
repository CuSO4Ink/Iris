import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService


def result_ok(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))
    return str(result.node_id)


def find_node(module_name, node_type):
    matches = [
        node
        for node in SERVICE.list_nodes(SYSTEM, EMITTER, module_name)
        if str(node.node_type) == node_type
    ]
    if not matches:
        raise RuntimeError(
            "No {} node in {}".format(node_type, module_name)
        )
    return str(matches[0].node_id)


def ensure_connect(module_name, from_node, from_pin, to_node, to_pin):
    for connection in SERVICE.list_connections(
        SYSTEM, EMITTER, module_name
    ):
        if (
            str(connection.from_node_id) == from_node
            and str(connection.from_pin) == from_pin
            and str(connection.to_node_id) == to_node
            and str(connection.to_pin) == to_pin
        ):
            return
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        module_name,
        from_node,
        from_pin,
        to_node,
        to_pin,
    ):
        raise RuntimeError(
            "Connect failed in {}: {} -> {}".format(
                module_name, from_pin, to_pin
            )
        )


def add_pin(module_name, node_id, direction, type_name, pin_name):
    result_ok(
        SERVICE.add_pin(
            SYSTEM,
            EMITTER,
            module_name,
            node_id,
            direction,
            type_name,
            pin_name,
        ),
        "Add pin {}/{}".format(module_name, pin_name),
    )


def create_module(stage, desired_name):
    existing = {
        str(name)
        for name in SERVICE.list_scratch_modules(SYSTEM, EMITTER)
    }
    if desired_name in existing:
        raise RuntimeError(
            "Scratch module already exists; refusing partial rebuild: "
            + desired_name
        )
    result = SERVICE.create_scratch_module(
        SYSTEM, EMITTER, stage, desired_name
    )
    if not result.success:
        raise RuntimeError(
            "Create module {} failed: {}".format(
                desired_name, result.message
            )
        )
    return str(result.module_name)


def add_output(module_name, output_name, type_name):
    return result_ok(
        SERVICE.add_module_output(
            SYSTEM,
            EMITTER,
            module_name,
            output_name,
            type_name,
        ),
        "Add output {}/{}".format(module_name, output_name),
    )


def add_module_input(module_name, input_name, type_name):
    return result_ok(
        SERVICE.add_module_input(
            SYSTEM,
            EMITTER,
            module_name,
            input_name,
            type_name,
        ),
        "Add module input {}/{}".format(module_name, input_name),
    )


created = []

# Spawn: define all custom attributes so the GPU particle layout is stable.
init_module = create_module("ParticleSpawn", "SSPR_InitAttrs")
created.append(init_module)
init_hlsl = result_ok(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        init_module,
        (
            "OutUV = float2(-1.0f, -1.0f);\n"
            "OutDepth = 0.0f;\n"
            "OutMark = 0.0f;\n"
            "OutScreenVelocityUV = float2(0.0f, 0.0f);"
        ),
        320,
        0,
    ),
    "Create init HLSL",
)
for pin_type, pin_name in (
    ("vec2", "OutUV"),
    ("float", "OutDepth"),
    ("float", "OutMark"),
    ("vec2", "OutScreenVelocityUV"),
):
    add_pin(init_module, init_hlsl, "Output", pin_type, pin_name)

init_mapset = add_output(
    init_module, "Particles.SSPR_ScreenUV", "vec2"
)
add_output(init_module, "Particles.SSPR_ViewDepth", "float")
add_output(init_module, "Particles.SSPR_WriteMark", "float")
add_output(
    init_module, "Particles.SSPR_ScreenVelocityUV", "vec2"
)
ensure_connect(
    init_module,
    init_hlsl,
    "OutUV",
    init_mapset,
    "Particles.SSPR_ScreenUV",
)
ensure_connect(
    init_module,
    init_hlsl,
    "OutDepth",
    init_mapset,
    "Particles.SSPR_ViewDepth",
)
ensure_connect(
    init_module,
    init_hlsl,
    "OutMark",
    init_mapset,
    "Particles.SSPR_WriteMark",
)
ensure_connect(
    init_module,
    init_hlsl,
    "OutScreenVelocityUV",
    init_mapset,
    "Particles.SSPR_ScreenVelocityUV",
)

# Update: project the solved white particles with the current view matrices.
projection_module = create_module(
    "ParticleUpdate", "SSPR_Projection"
)
created.append(projection_module)
projection_mapget = result_ok(
    SERVICE.add_node(
        SYSTEM,
        EMITTER,
        projection_module,
        "MapGet",
        0,
        0,
    ),
    "Create projection MapGet",
)
add_pin(
    projection_module,
    projection_mapget,
    "Output",
    "Position",
    "Particles.Position",
)
add_pin(
    projection_module,
    projection_mapget,
    "Output",
    "Vector",
    "Particles.Velocity",
)
projection_code = r"""// Current-camera world-to-screen projection.
const float ReferenceDt = 1.0f / 60.0f;
float4 clip0 = mul(float4(WorldPos, 1.0f), View.WorldToClip);
OutDepth = clip0.w;

bool inFront0 = clip0.w > 0.0001f;
float2 ndc0 = inFront0 ? clip0.xy / clip0.w : float2(0.0f, 0.0f);
float2 uv0 = ndc0 * float2(0.5f, -0.5f) + 0.5f;
bool onScreen = inFront0 &&
    uv0.x >= 0.0f && uv0.x < 1.0f &&
    uv0.y >= 0.0f && uv0.y < 1.0f;

float3 futureWorldPos = WorldPos + WorldVelocity * ReferenceDt;
float4 clip1 = mul(float4(futureWorldPos, 1.0f), View.WorldToClip);
bool inFront1 = clip1.w > 0.0001f;
float2 ndc1 = inFront1 ? clip1.xy / clip1.w : ndc0;
float2 uv1 = ndc1 * float2(0.5f, -0.5f) + 0.5f;

OutUV = onScreen ? uv0 : float2(-1.0f, -1.0f);
OutScreenVelocityUV = (onScreen && inFront1)
    ? (uv1 - uv0) / ReferenceDt
    : float2(0.0f, 0.0f);
"""
projection_hlsl = result_ok(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        projection_module,
        projection_code,
        320,
        0,
    ),
    "Create projection HLSL",
)
for direction, pin_type, pin_name in (
    ("Input", "Position", "WorldPos"),
    ("Input", "Vector", "WorldVelocity"),
    ("Output", "vec2", "OutUV"),
    ("Output", "float", "OutDepth"),
    ("Output", "vec2", "OutScreenVelocityUV"),
):
    add_pin(
        projection_module,
        projection_hlsl,
        direction,
        pin_type,
        pin_name,
    )
projection_mapset = add_output(
    projection_module, "Particles.SSPR_ScreenUV", "vec2"
)
add_output(
    projection_module, "Particles.SSPR_ViewDepth", "float"
)
add_output(
    projection_module,
    "Particles.SSPR_ScreenVelocityUV",
    "vec2",
)
ensure_connect(
    projection_module,
    projection_mapget,
    "Particles.Position",
    projection_hlsl,
    "WorldPos",
)
ensure_connect(
    projection_module,
    projection_mapget,
    "Particles.Velocity",
    projection_hlsl,
    "WorldVelocity",
)
ensure_connect(
    projection_module,
    projection_hlsl,
    "OutUV",
    projection_mapset,
    "Particles.SSPR_ScreenUV",
)
ensure_connect(
    projection_module,
    projection_hlsl,
    "OutDepth",
    projection_mapset,
    "Particles.SSPR_ViewDepth",
)
ensure_connect(
    projection_module,
    projection_hlsl,
    "OutScreenVelocityUV",
    projection_mapset,
    "Particles.SSPR_ScreenVelocityUV",
)

# Update: stamp only the currently alive white particles into an auto-cleared
# Grid2D. Particle age distribution, not temporal ping-pong, forms the trail.
writer_module = create_module(
    "ParticleUpdate", "SSPR_WriteParticleTrails"
)
created.append(writer_module)
writer_mapget = add_module_input(
    writer_module, "TrajectoryGrid", "Grid2D"
)
add_pin(
    writer_module,
    writer_mapget,
    "Output",
    "vec2",
    "Particles.SSPR_ScreenUV",
)
add_pin(
    writer_module,
    writer_mapget,
    "Output",
    "vec2",
    "Particles.SSPR_ScreenVelocityUV",
)
writer_code = r"""// Current-frame particle trajectory mask; no temporal history.
const float TrailTime = 0.025f;
const float MaxTrailPx = 8.0f;
const float RadiusPx = 1.0f;
const int MaxTrailSteps = 8;
const int RadiusSteps = 1;

int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
bool validSize = W > 0 && H > 0;
bool validUV =
    ScreenUV.x >= 0.0f && ScreenUV.x < 1.0f &&
    ScreenUV.y >= 0.0f && ScreenUV.y < 1.0f;
int safeW = max(W, 1);
int safeH = max(H, 1);
float2 gridSize = float2(safeW, safeH);
float2 headPx = saturate(ScreenUV) * gridSize;
float2 velocityPx = ScreenVelocityUV * gridSize;
float speedPx = length(velocityPx);
float2 tangent = speedPx > 0.001f
    ? velocityPx / speedPx
    : float2(0.0f, 0.0f);
float trailPx = clamp(speedPx * TrailTime, 0.0f, MaxTrailPx);
int activeSteps = min((int)ceil(trailPx), MaxTrailSteps);

for (int stepIndex = 0; stepIndex <= MaxTrailSteps; ++stepIndex)
{
    bool activeStep =
        validSize && validUV && stepIndex <= activeSteps;
    float stepDistance = min((float)stepIndex, trailPx);
    int2 centerPx = int2(floor(headPx - tangent * stepDistance));
    for (int offsetY = -RadiusSteps; offsetY <= RadiusSteps; ++offsetY)
    {
        for (int offsetX = -RadiusSteps; offsetX <= RadiusSteps; ++offsetX)
        {
            float2 offset = float2(offsetX, offsetY);
            int2 writePx = centerPx + int2(offsetX, offsetY);
            bool shouldWrite =
                activeStep &&
                dot(offset, offset) <= RadiusPx * RadiusPx &&
                writePx.x >= 0 && writePx.x < safeW &&
                writePx.y >= 0 && writePx.y < safeH;
            if (shouldWrite)
            {
                TrajectoryGrid.SetValueAtIndex(
                    writePx.x, writePx.y, 0, 1.0f);
            }
        }
    }
}
OutDummy = validSize && validUV ? 1.0f : 0.0f;
"""
writer_hlsl = result_ok(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        writer_module,
        writer_code,
        360,
        0,
    ),
    "Create writer HLSL",
)
for direction, pin_type, pin_name in (
    ("Input", "Grid2D", "TrajectoryGrid"),
    ("Input", "vec2", "ScreenUV"),
    ("Input", "vec2", "ScreenVelocityUV"),
    ("Output", "float", "OutDummy"),
):
    add_pin(
        writer_module,
        writer_hlsl,
        direction,
        pin_type,
        pin_name,
    )
writer_mapset = add_output(
    writer_module, "Particles.SSPR_WriteMark", "float"
)
ensure_connect(
    writer_module,
    writer_mapget,
    "Module.TrajectoryGrid",
    writer_hlsl,
    "TrajectoryGrid",
)
ensure_connect(
    writer_module,
    writer_mapget,
    "Particles.SSPR_ScreenUV",
    writer_hlsl,
    "ScreenUV",
)
ensure_connect(
    writer_module,
    writer_mapget,
    "Particles.SSPR_ScreenVelocityUV",
    writer_hlsl,
    "ScreenVelocityUV",
)
ensure_connect(
    writer_module,
    writer_hlsl,
    "OutDummy",
    writer_mapset,
    "Particles.SSPR_WriteMark",
)

# Preserve the Leader reference behavior: curl affects only this frame's solve.
reset_module = create_module(
    "ParticleUpdate", "SSPR_ResetVelocityAfterSolve"
)
created.append(reset_module)
reset_hlsl = result_ok(
    SERVICE.add_custom_hlsl_node(
        SYSTEM,
        EMITTER,
        reset_module,
        "OutVelocity = float3(0.0f, 0.0f, 0.0f);",
        320,
        0,
    ),
    "Create velocity reset HLSL",
)
add_pin(
    reset_module,
    reset_hlsl,
    "Output",
    "Vector",
    "OutVelocity",
)
reset_mapset = add_output(
    reset_module, "Particles.Velocity", "Vector"
)
ensure_connect(
    reset_module,
    reset_hlsl,
    "OutVelocity",
    reset_mapset,
    "Particles.Velocity",
)

# Authoring defaults: high-quality current-frame field and guaranteed clear
# before Particle Update writes into it.
patched_grids = []
for grid in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceGrid2DCollection
):
    path = grid.get_path_name()
    if SYSTEM not in path or writer_module not in path:
        continue
    grid.set_editor_property("num_cells_x", 2048)
    grid.set_editor_property("num_cells_y", 2048)
    grid.set_editor_property("num_attributes", 1)
    grid.set_editor_property("clear_before_non_iteration_stage", True)
    patched_grids.append(path)

if not patched_grids:
    raise RuntimeError("Writer Grid2D data interface was not found")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
summary = {
    "createdModules": created,
    "patchedGrids": patched_grids,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
}
print(
    "PARTICLE_PROJECTION_GRID="
    + json.dumps(summary, sort_keys=True)
)
if not applied or messages or not saved:
    raise RuntimeError(
        "White-particle projection/grid build failed: " + repr(summary)
    )
