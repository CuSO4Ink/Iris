import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
service = unreal.BlueprintService
bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("M2 orchestrator Blueprint is missing")

variables = (
    ("SmokeRT", "UTextureRenderTarget2D", ""),
    ("SmokeMaterial", "UMaterialInterface", ""),
    ("SmokeMID", "UMaterialInstanceDynamic", ""),
)
result = {"variables": {}, "defaults": {}}
for name, type_name, default_value in variables:
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
defaults = {
    "SmokeRT": "/Game/SSPR_Validation/M2/RT_SSPR_Smoke.RT_SSPR_Smoke",
    "SmokeMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_SmokeResolve.M_SSPR_SmokeResolve"
    ),
}
for name, value in defaults.items():
    result["defaults"][name] = bool(
        service.set_variable_default_value(BP_PATH, name, value)
    )

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
result["status"] = str(bp.get_editor_property("status"))
result["saved"] = bool(
    unreal.EditorAssetLibrary.save_asset(BP_PATH, False)
)
print("M2C_BP_CONFIG=" + json.dumps(result, sort_keys=True))
if not result["saved"] or "ERROR" in result["status"].upper():
    raise RuntimeError("M2-C Blueprint configuration failed: " + repr(result))
