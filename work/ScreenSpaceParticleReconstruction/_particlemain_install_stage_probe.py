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

probe_code = r"""int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int2 center = int2(max(W, 1) / 2, max(H, 1) / 2);
for (int y = -32; y <= 32; ++y)
{
    for (int x = -32; x <= 32; ++x)
    {
        int2 p = center + int2(x, y);
        if (p.x >= 0 && p.x < W && p.y >= 0 && p.y < H)
        {
            TrajectoryGrid.SetValueAtIndex(p.x, p.y, 0, 1.0f);
        }
    }
}
OutMark = 1.0f;
"""

hlsl = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(
        SYSTEM, EMITTER, MODULE
    )
    if str(node.node_type) == "CustomHlsl"
)
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl, probe_code
):
    raise RuntimeError("Failed to install stage probe HLSL")
if not SERVICE.apply_changes(SYSTEM):
    raise RuntimeError("Stage probe ApplyChanges failed")
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
if messages:
    raise RuntimeError("Stage probe compile errors: " + repr(messages))

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
component.advance_simulation(30, 1.0 / 60.0)
print(
    "PARTICLE_STAGE_PROBE_INSTALLED="
    + json.dumps(
        {
            "module": MODULE,
            "hlsl": hlsl,
            "active": bool(component.is_active()),
        },
        sort_keys=True,
    )
)
