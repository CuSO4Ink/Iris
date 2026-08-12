import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
FUNCTION_FOLDER = ROOT + "/Functions/M3_HQFluidV2"
PYRAMID_PATH = FUNCTION_FOLDER + "/MF_SSPR_MipPyramidDensity"
LIGHTING_PATH = FUNCTION_FOLDER + "/MF_SSPR_DensityGradientLighting"


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {} -> {}".format(source_output, target_input)
        )


def create_clean_function(asset_name, asset_path, description):
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        raise RuntimeError(
            "Refusing to rebuild published V2 function in place: " + asset_path
        )
    function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        FUNCTION_FOLDER,
        unreal.MaterialFunction,
        unreal.MaterialFunctionFactoryNew(),
    )
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Failed to create material function " + asset_path)
    function.set_editor_property("description", description)
    function.set_editor_property("expose_to_library", True)
    return function


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


def finish(function, asset_path):
    lib = unreal.MaterialEditingLibrary
    lib.layout_material_function_expressions(function)
    lib.update_material_function(function)
    if not unreal.EditorAssetLibrary.save_asset(asset_path, False):
        raise RuntimeError("Failed to save " + asset_path)
    return {
        "path": function.get_path_name(),
        "expressions": len(lib.get_material_function_expressions(function)),
    }


def build_pyramid_density():
    function = create_clean_function(
        "MF_SSPR_MipPyramidDensity",
        PYRAMID_PATH,
        "SSPR M3 V2: reconstruct core, filament and body density from the Niagara SimRT mip pyramid.",
    )
    specs = (
        ("SourceTexture", unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("TexelSize", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("SmallRadiusPx", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("LargeRadiusPx", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("SmallMipBias", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("LargeMipBias", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_input(
            function, name, input_type, index, -1120, -420 + index * 150
        )

    custom = make_custom(
        function,
        "SSPR M3 V2 Mip Pyramid Density",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
        [name for name, _ in specs],
        r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float core = max(Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, centerUV, 0.0f).r, 0.0f);

float smallRadius = max(SmallRadiusPx, 1.0f);
float largeRadius = max(LargeRadiusPx, smallRadius);
float smallMip = clamp(log2(smallRadius) - 1.0f + SmallMipBias, 0.0f, 10.0f);
float largeMip = clamp(log2(largeRadius) - 1.0f + LargeMipBias, 0.0f, 10.0f);

float w3[3] = {1.0f, 2.0f, 1.0f};
float smallSum = 0.0f;
float smallWeight = 0.0f;
float2 smallStep = safeTexel * max(smallRadius * 0.55f, 1.0f);
[unroll]
for (int sy = 0; sy < 3; ++sy)
{
    [unroll]
    for (int sx = 0; sx < 3; ++sx)
    {
        float2 tapUV = centerUV + float2(sx - 1, sy - 1) * smallStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w3[sx] * w3[sy] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), smallMip).r;
        smallSum += max(value, 0.0f) * weight;
        smallWeight += weight;
    }
}
float small = smallSum / max(smallWeight, 1.0e-5f);

float w5[5] = {1.0f, 4.0f, 6.0f, 4.0f, 1.0f};
float largeSum = 0.0f;
float largeWeight = 0.0f;
float2 largeStep = safeTexel * max(largeRadius * 0.42f, 1.0f);
[unroll]
for (int ly = 0; ly < 5; ++ly)
{
    [unroll]
    for (int lx = 0; lx < 5; ++lx)
    {
        float2 tapUV = centerUV + float2(lx - 2, ly - 2) * largeStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w5[lx] * w5[ly] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), largeMip).r;
        largeSum += max(value, 0.0f) * weight;
        largeWeight += weight;
    }
}
float large = largeSum / max(largeWeight, 1.0e-5f);
return float3(core, small, large);
""",
        -330,
        60,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Scales", 0, 360, 60)
    connect(custom, "", output, output_input_name(output))
    return finish(function, PYRAMID_PATH)


def build_gradient_lighting():
    function = create_clean_function(
        "MF_SSPR_DensityGradientLighting",
        LIGHTING_PATH,
        "SSPR M3 V2: low-frequency density-gradient lighting for soft smoke volume cues.",
    )
    specs = (
        ("SourceTexture", unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D),
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("TexelSize", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("LightingMipLevel", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("GradientRadius", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("GradientStrength", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("LightDirection", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("Ambient", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
        ("LightStrength", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_input(
            function, name, input_type, index, -1120, -560 + index * 135
        )

    custom = make_custom(
        function,
        "SSPR M3 V2 Density Gradient Lighting",
        unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        [name for name, _ in specs],
        r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float lod = clamp(LightingMipLevel, 0.0f, 10.0f);
float2 stepUV = safeTexel * exp2(lod) * max(GradientRadius, 0.5f);

float left = Texture2DSampleLevel(SourceTexture, SourceTextureSampler,
    clamp(centerUV - float2(stepUV.x, 0.0f), halfTexel, 1.0f - halfTexel), lod).r;
float right = Texture2DSampleLevel(SourceTexture, SourceTextureSampler,
    clamp(centerUV + float2(stepUV.x, 0.0f), halfTexel, 1.0f - halfTexel), lod).r;
float down = Texture2DSampleLevel(SourceTexture, SourceTextureSampler,
    clamp(centerUV - float2(0.0f, stepUV.y), halfTexel, 1.0f - halfTexel), lod).r;
float up = Texture2DSampleLevel(SourceTexture, SourceTextureSampler,
    clamp(centerUV + float2(0.0f, stepUV.y), halfTexel, 1.0f - halfTexel), lod).r;

float2 gradient = float2(right - left, up - down) * max(GradientStrength, 0.0f);
float3 normal = normalize(float3(-gradient.x, -gradient.y, 1.0f));
float2 safeDirection = LightDirection;
safeDirection /= max(length(safeDirection), 1.0e-5f);
float3 lightVector = normalize(float3(safeDirection, 0.75f));
float diffuse = saturate(dot(normal, lightVector));
return max(Ambient, 0.0f) + diffuse * max(LightStrength, 0.0f);
""",
        -330,
        60,
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_output(function, "Lighting", 0, 360, 60)
    connect(custom, "", output, output_input_name(output))
    return finish(function, LIGHTING_PATH)


def main():
    unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
    result = {
        "pyramidDensity": build_pyramid_density(),
        "gradientLighting": build_gradient_lighting(),
    }
    print("M3_HQ_FLUID_V2_FUNCTIONS=" + json.dumps(result, sort_keys=True))


main()
