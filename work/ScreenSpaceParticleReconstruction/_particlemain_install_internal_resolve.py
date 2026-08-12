import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
STAGE = "SSPR Resolve Grid To Material"
MODULE = "SSPR_ResolveGridToSimRT"
GRID_VARIABLE = "User.SSPR_TrajectoryGrid"
RT_VARIABLE = "User.SSPR_SimRT"
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
            "Connect failed: {}.{} -> {}.{}".format(
                from_node, from_pin, to_node, to_pin
            )
        )


rt_result = SERVICE.create_internal_render_target2d_user_parameter(
    SYSTEM, RT_VARIABLE, 2048, 2048
)
if not rt_result.success:
    raise RuntimeError("Create internal SimRT failed: " + str(rt_result.message))

stage_result = SERVICE.create_simulation_stage(SYSTEM, EMITTER, STAGE)
if not stage_result.success:
    raise RuntimeError("Create resolve stage failed: " + str(stage_result.message))

config_result = SERVICE.configure_grid2d_simulation_stage(
    SYSTEM, EMITTER, STAGE, GRID_VARIABLE
)
if not config_result.success:
    raise RuntimeError("Configure resolve stage failed: " + str(config_result.message))

existing = {str(name) for name in SERVICE.list_scratch_modules(SYSTEM, EMITTER)}
created_module = False
if MODULE not in existing:
    module_result = SERVICE.create_scratch_module(
        SYSTEM,
        EMITTER,
        "SimulationStage:" + STAGE,
        MODULE,
    )
    if not module_result.success:
        raise RuntimeError("Create resolve module failed: " + str(module_result.message))
    MODULE = str(module_result.module_name)
    created_module = True

if created_module:
    map_get = require(
        SERVICE.add_node(SYSTEM, EMITTER, MODULE, "MapGet", 0, 0),
        "Create resolve MapGet",
    )
    add_pin(map_get, "Output", "Grid2D", GRID_VARIABLE)
    add_pin(map_get, "Output", "RenderTarget2D", RT_VARIABLE)

    hlsl_code = r"""// Resolve the auto-cleared current-frame Grid2D field into a
// Niagara-owned texture that the sprite renderer can bind to the material.
int GridW = 1;
int GridH = 1;
TrajectoryGrid.GetNumCells(GridW, GridH);

int CellX = 0;
int CellY = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(CellX, CellY);

float Density = 0.0f;
bool ValidGrid =
    GridW > 0 && GridH > 0 &&
    CellX >= 0 && CellX < GridW &&
    CellY >= 0 && CellY < GridH;
if (ValidGrid)
{
    TrajectoryGrid.GetGridValue(CellX, CellY, 0, Density);
}

int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = ValidGrid && ValidRT
    ? clamp((int)(((float)CellX + 0.5f) * (float)RTW / (float)GridW), 0, RTW - 1)
    : 0;
int DstY = ValidGrid && ValidRT
    ? clamp((int)(((float)CellY + 0.5f) * (float)RTH / (float)GridH), 0, RTH - 1)
    : 0;

SimRT.SetRenderTargetValue(
    ValidGrid && ValidRT,
    DstX,
    DstY,
    float4(Density, Density, Density, Density));
OutMark = Density;
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
        "Create resolve HLSL",
    )
    for direction, type_name, pin_name in (
        ("Input", "Grid2D", "TrajectoryGrid"),
        ("Input", "RenderTarget2D", "SimRT"),
        ("Output", "float", "OutMark"),
    ):
        add_pin(hlsl, direction, type_name, pin_name)

    map_set = require(
        SERVICE.add_module_output(
            SYSTEM,
            EMITTER,
            MODULE,
            "StackContext.SSPR_ResolveMark",
            "float",
        ),
        "Create resolve stage output",
    )
    connect(map_get, GRID_VARIABLE, hlsl, "TrajectoryGrid")
    connect(map_get, RT_VARIABLE, hlsl, "SimRT")
    connect(hlsl, "OutMark", map_set, "StackContext.SSPR_ResolveMark")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))

result = {
    "internalRT": str(rt_result.script_path),
    "stage": str(stage_result.module_name),
    "configured": bool(config_result.success),
    "module": MODULE,
    "createdModule": created_module,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print("PARTICLE_INTERNAL_RESOLVE=" + json.dumps(result, sort_keys=True))
if not applied or not saved or messages:
    raise RuntimeError("Internal resolve validation failed: " + repr(result))
