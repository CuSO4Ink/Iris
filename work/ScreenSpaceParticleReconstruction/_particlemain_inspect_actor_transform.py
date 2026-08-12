import json
import unreal

actor = next(
    (
        item
        for item in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        if item.get_actor_label() == "SSPR_ParticleTrails_Main"
    ),
    None,
)
if actor is None:
    raise RuntimeError("White-particle main actor is missing")
location = actor.get_actor_location()
rotation = actor.get_actor_rotation()
scale = actor.get_actor_scale3d()
print(
    "PARTICLE_ACTOR_TRANSFORM="
    + json.dumps(
        {
            "actor": actor.get_path_name(),
            "location": [location.x, location.y, location.z],
            "rotation": [
                rotation.pitch,
                rotation.yaw,
                rotation.roll,
            ],
            "scale": [scale.x, scale.y, scale.z],
        },
        sort_keys=True,
    )
)
