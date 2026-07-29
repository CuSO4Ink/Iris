import json
import unreal


SYSTEM_PATH = "/Game/SSPR_Validation/M2/NewNiagaraSystem.NewNiagaraSystem"
system = unreal.load_object(None, SYSTEM_PATH)
if system is None:
    raise RuntimeError("System not found: " + SYSTEM_PATH)

result = {
    "system": system.get_path_name(),
    "system_dir": [
        name
        for name in dir(system)
        if any(token in name.lower() for token in ("emitter", "handle", "version"))
    ],
    "system_props": {},
    "emitters": [],
    "all_stage_objects": [],
}

for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    stage_path = stage.get_path_name()
    if not stage_path.startswith(SYSTEM_PATH + ":"):
        continue
    stage_info = {
        "repr": repr(stage),
        "path": stage_path,
        "class": stage.get_class().get_name(),
    }
    for prop_name in (
        "enabled",
        "script",
        "iteration_source",
        "num_iterations",
        "execute_behavior",
        "simulation_stage_name",
        "data_interface",
    ):
        try:
            value = stage.get_editor_property(prop_name)
            if hasattr(value, "get_path_name"):
                value = value.get_path_name()
            stage_info[prop_name] = str(value)
        except Exception:
            pass
    stage_info["dir"] = [
        name
        for name in dir(stage)
        if any(
            token in name.lower()
            for token in ("enabled", "script", "iteration", "source", "name")
        )
    ]
    result["all_stage_objects"].append(stage_info)

for prop_name in ("emitter_handles", "emitter_handles_deprecated"):
    try:
        value = system.get_editor_property(prop_name)
        result["system_props"][prop_name] = repr(value)
    except Exception as exc:
        result["system_props"][prop_name] = "ERROR: " + str(exc)

handles = []
for method_name in ("get_emitter_handles", "get_emitter_handles_deprecated"):
    method = getattr(system, method_name, None)
    if callable(method):
        try:
            handles = list(method())
            result["handle_method"] = method_name
            break
        except Exception as exc:
            result["handle_method_error"] = str(exc)

if not handles:
    try:
        handles = list(system.get_editor_property("emitter_handles"))
        result["handle_method"] = "property:emitter_handles"
    except Exception:
        pass

if not handles:
    emitter_objects = []
    for obj in unreal.ObjectIterator(unreal.NiagaraEmitter):
        path = obj.get_path_name()
        if path.startswith(SYSTEM_PATH + ":"):
            emitter_objects.append(obj)
    for obj in emitter_objects:
        handles.append(obj)
    result["handle_method"] = "ObjectIterator:NiagaraEmitter"

for handle in handles:
    handle_info = {
        "repr": repr(handle),
        "dir": [
            name
            for name in dir(handle)
            if any(token in name.lower() for token in ("name", "instance", "version", "emitter"))
        ],
    }
    instance = handle if isinstance(handle, unreal.NiagaraEmitter) else None
    for method_name in ("get_instance", "get_emitter", "get_emitter_data"):
        method = getattr(handle, method_name, None)
        if callable(method):
            try:
                candidate = method()
                if candidate is not None:
                    instance = candidate
                    handle_info["instance_method"] = method_name
                    break
            except Exception as exc:
                handle_info[method_name + "_error"] = str(exc)
    for prop_name in ("name", "id_name", "instance"):
        try:
            handle_info[prop_name] = str(handle.get_editor_property(prop_name))
        except Exception:
            pass
    if instance is not None:
        handle_info["instance"] = str(instance)
        handle_info["instance_type"] = str(type(instance))
        handle_info["instance_dir"] = [
            name
            for name in dir(instance)
            if any(
                token in name.lower()
                for token in ("data", "version", "simulation", "stage", "renderer")
            )
        ]
        data = None
        try:
            direct_stages = list(instance.get_editor_property("simulation_stages"))
        except Exception as exc:
            handle_info["direct_stages_error"] = str(exc)
            direct_stages = []
        handle_info["direct_stages"] = []
        for stage in direct_stages:
            stage_info = {
                "repr": repr(stage),
                "path": stage.get_path_name(),
                "class": stage.get_class().get_name(),
            }
            for prop_name in (
                "enabled",
                "script",
                "iteration_source",
                "num_iterations",
                "execute_behavior",
                "simulation_stage_name",
                "data_interface",
            ):
                try:
                    value = stage.get_editor_property(prop_name)
                    if hasattr(value, "get_path_name"):
                        value = value.get_path_name()
                    stage_info[prop_name] = str(value)
                except Exception:
                    pass
            stage_info["dir"] = [
                name
                for name in dir(stage)
                if any(
                    token in name.lower()
                    for token in ("enabled", "script", "iteration", "source", "name")
                )
            ]
            handle_info["direct_stages"].append(stage_info)
        for method_name in ("get_emitter_data", "get_latest_emitter_data"):
            method = getattr(instance, method_name, None)
            if callable(method):
                try:
                    data = method()
                    if data is not None:
                        handle_info["data_method"] = method_name
                        break
                except Exception as exc:
                    handle_info[method_name + "_error"] = str(exc)
        if data is None:
            try:
                data = instance.get_editor_property("emitter_data")
                handle_info["data_method"] = "property:emitter_data"
            except Exception:
                pass
        if data is not None:
            handle_info["data_type"] = str(type(data))
            handle_info["data_dir"] = [
                name
                for name in dir(data)
                if any(token in name.lower() for token in ("simulation", "stage", "renderer"))
            ]
            try:
                stages = list(data.get_editor_property("simulation_stages"))
            except Exception as exc:
                handle_info["stages_error"] = str(exc)
                stages = []
            handle_info["stages"] = []
            for stage in stages:
                stage_info = {
                    "repr": repr(stage),
                    "path": stage.get_path_name(),
                    "class": stage.get_class().get_name(),
                }
                for prop_name in (
                    "enabled",
                    "script",
                    "iteration_source",
                    "num_iterations",
                    "execute_behavior",
                    "simulation_stage_name",
                    "data_interface",
                ):
                    try:
                        value = stage.get_editor_property(prop_name)
                        if hasattr(value, "get_path_name"):
                            value = value.get_path_name()
                        stage_info[prop_name] = str(value)
                    except Exception:
                        pass
                stage_info["dir"] = [
                    name
                    for name in dir(stage)
                    if any(
                        token in name.lower()
                        for token in ("enabled", "script", "iteration", "source", "name")
                    )
                ]
                handle_info["stages"].append(stage_info)
    result["emitters"].append(handle_info)

print("GRIDMAIN_SIMSTAGES=" + json.dumps(result, sort_keys=True))
