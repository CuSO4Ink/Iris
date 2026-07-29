import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"

bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("Orchestrator Blueprint is missing")

service = unreal.BlueprintService
results = {"component": None, "variables": {}}

hierarchy = service.get_component_hierarchy(BP_PATH)
component_names = {str(item.component_name) for item in hierarchy}
if "SSPRNiagara" not in component_names:
    results["component"] = bool(
        service.add_component(
            BP_PATH,
            "NiagaraComponent",
            "SSPRNiagara",
            "",
        )
    )
else:
    results["component"] = "existing"

try:
    results["componentAsset"] = bool(
        service.set_component_property(
            BP_PATH,
            "SSPRNiagara",
            "Asset",
            SYSTEM_PATH,
        )
    )
except Exception as exc:
    results["componentAsset"] = {"error": str(exc)}

variable_specs = (
    ("CurrentRT", "UTextureRenderTarget2D", ""),
    ("HistoryA", "UTextureRenderTarget2D", ""),
    ("HistoryB", "UTextureRenderTarget2D", ""),
    ("TemporalMaterial", "UMaterialInterface", ""),
    ("TemporalMID", "UMaterialInstanceDynamic", ""),
    ("LatestHistory", "UTextureRenderTarget2D", ""),
    ("bWriteHistoryA", "bool", "true"),
    ("bHistoryValid", "bool", "false"),
    ("bEnableReprojection", "bool", "true"),
    ("HistoryValidValue", "float", "0.0"),
    ("ReprojectionValue", "float", "1.0"),
    ("DecayRate", "float", "6.0"),
    ("RepresentativeDepth", "float", "1000.0"),
    ("PreviousCameraPosition", "FVector", "(X=0.0,Y=0.0,Z=0.0)"),
    ("PreviousCameraForward", "FVector", "(X=1.0,Y=0.0,Z=0.0)"),
    ("PreviousCameraRight", "FVector", "(X=0.0,Y=1.0,Z=0.0)"),
    ("PreviousCameraUp", "FVector", "(X=0.0,Y=0.0,Z=1.0)"),
    ("CameraDataValid", "float", "0.0"),
)

for name, type_name, default_value in variable_specs:
    if service.variable_exists(BP_PATH, name):
        results["variables"][name] = "existing"
        continue
    try:
        added = service.add_member_variable(
            BP_PATH,
            name,
            type_name,
            default_value,
            False,
            "",
        )
        results["variables"][name] = bool(added)
    except Exception as exc:
        results["variables"][name] = {"error": str(exc)}

unreal.BlueprintEditorLibrary.compile_blueprint(bp)

default_values = {
    "CurrentRT": "/Game/SSPR_Validation/M2/RT_SSPR_Current.RT_SSPR_Current",
    "HistoryA": "/Game/SSPR_Validation/M2/RT_SSPR_HistoryA.RT_SSPR_HistoryA",
    "HistoryB": "/Game/SSPR_Validation/M2/RT_SSPR_HistoryB.RT_SSPR_HistoryB",
    "LatestHistory": "/Game/SSPR_Validation/M2/RT_SSPR_HistoryA.RT_SSPR_HistoryA",
    "TemporalMaterial": (
        "/Game/SSPR_Validation/M2/"
        "M_SSPR_TemporalCombine.M_SSPR_TemporalCombine"
    ),
    "bWriteHistoryA": "true",
    "bHistoryValid": "false",
    "bEnableReprojection": "true",
    "HistoryValidValue": "0.0",
    "ReprojectionValue": "1.0",
    "DecayRate": "6.0",
    "RepresentativeDepth": "1000.0",
    "PreviousCameraPosition": "(X=0.0,Y=0.0,Z=0.0)",
    "PreviousCameraForward": "(X=1.0,Y=0.0,Z=0.0)",
    "PreviousCameraRight": "(X=0.0,Y=1.0,Z=0.0)",
    "PreviousCameraUp": "(X=0.0,Y=0.0,Z=1.0)",
    "CameraDataValid": "0.0",
}
results["defaults"] = {}
for name, value in default_values.items():
    try:
        results["defaults"][name] = bool(
            service.set_variable_default_value(BP_PATH, name, value)
        )
    except Exception as exc:
        results["defaults"][name] = {"error": str(exc)}

try:
    results["autoActivate"] = bool(
        service.set_component_property(
            BP_PATH,
            "SSPRNiagara",
            "bAutoActivate",
            "false",
        )
    )
except Exception as exc:
    results["autoActivate"] = {"error": str(exc)}

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
saved = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))
results["saved"] = saved
results["hierarchy"] = [
    {
        "name": str(item.component_name),
        "class": str(item.component_class),
        "parent": str(item.attach_parent),
    }
    for item in service.get_component_hierarchy(BP_PATH)
]
results["variableInfo"] = [
    {
        "name": str(item.variable_name),
        "type": str(item.variable_type),
        "default": str(item.default_value),
    }
    for item in service.list_variables(BP_PATH)
]

print("M2A_BP_CONFIG=" + json.dumps(results, sort_keys=True))
