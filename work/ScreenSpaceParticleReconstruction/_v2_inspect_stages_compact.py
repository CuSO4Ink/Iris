import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
rows = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageGeneric):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    row = {"path": path}
    for name in (
        "simulation_stage_name",
        "enabled",
        "iteration_source",
        "data_interface",
        "b_particle_iteration_state_enabled",
        "execute_behavior",
        "script",
    ):
        try:
            value = stage.get_editor_property(name)
            row[name] = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
        except Exception as error:
            row[name] = "ERROR:" + str(error)
    rows.append(row)
print("V2_STAGES=" + json.dumps(rows, sort_keys=True))
