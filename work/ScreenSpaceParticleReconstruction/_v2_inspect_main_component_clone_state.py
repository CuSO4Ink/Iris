import json
import unreal


actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
transform = actor.get_actor_transform()
interfaces = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if not path.startswith(component.get_path_name() + "."):
        continue
    row = {
        "path": path,
        "class": data_interface.get_class().get_name(),
    }
    for name in (
        "num_cells",
        "precision",
        "clear_before_non_iteration_stage",
        "size",
        "override_render_target_format",
        "override_render_target_filter",
        "mip_map_generation",
    ):
        try:
            row[name] = str(data_interface.get_editor_property(name))
        except Exception:
            pass
    interfaces.append(row)

result = {
    "actor": actor.get_path_name(),
    "component": component.get_path_name(),
    "asset": (
        component.get_asset().get_path_name()
        if component.get_asset()
        else None
    ),
    "active": bool(component.is_active()),
    "forceSolo": bool(component.get_force_solo()),
    "autoActivate": bool(component.get_editor_property("auto_activate")),
    "visible": bool(component.is_visible()),
    "location": [
        float(transform.translation.x),
        float(transform.translation.y),
        float(transform.translation.z),
    ],
    "rotation": [
        float(transform.rotation.x),
        float(transform.rotation.y),
        float(transform.rotation.z),
        float(transform.rotation.w),
    ],
    "scale": [
        float(transform.scale3d.x),
        float(transform.scale3d.y),
        float(transform.scale3d.z),
    ],
    "interfaces": interfaces,
}
print("V2_MAIN_COMPONENT_CLONES=" + json.dumps(result, sort_keys=True))
