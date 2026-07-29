import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
queries = (
    "Get Player Camera Manager",
    "Get Camera Location",
    "Get Camera Rotation",
    "Get FOV Angle",
    "Get Forward Vector",
    "Get Right Vector",
    "Get Up Vector",
    "To LinearColor Vector",
    "Convert Vector LinearColor",
    "Set Vector Parameter Value",
    "Is Valid",
)

result = {}
for query in queries:
    items = unreal.BlueprintService.discover_nodes(BP, query, "", 20)
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
print("M2A_CAMERA_NODES=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
