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

for component in actor.get_components_by_class(unreal.NiagaraComponent):
    component.deactivate()

print(
    "M2A_HOLD_BEGIN "
    + json.dumps(
        {
            "actor": actor.get_path_name(),
            "bWriteHistoryA": actor.get_editor_property("bWriteHistoryA"),
            "LatestHistory": actor.get_editor_property("LatestHistory").get_path_name(),
            "DecayRate": actor.get_editor_property("DecayRate"),
            "ReprojectionValue": actor.get_editor_property("ReprojectionValue"),
        },
        ensure_ascii=False,
    )
)
