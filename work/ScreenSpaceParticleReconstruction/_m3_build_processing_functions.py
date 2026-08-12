import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
FUNCTION_FOLDER = ROOT + "/Functions/M3_HQBaseline"
RAW_PATH = FUNCTION_FOLDER + "/MF_SSPR_RawDensity"
MULTISCALE_PATH = FUNCTION_FOLDER + "/MF_SSPR_MultiScaleDensity"
SHAPE_PATH = FUNCTION_FOLDER + "/MF_SSPR_DensityShape"
RESOLVE_PATH = FUNCTION_FOLDER + "/MF_SSPR_SmokeResolve"
PROBE_PATH = FUNCTION_FOLDER + "/M_SSPR_M3_FunctionChain_Probe"


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {} -> {}".format(source_output, target_input)
        )


def create_or_reset_function(asset_name, asset_path, description):
    lib = unreal.MaterialEditingLibrary
    function = unreal.load_asset(asset_path)
    created = False
    if function is None:
        function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name,
            FUNCTION_FOLDER,
            unreal.MaterialFunction,
            unreal.MaterialFunctionFactoryNew(),
        )
        created = function is not None
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Invalid material function " + asset_path)
    lib.delete_all_material_expressions_in_function(function)
    function.set_editor_property("description", description)
    function.set_editor_property("expose_to_library", True)
    return function, created


def add_input(function, name, input_type, sort_priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionInput, x, y
    )
    if node is None:
        raise RuntimeError("Failed to create input " + name)
    node.set_editor_property("input_name", name)
    node.set_editor_property("input_type", input_type)
    node.set_editor_property("sort_priority", sort_priority)
    node.set_editor_property("use_preview_value_as_default", True)
    return node


def add_output(function, name, sort_priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionOutput, x, y
    )
    if node is None:
        raise RuntimeError("Failed to create output " + name)
    node.set_editor_property("output_name", name)
    node.set_editor_property("sort_priority", sort_priority)
    return node


def output_input_name(node):
    names = [
        str(value)
        for value in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            node
        )
    ]
    if not names:
        raise RuntimeError("Function output has no input pin")
    return names[0]


def make_custom(function, description, output_type, input_names, code, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionCustom, x, y
    )
    if node is None:
        raise RuntimeError("Failed to create custom node " + description)
    node.set_editor_property("description", description)
    node.set_editor_property("output_type", output_type)
    inputs = []
    for input_name in input_names:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", input_name)
        inputs.append(item)
    node.set_editor_property("inputs", inputs)
    node.set_editor_property("code", code.strip())
    return node


def finish_function(function, asset_path, created):
    lib = unreal.MaterialEditingLibrary
    lib.layout_material_function_expressions(function)
    lib.update_material_function(function)
    saved = bool(unreal.EditorAssetLibrary.save_asset(asset_path, False))
    if not saved:
        raise RuntimeError("Failed to save " + asset_path)
    return {
        "path": function.get_path_name(),
        "created": created,
        "saved": saved,
        "expressionCount": len(lib.get_material_function_expressions(function)),
    }


def build_raw():
    function, created = create_or_reset_function(
        "MF_SSPR_RawDensity",
        RAW_PATH,
        "SSPR M3: sample Niagara trajectory density with viewport UV.",
    )
    specs = (
        (
            "SourceTexture",
            unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
            -900,
            -140,
        ),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2, -900, 40),
        ("Gain", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -900, 220),
    )
    nodes = {}
    for index, (name, input_type, x, y) in enumerate(specs):
        nodes[name] = add_input(function, name, input_type, index, x, y)
    custom = make_custom(
        function,
        "SSPR M3 Raw Density Sample",
        unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        [name for name, _, _, _ in specs],
        r"""
float2 safeUV = saturate(UV);
float density = Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, safeUV, 0).r;
return max(density, 0.0f) * max(Gain, 0.0f);
""",
        -300,
        30,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Density", 0, 300, 30)
    connect(custom, "", output, output_input_name(output))
    return finish_function(function, RAW_PATH, created)


def build_multiscale():
    function, created = create_or_reset_function(
        "MF_SSPR_MultiScaleDensity",
        MULTISCALE_PATH,
        "SSPR M3: 7x7 + 13x13 high-quality density reconstruction.",
    )
    specs = (
        (
            "SourceTexture",
            unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
            -1100,
            -260,
        ),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2, -1100, -80),
        (
            "TexelSize",
            unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2,
            -1100,
            100,
        ),
        (
            "SmallRadiusPx",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            -1100,
            280,
        ),
        (
            "LargeRadiusPx",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            -1100,
            460,
        ),
    )
    nodes = {}
    for index, (name, input_type, x, y) in enumerate(specs):
        nodes[name] = add_input(function, name, input_type, index, x, y)

    custom = make_custom(
        function,
        "SSPR M3 HQ Continuous MultiScale Gaussian",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
        [name for name, _, _, _ in specs],
        r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float core = max(Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, centerUV, 0).r, 0.0f);

float w7[7] = {1.0f, 6.0f, 15.0f, 20.0f, 15.0f, 6.0f, 1.0f};
float smallSum = 0.0f;
float smallWeight = 0.0f;
float smallStep = max(SmallRadiusPx, 0.0f) / 3.0f;
[unroll]
for (int sy = 0; sy < 7; ++sy)
{
    [unroll]
    for (int sx = 0; sx < 7; ++sx)
    {
        float2 tapUV = UV + float2(sx - 3, sy - 3) * safeTexel * smallStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w7[sx] * w7[sy] * valid;
        float sampleValue = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), 0).r;
        smallSum += max(sampleValue, 0.0f) * weight;
        smallWeight += weight;
    }
}
float small = smallSum / max(smallWeight, 1.0e-5f);

float w13[13] = {
    1.0f, 12.0f, 66.0f, 220.0f, 495.0f, 792.0f, 924.0f,
    792.0f, 495.0f, 220.0f, 66.0f, 12.0f, 1.0f
};
float largeSum = 0.0f;
float largeWeight = 0.0f;
float largeStep = max(LargeRadiusPx, 0.0f) / 6.0f;
[unroll]
for (int ly = 0; ly < 13; ++ly)
{
    [unroll]
    for (int lx = 0; lx < 13; ++lx)
    {
        float2 tapUV = UV + float2(lx - 6, ly - 6) * safeTexel * largeStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w13[lx] * w13[ly] * valid;
        float sampleValue = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), 0).r;
        largeSum += max(sampleValue, 0.0f) * weight;
        largeWeight += weight;
    }
}
float large = largeSum / max(largeWeight, 1.0e-5f);
return float3(core, small, large);
""",
        -390,
        40,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Scales", 0, 360, 40)
    connect(custom, "", output, output_input_name(output))
    return finish_function(function, MULTISCALE_PATH, created)


def build_shape():
    function, created = create_or_reset_function(
        "MF_SSPR_DensityShape",
        SHAPE_PATH,
        "SSPR M3: combine and shape Core/Small/Large density fields.",
    )
    specs = (
        ("Scales", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3, -1050, -300),
        ("CoreWeight", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, -140),
        ("SmallWeight", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 20),
        ("LargeWeight", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 180),
        ("DetailStrength", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 340),
        ("EdgeStrength", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 500),
        ("BlackPoint", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 660),
        ("DensityGain", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 820),
        ("Contrast", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 980),
    )
    nodes = {}
    for index, (name, input_type, x, y) in enumerate(specs):
        nodes[name] = add_input(function, name, input_type, index, x, y)
    custom = make_custom(
        function,
        "SSPR M3 Density Shape",
        unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        [name for name, _, _, _ in specs],
        r"""
float3 positiveScales = max(Scales, 0.0f);
float3 weights = max(float3(CoreWeight, SmallWeight, LargeWeight), 0.0f);
float density = dot(positiveScales, weights);
float fineDetail = positiveScales.x - positiveScales.y;
float broadEdge = positiveScales.y - positiveScales.z;
density += fineDetail * max(DetailStrength, 0.0f);
density += broadEdge * max(EdgeStrength, 0.0f);
density = max(density - max(BlackPoint, 0.0f), 0.0f);
density *= max(DensityGain, 0.0f);
float safeContrast = max(Contrast, 0.01f);
return pow(max(density, 1.0e-6f), safeContrast);
""",
        -330,
        80,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Density", 0, 350, 80)
    connect(custom, "", output, output_input_name(output))
    return finish_function(function, SHAPE_PATH, created)


def build_resolve():
    function, created = create_or_reset_function(
        "MF_SSPR_SmokeResolve",
        RESOLVE_PATH,
        "SSPR M3: Beer-Lambert smoke color and opacity resolve.",
    )
    specs = (
        ("Density", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, -260),
        ("SmokeColor", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3, -1050, -80),
        ("Extinction", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 100),
        ("OpacityScale", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, -1050, 280),
        (
            "EmissiveStrength",
            unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
            -1050,
            460,
        ),
    )
    nodes = {}
    for index, (name, input_type, x, y) in enumerate(specs):
        nodes[name] = add_input(function, name, input_type, index, x, y)
    custom = make_custom(
        function,
        "SSPR M3 Smoke Resolve",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        [name for name, _, _, _ in specs],
        r"""
float safeDensity = max(Density, 0.0f);
float alpha = 1.0f - exp(-max(Extinction, 0.0f) * safeDensity);
alpha = saturate(alpha * max(OpacityScale, 0.0f));
float3 color = max(SmokeColor, 0.0f) * alpha * max(EmissiveStrength, 0.0f);
return float4(color, alpha);
""",
        -330,
        60,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)

    rgb = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionComponentMask, 20, -30
    )
    rgb.set_editor_property("r", True)
    rgb.set_editor_property("g", True)
    rgb.set_editor_property("b", True)
    rgb.set_editor_property("a", False)
    alpha = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionComponentMask, 20, 180
    )
    alpha.set_editor_property("r", False)
    alpha.set_editor_property("g", False)
    alpha.set_editor_property("b", False)
    alpha.set_editor_property("a", True)
    rgb_inputs = [
        str(value)
        for value in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            rgb
        )
    ]
    alpha_inputs = [
        str(value)
        for value in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            alpha
        )
    ]
    if not rgb_inputs or not alpha_inputs:
        raise RuntimeError("Resolve component masks expose no input")
    connect(custom, "", rgb, rgb_inputs[0])
    connect(custom, "", alpha, alpha_inputs[0])

    color_output = add_output(function, "Color", 0, 430, -30)
    opacity_output = add_output(function, "Opacity", 1, 430, 180)
    connect(rgb, "", color_output, output_input_name(color_output))
    connect(alpha, "", opacity_output, output_input_name(opacity_output))
    return finish_function(function, RESOLVE_PATH, created)


def create_function_call(material_path, function_path, x, y):
    lib = unreal.MaterialEditingLibrary
    material = unreal.load_asset(material_path)
    before = {
        expression.get_path_name()
        for expression in lib.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        material_path, function_path, x, y
    )
    if not str(info.id):
        raise RuntimeError("Failed function call " + function_path)
    candidates = [
        expression
        for expression in lib.get_material_expressions(material)
        if expression.get_path_name() not in before
        and isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
    ]
    if len(candidates) != 1:
        raise RuntimeError("Could not identify function call " + function_path)
    return candidates[0]


def scalar(material, name, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    return node


def validate_chain():
    lib = unreal.MaterialEditingLibrary
    if unreal.EditorAssetLibrary.does_asset_exist(PROBE_PATH):
        unreal.EditorAssetLibrary.delete_asset(PROBE_PATH)
    probe = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_M3_FunctionChain_Probe",
        FUNCTION_FOLDER,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(probe, unreal.Material):
        raise RuntimeError("Failed to create M3 function-chain probe")
    try:
        probe.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
        probe.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        try:
            probe.set_editor_property(
                "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
            )
        except Exception:
            pass

        default_texture = unreal.load_asset("/Engine/EngineResources/Black.Black")
        texture = lib.create_material_expression(
            probe, unreal.MaterialExpressionTextureObjectParameter, -1700, -500
        )
        texture.set_editor_property("parameter_name", "TrajectoryTexture")
        texture.set_editor_property("texture", default_texture)
        screen = lib.create_material_expression(
            probe, unreal.MaterialExpressionScreenPosition, -1700, -320
        )
        texel = lib.create_material_expression(
            probe, unreal.MaterialExpressionVectorParameter, -1700, -140
        )
        texel.set_editor_property("parameter_name", "SSPR_InvTextureSize")
        texel.set_editor_property(
            "default_value",
            unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
        )

        values = {
            "SmallRadiusPx": scalar(probe, "SmallRadiusPx", 3.0, -1700, 40),
            "LargeRadiusPx": scalar(probe, "LargeRadiusPx", 6.0, -1700, 180),
            "CoreWeight": scalar(probe, "CoreWeight", 0.55, -1050, 250),
            "SmallWeight": scalar(probe, "SmallWeight", 0.30, -1050, 380),
            "LargeWeight": scalar(probe, "LargeWeight", 0.15, -1050, 510),
            "DetailStrength": scalar(
                probe, "DetailStrength", 0.65, -1050, 640
            ),
            "EdgeStrength": scalar(probe, "EdgeStrength", 0.35, -1050, 770),
            "BlackPoint": scalar(probe, "BlackPoint", 0.002, -1050, 900),
            "DensityGain": scalar(probe, "DensityGain", 1.25, -1050, 1030),
            "Contrast": scalar(probe, "Contrast", 0.85, -1050, 1160),
            "Extinction": scalar(probe, "Extinction", 3.2, -420, 420),
            "OpacityScale": scalar(probe, "OpacityScale", 0.9, -420, 550),
            "EmissiveStrength": scalar(
                probe, "EmissiveStrength", 1.0, -420, 680
            ),
        }
        color = lib.create_material_expression(
            probe, unreal.MaterialExpressionVectorParameter, -420, 260
        )
        color.set_editor_property("parameter_name", "SmokeColor")
        color.set_editor_property(
            "default_value", unreal.LinearColor(0.78, 0.84, 0.92, 1.0)
        )

        multiscale = create_function_call(PROBE_PATH, MULTISCALE_PATH, -1050, -220)
        shape = create_function_call(PROBE_PATH, SHAPE_PATH, -420, -80)
        resolve = create_function_call(PROBE_PATH, RESOLVE_PATH, 260, 80)

        connect(texture, "", multiscale, "SourceTexture")
        connect(screen, "ViewportUV", multiscale, "UV")
        connect(texel, "", multiscale, "TexelSize")
        connect(values["SmallRadiusPx"], "", multiscale, "SmallRadiusPx")
        connect(values["LargeRadiusPx"], "", multiscale, "LargeRadiusPx")

        connect(multiscale, "Scales", shape, "Scales")
        for name in (
            "CoreWeight",
            "SmallWeight",
            "LargeWeight",
            "DetailStrength",
            "EdgeStrength",
            "BlackPoint",
            "DensityGain",
            "Contrast",
        ):
            connect(values[name], "", shape, name)

        connect(shape, "Density", resolve, "Density")
        connect(color, "", resolve, "SmokeColor")
        for name in ("Extinction", "OpacityScale", "EmissiveStrength"):
            connect(values[name], "", resolve, name)

        if not lib.connect_material_property(
            resolve, "Color", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        ):
            raise RuntimeError("Failed probe emissive connection")
        if not lib.connect_material_property(
            resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
        ):
            raise RuntimeError("Failed probe opacity connection")

        lib.layout_material_expressions(probe)
        lib.recompile_material(probe)
        saved = bool(unreal.EditorAssetLibrary.save_asset(PROBE_PATH, False))
        diagnostics = unreal.MaterialNodeService.get_material_diagnostics(PROBE_PATH)
        result = {
            "saved": saved,
            "compiled": bool(diagnostics.is_compiled_ok),
            "compileErrors": [str(item) for item in diagnostics.compile_errors],
            "expressionCount": len(lib.get_material_expressions(probe)),
            "functionInputs": {
                "multiscale": [
                    str(value)
                    for value in lib.get_material_expression_input_names(multiscale)
                ],
                "shape": [
                    str(value)
                    for value in lib.get_material_expression_input_names(shape)
                ],
                "resolve": [
                    str(value)
                    for value in lib.get_material_expression_input_names(resolve)
                ],
            },
        }
        if not saved or not result["compiled"] or result["compileErrors"]:
            raise RuntimeError("M3 function-chain probe failed: " + repr(result))
        return result
    finally:
        if unreal.EditorAssetLibrary.does_asset_exist(PROBE_PATH):
            unreal.EditorAssetLibrary.delete_asset(PROBE_PATH)


def main():
    unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
    result = {
        "raw": build_raw(),
        "multiScale": build_multiscale(),
        "densityShape": build_shape(),
        "smokeResolve": build_resolve(),
    }
    result["probe"] = validate_chain()
    print("M3_PROCESSING_FUNCTIONS=" + json.dumps(result, sort_keys=True))


main()
