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
            unreal.GaussianSplatting7DActor,
            unreal.CameraActor,
            unreal.CineCameraActor,
            unreal.PlayerStart,
        ),
    ):
        component = (
            actor.get_editor_property("gaussian_volume_component")
            if isinstance(actor, unreal.GaussianVolumeActor)
            else actor.get_editor_property("gs7d_component")
            if isinstance(actor, unreal.GaussianSplatting7DActor)
            else None
        )
        details = ""
        if isinstance(actor, unreal.GaussianSplatting7DActor):
            names = (
                "opacity_multiplier", "opacity_power", "relight_intensity_scale",
                "relight_color_tint", "ambient_light_intensity_scale",
                "deep_shadow_density_scale", "phase_mode", "phase_g", "phase_g2",
                "phase_blend", "phase_intensity",
            )
            details = " " + " ".join(
                f"{name}={component.get_editor_property(name)}" for name in names
            )
        unreal.log(
            "TECHLAB_ACTOR "
            f"label={actor.get_actor_label()} "
            f"class={actor.get_class().get_name()} "
            f"location={actor.get_actor_location()} "
            f"rotation={actor.get_actor_rotation()} "
            f"enabled={component.get_editor_property('enable_rendering') if isinstance(actor, unreal.GaussianVolumeActor) else '-'}"
            f"{details}"
        )
