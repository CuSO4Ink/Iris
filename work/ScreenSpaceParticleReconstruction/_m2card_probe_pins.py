import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
GRAPH = "EventGraph"
KEYS = {
    "SetMaterial": "FUNC PrimitiveComponent::SetMaterial",
    "SetWorldTransform": "FUNC SceneComponent::K2_SetWorldLocationAndRotation",
    "MultiplyVectorFloat": "FUNC KismetMathLibrary::Multiply_VectorFloat",
    "AddVectorVector": "FUNC KismetMathLibrary::Add_VectorVector",
}
service = unreal.BlueprintService
result = {}
created = []
try:
    for index, (label, key) in enumerate(KEYS.items()):
        node_id = service.create_node_by_key(
            BP,
            GRAPH,
            key,
            5200.0,
            float(index * 320),
        )
        if not node_id:
            result[label] = {"key": key, "error": "creation failed"}
            continue
        created.append(str(node_id))
        result[label] = {
            "key": key,
            "nodeId": str(node_id),
            "pins": [
                {
                    "name": str(pin.pin_name),
                    "type": str(pin.pin_type),
                    "input": bool(pin.is_input),
                    "default": str(pin.default_value),
                }
                for pin in service.get_node_pins(
                    BP,
                    GRAPH,
                    str(node_id),
                )
            ],
        }
finally:
    for node_id in created:
        service.delete_node(BP, GRAPH, node_id)
unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(BP))
unreal.EditorAssetLibrary.save_asset(BP, False)
print("M2CARD_PINS=" + json.dumps(result, sort_keys=True))
