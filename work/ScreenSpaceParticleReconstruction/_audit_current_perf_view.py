import json
import math

import unreal


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
camera_key = None
camera_info = None
camera_errors = {}
for candidate_key in (
    "LevelEditorViewport0",
    "LevelEditorViewport1",
    "LevelEditorViewport2",
    "LevelEditorViewport3",
):
    try:
        candidate_info = level_subsystem.get_level_viewport_camera_info(
            candidate_key
        )
        if candidate_info:
            camera_key = candidate_key
            camera_info = candidate_info
            break
    except Exception as exc:
        camera_errors[candidate_key] = str(exc)

if not camera_info:
    raise RuntimeError(
        "No level viewport camera information: " + repr(camera_errors)
    )

# UE 5.8 returns (success, location, rotation); older bindings returned only
# (location, rotation).
if isinstance(camera_info[0], bool):
    if not camera_info[0]:
        raise RuntimeError("Viewport camera query returned success=false")
    camera_location = camera_info[1]
    camera_rotation = camera_info[2]
else:
    camera_location = camera_info[0]
    camera_rotation = camera_info[1]

rows = []
for actor in unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors():
    components = actor.get_components_by_class(unreal.NiagaraComponent)
    if not components:
        continue
    component = components[0]
    asset = component.get_asset()
    actor_location = actor.get_actor_location()
    delta = actor_location - camera_location
    rows.append(
        {
            "cameraKey": camera_key,
            "label": actor.get_actor_label(),
            "actor": actor.get_path_name(),
            "system": asset.get_path_name() if asset else None,
            "active": bool(component.is_active()),
            "visible": not bool(actor.is_hidden_ed()),
            "location": [
                float(actor_location.x),
                float(actor_location.y),
                float(actor_location.z),
            ],
            "cameraDistanceUU": math.sqrt(
                float(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
            ),
        }
    )

print(
    "SSPR_PERF_VIEW_AUDIT="
    + json.dumps(
        {
            "cameraLocation": [
                float(camera_location.x),
                float(camera_location.y),
                float(camera_location.z),
            ],
            "cameraRotation": [
                float(camera_rotation.pitch),
                float(camera_rotation.yaw),
                float(camera_rotation.roll),
            ],
            "niagaraActors": rows,
        },
        sort_keys=True,
    )
)
