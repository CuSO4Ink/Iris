"""Keep only the validated Q2 Gaussian hero in TechLab."""

import unreal


LEVEL = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
KEEP_LABEL = "Smoke2 GFields Q2 10K High Fidelity"


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name().split(".")[0] != LEVEL:
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
editor_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
gaussians = [
    actor
    for actor in editor_actors.get_all_level_actors()
    if isinstance(actor, unreal.GaussianVolumeActor)
]
keep = [actor for actor in gaussians if actor.get_actor_label() == KEEP_LABEL]
if len(keep) != 1:
    raise RuntimeError(f"Expected one Q2 hero, found {len(keep)}")

removed = [actor.get_actor_label() for actor in gaussians if actor != keep[0]]
editor_actors.destroy_actors([actor for actor in gaussians if actor != keep[0]])
remaining = [
    actor
    for actor in editor_actors.get_all_level_actors()
    if isinstance(actor, unreal.GaussianVolumeActor)
]
if remaining != keep:
    raise RuntimeError("Gaussian actor cleanup did not leave exactly the Q2 hero")
if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    raise RuntimeError("Failed to save TechLab")
unreal.log(f"GAUSSIAN_VOLUME_CLEANUP removed={removed} kept={KEEP_LABEL}")
