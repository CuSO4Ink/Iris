import json
import unreal


SYSTEMS = (
    "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main",
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main",
)
rows = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    system = next((item for item in SYSTEMS if path.startswith(item + ":")), None)
    if system is None:
        continue
    row = {"system": system, "stagePath": path}
    for prop in ("simulation_stage_name", "script"):
        try:
            value = stage.get_editor_property(prop)
            row[prop] = (
                value.get_path_name()
                if hasattr(value, "get_path_name") else str(value)
            )
        except Exception as error:
            row[prop] = "ERROR:" + str(error)
    script = None
    try:
        script = stage.get_editor_property("script")
    except Exception:
        pass
    if script is not None:
        for prop in (
            "usage", "usage_id", "rapid_iteration_parameters",
        ):
            try:
                value = script.get_editor_property(prop)
                row["script." + prop] = (
                    value.get_path_name()
                    if hasattr(value, "get_path_name") else str(value)
                )
            except Exception as error:
                row["script." + prop] = "ERROR:" + str(error)
    rows.append(row)
print("V2_STAGE_SCRIPT_BINDINGS=" + json.dumps(rows, sort_keys=True))
