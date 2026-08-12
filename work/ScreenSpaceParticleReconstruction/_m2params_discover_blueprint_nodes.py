import json
import unreal


BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
queries = (
    "Set Niagara Variable Float",
    "Set Variable Float",
    "Get World Location",
    "Get Component Location",
    "Distance Vector",
    "Vector Distance",
    "Get Distance To",
)
result = {}
for query in queries:
    result[query] = [
        {
            "display": str(item.display_name),
            "category": str(item.category),
            "key": str(item.spawner_key),
            "class": str(item.node_class),
            "pure": bool(item.is_pure),
        }
        for item in unreal.BlueprintService.discover_nodes(
            BP,
            query,
            "",
            50,
        )
    ]
print("M2PARAMS_DISCOVERY=" + json.dumps(result, sort_keys=True))
