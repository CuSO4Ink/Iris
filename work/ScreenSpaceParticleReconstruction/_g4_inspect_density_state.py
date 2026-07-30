import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
FUNCTION_PATHS = (
    ROOT + "/Functions/AnisotropicSplat/MF_SSPR_RawAnisotropicDensity",
    ROOT + "/Functions/AnisotropicSplat/MF_SSPR_MipBodyDensity",
    ROOT + "/Functions/AnisotropicSplat/MF_SSPR_FilamentBodyBlend",
    ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity",
    SHAPE_PATH,
)


def scalar_overrides(instance):
    values = {}
    for row in instance.get_editor_property("scalar_parameter_values"):
        info = row.get_editor_property("parameter_info")
        name = str(info.get_editor_property("name"))
        values[name] = float(row.get_editor_property("parameter_value"))
    return values


def main():
    material = unreal.load_asset(MATERIAL_PATH)
    instance = unreal.load_asset(INSTANCE_PATH)
    shape = unreal.load_asset(SHAPE_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing V2 display material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Missing V2 HQ material instance")
    if not isinstance(shape, unreal.MaterialFunction):
        raise RuntimeError("Missing V2 density-shape function")

    function_nodes = {}
    for function_path in FUNCTION_PATHS:
        function = unreal.load_asset(function_path)
        if not isinstance(function, unreal.MaterialFunction):
            function_nodes[function_path] = None
            continue
        custom_nodes = []
        for expression in unreal.MaterialEditingLibrary.get_material_function_expressions(function):
            if isinstance(expression, unreal.MaterialExpressionCustom):
                custom_nodes.append({
                    "name": expression.get_name(),
                    "description": str(expression.get_editor_property("description")),
                    "code": str(expression.get_editor_property("code")),
                    "inputs": [
                        str(value.get_editor_property("input_name"))
                        for value in expression.get_editor_property("inputs")
                    ],
                })
        function_nodes[function_path] = custom_nodes

    calls = []
    for expression in unreal.MaterialEditingLibrary.get_material_expressions(material):
        if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall):
            function = expression.get_editor_property("material_function")
            if function and function.get_path_name().split(".")[0] == SHAPE_PATH:
                calls.append(expression.get_name())

    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    result = {
        "material": material.get_path_name(),
        "instance": instance.get_path_name(),
        "shape": shape.get_path_name(),
        "shapeCalls": calls,
        "functionCustomNodes": function_nodes,
        "scalarOverrides": scalar_overrides(instance),
        "materialCompiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [str(value) for value in diagnostics.compile_errors],
    }
    print("G4_DENSITY_STATE=" + json.dumps(result, sort_keys=True))


main()
