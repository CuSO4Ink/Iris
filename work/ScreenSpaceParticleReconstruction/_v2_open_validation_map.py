import json
import unreal


MAP = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/L_SSPR_AnisotropicSplat_Validation"
SYSTEM_PATH = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
loaded = bool(level_subsystem.load_level(MAP))
if not loaded:
    raise RuntimeError("Failed to load V2 validation map")

system = unreal.load_asset(SYSTEM_PATH)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Missing V2 Niagara system")

rows = []
changed = []
main_found = False
actors = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors()
for actor in actors:
    for component in actor.get_components_by_class(unreal.NiagaraComponent):
        asset = component.get_asset()
        before = asset.get_path_name() if asset is not None else None
        label = actor.get_actor_label()
        if label == "SSPR_ParticleTrails_Main":
            main_found = True
            if before != SYSTEM_PATH:
                component.set_asset(system)
                changed.append(component.get_path_name())
            component.reinitialize_system()
            component.activate(True)
            component.set_visibility(True, True)
        elif label == "NS_SSPR_ProjTest":
            projection_system = unreal.load_asset(
                "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
            )
            if projection_system is not None and before != projection_system.get_path_name():
                component.set_asset(projection_system)
                changed.append(component.get_path_name())
            component.deactivate()
            component.set_visibility(False, True)
        after_asset = component.get_asset()
        rows.append({
            "actor": actor.get_actor_label(),
            "component": component.get_path_name(),
            "before": before,
            "after": after_asset.get_path_name() if after_asset else None,
            "active": bool(component.is_active()),
            "visible": bool(component.is_visible()),
        })

if not main_found:
    actor = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).spawn_actor_from_class(unreal.NiagaraActor, unreal.Vector(0.0, 0.0, 0.0))
    actor.set_actor_label("NS_SSPR_AnisotropicSplat_Validation")
    component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
    component.set_asset(system)
    component.reinitialize_system()
    component.activate(True)
    changed.append(component.get_path_name())
    rows.append({
        "actor": actor.get_actor_label(),
        "component": component.get_path_name(),
        "before": None,
        "after": SYSTEM_PATH,
        "active": bool(component.is_active()),
        "visible": bool(component.is_visible()),
    })

saved = bool(level_subsystem.save_current_level())
print("V2_VALIDATION_MAP=" + json.dumps({
    "loaded": loaded,
    "saved": saved,
    "changedComponents": changed,
    "niagaraComponents": rows,
}, sort_keys=True))
if not saved:
    raise RuntimeError("Failed to save V2 validation map")
