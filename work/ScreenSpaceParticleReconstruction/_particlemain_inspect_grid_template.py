import json
import unreal


ASSET_PATH = "/NiagaraFluids/Templates/Gas/2D/Emitters/Grid2D_Gas_Emitter.Grid2D_Gas_Emitter"


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return default


def value_text(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    return str(value)


asset = unreal.load_object(None, ASSET_PATH)
if asset is None:
    raise RuntimeError("Missing emitter template: " + ASSET_PATH)

prefix = ASSET_PATH + ":"
stages = []
stage_by_usage = {}
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    if not stage.get_path_name().startswith(prefix):
        continue
    script = prop(stage, "script")
    usage_id = str(prop(script, "usage_id", "")) if script else ""
    row = {
        "path": stage.get_path_name(),
        "name": str(prop(stage, "simulation_stage_name", "")),
        "enabled": bool(prop(stage, "enabled", False)),
        "iteration_source": str(prop(stage, "iteration_source", "")),
        "data_interface": value_text(prop(stage, "data_interface")),
        "num_iterations": value_text(prop(stage, "num_iterations")),
        "execute_behavior": value_text(prop(stage, "execute_behavior")),
        "script": value_text(script),
        "usage_id": usage_id,
    }
    stages.append(row)
    if usage_id:
        stage_by_usage[usage_id] = row

outputs = []
for node in unreal.ObjectIterator(unreal.NiagaraNodeOutput):
    if not node.get_path_name().startswith(prefix):
        continue
    usage = str(prop(node, "usage", ""))
    if "SIMULATION_STAGE" not in usage.upper():
        continue
    usage_id = str(prop(node, "usage_id", ""))
    graph = node.get_outer()
    function_calls = []
    if graph is not None:
        for candidate in prop(graph, "nodes", []) or []:
            class_name = candidate.get_class().get_name()
            if class_name != "NiagaraNodeFunctionCall":
                continue
            function_calls.append(
                {
                    "name": candidate.get_name(),
                    "function_name": str(prop(candidate, "function_name", "")),
                    "function_script": value_text(prop(candidate, "function_script")),
                }
            )
    outputs.append(
        {
            "path": node.get_path_name(),
            "usage": usage,
            "usage_id": usage_id,
            "stage": stage_by_usage.get(usage_id),
            "function_calls": function_calls,
        }
    )

print(
    "GRID_TEMPLATE="
    + json.dumps(
        {
            "asset": asset.get_path_name(),
            "stages": stages,
            "outputs": outputs,
        },
        sort_keys=True,
    )
)
