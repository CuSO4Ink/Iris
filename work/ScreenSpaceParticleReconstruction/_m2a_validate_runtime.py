import json
import unreal

BP_CLASS_FRAGMENT = "BP_SSPR_TemporalOrchestrator_C"
ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"

actors = []
for candidate in unreal.ObjectIterator(unreal.Actor):
    try:
        candidate_world = candidate.get_world()
        world_path = candidate_world.get_path_name() if candidate_world else ""
        if (
            candidate.get_actor_label() == ACTOR_LABEL
            and BP_CLASS_FRAGMENT in candidate.get_class().get_path_name()
            and "UEDPIE" in world_path
        ):
            actors.append(candidate)
    except Exception:
        pass
if len(actors) != 1:
    raise RuntimeError("Expected exactly one runtime orchestrator, found {}".format(len(actors)))
actor = actors[0]
world = actor.get_world()

def object_path(value):
    return value.get_path_name() if value and hasattr(value, "get_path_name") else None

runtime_values = {}
for property_name in [
    "CurrentRT",
    "HistoryA",
    "HistoryB",
    "TemporalMaterial",
    "TemporalMID",
    "LatestHistory",
    "bWriteHistoryA",
    "HistoryValidValue",
    "DecayRate",
    "RepresentativeDepth",
    "ReprojectionValue",
    "PreviousCameraPosition",
    "PreviousCameraForward",
    "PreviousCameraRight",
    "PreviousCameraUp",
    "CameraDataValid",
]:
    value = actor.get_editor_property(property_name)
    runtime_values[property_name] = object_path(value) if hasattr(value, "get_path_name") else value

niagara_components = []
for component in actor.get_components_by_class(unreal.NiagaraComponent):
    asset = component.get_asset()
    niagara_components.append(
        {
            "name": component.get_name(),
            "asset": object_path(asset),
            "active": component.is_active(),
            "tick_enabled": component.is_component_tick_enabled(),
            "owner": object_path(component.get_owner()),
        }
    )

mid = actor.get_editor_property("TemporalMID")
mid_values = {}
if mid:
    for parameter_name in [
        "DeltaSeconds",
        "DecayRate",
        "RepresentativeDepth",
        "HistoryValid",
        "ReprojectionEnabled",
        "CameraDataValid",
        "TanHalfHorizontalFOV",
        "ViewAspect",
    ]:
        try:
            mid_values[parameter_name] = mid.get_scalar_parameter_value(parameter_name)
        except Exception as error:
            mid_values[parameter_name] = "ERROR: {}".format(error)
    for parameter_name in ["CurrentTexture", "HistoryTexture"]:
        try:
            mid_values[parameter_name] = object_path(mid.get_texture_parameter_value(parameter_name))
        except Exception as error:
            mid_values[parameter_name] = "ERROR: {}".format(error)
    for parameter_name in [
        "CurrentCameraPosition",
        "CurrentCameraForward",
        "CurrentCameraRight",
        "CurrentCameraUp",
        "PreviousCameraPosition",
        "PreviousCameraForward",
        "PreviousCameraRight",
        "PreviousCameraUp",
    ]:
        try:
            mid_values[parameter_name] = str(
                mid.get_vector_parameter_value(parameter_name)
            )
        except Exception as error:
            mid_values[parameter_name] = "ERROR: {}".format(error)

rt_stats = {}
for label, asset_path in [
    ("Current", "/Game/SSPR_Validation/M2/RT_SSPR_Current.RT_SSPR_Current"),
    ("HistoryA", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryA.RT_SSPR_HistoryA"),
    ("HistoryB", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryB.RT_SSPR_HistoryB"),
]:
    render_target = unreal.load_object(None, asset_path)
    raw = unreal.RenderingLibrary.read_render_target_raw(world, render_target, True)
    mode = "raw"
    if raw is not None:
        values = [float(color.r) for color in raw]
    else:
        colors = unreal.RenderingLibrary.read_render_target(world, render_target, True)
        mode = "color"
        if colors is None:
            rt_stats[label] = {"error": "raw and color readback returned None"}
            continue
        values = [float(color.r) / 255.0 for color in colors]
    rt_stats[label] = {
        "mode": mode,
        "sample_count": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "nonzero_pixels": sum(1 for value in values if value > 0.001),
        "strong_pixels": sum(1 for value in values if value > 0.5),
    }

result = {
    "world": world.get_path_name(),
    "actor": actor.get_path_name(),
    "runtime_values": runtime_values,
    "niagara_components": niagara_components,
    "mid_values": mid_values,
    "rt_stats": rt_stats,
}
print("M2A_RUNTIME " + json.dumps(result, ensure_ascii=False, default=str))
