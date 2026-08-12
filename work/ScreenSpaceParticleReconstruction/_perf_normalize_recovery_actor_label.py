import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/Recovery/DenseG5_20260730/"
    "NS_SSPR_AnisotropicSplat_Main."
    "NS_SSPR_AnisotropicSplat_Main"
)
LABEL = "SSPR_ParticleTrails_Main"


actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
matches = []
for actor in actor_subsystem.get_all_level_actors():
    for component in actor.get_components_by_class(
        unreal.NiagaraComponent
    ):
        asset = component.get_asset()
        if asset and asset.get_path_name() == SYSTEM:
            matches.append((actor, component))
if len(matches) != 1:
    raise RuntimeError(
        "Expected one recovery System actor, got "
        + str(len(matches))
    )
actor, component = matches[0]
before_label = actor.get_actor_label()
actor.set_actor_label(LABEL)

class_counts = {}
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterface
):
    if not data_interface.get_path_name().startswith(
        component.get_path_name() + "."
    ):
        continue
    name = data_interface.get_class().get_name()
    class_counts[name] = class_counts.get(name, 0) + 1

saved = bool(
    unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    ).save_current_level()
)
result = {
    "actor": actor.get_path_name(),
    "component": component.get_path_name(),
    "beforeLabel": before_label,
    "afterLabel": actor.get_actor_label(),
    "active": bool(component.is_active()),
    "visible": bool(component.is_visible()),
    "classCounts": class_counts,
    "saved": saved,
}
print(
    "PERF_NORMALIZE_RECOVERY_ACTOR_LABEL="
    + json.dumps(result, sort_keys=True)
)
if not saved:
    raise RuntimeError("Failed to save normalized recovery actor")
