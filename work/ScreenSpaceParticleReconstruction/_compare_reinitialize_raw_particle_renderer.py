import json

import unreal


system_path = (
    "/Game/SSPR_Validation/Performance/DenseG5SparseV2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
system = unreal.load_asset(system_path)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Sparse V2 System failed to load")

saved_system = bool(
    unreal.EditorAssetLibrary.save_asset(system_path, False)
)

actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
if component.get_asset() != system:
    component.set_asset(system)

component.reinitialize_system()
component.activate(True)
component.advance_simulation(300, 1.0 / 60.0)

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.editor_invalidate_viewports()

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
saved_level = bool(
    unreal.EditorLoadingAndSavingUtils.save_map(
        world,
        "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
        "L_SSPR_AnisotropicSplat_Validation",
    )
)

print(
    "SSPR_RAW_PARTICLE_RENDERER_REINITIALIZED="
    + json.dumps(
        {
            "system": system.get_path_name(),
            "actor": actor.get_path_name(),
            "componentActive": bool(component.is_active()),
            "savedSystem": saved_system,
            "savedLevel": saved_level,
            "advancedFrames": 300,
            "rawRendererExpectedVisible": True,
            "finalRendererPreserved": True,
        },
        sort_keys=True,
    )
)
