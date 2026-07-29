import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
nodes = unreal.BlueprintService.get_nodes_in_graph(
    BP,
    "EventGraph",
    0,
    "",
    False,
)
result = [node.to_dict() for node in nodes]
print("M2A_BP_GRAPH=" + json.dumps(result, sort_keys=True))
