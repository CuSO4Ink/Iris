import json
import unreal


targets = {
    "BlueprintEditorLibrary": unreal.BlueprintEditorLibrary,
    "BlueprintService": unreal.BlueprintService,
}
result = {}
for label, target in targets.items():
    result[label] = [
        name
        for name in dir(target)
        if (
            "variable" in name.lower()
            or "editable" in name.lower()
            or "category" in name.lower()
        )
    ]
variables = unreal.BlueprintService.list_variables(
    "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
)
result["BlueprintVariableInfo"] = (
    dir(variables[0]) if variables else []
)
detail = unreal.BlueprintService.get_variable_info(
    "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator",
    "SplatRadiusPx",
)
result["DetailedRawType"] = str(type(detail))
result["DetailedRaw"] = repr(detail)
detail_item = detail[-1] if isinstance(detail, tuple) else detail
result["DetailedDir"] = dir(detail_item) if detail_item else []
result["DetailedDict"] = (
    detail_item.to_dict()
    if detail_item and hasattr(detail_item, "to_dict")
    else None
)
print("M2PARAMS_BP_API=" + json.dumps(result, sort_keys=True))
