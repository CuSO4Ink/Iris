import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
service = unreal.BlueprintService

bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("M2 orchestrator Blueprint is missing")

variable_specs = (
    ("CoreRT", "UTextureRenderTarget2D", ""),
    ("BlurSmallRT", "UTextureRenderTarget2D", ""),
    ("BlurLargeRT", "UTextureRenderTarget2D", ""),
    ("DensityRT", "UTextureRenderTarget2D", ""),
    ("CoreMaterial", "UMaterialInterface", ""),
    ("SmallBlurMaterial", "UMaterialInterface", ""),
    ("LargeBlurMaterial", "UMaterialInterface", ""),
    ("DensityMaterial", "UMaterialInterface", ""),
    ("CoreMID", "UMaterialInstanceDynamic", ""),
    ("SmallBlurMID", "UMaterialInstanceDynamic", ""),
    ("LargeBlurMID", "UMaterialInstanceDynamic", ""),
    ("DensityMID", "UMaterialInstanceDynamic", ""),
)

results = {"variables": {}, "defaults": {}}
for name, type_name, default_value in variable_specs:
    if service.variable_exists(BP_PATH, name):
        results["variables"][name] = "existing"
        continue
    results["variables"][name] = bool(
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
    "CoreRT": "/Game/SSPR_Validation/M2/RT_SSPR_Core.RT_SSPR_Core",
    "BlurSmallRT": (
        "/Game/SSPR_Validation/M2/"
        "RT_SSPR_BlurSmall.RT_SSPR_BlurSmall"
    ),
    "BlurLargeRT": (
        "/Game/SSPR_Validation/M2/"
        "RT_SSPR_BlurLarge.RT_SSPR_BlurLarge"
    ),
    "DensityRT": (
        "/Game/SSPR_Validation/M2/"
        "RT_SSPR_Density.RT_SSPR_Density"
    ),
    "CoreMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_CoreExtract.M_SSPR_CoreExtract"
    ),
    "SmallBlurMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_BlurSmall.M_SSPR_BlurSmall"
    ),
    "LargeBlurMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_BlurLarge.M_SSPR_BlurLarge"
    ),
    "DensityMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_DensityCombine.M_SSPR_DensityCombine"
    ),
}
for name, value in defaults.items():
    results["defaults"][name] = bool(
        service.set_variable_default_value(BP_PATH, name, value)
    )

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
status = str(bp.get_editor_property("status"))
saved = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))
results["status"] = status
results["saved"] = saved
results["variableCount"] = len(service.list_variables(BP_PATH))
print("M2B_BP_CONFIG=" + json.dumps(results, sort_keys=True))

if not saved or "ERROR" in status.upper():
    raise RuntimeError("M2-B Blueprint configuration failed: " + repr(results))
