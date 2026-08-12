import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"
SYSTEM = ROOT + "/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"


material = unreal.load_asset(MATERIAL)
instance = unreal.load_asset(INSTANCE)
if not isinstance(material, unreal.Material):
    raise RuntimeError("Missing V2 display material")
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Missing V2 material instance")

expressions = []
for expression in unreal.MaterialEditingLibrary.get_material_expressions(material):
    row = {
        "class": expression.get_class().get_name(),
        "name": expression.get_name(),
    }
    try:
        row["parameter"] = str(expression.get_editor_property("parameter_name"))
    except Exception:
        pass
    if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall):
        function = expression.get_editor_property("material_function")
        row["function"] = function.get_path_name() if function else None
    expressions.append(row)

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL)
print("V2_MATERIAL_INSPECT=" + json.dumps({
    "material": material.get_path_name(),
    "instance": instance.get_path_name(),
    "instanceParent": instance.get_editor_property("parent").get_path_name(),
    "expressions": expressions,
    "compiled": bool(diagnostics.is_compiled_ok),
    "compileErrors": [str(value) for value in diagnostics.compile_errors],
}, sort_keys=True))
