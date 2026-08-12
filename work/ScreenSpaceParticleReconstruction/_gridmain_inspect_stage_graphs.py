import json
import unreal


SYSTEM_PATH = "/Game/SSPR_Validation/M2/GridTrails/NS_SSPR_GridTrails_Main.NS_SSPR_GridTrails_Main"


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return default


def path_name(obj):
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


def node_label(node):
    for name in ("function_name", "signature", "function_script", "usage", "simulation_stage_name"):
        value = prop(node, name)
        if value is not None:
            if hasattr(value, "get_path_name"):
                value = value.get_path_name()
            text = str(value)
            if text and text not in ("None", ""):
                return text
    return node.get_name()


def linked_nodes(node):
    result = []
    for pin in prop(node, "pins", []) or []:
        for linked_pin in prop(pin, "linked_to", []) or []:
            owner = prop(linked_pin, "owning_node")
            if owner is None:
                try:
                    owner = linked_pin.get_outer()
                except Exception:
                    owner = None
            if owner is not None and owner not in result:
                result.append(owner)
    return result


asset = unreal.load_object(None, SYSTEM_PATH)
if asset is None:
    raise RuntimeError("Missing system: " + SYSTEM_PATH)

stage_by_usage = {}
stage_rows = []
emitter_paths = []
all_matching_stage_paths = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    if "NS_SSPR_GridTrails_Main" in stage.get_path_name():
        all_matching_stage_paths.append(stage.get_path_name())
        script = prop(stage, "script")
        usage_id = str(prop(script, "usage_id", "")) if script else ""
        row = {
            "name": str(prop(stage, "simulation_stage_name", "")),
            "enabled": bool(prop(stage, "enabled", False)),
            "iteration_source": str(prop(stage, "iteration_source", "")),
            "data_interface": str(prop(stage, "data_interface", "")),
            "script": path_name(script),
            "usage_id": usage_id,
            "path": stage.get_path_name(),
        }
        stage_rows.append(row)
        if usage_id:
            stage_by_usage[usage_id] = row
for emitter in unreal.ObjectIterator(unreal.NiagaraEmitter):
    if not emitter.get_path_name().startswith(SYSTEM_PATH + ":"):
        continue
    emitter_paths.append(emitter.get_path_name())
    stages = prop(emitter, "simulation_stages", []) or []
    for stage in stages:
        script = prop(stage, "script")
        usage_id = str(prop(script, "usage_id", "")) if script else ""
        row = {
            "name": str(prop(stage, "simulation_stage_name", "")),
            "enabled": bool(prop(stage, "enabled", False)),
            "iteration_source": str(prop(stage, "iteration_source", "")),
            "data_interface": str(prop(stage, "data_interface", "")),
            "script": path_name(script),
            "usage_id": usage_id,
            "path": stage.get_path_name(),
        }
        stage_rows.append(row)
        if usage_id:
            stage_by_usage[usage_id] = row

outputs = []
for node in unreal.ObjectIterator(unreal.NiagaraNodeOutput):
    if not node.get_path_name().startswith(SYSTEM_PATH + ":"):
        continue
    usage = str(prop(node, "usage", ""))
    if "SIMULATION_STAGE" not in usage.upper() and "SimulationStage" not in usage:
        continue
    usage_id = str(prop(node, "usage_id", ""))
    visited = set()
    queue = [node]
    traversal = []
    while queue:
        current = queue.pop(0)
        key = current.get_path_name()
        if key in visited:
            continue
        visited.add(key)
        traversal.append(
            {
                "class": current.get_class().get_name(),
                "name": current.get_name(),
                "label": node_label(current),
                "path": key,
            }
        )
        queue.extend(linked_nodes(current))
    outputs.append(
        {
            "usage": usage,
            "usage_id": usage_id,
            "stage": stage_by_usage.get(usage_id),
            "traversal": traversal,
        }
    )

print(
    "GRIDMAIN_STAGE_GRAPHS="
    + json.dumps(
        {
            "emitters": emitter_paths,
            "all_matching_stage_paths": all_matching_stage_paths,
            "stages": stage_rows,
            "outputs": outputs,
        },
        sort_keys=True,
    )
)
