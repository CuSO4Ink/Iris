import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"


def get_prop(obj, name):
    try:
        value = obj.get_editor_property(name)
    except Exception:
        return None
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    if isinstance(value, (list, tuple)):
        return [
            item.get_path_name() if hasattr(item, "get_path_name") else str(item)
            for item in value
        ]
    return str(value)


result = {
    "system": SYSTEM,
    "simulationStages": [],
    "gridInterfaces": [],
    "scratch": {},
}

for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    row = {
        "path": path,
        "class": stage.get_class().get_name(),
    }
    for name in (
        "enabled",
        "simulation_stage_name",
        "iteration_source",
        "data_interface",
        "num_iterations",
        "execute_behavior",
        "writes_particles",
        "particle_iteration_state_enabled",
        "particle_iteration_state_binding",
        "particle_iteration_state_range",
        "disable_partial_particle_update",
        "script",
    ):
        value = get_prop(stage, name)
        if value is not None:
            row[name] = value
    result["simulationStages"].append(row)

for grid in unreal.ObjectIterator(unreal.NiagaraDataInterfaceGrid2DCollection):
    path = grid.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    row = {
        "path": path,
        "class": grid.get_class().get_name(),
    }
    for name in (
        "num_cells_x",
        "num_cells_y",
        "num_attributes",
        "override_buffer_format",
        "override_format",
        "clear_before_non_iteration_stage",
        "render_target_user_parameter",
        "preview_grid",
        "preview_attribute",
    ):
        value = get_prop(grid, name)
        if value is not None:
            row[name] = value
    try:
        binding = grid.get_editor_property("render_target_user_parameter")
        parameter = binding.get_editor_property("parameter")
        row["renderTargetBinding"] = str(parameter)
        try:
            row["renderTargetBindingName"] = str(
                parameter.get_editor_property("name")
            )
        except Exception:
            row["renderTargetBindingDir"] = [
                name
                for name in dir(parameter)
                if "name" in name.lower() or "type" in name.lower()
            ]
    except Exception as exc:
        row["renderTargetBindingError"] = str(exc)
    result["gridInterfaces"].append(row)

service = unreal.NiagaraScratchPadService
nodes = list(service.list_nodes(SYSTEM, EMITTER, MODULE))
result["scratch"]["nodes"] = []
for node in nodes:
    node_id = str(node.node_id)
    node_row = {
        "id": node_id,
        "type": str(node.node_type),
        "title": str(node.title),
        "pins": [],
    }
    for pin in service.get_node_pins(SYSTEM, EMITTER, MODULE, node_id):
        node_row["pins"].append(
            {
                "id": str(pin.pin_id),
                "name": str(pin.pin_name),
                "direction": str(pin.direction),
                "type": str(pin.type_name),
                "default": str(pin.default_value),
                "linked": bool(pin.is_connected),
            }
        )
    if str(node.node_type) == "CustomHlsl":
        node_row["code"] = service.get_custom_hlsl_code(
            SYSTEM, EMITTER, MODULE, node_id
        )
    result["scratch"]["nodes"].append(node_row)

print("RT_ASSET_INSPECT=" + json.dumps(result, sort_keys=True))
