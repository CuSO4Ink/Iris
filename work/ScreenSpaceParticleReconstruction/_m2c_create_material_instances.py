import json
import unreal

FOLDER = "/Game/SSPR_Validation/M2"
PARENT_PATH = FOLDER + "/M_SSPR_SmokeResolve"
parent = unreal.load_asset(PARENT_PATH)
if not isinstance(parent, unreal.Material):
    raise RuntimeError("Smoke Resolve parent material is missing")

specs = {
    "MI_SSPR_Smoke_Default": {
        "scalars": {
            "Extinction": 2.6,
            "DensityScale": 1.0,
            "OpacityScale": 0.82,
            "EmissiveStrength": 1.0,
            "BlackPoint": 0.015,
        },
        "vectors": {
            "SmokeColor": unreal.LinearColor(0.62, 0.72, 0.82, 1.0),
        },
    },
    "MI_SSPR_Smoke_DensityDebug": {
        "scalars": {
            "Extinction": 1.4,
            "DensityScale": 1.0,
            "OpacityScale": 1.0,
            "EmissiveStrength": 1.0,
            "BlackPoint": 0.0,
        },
        "vectors": {
            "SmokeColor": unreal.LinearColor(1.0, 1.0, 1.0, 1.0),
        },
    },
}

results = {}
for name, parameters in specs.items():
    path = FOLDER + "/" + name
    instance = unreal.load_asset(path)
    created = False
    if instance is None:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name,
            FOLDER,
            unreal.MaterialInstanceConstant,
            factory,
        )
        created = True
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(path + " is missing or has the wrong class")
    instance.set_editor_property("parent", parent)
    for parameter_name, value in parameters["scalars"].items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance,
            parameter_name,
            float(value),
        )
    for parameter_name, value in parameters["vectors"].items():
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            instance,
            parameter_name,
            value,
        )
    saved = bool(unreal.EditorAssetLibrary.save_asset(path, False))
    results[name] = {
        "path": instance.get_path_name(),
        "created": created,
        "saved": saved,
    }
    if not saved:
        raise RuntimeError("Failed to save " + path)

bp_path = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
default_instance = FOLDER + (
    "/MI_SSPR_Smoke_Default.MI_SSPR_Smoke_Default"
)
set_default = bool(
    unreal.BlueprintService.set_variable_default_value(
        bp_path,
        "SmokeMaterial",
        default_instance,
    )
)
bp = unreal.load_asset(bp_path)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
bp_status = str(bp.get_editor_property("status"))
bp_saved = bool(unreal.EditorAssetLibrary.save_asset(bp_path, False))
result = {
    "instances": results,
    "orchestratorDefaultSet": set_default,
    "blueprintStatus": bp_status,
    "blueprintSaved": bp_saved,
}
print("M2C_INSTANCES=" + json.dumps(result, sort_keys=True))
if (
    not set_default
    or not bp_saved
    or "ERROR" in bp_status.upper()
):
    raise RuntimeError("M2-C instance setup failed: " + repr(result))
