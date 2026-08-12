import json
import unreal


BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("M2 orchestrator Blueprint is missing")

service = unreal.BlueprintService
variable_specs = (
    ("SplatRadiusPx", "float", "0.75"),
    ("TrailTimeSeconds", "float", "0.075"),
    ("MaxTrailPx", "float", "96.0"),
    ("SmallBlurRadiusPx", "float", "8.0"),
    ("LargeBlurRadiusPx", "float", "20.0"),
    ("CoreWeight", "float", "0.60"),
    ("SmallBlurWeight", "float", "0.90"),
    ("LargeBlurWeight", "float", "0.45"),
)
result = {
    "variables": {},
    "defaults": {},
    "instanceEditable": {},
    "categories": {},
}

for name, type_name, default_value in variable_specs:
    if service.variable_exists(BP_PATH, name):
        result["variables"][name] = "existing"
    else:
        result["variables"][name] = bool(
            service.add_member_variable(
                BP_PATH,
                name,
                type_name,
                default_value,
                False,
                "",
            )
        )

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
for name, _, default_value in variable_specs:
    result["defaults"][name] = bool(
        service.set_variable_default_value(
            BP_PATH,
            name,
            default_value,
        )
    )
    result["instanceEditable"][name] = bool(
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
            bp,
            name,
            True,
        )
    )
    result["categories"][name] = bool(
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(
            bp,
            name,
            "SSPR Tuning",
        )
    )

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
result["saved"] = bool(
    unreal.EditorAssetLibrary.save_asset(BP_PATH, False)
)
result["verified"] = {}
for name, _, _ in variable_specs:
    info = service.get_variable_info(BP_PATH, name)
    if not info:
        continue
    result["verified"][name] = {
        "category": str(info.category),
        "instanceEditable": bool(info.is_instance_editable),
    }
print("M2PARAMS_BP_CONFIG=" + json.dumps(result, sort_keys=True))
if (
    not result["saved"]
    or not all(result["defaults"].values())
    or len(result["verified"]) != len(variable_specs)
    or not all(
        item["instanceEditable"]
        and item["category"] == "SSPR Tuning"
        for item in result["verified"].values()
    )
):
    raise RuntimeError("M2 parameter Blueprint configuration failed: " + repr(result))
