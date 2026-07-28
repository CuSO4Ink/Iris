"""Print TechLab camera and Gaussian actor transforms for headless profiling."""

import unreal


unreal.EditorLoadingAndSavingUtils.load_map(
    "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for actor in actors:
    if isinstance(
        actor,
        (
            unreal.GaussianVolumeActor,
            unreal.CameraActor,
            unreal.CineCameraActor,
            unreal.PlayerStart,
        ),
    ):
        component = (
            actor.get_editor_property("gaussian_volume_component")
            if isinstance(actor, unreal.GaussianVolumeActor)
            else None
        )
        unreal.log(
            "TECHLAB_ACTOR "
            f"label={actor.get_actor_label()} "
            f"class={actor.get_class().get_name()} "
            f"location={actor.get_actor_location()} "
            f"rotation={actor.get_actor_rotation()} "
            f"enabled={component.get_editor_property('enable_rendering') if component else '-'}"
        )
