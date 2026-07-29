import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
SERVICE = unreal.NiagaraScratchPadService

writer_code = r"""// One current-frame splat per alive white source particle.
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

hlsl = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(
        SYSTEM, EMITTER, MODULE
    )
    if str(node.node_type) == "CustomHlsl"
)
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl, writer_code
):
    raise RuntimeError("Failed to restore stage writer HLSL")
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
component.reinitialize_system()
component.activate(True)
result = {
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
    "active": bool(component.is_active()),
}
print(
    "PARTICLE_STAGE_WRITER_RESTORED="
    + json.dumps(result, sort_keys=True)
)
if not applied or not saved or messages:
    raise RuntimeError(
        "Stage writer restoration failed: " + repr(result)
    )
