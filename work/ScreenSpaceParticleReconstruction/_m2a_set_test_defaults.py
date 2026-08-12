import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
service = unreal.BlueprintService
blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
if blueprint is None:
    raise RuntimeError("Orchestrator Blueprint not found")

results = {
    "DecayRate": bool(service.set_variable_default_value(BP_PATH, "DecayRate", "0.0")),
    "ReprojectionValue": bool(
        service.set_variable_default_value(BP_PATH, "ReprojectionValue", "1.0")
    ),
}
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
results["saved"] = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))
print("M2A_TEST_DEFAULTS " + json.dumps(results, ensure_ascii=False))
