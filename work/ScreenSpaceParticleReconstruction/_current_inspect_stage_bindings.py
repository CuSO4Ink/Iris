import json
import unreal


SYSTEMS = (
    "/Game/SSPR_Validation/M2/NewNiagaraSystem.NewNiagaraSystem",
    "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main",
)


def safe_prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception as exc:
        return "ERROR: " + str(exc)


def dump_struct(value):
    row = {"text": str(value), "type": type(value).__name__}
    for name in ("bound_variable", "name", "type_def", "type_def_handle"):
        try:
            child = value.get_editor_property(name)
            row[name] = str(child)
            if name == "bound_variable":
                for child_name in ("name", "type_def", "type_def_handle"):
                    try:
                        row["bound_" + child_name] = str(
                            child.get_editor_property(child_name)
                        )
                    except Exception as exc:
                        row["bound_" + child_name] = "ERROR: " + str(exc)
        except Exception:
            pass
    return row


for system_path in SYSTEMS:
    system = unreal.load_object(None, system_path)
    rows = []
    if system is not None:
        for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
            path = stage.get_path_name()
            if not path.startswith(system_path + ":"):
                continue
            script = safe_prop(stage, "script")
            rows.append(
                {
                    "path": path,
                    "name": str(safe_prop(stage, "simulation_stage_name")),
                    "enabled": str(safe_prop(stage, "enabled")),
                    "iteration_source": str(safe_prop(stage, "iteration_source")),
                    "data_interface": dump_struct(safe_prop(stage, "data_interface")),
                    "script": script.get_path_name()
                    if hasattr(script, "get_path_name")
                    else str(script),
                }
            )
    print("STAGE_BINDINGS=" + json.dumps({"system": system_path, "rows": rows}, sort_keys=True))
