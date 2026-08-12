import json
import unreal

info = unreal.ViewportService.get_viewport_info()
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
actor_location = actor.get_actor_location()
camera_location = info.location
camera_rotation = info.rotation
offset = actor_location - camera_location
forward = camera_rotation.get_forward_vector()
right = camera_rotation.get_right_vector()
up = camera_rotation.get_up_vector()
result = {
    "cameraLocation": [
        camera_location.x,
        camera_location.y,
        camera_location.z,
    ],
    "cameraRotation": [
        camera_rotation.pitch,
        camera_rotation.yaw,
        camera_rotation.roll,
    ],
    "fov": float(info.fov),
    "actorLocation": [
        actor_location.x,
        actor_location.y,
        actor_location.z,
    ],
    "cameraSpaceApprox": [
        offset.dot(forward),
        offset.dot(right),
        offset.dot(up),
    ],
}
print(
    "PARTICLE_VIEW_ACTOR="
    + json.dumps(result, sort_keys=True)
)
