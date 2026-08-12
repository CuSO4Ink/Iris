import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
GRAPH = "EventGraph"
KEYS = {
    "GetCameraManager": "FUNC GameplayStatics::GetPlayerCameraManager",
    "GetCameraLocation": "FUNC PlayerCameraManager::GetCameraLocation",
    "GetCameraRotation": "FUNC PlayerCameraManager::GetCameraRotation",
    "GetForward": "FUNC KismetMathLibrary::GetForwardVector",
    "GetRight": "FUNC KismetMathLibrary::GetRightVector",
    "GetUp": "FUNC KismetMathLibrary::GetUpVector",
    "VectorToColor": "FUNC KismetMathLibrary::Conv_VectorToLinearColor",
    "SetVector": "FUNC MaterialInstanceDynamic::SetVectorParameterValue",
    "IsValidObject": "FUNC KismetSystemLibrary::IsValid",
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
            6000.0,
            float(index * 300),
        )
        if not node_id:
            result[label] = {"error": "creation failed", "key": key}
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
                for pin in service.get_node_pins(BP, GRAPH, str(node_id))
            ],
        }
finally:
    for node_id in created:
        service.delete_node(BP, GRAPH, node_id)

unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(BP))
unreal.EditorAssetLibrary.save_asset(BP, False)
print("M2A_CAMERA_PINS=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
