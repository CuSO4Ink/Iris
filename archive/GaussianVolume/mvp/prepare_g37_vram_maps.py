"""Create matched Empty/SVT/G37 cold-start maps from the current TechLab."""

import unreal


SOURCE = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
DESTINATIONS = {
    "Empty": "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_Empty",
    "SVT": "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_SVT",
    "GS": "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_G37_GS",
}
SVT_LABEL = "SVT | WDAS Half 378MiB Source / 85.8MiB U8"
GS_LABEL = "S3 | Standard Geometry + G2 Compact Relight / 312K"
CAMERA_LOCATION = unreal.Vector(1677.07570194, 4953.87681787, 577.09876377)
CAMERA_ROTATION = unreal.Rotator(-7.09999697, -91.77999607, 0.0)


assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def is_volume_actor(actor):
    return actor.get_class().get_name() in {
        "GaussianSplatting7DActor",
        "GaussianVolumeActor",
        "HeterogeneousVolume",
        "NanoVDBVolumeActor",
    }


for case, destination in DESTINATIONS.items():
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        if not assets.delete_asset(destination):
            raise RuntimeError(f"failed to delete stale {destination}")
    if not assets.duplicate_asset(SOURCE, destination):
        raise RuntimeError(f"failed to duplicate {SOURCE} to {destination}")
    unreal.EditorLoadingAndSavingUtils.load_map(destination)

    kept = []
    for actor in actors.get_all_level_actors():
        label = actor.get_actor_label()
        if isinstance(actor, (unreal.CameraActor, unreal.CineCameraActor, unreal.PlayerStart)):
            actors.destroy_actor(actor)
        elif is_volume_actor(actor):
            keep = (case == "SVT" and label == SVT_LABEL) or (case == "GS" and label == GS_LABEL)
            if keep:
                actor.set_actor_hidden_in_game(False)
                actor.set_is_temporarily_hidden_in_editor(False)
                root = actor.get_editor_property("root_component")
                if root:
                    root.set_visibility(True, True)
                    root.set_hidden_in_game(False, True)
                kept.append(f"{label} [{actor.get_class().get_name()}]")
            else:
                actors.destroy_actor(actor)

    camera = actors.spawn_actor_from_class(unreal.CameraActor, CAMERA_LOCATION, CAMERA_ROTATION)
    camera.set_actor_label("VRAM Benchmark Camera")
    camera.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)

    expected = 0 if case == "Empty" else 1
    if len(kept) != expected:
        raise RuntimeError(f"{case}: expected {expected} volume actors, kept {kept}")
    if not unreal.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError(f"failed to save {destination}")
    unreal.log(f"VRAM_MAP_READY case={case} map={destination} kept={kept}")

unreal.EditorLoadingAndSavingUtils.load_map(SOURCE)
unreal.log("VRAM_MAP_PREP_COMPLETE")
