import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
FUNCTION_FOLDER = ROOT + "/Functions/AnisotropicSplat"
RAW_PATH = FUNCTION_FOLDER + "/MF_SSPR_RawAnisotropicDensity"
BODY_PATH = FUNCTION_FOLDER + "/MF_SSPR_MipBodyDensity"
BLEND_PATH = FUNCTION_FOLDER + "/MF_SSPR_FilamentBodyBlend"


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


def finish(function, asset_path, created):
    lib = unreal.MaterialEditingLibrary
    lib.layout_material_function_expressions(function)
    lib.update_material_function(function)
    saved = bool(unreal.EditorAssetLibrary.save_asset(asset_path, False))
    if not saved:
        raise RuntimeError("Failed to save " + asset_path)
    return {
        "path": function.get_path_name(),
        "created": created,
        "expressions": len(lib.get_material_function_expressions(function)),
    }


def build_raw_density():
    function, created = create_or_reset_function(
        "MF_SSPR_RawAnisotropicDensity",
        RAW_PATH,
        "V2: sample the unblurred anisotropic atomic density field.",
    )
    specs = (
        ("SourceTexture", unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("TexelSize", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("InputGain", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_input(
            function, name, input_type, index, -1000, -250 + index * 150
        )
    custom = make_custom(
        function,
        "Raw anisotropic density",
        unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        [name for name, _ in specs],
        r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 safeUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float density = Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, safeUV, 0.0f).r;
return max(density, 0.0f) * max(InputGain, 0.0f);
""",
        -280,
        0,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Density", 0, 360, 0)
    connect(custom, "", output, output_input_name(output))
    return finish(function, RAW_PATH, created)


def build_mip_body():
    function, created = create_or_reset_function(
        "MF_SSPR_MipBodyDensity",
        BODY_PATH,
        "V2: reconstruct medium connected density and broad smoke body from mips.",
    )
    specs = (
        ("SourceTexture", unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("TexelSize", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("MediumRadiusPx", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("BodyRadiusPx", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("MediumMipBias", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("BodyMipBias", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_input(
            function, name, input_type, index, -1120, -430 + index * 145
        )
    custom = make_custom(
        function,
        "Mip medium and body reconstruction",
        unreal.CustomMaterialOutputType.CMOT_FLOAT2,
        [name for name, _ in specs],
        r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float mediumRadius = max(MediumRadiusPx, 1.0f);
float bodyRadius = max(BodyRadiusPx, mediumRadius);
float mediumMip = clamp(
    log2(mediumRadius) - 1.0f + MediumMipBias, 0.0f, 10.0f);
float bodyMip = clamp(
    log2(bodyRadius) - 1.0f + BodyMipBias, 0.0f, 10.0f);

float w3[3] = {1.0f, 2.0f, 1.0f};
float mediumSum = 0.0f;
float mediumWeight = 0.0f;
float2 mediumStep = safeTexel * max(mediumRadius * 0.55f, 1.0f);
[unroll]
for (int y = 0; y < 3; ++y)
{
    [unroll]
    for (int x = 0; x < 3; ++x)
    {
        float2 tapUV = centerUV + float2(x - 1, y - 1) * mediumStep;
        float valid = step(halfTexel.x, tapUV.x)
            * step(tapUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, tapUV.y)
            * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w3[x] * w3[y] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), mediumMip).r;
        mediumSum += max(value, 0.0f) * weight;
        mediumWeight += weight;
    }
}
float medium = mediumSum / max(mediumWeight, 1.0e-5f);

float w5[5] = {1.0f, 4.0f, 6.0f, 4.0f, 1.0f};
float bodySum = 0.0f;
float bodyWeight = 0.0f;
float2 bodyStep = safeTexel * max(bodyRadius * 0.42f, 1.0f);
[unroll]
for (int y = 0; y < 5; ++y)
{
    [unroll]
    for (int x = 0; x < 5; ++x)
    {
        float2 tapUV = centerUV + float2(x - 2, y - 2) * bodyStep;
        float valid = step(halfTexel.x, tapUV.x)
            * step(tapUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, tapUV.y)
            * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w5[x] * w5[y] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), bodyMip).r;
        bodySum += max(value, 0.0f) * weight;
        bodyWeight += weight;
    }
}
float body = bodySum / max(bodyWeight, 1.0e-5f);
return float2(medium, body);
""",
        -300,
        50,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "BodyScales", 0, 390, 50)
    connect(custom, "", output, output_input_name(output))
    return finish(function, BODY_PATH, created)


def build_filament_body_blend():
    function, created = create_or_reset_function(
        "MF_SSPR_FilamentBodyBlend",
        BLEND_PATH,
        "V2: preserve anisotropic filaments while exposing medium and body layers.",
    )
    specs = (
        ("RawDensity", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("BodyScales", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("RidgeStrength", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_input(
            function, name, input_type, index, -940, -160 + index * 180
        )
    custom = make_custom(
        function,
        "Filament, medium and body layers",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
        [name for name, _ in specs],
        r"""
float raw = max(RawDensity, 0.0f);
float medium = max(BodyScales.x, 0.0f);
float body = max(BodyScales.y, 0.0f);
float fineRidge = max(raw - medium, 0.0f);
float filament = raw + fineRidge * max(RidgeStrength, 0.0f);
return float3(filament, medium, body);
""",
        -220,
        30,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Layers", 0, 390, 30)
    connect(custom, "", output, output_input_name(output))
    return finish(function, BLEND_PATH, created)


def main():
    unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
    result = {
        "raw": build_raw_density(),
        "mipBody": build_mip_body(),
        "blend": build_filament_body_blend(),
    }
    print("V2_ANISOTROPIC_FUNCTIONS=" + json.dumps(result, sort_keys=True))


main()
