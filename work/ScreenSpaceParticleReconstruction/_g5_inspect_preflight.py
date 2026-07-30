import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
SYSTEM = ROOT + "/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
MATERIAL = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"
EMITTER = "Fountain"
MODULES = (
    "SSPR_RasterizeWhiteParticles",
    "SSPR_ResolveGridToSimRT",
)
SERVICE = unreal.NiagaraScratchPadService


def safe_property(value, name):
    try:
        result = value.get_editor_property(name)
    except Exception:
        return None
    if isinstance(result, unreal.IntVector):
        return [int(result.x), int(result.y), int(result.z)]
    return str(result)


def main():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    module_rows = {}
    for module in MODULES:
        custom_nodes = [
            node
            for node in SERVICE.list_nodes(SYSTEM, EMITTER, module)
            if str(node.node_type) == "CustomHlsl"
        ]
        if len(custom_nodes) != 1:
            raise RuntimeError(
                "Expected one Custom HLSL node in {}, found {}".format(
                    module, len(custom_nodes)
                )
            )
        node_id = str(custom_nodes[0].node_id)
        module_rows[module] = {
            "nodeId": node_id,
            "code": str(
                SERVICE.get_custom_hlsl_code(
                    SYSTEM, EMITTER, module, node_id
                )
            ),
            "pins": [
                {
                    "name": str(pin.pin_name),
                    "direction": str(pin.direction),
                    "type": str(pin.type_name),
                    "connected": bool(pin.is_connected),
                }
                for pin in SERVICE.get_node_pins(
                    SYSTEM, EMITTER, module, node_id
                )
            ],
        }

    raster_rows = []
    rt_rows = []
    for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
        path = data_interface.get_path_name()
        if ROOT not in path:
            continue
        class_name = data_interface.get_class().get_name()
        if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
            raster_rows.append({
                "path": path,
                "numCells": safe_property(data_interface, "num_cells"),
                "numAttributes": safe_property(
                    data_interface, "num_attributes"
                ),
                "precision": safe_property(data_interface, "precision"),
                "resetValue": safe_property(data_interface, "reset_value"),
                "clear": safe_property(
                    data_interface, "clear_before_non_iteration_stage"
                ),
            })
        elif class_name == "NiagaraDataInterfaceRenderTarget2D":
            rt_rows.append({
                "path": path,
                "size": [
                    safe_property(data_interface, "size"),
                    safe_property(data_interface, "override_format"),
                ],
                "inherit": safe_property(
                    data_interface, "inherit_user_parameter_settings"
                ),
                "filter": safe_property(
                    data_interface, "override_render_target_filter"
                ),
                "mips": safe_property(
                    data_interface, "mip_map_generation"
                ),
            })

    material = unreal.load_asset(MATERIAL)
    instance = unreal.load_asset(INSTANCE)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing G5 parent material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Missing G5 HQ material instance")
    texture_parameters = []
    for expression in unreal.MaterialEditingLibrary.get_material_expressions(
        material
    ):
        if isinstance(
            expression, unreal.MaterialExpressionTextureObjectParameter
        ):
            texture_parameters.append(
                str(expression.get_editor_property("parameter_name"))
            )

    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL)
    result = {
        "inPIE": bool(level_subsystem.is_in_play_in_editor()),
        "modules": module_rows,
        "rasterInterfaces": raster_rows,
        "renderTargetInterfaces": rt_rows,
        "textureParameters": sorted(texture_parameters),
        "materialCompiled": bool(diagnostics.is_compiled_ok),
        "materialCompileErrors": [
            str(value) for value in diagnostics.compile_errors
        ],
    }
    print("G5_PREFLIGHT=" + json.dumps(result, sort_keys=True))


main()
