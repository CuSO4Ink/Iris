import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
SYSTEM_PATH = ROOT + "/NS_SSPR_AnisotropicSplat_Main"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_FieldRecon_V1"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ"
RECON_PATH = (
    ROOT + "/Functions/G5/MF_SSPR_G5_NormalizedFieldReconstructionV1"
)
LIGHTING_PATH = (
    ROOT + "/Functions/G5/MF_SSPR_G5_DepthTransportLightingV1"
)
EXPECTED_CALLS = {
    RECON_PATH,
    LIGHTING_PATH,
    ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape",
    ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve",
    ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_ScreenEdgeMask",
}
FORBIDDEN_CALL_TOKENS = (
    "MipPyramidDensity",
    "StreamlineDensityV1",
    "StreamlineDensityV2",
)


def package_path(value):
    return value.get_path_name().split(".", 1)[0]


material = unreal.load_asset(MATERIAL_PATH)
instance = unreal.load_asset(INSTANCE_PATH)
system = unreal.load_asset(SYSTEM_PATH)
reconstruction = unreal.load_asset(RECON_PATH)
lighting = unreal.load_asset(LIGHTING_PATH)
if not isinstance(material, unreal.Material):
    raise RuntimeError("Missing normalized field material")
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Missing normalized field MI")
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("Missing V2 Niagara system")

calls = []
for expression in unreal.MaterialEditingLibrary.get_material_expressions(
    material
):
    if not isinstance(
        expression, unreal.MaterialExpressionMaterialFunctionCall
    ):
        continue
    function = expression.get_editor_property("material_function")
    if isinstance(function, unreal.MaterialFunction):
        calls.append(package_path(function))

custom_code = {}
for path, function in (
    (RECON_PATH, reconstruction),
    (LIGHTING_PATH, lighting),
):
    nodes = [
        expression
        for expression in unreal.MaterialEditingLibrary.get_material_function_expressions(
            function
        )
        if isinstance(expression, unreal.MaterialExpressionCustom)
    ]
    if len(nodes) != 1:
        raise RuntimeError(
            "Expected one Custom node in {}, found {}".format(
                path, len(nodes)
            )
        )
    custom_code[path] = str(nodes[0].get_editor_property("code"))

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    MATERIAL_PATH
)
result = {
    "material": MATERIAL_PATH,
    "instance": INSTANCE_PATH,
    "instanceParent": package_path(
        instance.get_editor_property("parent")
    ),
    "functionCalls": sorted(calls),
    "forbiddenCalls": sorted(
        call
        for call in calls
        if any(token in call for token in FORBIDDEN_CALL_TOKENS)
    ),
    "historyTokens": {
        path: "History" in code
        for path, code in custom_code.items()
    },
    "normalizedCoverageContract": all(
        token in custom_code[RECON_PATH]
        for token in (
            "coverage",
            "denominator",
            "normalizedDensity",
            "supportEnvelope",
        )
    ),
    "frontMeanSigmaContract": all(
        token in custom_code[LIGHTING_PATH]
        for token in (
            "meanDepth",
            "frontDepth",
            "sigma",
            "backDepth",
            "opticalThickness",
        )
    ),
    "fixedTick": bool(
        system.get_editor_property("fixed_tick_delta")
    ),
    "fixedTickDeltaTime": float(
        system.get_editor_property("fixed_tick_delta_time")
    ),
    "compileMessages": [
        str(message)
        for message in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM_PATH + ".NS_SSPR_AnisotropicSplat_Main",
            False,
        )
    ],
    "materialCompiled": bool(diagnostics.is_compiled_ok),
    "materialErrors": [
        str(value) for value in diagnostics.compile_errors
    ],
}
print(
    "G5_NORMALIZED_FIELD_RECONSTRUCTION_V1_AUDIT="
    + json.dumps(result, sort_keys=True)
)
if (
    set(calls) != EXPECTED_CALLS
    or result["instanceParent"] != MATERIAL_PATH
    or result["forbiddenCalls"]
    or any(result["historyTokens"].values())
    or not result["normalizedCoverageContract"]
    or not result["frontMeanSigmaContract"]
    or not result["fixedTick"]
    or abs(result["fixedTickDeltaTime"] - 0.01667) > 0.00001
    or result["compileMessages"]
    or not result["materialCompiled"]
    or result["materialErrors"]
):
    raise RuntimeError(
        "Normalized field reconstruction audit failed: "
        + repr(result)
    )
