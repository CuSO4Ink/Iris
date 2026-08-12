import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
FUNCTION_FOLDER = ROOT + "/Functions/G5"
FUNCTION_PATH = FUNCTION_FOLDER + "/MF_SSPR_G5_FieldDebugV2"
MATERIAL_PATH = ROOT + "/M_SSPR_G5_FieldDebugV2"
INSTANCE_PATH = ROOT + "/MI_SSPR_G5_FieldDebugV2"


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {} -> {}".format(source_output, target_input)
        )


def function_input(function, name, input_type, priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionInput, x, y
    )
    node.set_editor_property("input_name", name)
    node.set_editor_property("input_type", input_type)
    node.set_editor_property("sort_priority", priority)
    node.set_editor_property(
        "use_preview_value_as_default",
        input_type != unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
    )
    return node


def function_output(function, name, priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionOutput, x, y
    )
    node.set_editor_property("output_name", name)
    node.set_editor_property("sort_priority", priority)
    return node


def scalar(material, name, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    try:
        node.set_editor_property("group", "G5 Field Debug")
    except Exception:
        pass
    return node


def build_function():
    lib = unreal.MaterialEditingLibrary
    function = unreal.load_asset(FUNCTION_PATH)
    created = False
    if function is None:
        function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "MF_SSPR_G5_FieldDebugV2",
            FUNCTION_FOLDER,
            unreal.MaterialFunction,
            unreal.MaterialFunctionFactoryNew(),
        )
        created = True
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Failed to create G5 field debug function")
    lib.delete_all_material_expressions_in_function(function)
    function.set_editor_property(
        "description",
        "G5 current-frame direction tensor and depth-field debug views.",
    )
    function.set_editor_property("expose_to_library", True)

    inputs = {
        "MainTexture": function_input(
            function,
            "MainTexture",
            unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
            0,
            -1200,
            -320,
        ),
        "AuxTexture": function_input(
            function,
            "AuxTexture",
            unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
            1,
            -1200,
            -160,
        ),
        "UV": function_input(
            function,
            "UV",
            unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2,
            2,
            -1200,
            0,
        ),
        "DebugMode": function_input(
            function,
            "DebugMode",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            3,
            -1200,
            160,
        ),
        "DensityDisplayGain": function_input(
            function,
            "DensityDisplayGain",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            4,
            -1200,
            320,
        ),
        "SigmaDisplayGain": function_input(
            function,
            "SigmaDisplayGain",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            5,
            -1200,
            480,
        ),
        "DepthDisplayGain": function_input(
            function,
            "DepthDisplayGain",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            6,
            -1200,
            640,
        ),
    }

    custom = lib.create_material_expression_in_function(
        function, unreal.MaterialExpressionCustom, -520, 20
    )
    custom.set_editor_property("description", "G5 Field Debug View")
    custom.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4
    )
    custom_inputs = []
    for name in (
        "MainTexture",
        "AuxTexture",
        "UV",
        "DebugMode",
        "DensityDisplayGain",
        "SigmaDisplayGain",
        "DepthDisplayGain",
    ):
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)
    custom.set_editor_property(
        "code",
        r"""
float mode = floor(DebugMode + 0.5f);
float2 unitUV = clamp(UV, 0.0f, 0.999999f);
float2 panelIndex = floor(unitUV * 2.0f);
float panel = panelIndex.x + panelIndex.y * 2.0f;
float2 safeUV = mode >= 5.5f
    ? frac(unitUV * 2.0f)
    : unitUV;
float4 mainField = Texture2DSampleLevel(
    MainTexture, MainTextureSampler, safeUV, 0);
float4 auxField = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, safeUV, 0);

float density = max(mainField.r, 0.0f);
float densityView = 1.0f - exp(
    -density * max(DensityDisplayGain, 0.0f));
float2 tensor = mainField.gb;
float coherence = saturate(length(tensor));
float2 tensorDirection = coherence > 1.0e-5f
    ? tensor / coherence
    : float2(0.0f, 0.0f);

float value = 0.0f;
float3 color = densityView.xxx;
if (mode >= 5.5f)
{
    if (panel < 0.5f)
    {
        color = float3(
            0.5f + 0.5f * tensorDirection.x,
            0.5f + 0.5f * tensorDirection.y,
            coherence);
    }
    else
    {
        value = panel < 1.5f
            ? saturate(
                mainField.a * max(DepthDisplayGain, 0.0f))
            : (
                panel < 2.5f
                ? saturate(
                    auxField.r * max(SigmaDisplayGain, 0.0f))
                : saturate(
                    auxField.g * max(DepthDisplayGain, 0.0f))
            );
        color = saturate(float3(
            1.5f - abs(4.0f * value - 3.0f),
            1.5f - abs(4.0f * value - 2.0f),
            1.5f - abs(4.0f * value - 1.0f)));
    }
}
else if (mode >= 0.5f && mode < 1.5f)
{
    color = float3(
        0.5f + 0.5f * tensorDirection.x,
        0.5f + 0.5f * tensorDirection.y,
        coherence);
}
else if (mode >= 1.5f && mode < 2.5f)
{
    color = coherence.xxx;
}
else if (mode >= 2.5f && mode < 3.5f)
{
    value = saturate(
        mainField.a * max(DepthDisplayGain, 0.0f));
    color = saturate(float3(
        1.5f - abs(4.0f * value - 3.0f),
        1.5f - abs(4.0f * value - 2.0f),
        1.5f - abs(4.0f * value - 1.0f)));
}
else if (mode >= 3.5f && mode < 4.5f)
{
    value = saturate(auxField.r * max(SigmaDisplayGain, 0.0f));
    color = saturate(float3(
        1.5f - abs(4.0f * value - 3.0f),
        1.5f - abs(4.0f * value - 2.0f),
        1.5f - abs(4.0f * value - 1.0f)));
}
else if (mode >= 4.5f)
{
    value = saturate(
        auxField.g * max(DepthDisplayGain, 0.0f));
    color = saturate(float3(
        1.5f - abs(4.0f * value - 3.0f),
        1.5f - abs(4.0f * value - 2.0f),
        1.5f - abs(4.0f * value - 1.0f)));
}

float fieldSupport = saturate(max(densityView, auxField.a));
float opacity = mode < 0.5f
    ? densityView
    : fieldSupport;
return float4(color, opacity);
""".strip(),
    )

    output = function_output(function, "Debug", 0, 240, 20)
    for name, node in inputs.items():
        connect(node, "", custom, name)
    output_inputs = [
        str(value)
        for value in lib.get_material_expression_input_names(output)
    ]
    if not output_inputs:
        raise RuntimeError("G5 debug output pin is missing")
    connect(custom, "", output, output_inputs[0])

    lib.layout_material_function_expressions(function)
    lib.update_material_function(function)
    saved = bool(unreal.EditorAssetLibrary.save_asset(FUNCTION_PATH, False))
    return function, created, saved


def create_function_call(material):
    lib = unreal.MaterialEditingLibrary
    before = {
        expression.get_path_name()
        for expression in lib.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        MATERIAL_PATH, FUNCTION_PATH, -300, 0
    )
    if not str(info.id):
        raise RuntimeError("Failed to create G5 field debug function call")
    candidates = [
        expression
        for expression in lib.get_material_expressions(material)
        if expression.get_path_name() not in before
        and isinstance(
            expression, unreal.MaterialExpressionMaterialFunctionCall
        )
    ]
    if len(candidates) != 1:
        raise RuntimeError("Could not identify G5 debug function call")
    return candidates[0]


def build_material():
    lib = unreal.MaterialEditingLibrary
    material = unreal.load_asset(MATERIAL_PATH)
    created = False
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_SSPR_G5_FieldDebugV2",
            ROOT,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        created = True
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Failed to create G5 field debug material")
    lib.delete_all_material_expressions(material)
    material.set_editor_property(
        "material_domain", unreal.MaterialDomain.MD_SURFACE
    )
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    try:
        material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )
    except Exception:
        pass
    material.set_editor_property("two_sided", True)
    material.set_editor_property("disable_depth_test", True)

    black = unreal.load_asset("/Engine/EngineResources/Black.Black")
    main_texture = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -1000,
        -300,
    )
    main_texture.set_editor_property("parameter_name", "TrajectoryTexture")
    main_texture.set_editor_property("texture", black)
    aux_texture = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -1000,
        -140,
    )
    aux_texture.set_editor_property("parameter_name", "TrajectoryAuxTexture")
    aux_texture.set_editor_property("texture", black)
    screen = lib.create_material_expression(
        material, unreal.MaterialExpressionScreenPosition, -1000, 20
    )
    params = {
        "DebugMode": scalar(material, "G5_DebugMode", 6.0, -1000, 180),
        "DensityDisplayGain": scalar(
            material, "G5_DensityDisplayGain", 0.9, -1000, 340
        ),
        "SigmaDisplayGain": scalar(
            material, "G5_SigmaDisplayGain", 8.0, -1000, 500
        ),
        "DepthDisplayGain": scalar(
            material, "G5_DepthDisplayGain", 10.0, -1000, 660
        ),
    }
    function = unreal.load_asset(FUNCTION_PATH)
    function_custom = next(
        (
            expression
            for expression in lib.get_material_function_expressions(function)
            if isinstance(expression, unreal.MaterialExpressionCustom)
        ),
        None,
    )
    if function_custom is None:
        raise RuntimeError("G5 debug function Custom expression is missing")
    custom = lib.create_material_expression(
        material, unreal.MaterialExpressionCustom, -300, 0
    )
    custom.set_editor_property("description", "G5 Field Debug View")
    custom.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4
    )
    custom_inputs = []
    for name in (
        "MainTexture",
        "AuxTexture",
        "UV",
        "DebugMode",
        "DensityDisplayGain",
        "SigmaDisplayGain",
        "DepthDisplayGain",
    ):
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)
    custom.set_editor_property(
        "code", function_custom.get_editor_property("code")
    )
    connect(main_texture, "", custom, "MainTexture")
    connect(aux_texture, "", custom, "AuxTexture")
    connect(screen, "ViewportUV", custom, "UV")
    for custom_input, parameter in params.items():
        connect(parameter, "", custom, custom_input)
    color_mask = lib.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 100, -60
    )
    color_mask.set_editor_property("r", True)
    color_mask.set_editor_property("g", True)
    color_mask.set_editor_property("b", True)
    color_mask.set_editor_property("a", False)
    opacity_mask = lib.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 100, 100
    )
    opacity_mask.set_editor_property("r", False)
    opacity_mask.set_editor_property("g", False)
    opacity_mask.set_editor_property("b", False)
    opacity_mask.set_editor_property("a", True)
    color_mask_inputs = [
        str(value)
        for value in lib.get_material_expression_input_names(color_mask)
    ]
    opacity_mask_inputs = [
        str(value)
        for value in lib.get_material_expression_input_names(opacity_mask)
    ]
    if not color_mask_inputs or not opacity_mask_inputs:
        raise RuntimeError("G5 debug material mask pins are missing")
    connect(custom, "", color_mask, color_mask_inputs[0])
    connect(custom, "", opacity_mask, opacity_mask_inputs[0])
    if not lib.connect_material_property(
        color_mask, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Failed G5 debug emissive connection")
    if not lib.connect_material_property(
        opacity_mask, "", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed G5 debug opacity connection")
    try:
        lib.set_material_usage(
            material, unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES
        )
    except Exception:
        try:
            material.set_editor_property("used_with_niagara_sprites", True)
        except Exception:
            pass
    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False))
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
        MATERIAL_PATH
    )
    result = {
        "created": created,
        "saved": saved,
        "compiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [
            str(item) for item in diagnostics.compile_errors
        ],
        "expressions": len(lib.get_material_expressions(material)),
    }
    if (
        not result["saved"]
        or not result["compiled"]
        or result["compileErrors"]
    ):
        raise RuntimeError("G5 debug material gate failed: " + repr(result))
    return material, result


def build_instance(material):
    instance = unreal.load_asset(INSTANCE_PATH)
    created = False
    if instance is None:
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "MI_SSPR_G5_FieldDebugV2",
            ROOT,
            unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew(),
        )
        created = True
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Failed to create G5 field debug MI")
    instance.set_editor_property("parent", material)
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "G5_DebugMode", 6.0
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "G5_DensityDisplayGain", 0.9
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "G5_SigmaDisplayGain", 8.0
    )
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, "G5_DepthDisplayGain", 10.0
    )
    saved = bool(unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False))
    if not saved:
        raise RuntimeError("Failed to save G5 field debug MI")
    return {"created": created, "saved": saved}


unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
function, function_created, function_saved = build_function()
material, material_result = build_material()
instance_result = build_instance(material)
result = {
    "function": {
        "path": function.get_path_name(),
        "created": function_created,
        "saved": function_saved,
    },
    "material": material_result,
    "instance": instance_result,
    "debugModes": {
        "0": "Density",
        "1": "DirectionTensor",
        "2": "Coherence",
        "3": "MeanDepth",
        "4": "DepthSigma",
        "5": "FrontDepth",
        "6": "FourPanelDirectionMeanSigmaFront",
    },
}
print("G5_FIELD_DEBUG=" + json.dumps(result, sort_keys=True))
if not function_saved:
    raise RuntimeError("G5 field debug function was not saved")
