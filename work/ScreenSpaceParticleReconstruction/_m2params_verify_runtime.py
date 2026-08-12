import json
import math
import unreal


ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"


def find_pie_object(object_type, predicate):
    for candidate in unreal.ObjectIterator(object_type):
        try:
            world = candidate.get_world()
            if (
                world
                and "UEDPIE" in world.get_path_name()
                and predicate(candidate)
            ):
                return candidate
        except Exception:
            pass
    return None


actor = find_pie_object(
    unreal.Actor,
    lambda item: item.get_actor_label() == ACTOR_LABEL,
)
if actor is None:
    raise RuntimeError("Runtime M2 orchestrator actor not found")

camera_manager = find_pie_object(
    unreal.PlayerCameraManager,
    lambda item: True,
)
if camera_manager is None:
    raise RuntimeError("Runtime camera manager not found")

property_names = (
    "SplatRadiusPx",
    "TrailTimeSeconds",
    "MaxTrailPx",
    "SmallBlurRadiusPx",
    "LargeBlurRadiusPx",
    "CoreWeight",
    "SmallBlurWeight",
    "LargeBlurWeight",
)
actor_values = {
    name: float(actor.get_editor_property(name))
    for name in property_names
}

niagara_components = actor.get_components_by_class(unreal.NiagaraComponent)
if len(niagara_components) != 1:
    raise RuntimeError(
        "Expected one orchestrator Niagara component, got "
        + str(len(niagara_components))
    )
niagara = niagara_components[0]
niagara_values = {}
for parameter_name in (
    "User.SSPR_RadiusPx",
    "User.SSPR_TrailTime",
    "User.SSPR_MaxTrailPx",
):
    try:
        raw_value = niagara.get_variable_float(parameter_name)
        if isinstance(raw_value, tuple):
            if len(raw_value) != 2 or not raw_value[1]:
                raise RuntimeError("Niagara getter failed: " + repr(raw_value))
            raw_value = raw_value[0]
        niagara_values[parameter_name] = float(raw_value)
    except Exception as exc:
        niagara_values[parameter_name] = "ERROR: " + str(exc)

mid_specs = (
    ("TemporalMID", ("RepresentativeDepth",)),
    ("SmallBlurMID", ("RadiusPx",)),
    ("LargeBlurMID", ("RadiusPx",)),
    (
        "DensityMID",
        ("CoreWeight", "SmallBlurWeight", "LargeBlurWeight"),
    ),
)
mid_values = {}
for variable_name, parameter_names in mid_specs:
    mid = actor.get_editor_property(variable_name)
    if mid is None:
        mid_values[variable_name] = {"error": "MID is None"}
        continue
    mid_values[variable_name] = {}
    for parameter_name in parameter_names:
        try:
            mid_values[variable_name][parameter_name] = float(
                mid.get_scalar_parameter_value(parameter_name)
            )
        except Exception as exc:
            mid_values[variable_name][parameter_name] = "ERROR: " + str(exc)

actor_location = actor.get_actor_location()
camera_location = camera_manager.get_camera_location()
dx = camera_location.x - actor_location.x
dy = camera_location.y - actor_location.y
dz = camera_location.z - actor_location.z
measured_depth = math.sqrt(dx * dx + dy * dy + dz * dz)
material_depth = mid_values["TemporalMID"]["RepresentativeDepth"]
depth_error = (
    abs(material_depth - measured_depth)
    if isinstance(material_depth, float)
    else None
)

expected = {
    "User.SSPR_RadiusPx": actor_values["SplatRadiusPx"],
    "User.SSPR_TrailTime": actor_values["TrailTimeSeconds"],
    "User.SSPR_MaxTrailPx": actor_values["MaxTrailPx"],
}
niagara_matches = {
    name: (
        isinstance(niagara_values[name], float)
        and abs(niagara_values[name] - value) < 0.001
    )
    for name, value in expected.items()
}

result = {
    "actor": actor.get_path_name(),
    "actorValues": actor_values,
    "niagara": {
        "active": bool(niagara.is_active()),
        "values": niagara_values,
        "matchesActor": niagara_matches,
    },
    "materialValues": mid_values,
    "dynamicDepth": {
        "cameraToActor": measured_depth,
        "materialRepresentativeDepth": material_depth,
        "absoluteError": depth_error,
        "matches": depth_error is not None and depth_error < 1.0,
    },
}
print("M2PARAMS_RUNTIME=" + json.dumps(result, sort_keys=True))
if (
    not niagara.is_active()
    or not all(niagara_matches.values())
    or depth_error is None
    or depth_error >= 1.0
):
    raise RuntimeError("M2 runtime parameter verification failed: " + repr(result))
