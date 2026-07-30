import json
import math

import unreal


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

camera_key = "LevelEditorViewport0"
camera_info = level_subsystem.get_level_viewport_camera_info(camera_key)
if isinstance(camera_info[0], bool):
    if not camera_info[0]:
        raise RuntimeError("Viewport camera query returned success=false")
    camera_location = camera_info[1]
    camera_rotation = camera_info[2]
else:
    camera_location = camera_info[0]
    camera_rotation = camera_info[1]

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
asset = component.get_asset()
if asset is None:
    raise RuntimeError("Active Niagara component has no System")

actor_location = actor.get_actor_location()
delta = actor_location - camera_location
distance = math.sqrt(
    float(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
)

# A single explicit fixed step plus a viewport redraw makes ProfileGPU include
# the Niagara scene work in an otherwise-idle editor. The camera is read only.
component.advance_simulation(1, 1.0 / 60.0)
level_subsystem.editor_invalidate_viewports()
unreal.SystemLibrary.execute_console_command(world, "r.ProfileGPU.ShowUI 0")
unreal.SystemLibrary.execute_console_command(world, "ProfileGPU")
level_subsystem.editor_invalidate_viewports()

print(
    "SSPR_PROFILE_CURRENT_VIEW="
    + json.dumps(
        {
            "system": asset.get_path_name(),
            "cameraKey": camera_key,
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
            "actorLocation": [
                float(actor_location.x),
                float(actor_location.y),
                float(actor_location.z),
            ],
            "cameraDistanceUU": distance,
            "componentActive": bool(component.is_active()),
        },
        sort_keys=True,
    )
)
