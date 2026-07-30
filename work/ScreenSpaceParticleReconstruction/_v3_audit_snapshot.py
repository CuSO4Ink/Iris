import json
import unreal


ROOT = "/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730"
SYSTEM_PATH = ROOT + "/NS_SSPR_AnisotropicSplat_V3"
SYSTEM_OBJECT = SYSTEM_PATH + ".NS_SSPR_AnisotropicSplat_V3"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_V3"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_V3_HQ"
LEVEL_PATH = ROOT + "/L_SSPR_AnisotropicSplat_V3_Validation"
EXPECTED_FUNCTIONS = {
    ROOT + "/Functions/RasterInput/MF_SSPR_V3_RawAnisotropicDensity",
    ROOT + "/Functions/Reconstruction/MF_SSPR_V3_DensityShape",
    ROOT + "/Functions/Reconstruction/MF_SSPR_V3_MipPyramidDensity",
    ROOT + "/Functions/Reconstruction/MF_SSPR_V3_StreamlineDensity",
    ROOT + "/Functions/Shading/MF_SSPR_V3_DepthLighting",
    ROOT + "/Functions/Shading/MF_SSPR_V3_SmokeResolve",
    ROOT + "/Functions/Utility/MF_SSPR_V3_ScreenEdgeMask",
}


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


assets = sorted(
    unreal.EditorAssetLibrary.list_assets(ROOT, True, False)
)
material = unreal.load_asset(MATERIAL_PATH)
instance = unreal.load_asset(INSTANCE_PATH)
system = unreal.load_asset(SYSTEM_PATH)
if not isinstance(material, unreal.Material):
    raise RuntimeError("Missing V3 material")
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Missing V3 material instance")
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Missing V3 Niagara system")

calls = set(function_calls(material))
function_graph = {}
for path in sorted(EXPECTED_FUNCTIONS):
    function = unreal.load_asset(path)
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Missing V3 function " + path)
    function_graph[path] = function_calls(function)

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    MATERIAL_PATH
)
main_components = []
for actor in unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors():
    if actor.get_actor_label() != "SSPR_ParticleTrails_Main":
        continue
    for component in actor.get_components_by_class(
        unreal.NiagaraComponent
    ):
        asset = component.get_asset()
        main_components.append(
            asset.get_path_name() if asset else None
        )

result = {
    "root": ROOT,
    "assetCount": len(assets),
    "assets": assets,
    "directFunctionCalls": sorted(calls),
    "functionGraph": function_graph,
    "instanceParent": package_path(
        instance.get_editor_property("parent")
    ),
    "levelMainComponents": main_components,
    "fixedTick": bool(
        system.get_editor_property("fixed_tick_delta")
    ),
    "fixedTickDeltaTime": float(
        system.get_editor_property("fixed_tick_delta_time")
    ),
    "compileMessages": [
        str(message)
        for message in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM_OBJECT, False
        )
    ],
    "materialCompiled": bool(diagnostics.is_compiled_ok),
    "materialErrors": [
        str(value) for value in diagnostics.compile_errors
    ],
    "v2ReferencesInEffectClosure": sorted(
        path
        for path in [
            *calls,
            package_path(instance.get_editor_property("parent")),
            *main_components,
        ]
        if path and "/M2/AnisotropicSplat_V2/" in path
    ),
}
print("V3_SNAPSHOT_AUDIT=" + json.dumps(result, sort_keys=True))
if (
    result["assetCount"] != 11
    or calls != EXPECTED_FUNCTIONS
    or any(function_graph.values())
    or result["instanceParent"] != MATERIAL_PATH
    or main_components != [SYSTEM_OBJECT]
    or not result["fixedTick"]
    or abs(result["fixedTickDeltaTime"] - 0.01667) > 0.00001
    or result["compileMessages"]
    or not result["materialCompiled"]
    or result["materialErrors"]
    or result["v2ReferencesInEffectClosure"]
):
    raise RuntimeError("V3 snapshot audit failed: " + repr(result))
