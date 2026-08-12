import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
queries = (
    "Texture Render Target",
    "Niagara Variable Texture",
    "Set Niagara Variable",
    "Create Dynamic Material Instance",
    "Draw Material to Render Target",
    "Clear Render Target 2D",
    "Set Texture Parameter Value",
    "Set Scalar Parameter Value",
    "Set Variable Texture Render Target",
    "Add Tick Prerequisite Component",
    "Activate",
)

result = {}
for query in queries:
    items = unreal.BlueprintService.discover_nodes(BP, query, "", 30)
    result[query] = [
        {
            "display": str(item.display_name),
            "category": str(item.category),
            "key": str(item.spawner_key),
            "class": str(item.node_class),
            "pure": bool(item.is_pure),
        }
        for item in items
    ]
print("M2A_VIBE_BP_NODES=" + json.dumps(result, sort_keys=True))
