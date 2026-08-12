import json
import unreal


V3_LEVEL = (
    "/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730/"
    "L_SSPR_AnisotropicSplat_V3_Validation"
)
V3_SYSTEM = (
    "/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730/"
    "NS_SSPR_AnisotropicSplat_V3.NS_SSPR_AnisotropicSplat_V3"
)


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(V3_LEVEL):
    raise RuntimeError("Failed to load the V3 validation level")

system = unreal.load_asset(V3_SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Missing V3 Niagara system")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rows = []
main_components = []
for actor in actor_subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    for component in actor.get_components_by_class(unreal.NiagaraComponent):
        before_asset = component.get_asset()
        before = before_asset.get_path_name() if before_asset else None
        if label == "SSPR_ParticleTrails_Main":
            component.deactivate()
            component.set_asset(None)
            component.set_asset(system)
            component.reinitialize_system()
            component.set_visibility(True, True)
            component.activate(True)
            main_components.append(component)
        after_asset = component.get_asset()
        rows.append(
            {
                "actor": label,
                "component": component.get_path_name(),
                "before": before,
                "after": after_asset.get_path_name() if after_asset else None,
                "active": bool(component.is_active()),
                "visible": bool(component.is_visible()),
            }
        )

if len(main_components) != 1:
    raise RuntimeError(
        "Expected exactly one SSPR_ParticleTrails_Main component, got "
        + str(len(main_components))
    )

saved = bool(level_subsystem.save_current_level())
after = main_components[0].get_asset().get_path_name()
result = {
    "loaded": True,
    "saved": saved,
    "mainComponentCount": len(main_components),
    "mainAsset": after,
    "components": rows,
}
print("V3_LEVEL_RETARGET=" + json.dumps(result, sort_keys=True))
if not saved or after != V3_SYSTEM:
    raise RuntimeError("V3 level retarget/save gate failed: " + repr(result))
