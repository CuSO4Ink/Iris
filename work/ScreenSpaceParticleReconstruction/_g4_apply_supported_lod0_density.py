import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
PYRAMID_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity"


SUPPORTED_DENSITY_CODE = r"""
float3 positiveScales = max(Scales, 0.0f);
float core = positiveScales.x;
float medium = positiveScales.y;
float body = positiveScales.z;

// A raw splat is allowed to sharpen the result only when the reconstructed
// neighborhood supports it. This attenuates isolated particle centers while
// retaining the core of connected filaments.
float neighborhood = medium + 0.5f * body;
float relativeSupport = neighborhood / max(max(core, neighborhood), 1.0e-5f);
float support = smoothstep(0.12f, 0.45f, relativeSupport)
              * smoothstep(0.002f, 0.030f, neighborhood);
float supportedCore = core * support;

float3 weights = max(float3(CoreWeight, SmallWeight, LargeWeight), 0.0f);
float density = dot(float3(supportedCore, medium, body), weights);
float fineDetail = max(supportedCore - medium, 0.0f);
float broadEdge = max(medium - body, 0.0f);
density += fineDetail * max(DetailStrength, 0.0f);
density += broadEdge * max(EdgeStrength, 0.0f);
density = max(density - max(BlackPoint, 0.0f), 0.0f);
density *= max(DensityGain, 0.0f);
float safeContrast = max(Contrast, 0.01f);
return pow(max(density, 1.0e-6f), safeContrast);
"""


SCALAR_VALUES = {
    "AS_InputGain": 1.0,
    "AS_MediumRadiusPx": 16.0,
    "AS_BodyRadiusPx": 52.0,
    # Retained for the published interface. The active reconstruction is LOD0.
    "AS_MediumMipBias": -0.15,
    "AS_BodyMipBias": 0.35,
    "AS_RidgeStrength": 0.0,
    "AS_FilamentWeight": 0.06,
    "AS_MediumWeight": 0.58,
    "AS_BodyWeight": 0.36,
    "AS_DetailStrength": 0.0,
    "AS_EdgeStrength": 0.0,
    "AS_BlackPoint": 0.003,
    "AS_DensityGain": 1.40,
    "AS_Contrast": 1.10,
    "AS_EdgeFadeWidthPx": 20.0,
    "AS_LightingMipLevel": 4.0,
    "AS_LightingGradientRadius": 1.0,
    "AS_LightingGradientStrength": 2.0,
    "AS_AmbientLight": 1.0,
    "AS_LightStrength": 0.0,
    "AS_Extinction": 1.70,
    "AS_OpacityScale": 0.82,
    "AS_EmissiveStrength": 1.0,
    "AS_DebugRaw": 0.0,
}


def function_path(call):
    function = call.get_editor_property("material_function")
    if function is None:
        return None
    return function.get_path_name().split(".")[0]


def find_parameter(expressions, name):
    matches = []
    for expression in expressions:
        try:
            parameter_name = str(expression.get_editor_property("parameter_name"))
        except Exception:
            continue
        if parameter_name == name:
            matches.append(expression)
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one material parameter {}, found {}".format(name, len(matches))
        )
    return matches[0]


def find_function_call(expressions, path):
    matches = [
        expression
        for expression in expressions
        if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
        and function_path(expression) == path
    ]
    if len(matches) > 1:
        raise RuntimeError(
            "Expected at most one call to {}, found {}".format(path, len(matches))
        )
    return matches[0] if matches else None


def create_function_call(material, path, x, y):
    library = unreal.MaterialEditingLibrary
    before = {
        expression.get_path_name()
        for expression in library.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        MATERIAL_PATH, path, int(x), int(y)
    )
    if not str(info.id):
        raise RuntimeError("Failed to create material-function call: " + path)
    candidates = [
        expression
        for expression in library.get_material_expressions(material)
        if expression.get_path_name() not in before
        and isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
        and function_path(expression) == path
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "Could not identify newly created function call: " + path
        )
    return candidates[0]


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {}.{} -> {}.{}".format(
                source.get_name(), source_output, target.get_name(), target_input
            )
        )


def save_loaded(asset, path):
    saved = bool(unreal.EditorAssetLibrary.save_loaded_asset(asset, False))
    if not saved:
        saved = bool(unreal.EditorAssetLibrary.save_asset(path, False))
    return saved


def scalar_overrides(instance):
    return {
        str(
            row.get_editor_property("parameter_info").get_editor_property("name")
        ): float(row.get_editor_property("parameter_value"))
        for row in instance.get_editor_property("scalar_parameter_values")
    }


def main():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem.is_in_play_in_editor():
        raise RuntimeError("Refusing to modify published assets while PIE is active")

    material = unreal.load_asset(MATERIAL_PATH)
    instance = unreal.load_asset(INSTANCE_PATH)
    shape = unreal.load_asset(SHAPE_PATH)
    pyramid = unreal.load_asset(PYRAMID_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing V2 display material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Missing V2 HQ material instance")
    if not isinstance(shape, unreal.MaterialFunction):
        raise RuntimeError("Missing V2 density-shape function")
    if not isinstance(pyramid, unreal.MaterialFunction):
        raise RuntimeError("Missing V2 LOD0 pyramid function")

    library = unreal.MaterialEditingLibrary
    shape_custom_nodes = [
        expression
        for expression in library.get_material_function_expressions(shape)
        if isinstance(expression, unreal.MaterialExpressionCustom)
    ]
    if len(shape_custom_nodes) != 1:
        raise RuntimeError(
            "Expected exactly one density-shape Custom node, found {}".format(
                len(shape_custom_nodes)
            )
        )
    expected_inputs = [
        "Scales",
        "CoreWeight",
        "SmallWeight",
        "LargeWeight",
        "DetailStrength",
        "EdgeStrength",
        "BlackPoint",
        "DensityGain",
        "Contrast",
    ]
    actual_inputs = [
        str(value.get_editor_property("input_name"))
        for value in shape_custom_nodes[0].get_editor_property("inputs")
    ]
    if actual_inputs != expected_inputs:
        raise RuntimeError(
            "Density-shape interface changed: {}".format(actual_inputs)
        )

    shape.modify()
    shape_custom_nodes[0].modify()
    shape_custom_nodes[0].set_editor_property(
        "code", SUPPORTED_DENSITY_CODE.strip()
    )
    shape_custom_nodes[0].set_editor_property(
        "description", "SSPR G4 supported multiscale density shape"
    )
    shape.set_editor_property(
        "description",
        "SSPR G4: suppress isolated splat cores using current-frame multiscale neighborhood support.",
    )
    library.update_material_function(shape)
    shape_saved = save_loaded(shape, SHAPE_PATH)

    material.modify()
    expressions = list(library.get_material_expressions(material))
    texture = find_parameter(expressions, "TrajectoryTexture")
    texel = find_parameter(expressions, "SSPR_InvTextureSize")
    screen_nodes = [
        expression
        for expression in expressions
        if isinstance(expression, unreal.MaterialExpressionScreenPosition)
    ]
    if len(screen_nodes) != 1:
        raise RuntimeError(
            "Expected one ScreenPosition node, found {}".format(len(screen_nodes))
        )
    screen = screen_nodes[0]
    shape_call = find_function_call(expressions, SHAPE_PATH)
    if shape_call is None:
        raise RuntimeError("Density-shape call is missing from the display material")

    pyramid_call = find_function_call(expressions, PYRAMID_PATH)
    pyramid_created = pyramid_call is None
    if pyramid_call is None:
        pyramid_call = create_function_call(material, PYRAMID_PATH, -1280, -180)

    connect(texture, "", pyramid_call, "SourceTexture")
    connect(screen, "ViewportUV", pyramid_call, "UV")
    connect(texel, "", pyramid_call, "TexelSize")
    for input_name, parameter_name in (
        ("SmallRadiusPx", "AS_MediumRadiusPx"),
        ("LargeRadiusPx", "AS_BodyRadiusPx"),
        ("SmallMipBias", "AS_MediumMipBias"),
        ("LargeMipBias", "AS_BodyMipBias"),
    ):
        connect(
            find_parameter(expressions, parameter_name),
            "",
            pyramid_call,
            input_name,
        )
    connect(pyramid_call, "Scales", shape_call, "Scales")

    library.layout_material_expressions(material)
    library.recompile_material(material)
    material_saved = save_loaded(material, MATERIAL_PATH)

    instance.modify()
    for name, value in SCALAR_VALUES.items():
        library.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
    try:
        instance.post_edit_change()
    except Exception:
        pass
    instance_saved = save_loaded(instance, INSTANCE_PATH)

    stored = scalar_overrides(instance)
    missing = sorted(set(SCALAR_VALUES) - set(stored))
    mismatched = {
        name: {"expected": value, "stored": stored.get(name)}
        for name, value in SCALAR_VALUES.items()
        if name in stored and abs(stored[name] - value) > 1.0e-5
    }
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    active_calls = [
        function_path(expression)
        for expression in library.get_material_expressions(material)
        if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
    ]
    result = {
        "shapeSaved": shape_saved,
        "materialSaved": material_saved,
        "instanceSaved": instance_saved,
        "pyramidCreated": pyramid_created,
        "activeFunctionCalls": active_calls,
        "scalarValues": SCALAR_VALUES,
        "missing": missing,
        "mismatched": mismatched,
        "materialCompiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [str(value) for value in diagnostics.compile_errors],
    }
    print("G4_SUPPORTED_LOD0_DENSITY=" + json.dumps(result, sort_keys=True))
    if (
        not shape_saved
        or not material_saved
        or not instance_saved
        or missing
        or mismatched
        or not diagnostics.is_compiled_ok
        or diagnostics.compile_errors
    ):
        raise RuntimeError("G4 density validation failed: " + repr(result))


main()
