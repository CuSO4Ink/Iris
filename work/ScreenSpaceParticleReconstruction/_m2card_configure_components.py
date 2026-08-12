import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
service = unreal.BlueprintService
bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("M2 orchestrator Blueprint is missing")

result = {"components": {}, "properties": {}, "variables": {}}
component_names = {
    str(item.component_name)
    for item in service.get_component_hierarchy(BP_PATH)
}

if "SmokeCardPivot" not in component_names:
    result["components"]["SmokeCardPivot"] = bool(
        service.add_component(
            BP_PATH,
            "SceneComponent",
            "SmokeCardPivot",
            "SSPRNiagara",
        )
    )
else:
    result["components"]["SmokeCardPivot"] = "existing"

component_names = {
    str(item.component_name)
    for item in service.get_component_hierarchy(BP_PATH)
}
if "SmokeCard" not in component_names:
    result["components"]["SmokeCard"] = bool(
        service.add_component(
            BP_PATH,
            "StaticMeshComponent",
            "SmokeCard",
            "SmokeCardPivot",
        )
    )
else:
    result["components"]["SmokeCard"] = "existing"

essential_properties = {
    "StaticMesh": "/Engine/BasicShapes/Plane.Plane",
    "RelativeRotation": "(Pitch=90.0,Yaw=0.0,Roll=0.0)",
    "RelativeScale3D": "(X=4.0,Y=4.0,Z=1.0)",
}
for property_name, value in essential_properties.items():
    result["properties"][property_name] = bool(
        service.set_component_property(
            BP_PATH,
            "SmokeCard",
            property_name,
            value,
        )
    )

optional_properties = {
    "CastShadow": "false",
    "bCastDynamicShadow": "false",
    "bCastStaticShadow": "false",
    "TranslucencySortPriority": "100",
    "bReceivesDecals": "false",
    "Mobility": "Movable",
}
for property_name, value in optional_properties.items():
    try:
        result["properties"][property_name] = bool(
            service.set_component_property(
                BP_PATH,
                "SmokeCard",
                property_name,
                value,
            )
        )
    except Exception as exc:
        result["properties"][property_name] = {"optionalError": str(exc)}

if service.variable_exists(BP_PATH, "SmokeCardDistance"):
    result["variables"]["SmokeCardDistance"] = "existing"
else:
    result["variables"]["SmokeCardDistance"] = bool(
        service.add_member_variable(
            BP_PATH,
            "SmokeCardDistance",
            "float",
            "100.0",
            False,
            "",
        )
    )

if service.variable_exists(BP_PATH, "SmokeCardMaterial"):
    result["variables"]["SmokeCardMaterial"] = "existing"
else:
    result["variables"]["SmokeCardMaterial"] = bool(
        service.add_member_variable(
            BP_PATH,
            "SmokeCardMaterial",
            "UMaterialInterface",
            "",
            False,
            "",
        )
    )

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
result["distanceDefault"] = bool(
    service.set_variable_default_value(
        BP_PATH,
        "SmokeCardDistance",
        "100.0",
    )
)
result["materialDefault"] = bool(
    service.set_variable_default_value(
        BP_PATH,
        "SmokeCardMaterial",
        (
            "/Game/SSPR_Validation/M2/"
            "MI_SSPR_SmokeCard_Default.MI_SSPR_SmokeCard_Default"
        ),
    )
)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
result["status"] = str(bp.get_editor_property("status"))
result["saved"] = bool(
    unreal.EditorAssetLibrary.save_asset(BP_PATH, False)
)
result["hierarchy"] = [
    {
        "name": str(item.component_name),
        "class": str(item.component_class),
        "parent": str(item.attach_parent),
    }
    for item in service.get_component_hierarchy(BP_PATH)
]
print("M2CARD_COMPONENTS=" + json.dumps(result, sort_keys=True))

if (
    not result["saved"]
    or "ERROR" in result["status"].upper()
    or not all(result["properties"].get(name) is True for name in essential_properties)
):
    raise RuntimeError("Smoke Card component setup failed: " + repr(result))
