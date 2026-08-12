import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
FUNCTION_FOLDER = ROOT + "/Functions/G5"
STREAMLINE_PATH = FUNCTION_FOLDER + "/MF_SSPR_G5_StreamlineDensityV1"
DEPTH_CUE_PATH = FUNCTION_FOLDER + "/MF_SSPR_G5_DepthCueV1"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_G5"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_G5_HQ"
PYRAMID_PATH = (
    ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity"
)
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
RESOLVE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"
EDGE_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_ScreenEdgeMask"
RAW_PATH = (
    ROOT
    + "/Functions/AnisotropicSplat/MF_SSPR_RawAnisotropicDensity"
)


STREAMLINE_CODE = r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float4 centerMain = Texture2DSampleLevel(
    MainTexture, MainTextureSampler, centerUV, 0);
float centerDensity = max(centerMain.r, 0.0f);

// Dilate only the guidance field, not density. This lets pixels in short
// gaps discover a nearby tangent without turning the source into a wide blur.
float directionSearch = max(DirectionSearchPx, 0.0f);
float2 tensorSum = float2(0.0f, 0.0f);
float depthSum = 0.0f;
float sigmaSum = 0.0f;
float guidanceWeight = 0.0f;
[unroll]
for (int gy = -1; gy <= 1; ++gy)
{
    [unroll]
    for (int gx = -1; gx <= 1; ++gx)
    {
        float2 guideUV = centerUV
            + float2(gx, gy) * safeTexel * directionSearch;
        float valid =
            step(halfTexel.x, guideUV.x)
            * step(guideUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, guideUV.y)
            * step(guideUV.y, 1.0f - halfTexel.y);
        float2 clampedGuideUV = clamp(
            guideUV, halfTexel, 1.0f - halfTexel);
        float4 guideMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, clampedGuideUV, 0);
        float4 guideAux = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, clampedGuideUV, 0);
        float spatialWeight = (gx == 0 && gy == 0) ? 2.0f : 1.0f;
        float weight = max(guideMain.r, 0.0f)
            * spatialWeight * valid;
        tensorSum += guideMain.gb * weight;
        depthSum += guideMain.a * weight;
        sigmaSum += guideAux.r * weight;
        guidanceWeight += weight;
    }
}

float safeGuidanceWeight = max(guidanceWeight, 1.0e-6f);
float2 seedTensor = tensorSum / safeGuidanceWeight;
float seedMeanDepth = depthSum / safeGuidanceWeight;
float seedSigma = sigmaSum / safeGuidanceWeight;
float seedCoherence = saturate(length(seedTensor));
float seedAngle = 0.5f * atan2(seedTensor.y, seedTensor.x);
float2 seedDirection = seedCoherence > 1.0e-5f
    ? float2(cos(seedAngle), sin(seedAngle))
    : float2(1.0f, 0.0f);

float activeSteps = clamp(floor(ActiveSteps + 0.5f), 1.0f, 8.0f);
float2 stepUV = safeTexel * max(StepPx, 0.5f);
float coherenceFloor = saturate(CoherenceMin);
float curvatureFloor = saturate(CurvatureMinDot);
float depthFalloff = max(DepthFalloff, 0.0f);
float sigmaScale = max(DepthSigmaScale, 0.0f);
float taperPower = max(TaperPower, 0.1f);

float forwardSupport = 0.0f;
float backwardSupport = 0.0f;
const int MaxSteps = 8;
[unroll]
for (int branch = 0; branch < 2; ++branch)
{
    float branchSign = branch == 0 ? 1.0f : -1.0f;
    float2 traceUV = centerUV;
    float2 previousDirection = seedDirection * branchSign;
    float alive = seedCoherence > 1.0e-5f ? 1.0f : 0.0f;
    float branchMaximum = 0.0f;
    float branchSum = 0.0f;
    float branchWeight = 0.0f;

    [unroll]
    for (int stepIndex = 0; stepIndex < MaxSteps; ++stepIndex)
    {
        float enabled = (float)stepIndex < activeSteps ? 1.0f : 0.0f;

        float4 localMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, traceUV, 0);
        float2 localTensor = localMain.gb;
        float localCoherence = saturate(length(localTensor));
        float2 localDirection = previousDirection;
        if (localCoherence > 1.0e-5f)
        {
            float localAngle = 0.5f * atan2(
                localTensor.y, localTensor.x);
            localDirection = float2(cos(localAngle), sin(localAngle));
            if (dot(localDirection, previousDirection) < 0.0f)
            {
                localDirection *= -1.0f;
            }
        }

        float2 midpointUV = traceUV + localDirection * stepUV * 0.5f;
        float midpointValid =
            step(halfTexel.x, midpointUV.x)
            * step(midpointUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, midpointUV.y)
            * step(midpointUV.y, 1.0f - halfTexel.y);
        midpointUV = clamp(
            midpointUV, halfTexel, 1.0f - halfTexel);
        float4 midpointMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, midpointUV, 0);
        float2 midpointTensor = midpointMain.gb;
        float midpointCoherence = saturate(length(midpointTensor));
        float2 midpointDirection = localDirection;
        if (midpointCoherence > 1.0e-5f)
        {
            float midpointAngle = 0.5f * atan2(
                midpointTensor.y, midpointTensor.x);
            midpointDirection = float2(
                cos(midpointAngle), sin(midpointAngle));
            if (dot(midpointDirection, localDirection) < 0.0f)
            {
                midpointDirection *= -1.0f;
            }
        }

        float2 nextUV = traceUV + midpointDirection * stepUV;
        float nextValid =
            step(halfTexel.x, nextUV.x)
            * step(nextUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, nextUV.y)
            * step(nextUV.y, 1.0f - halfTexel.y);
        float2 clampedNextUV = clamp(
            nextUV, halfTexel, 1.0f - halfTexel);
        float4 nextMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, clampedNextUV, 0);
        float4 nextAux = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, clampedNextUV, 0);
        float nextDensity = max(nextMain.r, 0.0f);
        float nextCoherence = saturate(length(nextMain.gb));

        float coherenceWeight = lerp(
            0.35f,
            1.0f,
            smoothstep(
                coherenceFloor,
                min(coherenceFloor + 0.25f, 1.0f),
                nextCoherence));
        float depthDifference = abs(nextMain.a - seedMeanDepth);
        float depthRelaxation = 1.0f
            + (seedSigma + max(nextAux.r, 0.0f)) * sigmaScale;
        float depthWeight = exp(
            -depthDifference * depthFalloff
            / max(depthRelaxation, 1.0e-4f));
        float curvature = saturate(
            dot(previousDirection, midpointDirection));
        float curvatureWeight = smoothstep(
            curvatureFloor, 1.0f, curvature);
        float taper = pow(
            saturate(
                1.0f
                - ((float)stepIndex + 0.35f)
                / (activeSteps + 0.65f)),
            taperPower);

        alive *= enabled * midpointValid * nextValid;
        float sampleWeight = alive * coherenceWeight
            * depthWeight * curvatureWeight * taper;
        branchMaximum = max(
            branchMaximum, nextDensity * sampleWeight);
        branchSum += nextDensity * sampleWeight;
        branchWeight += sampleWeight;

        traceUV = clampedNextUV;
        previousDirection = midpointDirection;
    }

    float branchAverage = branchSum / max(branchWeight, 1.0e-5f);
    float branchSupport = max(
        branchMaximum, branchAverage * 0.70f);
    if (branch == 0)
    {
        forwardSupport = branchSupport;
    }
    else
    {
        backwardSupport = branchSupport;
    }
}

float oneSidedSupport = max(forwardSupport, backwardSupport);
float twoSidedSupport = sqrt(max(
    forwardSupport * backwardSupport, 0.0f));
float connectedSupport = lerp(
    oneSidedSupport,
    twoSidedSupport,
    saturate(TwoSidedness));
float isolatedCore = centerDensity
    * saturate(IsolatedCoreScale)
    * lerp(0.35f, 1.0f, seedCoherence);
float filament = max(isolatedCore, connectedSupport);
return filament * max(FilamentGain, 0.0f);
""".strip()


DEPTH_CUE_CODE = r"""
float2 safeUV = saturate(UV);
float4 mainField = Texture2DSampleLevel(
    MainTexture, MainTextureSampler, safeUV, 0);
float4 auxField = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, safeUV, 0);
float coverage = saturate(auxField.a);
float scaledDepth = saturate(
    max(mainField.a, 0.0f) * max(DepthRangeScale, 0.0f));
float nearFar = (0.5f - scaledDepth) * 2.0f;
float thickness = 1.0f - exp(
    -max(auxField.r, 0.0f) * max(SigmaScale, 0.0f));
float frontSeparation = saturate(
    max(mainField.a - auxField.g, 0.0f)
    * max(DepthRangeScale, 0.0f));
float cue = 1.0f
    + nearFar * DepthContrast
    - thickness * ThicknessShadow
    - frontSeparation * LayerShadow;
cue = clamp(cue, 0.65f, 1.20f);
return lerp(
    1.0f,
    lerp(1.0f, cue, coverage),
    saturate(CueStrength));
""".strip()


SCALAR_DEFAULTS = {
    "G5_StreamlineStepPx": 3.0,
    "G5_StreamlineSteps": 6.0,
    "G5_DirectionSearchPx": 2.0,
    "G5_CoherenceMin": 0.15,
    "G5_DepthFalloff": 70.0,
    "G5_DepthSigmaScale": 32.0,
    "G5_CurvatureMinDot": 0.45,
    "G5_TaperPower": 1.35,
    "G5_TwoSidedness": 0.35,
    "G5_IsolatedCoreScale": 0.12,
    "G5_FilamentGain": 1.10,
    "AS_MediumRadiusPx": 12.0,
    "AS_BodyRadiusPx": 40.0,
    "AS_MediumMipBias": -0.15,
    "AS_BodyMipBias": 0.35,
    "AS_FilamentWeight": 0.25,
    "AS_MediumWeight": 0.50,
    "AS_BodyWeight": 0.25,
    "AS_DetailStrength": 0.06,
    "AS_EdgeStrength": 0.02,
    "AS_BlackPoint": 0.002,
    "AS_DensityGain": 1.25,
    "AS_Contrast": 0.90,
    "AS_EdgeFadeWidthPx": 20.0,
    "AS_Extinction": 1.80,
    "AS_OpacityScale": 0.82,
    "AS_EmissiveStrength": 1.0,
    "G5_DepthRangeScale": 10.0,
    "G5_DepthContrast": 0.12,
    "G5_SigmaScale": 32.0,
    "G5_ThicknessShadow": 0.12,
    "G5_LayerShadow": 0.10,
    "G5_DepthCueStrength": 0.65,
    "G5_DebugRaw": 0.0,
    "G5_DebugStreamline": 0.0,
}


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {}.{} -> {}.{}".format(
                source.get_name(),
                source_output,
                target.get_name(),
                target_input,
            )
        )


def add_function_input(function, name, input_type, priority, x, y):
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


def add_function_output(function, name, priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionOutput, x, y
    )
    node.set_editor_property("output_name", name)
    node.set_editor_property("sort_priority", priority)
    return node


def create_clean_function(asset_name, path, description, specs, code):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError("Refusing to rebuild clean function: " + path)
    function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        FUNCTION_FOLDER,
        unreal.MaterialFunction,
        unreal.MaterialFunctionFactoryNew(),
    )
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Failed to create " + path)
    function.set_editor_property("description", description)
    function.set_editor_property("expose_to_library", True)
    nodes = {}
    for index, (name, input_type) in enumerate(specs):
        nodes[name] = add_function_input(
            function,
            name,
            input_type,
            index,
            -1250,
            -650 + index * 125,
        )
    custom = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionCustom, -430, 20
    )
    custom.set_editor_property("description", description)
    custom.set_editor_property("code", code)
    custom.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1
    )
    custom_inputs = []
    for name, _ in specs:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)
    for name in nodes:
        connect(nodes[name], "", custom, name)
    output = add_function_output(function, "Value", 0, 280, 20)
    output_inputs = [
        str(item)
        for item in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            output
        )
    ]
    if not output_inputs:
        raise RuntimeError("Function output exposes no input: " + path)
    connect(custom, "", output, output_inputs[0])
    unreal.MaterialEditingLibrary.layout_material_function_expressions(
        function
    )
    unreal.MaterialEditingLibrary.update_material_function(function)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return function


def scalar(material, name, value, x, y, group):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", float(value))
    try:
        node.set_editor_property("group", group)
    except Exception:
        pass
    return node


def vector(material, name, value, x, y, group):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    try:
        node.set_editor_property("group", group)
    except Exception:
        pass
    return node


def create_function_call(function_path, x, y):
    lib = unreal.MaterialEditingLibrary
    material = unreal.load_asset(MATERIAL_PATH)
    before = {
        expression.get_path_name()
        for expression in lib.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        MATERIAL_PATH, function_path, x, y
    )
    if not str(info.id):
        raise RuntimeError("Failed function call " + function_path)
    candidates = [
        expression
        for expression in lib.get_material_expressions(material)
        if expression.get_path_name() not in before
        and isinstance(
            expression, unreal.MaterialExpressionMaterialFunctionCall
        )
    ]
    if len(candidates) != 1:
        raise RuntimeError("Could not identify function call " + function_path)
    return candidates[0]


def build_functions():
    texture = unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D
    vector2 = unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2
    scalar_type = unreal.FunctionInputType.FUNCTION_INPUT_SCALAR
    streamline_specs = (
        ("MainTexture", texture),
        ("AuxTexture", texture),
        ("UV", vector2),
        ("TexelSize", vector2),
        ("StepPx", scalar_type),
        ("ActiveSteps", scalar_type),
        ("DirectionSearchPx", scalar_type),
        ("CoherenceMin", scalar_type),
        ("DepthFalloff", scalar_type),
        ("DepthSigmaScale", scalar_type),
        ("CurvatureMinDot", scalar_type),
        ("TaperPower", scalar_type),
        ("TwoSidedness", scalar_type),
        ("IsolatedCoreScale", scalar_type),
        ("FilamentGain", scalar_type),
    )
    depth_specs = (
        ("MainTexture", texture),
        ("AuxTexture", texture),
        ("UV", vector2),
        ("DepthRangeScale", scalar_type),
        ("DepthContrast", scalar_type),
        ("SigmaScale", scalar_type),
        ("ThicknessShadow", scalar_type),
        ("LayerShadow", scalar_type),
        ("CueStrength", scalar_type),
    )
    streamline = create_clean_function(
        "MF_SSPR_G5_StreamlineDensityV1",
        STREAMLINE_PATH,
        "G5 current-frame bidirectional RK2 streamline filament density.",
        streamline_specs,
        STREAMLINE_CODE,
    )
    depth_cue = create_clean_function(
        "MF_SSPR_G5_DepthCueV1",
        DEPTH_CUE_PATH,
        "G5 current-frame mean/front depth and thickness cue.",
        depth_specs,
        DEPTH_CUE_CODE,
    )
    return streamline, depth_cue


def build_material():
    required = (
        STREAMLINE_PATH,
        DEPTH_CUE_PATH,
        PYRAMID_PATH,
        SHAPE_PATH,
        RESOLVE_PATH,
        EDGE_PATH,
        RAW_PATH,
    )
    for path in required:
        if not isinstance(unreal.load_asset(path), unreal.MaterialFunction):
            raise RuntimeError("Missing required function: " + path)
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        raise RuntimeError("Refusing to rebuild clean material")
    if unreal.EditorAssetLibrary.does_asset_exist(INSTANCE_PATH):
        raise RuntimeError("Refusing to rebuild clean material instance")

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_AnisotropicSplat_G5",
        ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Failed to create G5 production material")
    material.set_editor_property(
        "material_domain", unreal.MaterialDomain.MD_SURFACE
    )
    material.set_editor_property(
        "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT
    )
    try:
        material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )
    except Exception:
        pass
    material.set_editor_property("two_sided", True)
    material.set_editor_property("disable_depth_test", True)

    lib = unreal.MaterialEditingLibrary
    black = unreal.load_asset("/Engine/EngineResources/Black.Black")
    main_texture = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -3300,
        -850,
    )
    main_texture.set_editor_property("parameter_name", "TrajectoryTexture")
    main_texture.set_editor_property("texture", black)
    aux_texture = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -3300,
        -680,
    )
    aux_texture.set_editor_property(
        "parameter_name", "TrajectoryAuxTexture"
    )
    aux_texture.set_editor_property("texture", black)
    screen = lib.create_material_expression(
        material, unreal.MaterialExpressionScreenPosition, -3300, -500
    )
    texel = vector(
        material,
        "SSPR_InvTextureSize",
        unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
        -3300,
        -320,
        "00 Niagara Input",
    )

    groups = {}
    for name in SCALAR_DEFAULTS:
        if name.startswith("G5_Streamline") or name in (
            "G5_DirectionSearchPx",
            "G5_CoherenceMin",
            "G5_DepthFalloff",
            "G5_DepthSigmaScale",
            "G5_CurvatureMinDot",
            "G5_TaperPower",
            "G5_TwoSidedness",
            "G5_IsolatedCoreScale",
            "G5_FilamentGain",
        ):
            groups[name] = "10 Streamline"
        elif name.startswith("AS_Medium") or name.startswith("AS_Body"):
            groups[name] = "20 Body Reconstruction"
        elif name.startswith("AS_Filament") or name in (
            "AS_DetailStrength",
            "AS_EdgeStrength",
            "AS_BlackPoint",
            "AS_DensityGain",
            "AS_Contrast",
        ):
            groups[name] = "30 Density Shape"
        elif name.startswith("G5_Depth") or name in (
            "G5_SigmaScale",
            "G5_ThicknessShadow",
            "G5_LayerShadow",
        ):
            groups[name] = "40 Depth Cue"
        elif name.startswith("AS_"):
            groups[name] = "50 Smoke Resolve"
        else:
            groups[name] = "90 Debug"
    params = {}
    for index, (name, value) in enumerate(SCALAR_DEFAULTS.items()):
        params[name] = scalar(
            material,
            name,
            value,
            -3300 + (index // 12) * 520,
            -80 + (index % 12) * 135,
            groups[name],
        )
    smoke_color = vector(
        material,
        "AS_SmokeColor",
        unreal.LinearColor(0.72, 0.77, 0.84, 1.0),
        700,
        160,
        "50 Smoke Resolve",
    )

    streamline = create_function_call(STREAMLINE_PATH, -1900, -700)
    raw = create_function_call(RAW_PATH, -1900, -420)
    pyramid = create_function_call(PYRAMID_PATH, -1900, -100)
    depth_cue = create_function_call(DEPTH_CUE_PATH, -900, 850)
    compose = lib.create_material_expression(
        material, unreal.MaterialExpressionCustom, -900, -220
    )
    compose.set_editor_property(
        "description", "G5 filament plus multiscale body layers"
    )
    compose.set_editor_property(
        "code",
        "return float3(max(Filament, 0.0f), "
        "max(BodyScales.y, 0.0f), max(BodyScales.z, 0.0f));",
    )
    compose.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3
    )
    compose_inputs = []
    for name in ("Filament", "BodyScales"):
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        compose_inputs.append(item)
    compose.set_editor_property("inputs", compose_inputs)
    shape = create_function_call(SHAPE_PATH, -250, -240)
    debug_raw = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 300, -220
    )
    debug_streamline = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 700, -220
    )
    edge = create_function_call(EDGE_PATH, 300, 820)
    masked_density = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1050, -200
    )
    resolve = create_function_call(RESOLVE_PATH, 1400, -80)
    depth_lit_color = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1950, -80
    )

    for texture_node in (main_texture, aux_texture):
        try:
            texture_node.set_editor_property(
                "sampler_type",
                unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
            )
            texture_node.set_editor_property("group", "00 Niagara Input")
        except Exception:
            pass

    for call in (streamline, raw, pyramid, depth_cue):
        connect(main_texture, "", call, "MainTexture" if call in (
            streamline, depth_cue
        ) else "SourceTexture")
        connect(screen, "ViewportUV", call, "UV")
    connect(aux_texture, "", streamline, "AuxTexture")
    connect(aux_texture, "", depth_cue, "AuxTexture")
    connect(texel, "", streamline, "TexelSize")
    connect(texel, "", raw, "TexelSize")
    connect(texel, "", pyramid, "TexelSize")

    streamline_inputs = (
        ("StepPx", "G5_StreamlineStepPx"),
        ("ActiveSteps", "G5_StreamlineSteps"),
        ("DirectionSearchPx", "G5_DirectionSearchPx"),
        ("CoherenceMin", "G5_CoherenceMin"),
        ("DepthFalloff", "G5_DepthFalloff"),
        ("DepthSigmaScale", "G5_DepthSigmaScale"),
        ("CurvatureMinDot", "G5_CurvatureMinDot"),
        ("TaperPower", "G5_TaperPower"),
        ("TwoSidedness", "G5_TwoSidedness"),
        ("IsolatedCoreScale", "G5_IsolatedCoreScale"),
        ("FilamentGain", "G5_FilamentGain"),
    )
    for input_name, parameter_name in streamline_inputs:
        connect(params[parameter_name], "", streamline, input_name)
    connect(params["G5_FilamentGain"], "", raw, "InputGain")

    for input_name, parameter_name in (
        ("SmallRadiusPx", "AS_MediumRadiusPx"),
        ("LargeRadiusPx", "AS_BodyRadiusPx"),
        ("SmallMipBias", "AS_MediumMipBias"),
        ("LargeMipBias", "AS_BodyMipBias"),
    ):
        connect(params[parameter_name], "", pyramid, input_name)
    connect(streamline, "Value", compose, "Filament")
    connect(pyramid, "Scales", compose, "BodyScales")
    connect(compose, "", shape, "Scales")
    for input_name, parameter_name in (
        ("CoreWeight", "AS_FilamentWeight"),
        ("SmallWeight", "AS_MediumWeight"),
        ("LargeWeight", "AS_BodyWeight"),
        ("DetailStrength", "AS_DetailStrength"),
        ("EdgeStrength", "AS_EdgeStrength"),
        ("BlackPoint", "AS_BlackPoint"),
        ("DensityGain", "AS_DensityGain"),
        ("Contrast", "AS_Contrast"),
    ):
        connect(params[parameter_name], "", shape, input_name)

    connect(shape, "Density", debug_raw, "A")
    connect(raw, "Density", debug_raw, "B")
    connect(params["G5_DebugRaw"], "", debug_raw, "Alpha")
    connect(debug_raw, "", debug_streamline, "A")
    connect(streamline, "Value", debug_streamline, "B")
    connect(
        params["G5_DebugStreamline"],
        "",
        debug_streamline,
        "Alpha",
    )

    connect(screen, "ViewportUV", edge, "UV")
    connect(texel, "", edge, "TexelSize")
    connect(
        params["AS_EdgeFadeWidthPx"], "", edge, "FadeWidthPx"
    )
    connect(debug_streamline, "", masked_density, "A")
    connect(edge, "Mask", masked_density, "B")

    for input_name, parameter_name in (
        ("DepthRangeScale", "G5_DepthRangeScale"),
        ("DepthContrast", "G5_DepthContrast"),
        ("SigmaScale", "G5_SigmaScale"),
        ("ThicknessShadow", "G5_ThicknessShadow"),
        ("LayerShadow", "G5_LayerShadow"),
        ("CueStrength", "G5_DepthCueStrength"),
    ):
        connect(params[parameter_name], "", depth_cue, input_name)

    connect(masked_density, "", resolve, "Density")
    connect(smoke_color, "", resolve, "SmokeColor")
    for input_name, parameter_name in (
        ("Extinction", "AS_Extinction"),
        ("OpacityScale", "AS_OpacityScale"),
        ("EmissiveStrength", "AS_EmissiveStrength"),
    ):
        connect(params[parameter_name], "", resolve, input_name)
    connect(resolve, "Color", depth_lit_color, "A")
    connect(depth_cue, "Value", depth_lit_color, "B")
    if not lib.connect_material_property(
        depth_lit_color,
        "",
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    ):
        raise RuntimeError("Failed G5 emissive connection")
    if not lib.connect_material_property(
        resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed G5 opacity connection")

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
    if not unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False):
        raise RuntimeError("Failed to save G5 production material")
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
        MATERIAL_PATH
    )
    material_result = {
        "compiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [
            str(item) for item in diagnostics.compile_errors
        ],
        "expressions": len(lib.get_material_expressions(material)),
        "saved": True,
    }
    if (
        not material_result["compiled"]
        or material_result["compileErrors"]
    ):
        raise RuntimeError(
            "G5 production material failed: " + repr(material_result)
        )

    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_SSPR_AnisotropicSplat_G5_HQ",
        ROOT,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Failed to create G5 production MI")
    instance.set_editor_property("parent", material)
    for name, value in SCALAR_DEFAULTS.items():
        lib.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
    lib.set_material_instance_vector_parameter_value(
        instance,
        "SSPR_InvTextureSize",
        unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
    )
    lib.set_material_instance_vector_parameter_value(
        instance,
        "AS_SmokeColor",
        unreal.LinearColor(0.72, 0.77, 0.84, 1.0),
    )
    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save G5 production MI")
    return material_result, instance


unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
streamline_function, depth_function = build_functions()
material_result, instance = build_material()
result = {
    "streamlineFunction": streamline_function.get_path_name(),
    "depthCueFunction": depth_function.get_path_name(),
    "material": MATERIAL_PATH,
    "instance": instance.get_path_name(),
    "materialGate": material_result,
    "scalarDefaults": SCALAR_DEFAULTS,
    "historyUsed": False,
    "streamline": {
        "integration": "Bidirectional RK2",
        "maxStepsPerDirection": 8,
        "activeStepsPerDirection": SCALAR_DEFAULTS[
            "G5_StreamlineSteps"
        ],
        "depthBilateral": True,
        "directionRepresentation": "DoubleAngleTensor",
    },
}
print("G5_STREAMLINE_PRODUCTION=" + json.dumps(result, sort_keys=True))
