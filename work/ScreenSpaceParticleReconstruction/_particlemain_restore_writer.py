import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_WriteParticleTrails"
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
TARGET_NAME = "SSPR_TrajectoryRT_Runtime"
SERVICE = unreal.NiagaraScratchPadService

original_code = r"""// Current-frame particle trajectory mask; no temporal history.
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
hlsl = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
    if str(node.node_type) == "CustomHlsl"
)
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl, original_code
):
    raise RuntimeError("Failed to restore trajectory writer HLSL")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == ACTOR_LABEL
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
target = next(
    item
    for item in unreal.ObjectIterator(
        unreal.TextureRenderTarget2D
    )
    if item.get_name() == TARGET_NAME
    and component.get_path_name() in item.get_path_name()
)
system = unreal.load_object(None, SYSTEM)
component.deactivate()
component.set_asset(None)
component.set_asset(system)
component.set_variable_texture_render_target(
    "User.SSPR_TrajectoryRT", target
)
component.set_force_solo(True)
component.reinitialize_system()
component.activate(True)
result = {
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
    "active": bool(component.is_active()),
}
print(
    "PARTICLE_WRITER_RESTORED="
    + json.dumps(result, sort_keys=True)
)
if not applied or messages or not saved or not result["active"]:
    raise RuntimeError(
        "Trajectory writer restoration failed: " + repr(result)
    )
