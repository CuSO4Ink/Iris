import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService


def serialize_pin(pin):
    return {
        "name": str(pin.pin_name),
        "direction": str(pin.direction),
        "type": str(pin.type_name),
        "connected": bool(pin.is_connected),
        "default": str(pin.default_value),
    }


system = unreal.load_object(None, SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("V2 Niagara system is missing: " + SYSTEM)

modules = {}
for module_value in SERVICE.list_scratch_modules(SYSTEM, EMITTER):
    module = str(module_value)
    nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, module))
    rows = []
    for node in nodes:
        node_id = str(node.node_id)
        row = {
            "id": node_id,
            "title": str(node.title),
            "type": str(node.node_type),
            "pins": [
                serialize_pin(pin)
                for pin in SERVICE.get_node_pins(
                    SYSTEM, EMITTER, module, node_id
                )
            ],
        }
        if str(node.node_type) == "CustomHlsl":
            row["hlsl"] = str(
                SERVICE.get_custom_hlsl_code(
                    SYSTEM, EMITTER, module, node_id
                )
            )
        rows.append(row)
    modules[module] = {
        "nodes": rows,
        "connections": [
            {
                "fromNode": str(item.from_node_id),
                "fromPin": str(item.from_pin),
                "toNode": str(item.to_node_id),
                "toPin": str(item.to_pin),
            }
            for item in SERVICE.list_connections(
                SYSTEM, EMITTER, module
            )
        ],
    }

data_interfaces = []
for class_name in (
    "NiagaraDataInterfaceGrid2DCollection",
    "NiagaraDataInterfaceRasterizationGrid3D",
    "NiagaraDataInterfaceRenderTarget2D",
):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        continue
    for obj in unreal.ObjectIterator(cls):
        path = obj.get_path_name()
        if SYSTEM not in path:
            continue
        props = {}
        for prop in (
            "num_cells_x",
            "num_cells_y",
            "num_cells_z",
            "num_attributes",
            "precision",
            "reset_value",
            "clear_before_non_iteration_stage",
            "size",
            "override_render_target_format",
        ):
            try:
                value = obj.get_editor_property(prop)
                if hasattr(value, "x") and hasattr(value, "y"):
                    value = [int(value.x), int(value.y)]
                else:
                    value = str(value)
                props[prop] = value
            except Exception:
                pass
        data_interfaces.append(
            {"class": class_name, "path": path, "properties": props}
        )

stages = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    row = {"path": path}
    for prop in (
        "simulation_stage_name",
        "enabled",
        "iteration_source",
        "iterations",
    ):
        try:
            row[prop] = str(stage.get_editor_property(prop))
        except Exception:
            pass
    stages.append(row)

result = {
    "system": SYSTEM,
    "modules": modules,
    "dataInterfaces": data_interfaces,
    "simulationStages": stages,
    "compileMessages": [
        str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
    ],
}
print("V2_BASELINE=" + json.dumps(result, sort_keys=True))
