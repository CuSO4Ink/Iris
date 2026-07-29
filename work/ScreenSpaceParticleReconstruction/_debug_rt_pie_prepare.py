import json
import time
import unreal

SOURCE = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main"
)
DEBUG_ROOT = "/Game/SSPR_Validation/Debug"
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
LABEL = "SSPR_RTWriteProbe_Temporary"
SERVICE = unreal.NiagaraScratchPadService

probe_code = r"""
int W = 1;
int H = 1;
TrajectoryGrid.GetNumCells(W, H);
int2 center = int2(max(W / 2, 0), max(H / 2, 0));
for (int y = -8; y <= 8; ++y)
{
    for (int x = -8; x <= 8; ++x)
    {
        int2 p = center + int2(x, y);
        if (p.x >= 0 && p.x < W && p.y >= 0 && p.y < H)
        {
            TrajectoryGrid.SetValueAtIndex(p.x, p.y, 0, 1.0f);
        }
    }
}
OutMark = (W > 0 && H > 0) ? 1.0f : 0.0f;
"""

level_editor = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
if level_editor.is_in_play_in_editor():
    raise RuntimeError("PIE is already active")

actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() == LABEL:
        actor_subsystem.destroy_actor(actor)

unreal.EditorAssetLibrary.make_directory(DEBUG_ROOT)
suffix = str(int(time.time() * 1000))
debug_package = (
    DEBUG_ROOT + "/NS_SSPR_RTWriteProbe_" + suffix
)
debug_asset = unreal.EditorAssetLibrary.duplicate_asset(
    SOURCE, debug_package
)
if not isinstance(debug_asset, unreal.NiagaraSystem):
    raise RuntimeError("Failed to duplicate Niagara debug system")
debug_system = debug_asset.get_path_name()

hlsl = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(
        debug_system, EMITTER, MODULE
    )
    if str(node.node_type) == "CustomHlsl"
)
if not SERVICE.set_custom_hlsl_code(
    debug_system, EMITTER, MODULE, hlsl, probe_code
):
    raise RuntimeError("Failed to install PIE Grid2D probe")
applied = bool(SERVICE.apply_changes(debug_system))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(
        debug_system, False
    )
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(debug_package, False)
)
if not applied or messages or not saved:
    raise RuntimeError(
        "PIE probe compile failed: "
        + repr(
            {
                "applied": applied,
                "messages": messages,
                "saved": saved,
            }
        )
    )

actor = actor_subsystem.spawn_actor_from_class(
    unreal.NiagaraActor,
    unreal.Vector(0.0, 0.0, 0.0),
    unreal.Rotator(0.0, 0.0, 0.0),
    False,
)
actor.set_actor_label(LABEL)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
component.set_asset(debug_asset)
component.set_force_solo(True)
component.reinitialize_system()
component.activate(True)

level_editor.editor_request_begin_play()
print(
    "RT_PIE_PREPARED="
    + json.dumps(
        {
            "debugPackage": debug_package,
            "debugSystem": debug_system,
            "actor": actor.get_path_name(),
            "componentActive": bool(component.is_active()),
            "pieRequested": True,
        },
        sort_keys=True,
    )
)
