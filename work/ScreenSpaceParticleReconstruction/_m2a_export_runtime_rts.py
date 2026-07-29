import json
import unreal

ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"
actor = None
for candidate in unreal.ObjectIterator(unreal.Actor):
    try:
        world = candidate.get_world()
        if (
            candidate.get_actor_label() == ACTOR_LABEL
            and world
            and "UEDPIE" in world.get_path_name()
        ):
            actor = candidate
            break
    except Exception:
        pass
if actor is None:
    raise RuntimeError("Runtime orchestrator actor not found")

output_directory = unreal.Paths.project_saved_dir()
outputs = {}
state = {
    "bWriteHistoryA": actor.get_editor_property("bWriteHistoryA"),
    "LatestHistory": actor.get_editor_property("LatestHistory").get_path_name(),
}
for label, asset_path in [
    ("Current", "/Game/SSPR_Validation/M2/RT_SSPR_Current.RT_SSPR_Current"),
    ("HistoryA", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryA.RT_SSPR_HistoryA"),
    ("HistoryB", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryB.RT_SSPR_HistoryB"),
]:
    render_target = unreal.load_object(None, asset_path)
    filename = "M2A_PRODUCTION_DECAYED_{}".format(label)
    unreal.RenderingLibrary.export_render_target(
        actor,
        render_target,
        output_directory,
        filename,
    )
    outputs[label] = output_directory + filename

print("M2A_EXPORTS " + json.dumps({"state": state, "outputs": outputs}, ensure_ascii=False))
