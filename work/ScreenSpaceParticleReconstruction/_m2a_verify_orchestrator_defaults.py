import json
import unreal

BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"

blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
blueprint_class = unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH)
if blueprint is None or blueprint_class is None:
    raise RuntimeError("Unable to load M2-A orchestrator Blueprint or generated class")

cdo = unreal.get_default_object(blueprint_class)

requested_properties = [
    "CurrentRT",
    "HistoryA",
    "HistoryB",
    "TemporalMaterial",
    "TemporalMID",
    "LatestHistory",
    "bWriteHistoryA",
    "bHistoryValid",
    "bEnableReprojection",
    "DecayRate",
    "RepresentativeDepth",
    "HistoryValidValue",
    "ReprojectionValue",
    "PreviousCameraPosition",
    "PreviousCameraForward",
    "PreviousCameraRight",
    "PreviousCameraUp",
    "CameraDataValid",
]

values = {}
for property_name in requested_properties:
    try:
        value = cdo.get_editor_property(property_name)
        values[property_name] = (
            value.get_path_name()
            if hasattr(value, "get_path_name")
            else value
        )
    except Exception as error:
        values[property_name] = "ERROR: {}".format(error)

components = []
for component in cdo.get_components_by_class(unreal.NiagaraComponent):
    asset = component.get_editor_property("asset")
    components.append(
        {
            "name": component.get_name(),
            "asset": asset.get_path_name() if asset else None,
            "auto_activate": component.get_editor_property("auto_activate"),
            "tick_enabled": component.get_editor_property("start_with_tick_enabled"),
        }
    )

result = {
    "blueprint": blueprint.get_path_name(),
    "class": blueprint_class.get_path_name(),
    "properties": values,
    "niagara_components": components,
}
print("M2A_DEFAULTS " + json.dumps(result, ensure_ascii=False, default=str))
