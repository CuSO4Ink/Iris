import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/Recovery/DenseG5_20260730/NS_SSPR_AnisotropicSplat_Main"

system = unreal.load_asset(SYSTEM_PATH)
if system is None:
    raise RuntimeError("Recovery Dense G5 system is missing")

system_names = [
    name
    for name in dir(system)
    if "parameter" in name.lower() or "exposed" in name.lower()
]
component = None
for actor in unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors():
    for candidate in actor.get_components_by_class(unreal.NiagaraComponent):
        asset = candidate.get_asset()
        if asset is not None and asset.get_path_name() == system.get_path_name():
            component = candidate
            break
    if component is not None:
        break
if component is None:
    raise RuntimeError("Active recovery Dense G5 component is missing")

component_names = [
    name
    for name in dir(component)
    if "variable" in name.lower()
    or "parameter" in name.lower()
    or "override" in name.lower()
]

print(
    "PERF_USER_PARAMETER_API="
    + json.dumps(
        {
            "system": system.get_path_name(),
            "systemNames": system_names,
            "component": component.get_path_name(),
            "componentNames": component_names,
        },
        sort_keys=True,
    )
)
