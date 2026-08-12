import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
queries = (
    "Set Material",
    "Set World Location And Rotation",
    "Set World Scale 3D",
    "Get Viewport Size",
    "Get FOV Angle",
    "Get Player Controller",
    "Degrees To Radians",
    "Tan",
    "Divide Float",
    "Multiply Float",
    "Make Vector",
    "Set World Location",
    "Set World Rotation",
    "Vector Float",
    "Add Vector",
)

result = {
    "hierarchy": [
        {
            "name": str(item.component_name),
            "class": str(item.component_class),
            "parent": str(item.attach_parent),
        }
        for item in unreal.BlueprintService.get_component_hierarchy(BP)
    ],
    "queries": {},
}
for query in queries:
    result["queries"][query] = [
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
            40,
        )
    ]
print("M2CARD_DISCOVERY=" + json.dumps(result, sort_keys=True))
