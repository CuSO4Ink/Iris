import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_G5_V2"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_G5_V2_HQ"
SYSTEM_PATH = ROOT + "/NS_SSPR_AnisotropicSplat_Main"
LEVEL_PATH = ROOT + "/L_SSPR_AnisotropicSplat_Validation"


def package_path(value):
    return value.get_path_name().split(".", 1)[0]


def function_calls(container):
    if isinstance(container, unreal.Material):
        expressions = unreal.MaterialEditingLibrary.get_material_expressions(
            container
        )
    elif isinstance(container, unreal.MaterialFunction):
        expressions = (
            unreal.MaterialEditingLibrary.get_material_function_expressions(
                container
            )
        )
    else:
        return []
    result = []
    for expression in expressions:
        if not isinstance(
            expression, unreal.MaterialExpressionMaterialFunctionCall
        ):
            continue
        function = expression.get_editor_property("material_function")
        if isinstance(function, unreal.MaterialFunction):
            result.append(package_path(function))
    return sorted(set(result))


material = unreal.load_asset(MATERIAL_PATH)
instance = unreal.load_asset(INSTANCE_PATH)
system = unreal.load_asset(SYSTEM_PATH)
level = unreal.load_asset(LEVEL_PATH)
if not isinstance(material, unreal.Material):
    raise RuntimeError("Current G5 Visual V2 material is missing")
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Current G5 Visual V2 instance is missing")
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Current V2 system is missing")
if level is None:
    raise RuntimeError("Current validation level is missing")

pending = function_calls(material)
visited = set()
function_graph = {}
while pending:
    path = pending.pop(0)
    if path in visited:
        continue
    visited.add(path)
    function = unreal.load_asset(path)
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Missing function dependency: " + path)
    children = function_calls(function)
    function_graph[path] = children
    pending.extend(path for path in children if path not in visited)

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    MATERIAL_PATH
)
result = {
    "roots": {
        "level": LEVEL_PATH,
        "system": SYSTEM_PATH,
        "material": MATERIAL_PATH,
        "instance": INSTANCE_PATH,
    },
    "instanceParent": package_path(
        instance.get_editor_property("parent")
    ),
    "directFunctionCalls": function_calls(material),
    "recursiveFunctionGraph": function_graph,
    "effectAssetPackages": sorted(
        {
            LEVEL_PATH,
            SYSTEM_PATH,
            MATERIAL_PATH,
            INSTANCE_PATH,
            *visited,
        }
    ),
    "effectAssetCount": 4 + len(visited),
    "materialCompiled": bool(diagnostics.is_compiled_ok),
    "materialErrors": [
        str(value) for value in diagnostics.compile_errors
    ],
}
print("V3_CURRENT_OUTPUT_CHAIN=" + json.dumps(result, sort_keys=True))
if (
    result["instanceParent"] != MATERIAL_PATH
    or not result["materialCompiled"]
    or result["materialErrors"]
):
    raise RuntimeError("Current output chain audit failed: " + repr(result))
