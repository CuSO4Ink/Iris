import json
import unreal


TOKEN = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"


def read_properties(value, names):
    row = {"path": value.get_path_name()}
    for name in names:
        try:
            item = value.get_editor_property(name)
            if hasattr(item, "x") and hasattr(item, "y"):
                row[name] = [int(item.x), int(item.y)]
            else:
                row[name] = str(item)
        except Exception as exc:
            row[name] = "ERROR: " + str(exc)
    return row


def main():
    data_interfaces = []
    for value in unreal.ObjectIterator(unreal.NiagaraDataInterfaceRenderTarget2D):
        if TOKEN not in value.get_path_name():
            continue
        data_interfaces.append(read_properties(value, (
            "mip_map_generation",
            "mip_map_generation_type",
            "inherit_user_parameter_settings",
            "size",
            "override_render_target_filter",
            "override_render_target_format",
        )))

    render_targets = []
    for value in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
        if TOKEN not in value.get_path_name():
            continue
        render_targets.append(read_properties(value, (
            "size_x",
            "size_y",
            "auto_generate_mips",
            "filter",
            "render_target_format",
            "address_x",
            "address_y",
        )))

    components = []
    for component in unreal.ObjectIterator(unreal.NiagaraComponent):
        if TOKEN not in component.get_path_name():
            continue
        row = {
            "path": component.get_path_name(),
            "active": bool(component.is_active()),
        }
        try:
            row["age"] = float(component.get_age())
        except Exception as exc:
            row["age"] = "ERROR: " + str(exc)
        components.append(row)

    print("V2_SIMRT_MIPS_RUNTIME=" + json.dumps({
        "dataInterfaces": data_interfaces,
        "renderTargets": render_targets,
        "components": components,
    }, sort_keys=True))


main()
