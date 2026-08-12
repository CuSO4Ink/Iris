import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
FUNCTION_FOLDER = ROOT + "/Functions/G5"
RECON_PATH = (
    FUNCTION_FOLDER + "/MF_SSPR_G5_NormalizedFieldReconstructionV1"
)
LIGHTING_PATH = (
    FUNCTION_FOLDER + "/MF_SSPR_G5_DepthTransportLightingV1"
)
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_FieldRecon_V1"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
RESOLVE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"
EDGE_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_ScreenEdgeMask"
BASE_BUILDER = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_g5_build_streamline_production.py"
)


with open(BASE_BUILDER, "r", encoding="utf-8") as source_file:
    base_source = source_file.read()
main_marker = "unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)"
if main_marker not in base_source:
    raise RuntimeError("Could not isolate reusable material builder helpers")
base_source = base_source.split(main_marker, 1)[0]
scope = {
    "__name__": "g5_normalized_field_reconstruction_v1",
    "__file__": BASE_BUILDER,
}
exec(compile(base_source, BASE_BUILDER, "exec"), scope)
scope["MATERIAL_PATH"] = MATERIAL_PATH

connect = scope["connect"]
add_function_input = scope["add_function_input"]
add_function_output = scope["add_function_output"]
scalar = scope["scalar"]
vector = scope["vector"]
create_function_call = scope["create_function_call"]


RECONSTRUCTION_CODE = r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);

// First regularize the line field and particle depth around the query.
// Coverage is explicit confidence; empty texels never become valid samples.
float2 seedTensorSum = float2(0.0f, 0.0f);
float seedDepthSum = 0.0f;
float seedFrontSum = 0.0f;
float seedSigmaSum = 0.0f;
float seedDensitySum = 0.0f;
float seedWeight = 0.0f;
float guideRadius = max(GuideRadiusPx, 0.5f);
[unroll]
for (int gy = -1; gy <= 1; ++gy)
{
    [unroll]
    for (int gx = -1; gx <= 1; ++gx)
    {
        float2 guideUV = centerUV
            + float2(gx, gy) * safeTexel * guideRadius;
        float valid =
            step(halfTexel.x, guideUV.x)
            * step(guideUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, guideUV.y)
            * step(guideUV.y, 1.0f - halfTexel.y);
        float2 clampedUV = clamp(
            guideUV, halfTexel, 1.0f - halfTexel);
        float4 mainSample = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, clampedUV, 0);
        float4 auxSample = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, clampedUV, 0);
        float density = max(mainSample.r, 0.0f);
        float coverage = saturate(auxSample.a);
        float spatial = (gx == 0 && gy == 0)
            ? 2.0f
            : ((gx == 0 || gy == 0) ? 1.0f : 0.72f);
        float confidence = coverage
            * sqrt(max(density, 0.0f) + 1.0e-4f)
            * spatial * valid;
        seedTensorSum += mainSample.gb * confidence;
        seedDepthSum += max(mainSample.a, 0.0f) * confidence;
        seedFrontSum += max(auxSample.g, 0.0f) * confidence;
        seedSigmaSum += max(auxSample.r, 0.0f) * confidence;
        seedDensitySum += log2(1.0f + density) * confidence;
        seedWeight += confidence;
    }
}

float safeSeedWeight = max(seedWeight, 1.0e-6f);
float2 seedTensor = seedTensorSum / safeSeedWeight;
float seedMeanDepth = seedDepthSum / safeSeedWeight;
float seedFrontDepth = seedFrontSum / safeSeedWeight;
float seedSigma = seedSigmaSum / safeSeedWeight;
float seedDensity = seedDensitySum / safeSeedWeight;
float seedCoherence = saturate(length(seedTensor));
float seedAngle = 0.5f * atan2(seedTensor.y, seedTensor.x);
float2 seedDirection = float2(cos(seedAngle), sin(seedAngle));
float seedConfidence = 1.0f - exp(
    -seedWeight * max(SupportGain, 0.0f));

float activeSteps = clamp(
    floor(ActiveSteps + 0.5f), 1.0f, 8.0f);
float2 stepUV = safeTexel * max(StepPx, 0.5f);
float mediumCross = max(MediumCrossPx, 0.5f);
float bodyCross = max(BodyCrossPx, mediumCross + 0.5f);
float coherenceFloor = saturate(CoherenceMin);
float depthFalloff = max(DepthFalloff, 0.0f);
float sigmaScale = max(DepthSigmaScale, 0.0f);
float3 branchForward = float3(0.0f, 0.0f, 0.0f);
float3 branchBackward = float3(0.0f, 0.0f, 0.0f);
float3 supportForward = float3(0.0f, 0.0f, 0.0f);
float3 supportBackward = float3(0.0f, 0.0f, 0.0f);
const int MaxSteps = 8;

[unroll]
for (int branch = 0; branch < 2; ++branch)
{
    float branchSign = branch == 0 ? 1.0f : -1.0f;
    float2 traceUV = centerUV;
    float2 previousDirection = seedDirection * branchSign;
    float3 numerator = float3(0.0f, 0.0f, 0.0f);
    float3 denominator = float3(0.0f, 0.0f, 0.0f);

    [unroll]
    for (int stepIndex = 0; stepIndex < MaxSteps; ++stepIndex)
    {
        float enabled = (float)stepIndex < activeSteps ? 1.0f : 0.0f;
        float2 midpointUV = traceUV
            + previousDirection * stepUV * 0.5f;
        float midpointValid =
            step(halfTexel.x, midpointUV.x)
            * step(midpointUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, midpointUV.y)
            * step(midpointUV.y, 1.0f - halfTexel.y);
        midpointUV = clamp(
            midpointUV, halfTexel, 1.0f - halfTexel);
        float4 midpointMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, midpointUV, 0);
        float midpointCoherence = saturate(
            length(midpointMain.gb));
        float2 midpointDirection = previousDirection;
        if (midpointCoherence > 1.0e-5f)
        {
            float midpointAngle = 0.5f * atan2(
                midpointMain.b, midpointMain.g);
            midpointDirection = float2(
                cos(midpointAngle), sin(midpointAngle));
            if (dot(midpointDirection, previousDirection) < 0.0f)
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
        float2 normalDirection = float2(
            -midpointDirection.y, midpointDirection.x);
        float2 nextTensorSum = float2(0.0f, 0.0f);
        float nextTensorWeight = 0.0f;
        float t = ((float)stepIndex + 0.65f)
            / (activeSteps + 0.65f);
        float3 longitudinal = float3(
            pow(saturate(1.0f - t), max(FilamentTaper, 0.1f)),
            pow(saturate(1.0f - t), max(MediumTaper, 0.1f)),
            pow(saturate(1.0f - t), max(BodyTaper, 0.1f)));

        [unroll]
        for (int laneIndex = -2; laneIndex <= 2; ++laneIndex)
        {
            int absoluteLane = abs(laneIndex);
            float laneSign = laneIndex < 0 ? -1.0f : 1.0f;
            float laneOffsetPx = absoluteLane == 0
                ? 0.0f
                : (absoluteLane == 1 ? mediumCross : bodyCross);
            float2 laneUV = clampedNextUV
                + normalDirection * safeTexel
                * laneOffsetPx * laneSign;
            float laneValid =
                step(halfTexel.x, laneUV.x)
                * step(laneUV.x, 1.0f - halfTexel.x)
                * step(halfTexel.y, laneUV.y)
                * step(laneUV.y, 1.0f - halfTexel.y);
            float2 clampedLaneUV = clamp(
                laneUV, halfTexel, 1.0f - halfTexel);
            float4 laneMain = Texture2DSampleLevel(
                MainTexture, MainTextureSampler, clampedLaneUV, 0);
            float4 laneAux = Texture2DSampleLevel(
                AuxTexture, AuxTextureSampler, clampedLaneUV, 0);
            float density = max(laneMain.r, 0.0f);
            float densitySignal = log2(1.0f + density);
            float coverage = saturate(laneAux.a);
            float coherence = saturate(length(laneMain.gb));
            float coherenceWeight = lerp(
                0.28f,
                1.0f,
                smoothstep(
                    coherenceFloor,
                    min(coherenceFloor + 0.30f, 1.0f),
                    coherence));
            float depthDifference = abs(
                max(laneMain.a, 0.0f) - seedMeanDepth);
            float frontDifference = abs(
                max(laneAux.g, 0.0f) - seedFrontDepth);
            float depthRelaxation = 1.0f
                + (seedSigma + max(laneAux.r, 0.0f))
                * sigmaScale;
            float depthWeight = exp(
                -(depthDifference + frontDifference * 0.45f)
                * depthFalloff
                / max(depthRelaxation, 1.0e-4f));
            float confidence = enabled * midpointValid * nextValid
                * laneValid * coverage * coherenceWeight * depthWeight;

            float offset = laneOffsetPx;
            float filamentCross = exp(
                -0.5f * (offset / max(mediumCross * 0.42f, 0.5f))
                * (offset / max(mediumCross * 0.42f, 0.5f)));
            float mediumCrossWeight = exp(
                -0.5f * (offset / max(mediumCross, 0.5f))
                * (offset / max(mediumCross, 0.5f)));
            float bodyCrossWeight = exp(
                -0.5f * (offset / max(bodyCross, 0.5f))
                * (offset / max(bodyCross, 0.5f)));
            float3 kernelWeight = longitudinal * float3(
                filamentCross,
                mediumCrossWeight,
                bodyCrossWeight);
            float3 weightedConfidence = kernelWeight * confidence;
            numerator += densitySignal * weightedConfidence;
            denominator += weightedConfidence;

            float guideLaneWeight = absoluteLane == 0
                ? 1.0f
                : (absoluteLane == 1 ? 0.55f : 0.12f);
            float tensorWeight = confidence * guideLaneWeight
                * sqrt(density + 1.0e-4f);
            nextTensorSum += laneMain.gb * tensorWeight;
            nextTensorWeight += tensorWeight;
        }

        if (nextTensorWeight > 1.0e-6f)
        {
            float2 nextTensor = nextTensorSum / nextTensorWeight;
            float nextAngle = 0.5f * atan2(
                nextTensor.y, nextTensor.x);
            float2 nextDirection = float2(
                cos(nextAngle), sin(nextAngle));
            if (dot(nextDirection, midpointDirection) < 0.0f)
            {
                nextDirection *= -1.0f;
            }
            previousDirection = normalize(
                lerp(midpointDirection, nextDirection, 0.72f));
        }
        else
        {
            previousDirection = midpointDirection;
        }
        traceUV = clampedNextUV;
    }

    float3 normalizedDensity = numerator / max(
        denominator, float3(1.0e-5f, 1.0e-5f, 1.0e-5f));
    float3 supportEnvelope = 1.0f - exp(
        -denominator * max(SupportGain, 0.0f));
    float3 branchField = normalizedDensity * supportEnvelope;
    if (branch == 0)
    {
        branchForward = branchField;
        supportForward = denominator;
    }
    else
    {
        branchBackward = branchField;
        supportBackward = denominator;
    }
}

float3 twoSided = sqrt(max(
    branchForward * branchBackward, 0.0f));
float3 oneSided = max(branchForward, branchBackward);
float oneSidedAmount = saturate(OneSidedBlend);
float3 connected = lerp(
    twoSided,
    oneSided,
    oneSidedAmount * float3(0.30f, 0.52f, 0.70f));

// Preserve a soft dense body only where both streamline branches found
// support. A single isolated particle never becomes a visible fallback core.
float3 bilateralSupport = 1.0f - exp(
    -min(supportForward, supportBackward)
    * max(SupportGain, 0.0f));
float coherenceGate = smoothstep(
    coherenceFloor,
    min(coherenceFloor + 0.28f, 1.0f),
    seedCoherence);
float seedBody = seedDensity * seedConfidence
    * bilateralSupport.z;
connected.y = max(
    connected.y,
    seedBody * 0.42f * bilateralSupport.y);
connected.z = max(
    connected.z,
    seedBody * 0.72f);
connected *= seedConfidence * lerp(
    float3(0.0f, 0.42f, 0.72f),
    float3(1.0f, 1.0f, 1.0f),
    coherenceGate);

return max(connected, 0.0f) * max(
    float3(FilamentGain, MediumGain, BodyGain), 0.0f);
""".strip()


DEPTH_LIGHTING_CODE = r"""
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float radius = max(RegularizationRadiusPx, 0.5f);
float meanSum = 0.0f;
float frontSum = 0.0f;
float sigmaSum = 0.0f;
float weightSum = 0.0f;

[unroll]
for (int y = -1; y <= 1; ++y)
{
    [unroll]
    for (int x = -1; x <= 1; ++x)
    {
        float2 sampleUV = centerUV
            + float2(x, y) * safeTexel * radius;
        float valid =
            step(halfTexel.x, sampleUV.x)
            * step(sampleUV.x, 1.0f - halfTexel.x)
            * step(halfTexel.y, sampleUV.y)
            * step(sampleUV.y, 1.0f - halfTexel.y);
        sampleUV = clamp(
            sampleUV, halfTexel, 1.0f - halfTexel);
        float4 mainSample = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, sampleUV, 0);
        float4 auxSample = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, sampleUV, 0);
        float spatial = (x == 0 && y == 0)
            ? 2.0f
            : ((x == 0 || y == 0) ? 1.0f : 0.72f);
        float weight = saturate(auxSample.a)
            * sqrt(max(mainSample.r, 0.0f) + 1.0e-4f)
            * spatial * valid;
        meanSum += max(mainSample.a, 0.0f) * weight;
        frontSum += max(auxSample.g, 0.0f) * weight;
        sigmaSum += max(auxSample.r, 0.0f) * weight;
        weightSum += weight;
    }
}

float safeWeight = max(weightSum, 1.0e-6f);
float meanDepth = meanSum / safeWeight;
float frontDepth = frontSum / safeWeight;
float sigma = sigmaSum / safeWeight;
float fieldConfidence = 1.0f - exp(-weightSum * 0.35f);
float backDepth = max(
    meanDepth + sigma * 1.65f,
    frontDepth);
float normalizedThickness = saturate(
    max(backDepth - frontDepth, 0.0f)
    * max(DepthRangeScale, 0.0f));
float opticalThickness = 1.0f - exp(
    -normalizedThickness * max(ThicknessAbsorption, 0.0f));

float2 gradientOffset = safeTexel
    * max(GradientRadiusPx, 0.5f);
float2 leftUV = clamp(
    centerUV - float2(gradientOffset.x, 0.0f),
    halfTexel, 1.0f - halfTexel);
float2 rightUV = clamp(
    centerUV + float2(gradientOffset.x, 0.0f),
    halfTexel, 1.0f - halfTexel);
float2 upUV = clamp(
    centerUV - float2(0.0f, gradientOffset.y),
    halfTexel, 1.0f - halfTexel);
float2 downUV = clamp(
    centerUV + float2(0.0f, gradientOffset.y),
    halfTexel, 1.0f - halfTexel);
float4 leftAux = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, leftUV, 0);
float4 rightAux = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, rightUV, 0);
float4 upAux = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, upUV, 0);
float4 downAux = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, downUV, 0);
float leftDepth = lerp(
    frontDepth, max(leftAux.g, 0.0f), saturate(leftAux.a));
float rightDepth = lerp(
    frontDepth, max(rightAux.g, 0.0f), saturate(rightAux.a));
float upDepth = lerp(
    frontDepth, max(upAux.g, 0.0f), saturate(upAux.a));
float downDepth = lerp(
    frontDepth, max(downAux.g, 0.0f), saturate(downAux.a));
float2 depthGradient = 0.5f * float2(
    rightDepth - leftDepth,
    downDepth - upDepth);
float3 depthNormal = normalize(float3(
    -depthGradient * max(DepthRangeScale, 0.0f) * 16.0f,
    1.0f));
float3 screenLight = normalize(float3(-0.48f, -0.72f, 0.64f));
float directional = smoothstep(
    0.12f, 0.92f, saturate(dot(depthNormal, screenLight)));
float lighting = max(Ambient, 0.0f)
    + directional * max(DirectionalStrength, 0.0f);
float selfTransmission = lerp(
    1.0f,
    0.58f,
    opticalThickness);
float rangeDepth = saturate(
    meanDepth * max(DepthRangeScale, 0.0f));
float rangeCue = 1.0f
    + (0.5f - rangeDepth) * 2.0f * NearFarContrast;
float3 depthTint = lerp(
    max(NearTint, 0.0f),
    max(FarTint, 0.0f),
    rangeDepth);
float3 thicknessTint = lerp(
    float3(1.0f, 1.0f, 1.0f),
    max(ThickTint, 0.0f),
    opticalThickness);
float3 cue = depthTint * thicknessTint
    * lighting * selfTransmission * rangeCue;
cue = clamp(cue, 0.18f, 1.18f);
return lerp(
    float3(1.0f, 1.0f, 1.0f),
    cue,
    saturate(CueStrength) * fieldConfidence);
""".strip()


SCALAR_DEFAULTS = {
    "FR_GuideRadiusPx": 3.5,
    "FR_StepPx": 3.25,
    "FR_ActiveSteps": 8.0,
    "FR_MediumCrossPx": 4.0,
    "FR_BodyCrossPx": 13.0,
    "FR_CoherenceMin": 0.10,
    "FR_DepthFalloff": 58.0,
    "FR_DepthSigmaScale": 52.0,
    "FR_FilamentTaper": 1.45,
    "FR_MediumTaper": 0.95,
    "FR_BodyTaper": 0.62,
    "FR_OneSidedBlend": 0.32,
    "FR_SupportGain": 0.38,
    "FR_FilamentGain": 1.10,
    "FR_MediumGain": 0.92,
    "FR_BodyGain": 0.72,
    "FR_FilamentWeight": 0.34,
    "FR_MediumWeight": 0.46,
    "FR_BodyWeight": 0.20,
    "FR_DetailStrength": 0.04,
    "FR_EdgeStrength": 0.015,
    "FR_BlackPoint": 0.006,
    "FR_DensityGain": 0.92,
    "FR_Contrast": 0.92,
    "FR_EdgeFadeWidthPx": 20.0,
    "FR_Extinction": 1.12,
    "FR_OpacityScale": 0.78,
    "FR_EmissiveStrength": 0.84,
    "FR_DepthRegularizationPx": 3.5,
    "FR_DepthGradientPx": 3.0,
    "FR_DepthRangeScale": 12.0,
    "FR_ThicknessAbsorption": 5.5,
    "FR_Ambient": 0.62,
    "FR_DirectionalStrength": 0.50,
    "FR_NearFarContrast": 0.10,
    "FR_DepthCueStrength": 1.0,
}
VECTOR_DEFAULTS = {
    "SSPR_InvTextureSize": unreal.LinearColor(
        1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0
    ),
    "FR_SmokeColor": unreal.LinearColor(0.52, 0.58, 0.68, 1.0),
    "FR_NearTint": unreal.LinearColor(1.04, 1.00, 0.96, 1.0),
    "FR_FarTint": unreal.LinearColor(0.78, 0.87, 1.02, 1.0),
    "FR_ThickTint": unreal.LinearColor(0.68, 0.76, 0.88, 1.0),
}


def output_input_name(output):
    names = [
        str(value)
        for value in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            output
        )
    ]
    if not names:
        raise RuntimeError("Material function output exposes no input")
    return names[0]


def create_clean_function(
    asset_name,
    path,
    description,
    specs,
    code,
    output_type,
):
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
    inputs = {}
    for index, (name, input_type) in enumerate(specs):
        inputs[name] = add_function_input(
            function,
            name,
            input_type,
            index,
            -1450,
            -900 + index * 110,
        )
    custom = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionCustom, -420, 40
    )
    custom.set_editor_property("description", description)
    custom.set_editor_property("code", code)
    custom.set_editor_property("output_type", output_type)
    custom_inputs = []
    for name, _ in specs:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)
    for name, input_node in inputs.items():
        connect(input_node, "", custom, name)
    output = add_function_output(function, "Value", 0, 320, 40)
    connect(custom, "", output, output_input_name(output))
    unreal.MaterialEditingLibrary.layout_material_function_expressions(
        function
    )
    unreal.MaterialEditingLibrary.update_material_function(function)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return function


def build_functions():
    texture = unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D
    vector2 = unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2
    vector3 = unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3
    scalar_type = unreal.FunctionInputType.FUNCTION_INPUT_SCALAR
    recon_specs = (
        ("MainTexture", texture),
        ("AuxTexture", texture),
        ("UV", vector2),
        ("TexelSize", vector2),
        ("GuideRadiusPx", scalar_type),
        ("StepPx", scalar_type),
        ("ActiveSteps", scalar_type),
        ("MediumCrossPx", scalar_type),
        ("BodyCrossPx", scalar_type),
        ("CoherenceMin", scalar_type),
        ("DepthFalloff", scalar_type),
        ("DepthSigmaScale", scalar_type),
        ("FilamentTaper", scalar_type),
        ("MediumTaper", scalar_type),
        ("BodyTaper", scalar_type),
        ("OneSidedBlend", scalar_type),
        ("SupportGain", scalar_type),
        ("FilamentGain", scalar_type),
        ("MediumGain", scalar_type),
        ("BodyGain", scalar_type),
    )
    lighting_specs = (
        ("MainTexture", texture),
        ("AuxTexture", texture),
        ("UV", vector2),
        ("TexelSize", vector2),
        ("RegularizationRadiusPx", scalar_type),
        ("GradientRadiusPx", scalar_type),
        ("DepthRangeScale", scalar_type),
        ("ThicknessAbsorption", scalar_type),
        ("Ambient", scalar_type),
        ("DirectionalStrength", scalar_type),
        ("NearFarContrast", scalar_type),
        ("CueStrength", scalar_type),
        ("NearTint", vector3),
        ("FarTint", vector3),
        ("ThickTint", vector3),
    )
    reconstruction = create_clean_function(
        "MF_SSPR_G5_NormalizedFieldReconstructionV1",
        RECON_PATH,
        "Current-frame confidence-normalized field-aligned density reconstruction.",
        recon_specs,
        RECONSTRUCTION_CODE,
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
    )
    lighting = create_clean_function(
        "MF_SSPR_G5_DepthTransportLightingV1",
        LIGHTING_PATH,
        "Current-frame front/mean/sigma thickness, transport, and depth lighting.",
        lighting_specs,
        DEPTH_LIGHTING_CODE,
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
    )
    return reconstruction, lighting


def build_material():
    for path in (
        RECON_PATH,
        LIGHTING_PATH,
        SHAPE_PATH,
        RESOLVE_PATH,
        EDGE_PATH,
    ):
        if not isinstance(unreal.load_asset(path), unreal.MaterialFunction):
            raise RuntimeError("Missing required function: " + path)
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        raise RuntimeError("Refusing to rebuild clean material")
    if unreal.EditorAssetLibrary.does_asset_exist(INSTANCE_PATH):
        raise RuntimeError("Refusing to rebuild clean material instance")

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_AnisotropicSplat_FieldRecon_V1",
        ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Failed to create FieldRecon V1 material")
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
        -900,
    )
    main_texture.set_editor_property("parameter_name", "TrajectoryTexture")
    main_texture.set_editor_property("texture", black)
    aux_texture = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -3300,
        -730,
    )
    aux_texture.set_editor_property(
        "parameter_name", "TrajectoryAuxTexture"
    )
    aux_texture.set_editor_property("texture", black)
    screen = lib.create_material_expression(
        material, unreal.MaterialExpressionScreenPosition, -3300, -540
    )

    params = {}
    for index, (name, value) in enumerate(SCALAR_DEFAULTS.items()):
        if name.startswith("FR_Depth") or name in (
            "FR_ThicknessAbsorption",
            "FR_Ambient",
            "FR_DirectionalStrength",
            "FR_NearFarContrast",
        ):
            group = "40 Depth Transport"
        elif name in (
            "FR_FilamentWeight",
            "FR_MediumWeight",
            "FR_BodyWeight",
            "FR_DetailStrength",
            "FR_EdgeStrength",
            "FR_BlackPoint",
            "FR_DensityGain",
            "FR_Contrast",
        ):
            group = "20 Density Shape"
        elif name in (
            "FR_Extinction",
            "FR_OpacityScale",
            "FR_EmissiveStrength",
            "FR_EdgeFadeWidthPx",
        ):
            group = "50 Smoke Resolve"
        else:
            group = "10 Normalized Field Reconstruction"
        params[name] = scalar(
            material,
            name,
            value,
            -3300 + (index // 12) * 520,
            -290 + (index % 12) * 125,
            group,
        )

    vector_params = {}
    for index, (name, value) in enumerate(VECTOR_DEFAULTS.items()):
        group = (
            "00 Niagara Input"
            if name == "SSPR_InvTextureSize"
            else (
                "50 Smoke Resolve"
                if name == "FR_SmokeColor"
                else "40 Depth Transport"
            )
        )
        vector_params[name] = vector(
            material,
            name,
            value,
            -3300 + index * 440,
            1320,
            group,
        )

    reconstruction = create_function_call(RECON_PATH, -1800, -640)
    shape = create_function_call(SHAPE_PATH, -780, -520)
    edge = create_function_call(EDGE_PATH, -780, 700)
    masked_density = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -150, -420
    )
    resolve = create_function_call(RESOLVE_PATH, 280, -300)
    depth_lighting = create_function_call(LIGHTING_PATH, 280, 660)
    depth_lit_color = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1050, -180
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

    for call in (reconstruction, depth_lighting):
        connect(main_texture, "", call, "MainTexture")
        connect(aux_texture, "", call, "AuxTexture")
        connect(screen, "ViewportUV", call, "UV")
        connect(
            vector_params["SSPR_InvTextureSize"],
            "",
            call,
            "TexelSize",
        )

    for input_name, parameter_name in (
        ("GuideRadiusPx", "FR_GuideRadiusPx"),
        ("StepPx", "FR_StepPx"),
        ("ActiveSteps", "FR_ActiveSteps"),
        ("MediumCrossPx", "FR_MediumCrossPx"),
        ("BodyCrossPx", "FR_BodyCrossPx"),
        ("CoherenceMin", "FR_CoherenceMin"),
        ("DepthFalloff", "FR_DepthFalloff"),
        ("DepthSigmaScale", "FR_DepthSigmaScale"),
        ("FilamentTaper", "FR_FilamentTaper"),
        ("MediumTaper", "FR_MediumTaper"),
        ("BodyTaper", "FR_BodyTaper"),
        ("OneSidedBlend", "FR_OneSidedBlend"),
        ("SupportGain", "FR_SupportGain"),
        ("FilamentGain", "FR_FilamentGain"),
        ("MediumGain", "FR_MediumGain"),
        ("BodyGain", "FR_BodyGain"),
    ):
        connect(params[parameter_name], "", reconstruction, input_name)

    connect(reconstruction, "Value", shape, "Scales")
    for input_name, parameter_name in (
        ("CoreWeight", "FR_FilamentWeight"),
        ("SmallWeight", "FR_MediumWeight"),
        ("LargeWeight", "FR_BodyWeight"),
        ("DetailStrength", "FR_DetailStrength"),
        ("EdgeStrength", "FR_EdgeStrength"),
        ("BlackPoint", "FR_BlackPoint"),
        ("DensityGain", "FR_DensityGain"),
        ("Contrast", "FR_Contrast"),
    ):
        connect(params[parameter_name], "", shape, input_name)

    connect(screen, "ViewportUV", edge, "UV")
    connect(
        vector_params["SSPR_InvTextureSize"], "", edge, "TexelSize"
    )
    connect(
        params["FR_EdgeFadeWidthPx"], "", edge, "FadeWidthPx"
    )
    connect(shape, "Density", masked_density, "A")
    connect(edge, "Mask", masked_density, "B")

    connect(masked_density, "", resolve, "Density")
    connect(vector_params["FR_SmokeColor"], "", resolve, "SmokeColor")
    for input_name, parameter_name in (
        ("Extinction", "FR_Extinction"),
        ("OpacityScale", "FR_OpacityScale"),
        ("EmissiveStrength", "FR_EmissiveStrength"),
    ):
        connect(params[parameter_name], "", resolve, input_name)

    for input_name, parameter_name in (
        ("RegularizationRadiusPx", "FR_DepthRegularizationPx"),
        ("GradientRadiusPx", "FR_DepthGradientPx"),
        ("DepthRangeScale", "FR_DepthRangeScale"),
        ("ThicknessAbsorption", "FR_ThicknessAbsorption"),
        ("Ambient", "FR_Ambient"),
        ("DirectionalStrength", "FR_DirectionalStrength"),
        ("NearFarContrast", "FR_NearFarContrast"),
        ("CueStrength", "FR_DepthCueStrength"),
    ):
        connect(params[parameter_name], "", depth_lighting, input_name)
    for input_name, parameter_name in (
        ("NearTint", "FR_NearTint"),
        ("FarTint", "FR_FarTint"),
        ("ThickTint", "FR_ThickTint"),
    ):
        connect(vector_params[parameter_name], "", depth_lighting, input_name)

    connect(resolve, "Color", depth_lit_color, "A")
    connect(depth_lighting, "Value", depth_lit_color, "B")
    if not lib.connect_material_property(
        depth_lit_color,
        "",
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    ):
        raise RuntimeError("Failed FieldRecon emissive connection")
    if not lib.connect_material_property(
        resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed FieldRecon opacity connection")

    try:
        lib.set_material_usage(
            material, unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES
        )
    except Exception:
        try:
            material.set_editor_property(
                "used_with_niagara_sprites", True
            )
        except Exception:
            pass
    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False):
        raise RuntimeError("Failed to save FieldRecon material")
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
        MATERIAL_PATH
    )
    material_result = {
        "compiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [
            str(value) for value in diagnostics.compile_errors
        ],
        "expressions": len(lib.get_material_expressions(material)),
        "saved": True,
    }
    if (
        not material_result["compiled"]
        or material_result["compileErrors"]
    ):
        raise RuntimeError(
            "FieldRecon material failed: " + repr(material_result)
        )

    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ",
        ROOT,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Failed to create FieldRecon MI")
    instance.set_editor_property("parent", material)
    for name, value in SCALAR_DEFAULTS.items():
        lib.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
    for name, value in VECTOR_DEFAULTS.items():
        lib.set_material_instance_vector_parameter_value(
            instance, name, value
        )
    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save FieldRecon MI")
    return material_result, instance


unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
reconstruction_function, lighting_function = build_functions()
material_gate, instance = build_material()
result = {
    "reconstructionFunction": reconstruction_function.get_path_name(),
    "lightingFunction": lighting_function.get_path_name(),
    "material": MATERIAL_PATH,
    "instance": instance.get_path_name(),
    "materialGate": material_gate,
    "scalarDefaults": SCALAR_DEFAULTS,
    "vectorDefaults": {
        name: [value.r, value.g, value.b, value.a]
        for name, value in VECTOR_DEFAULTS.items()
    },
    "historyUsed": False,
    "oldMipPyramidUsed": False,
    "oldStreamlineUsed": False,
    "maxStepsPerDirection": 8,
    "crossLanes": 5,
}
print(
    "G5_NORMALIZED_FIELD_RECONSTRUCTION_V1="
    + json.dumps(result, sort_keys=True)
)
