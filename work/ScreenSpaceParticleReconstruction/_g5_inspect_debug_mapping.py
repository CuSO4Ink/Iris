import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_G5_FieldDebugV2"
INSTANCE_PATH = ROOT + "/MI_SSPR_G5_FieldDebugV2"

material = unreal.load_asset(MATERIAL_PATH)
instance = unreal.load_asset(INSTANCE_PATH)
if not isinstance(material, unreal.Material):
    raise RuntimeError("G5 debug material is missing")
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("G5 debug MI is missing")

scalars = {}
custom_nodes = []
for expression in unreal.MaterialEditingLibrary.get_material_expressions(
    material
):
    if isinstance(expression, unreal.MaterialExpressionScalarParameter):
        scalars[
            str(expression.get_editor_property("parameter_name"))
        ] = float(expression.get_editor_property("default_value"))
    if isinstance(expression, unreal.MaterialExpressionCustom):
        custom_nodes.append(
            {
                "name": expression.get_name(),
                "inputs": [
                    str(item.get_editor_property("input_name"))
                    for item in expression.get_editor_property("inputs")
                ],
                "code": str(expression.get_editor_property("code")),
            }
        )

overrides = {}
for row in instance.get_editor_property("scalar_parameter_values"):
    info = row.get_editor_property("parameter_info")
    overrides[
        str(info.get_editor_property("name"))
    ] = float(row.get_editor_property("parameter_value"))

resolved = {}
for name in (
    "G5_DebugMode",
    "G5_DensityDisplayGain",
    "G5_SigmaDisplayGain",
    "G5_DepthDisplayGain",
):
    try:
        resolved[name] = float(
            unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                instance, name
            )
        )
    except Exception as error:
        resolved[name] = "ERROR:" + str(error)

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    MATERIAL_PATH
)
result = {
    "parent": instance.get_editor_property("parent").get_path_name(),
    "defaults": scalars,
    "overrides": overrides,
    "resolved": resolved,
    "customNodes": custom_nodes,
    "compiled": bool(diagnostics.is_compiled_ok),
    "compileErrors": [
        str(item) for item in diagnostics.compile_errors
    ],
}
print("G5_DEBUG_MAPPING=" + json.dumps(result, sort_keys=True))
