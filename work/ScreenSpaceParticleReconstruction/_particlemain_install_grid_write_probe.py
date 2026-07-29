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

hlsl = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
    if str(node.node_type) == "CustomHlsl"
)
code = r"""
int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int centerX = max(W / 2, 0);
int centerY = max(H / 2, 0);
for (int y = -96; y <= 96; ++y)
{
    for (int x = -96; x <= 96; ++x)
    {
        int px = centerX + x;
        int py = centerY + y;
        if (px >= 0 && px < W && py >= 0 && py < H)
        {
            TrajectoryGrid.SetValueAtIndex(px, py, 0, 1.0f);
        }
    }
}
OutDummy = 1.0f;
"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, hlsl, code
):
    raise RuntimeError("Failed to install live Grid write probe")
if not SERVICE.apply_changes(SYSTEM):
    raise RuntimeError("Live Grid write probe did not apply")

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
print(
    "PARTICLE_GRID_WRITE_PROBE_INSTALLED="
    + json.dumps(
        {
            "hlsl": hlsl,
            "component": component.get_path_name(),
            "target": target.get_path_name(),
            "active": bool(component.is_active()),
        },
        sort_keys=True,
    )
)
