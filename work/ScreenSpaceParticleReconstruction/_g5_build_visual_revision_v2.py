import json
import unreal


BASE_BUILDER = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_g5_build_streamline_production.py"
)


with open(BASE_BUILDER, encoding="utf-8") as source_file:
    builder_source = source_file.read()

main_marker = "unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)"
if main_marker not in builder_source:
    raise RuntimeError("Could not isolate reusable G5 builder definitions")
builder_source = builder_source.split(main_marker, 1)[0]

name_replacements = (
    (
        "MI_SSPR_AnisotropicSplat_G5_HQ",
        "MI_SSPR_AnisotropicSplat_G5_V2_HQ",
    ),
    (
        "M_SSPR_AnisotropicSplat_G5",
        "M_SSPR_AnisotropicSplat_G5_V2",
    ),
    (
        "MF_SSPR_G5_StreamlineDensityV1",
        "MF_SSPR_G5_StreamlineDensityV2",
    ),
    (
        "MF_SSPR_G5_DepthCueV1",
        "MF_SSPR_G5_DepthLightingV2",
    ),
)
for old_name, new_name in name_replacements:
    builder_source = builder_source.replace(old_name, new_name)

old_compose_source = (
    '        "return float3(max(Filament, 0.0f), "\n'
    '        "max(BodyScales.y, 0.0f), max(BodyScales.z, 0.0f));",'
)
if old_compose_source not in builder_source:
    raise RuntimeError("Could not parameterize G5 body composition code")
builder_source = builder_source.replace(
    old_compose_source,
    "        COMPOSE_CODE,",
)

builder_scope = {
    "__name__": "g5_visual_revision_v2_builder",
    "__file__": BASE_BUILDER,
}
exec(
    compile(builder_source, BASE_BUILDER, "exec"),
    builder_scope,
)


streamline_code = builder_scope["STREAMLINE_CODE"]
old_support_block = """float4 nextMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, clampedNextUV, 0);
        float4 nextAux = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, clampedNextUV, 0);
        float nextDensity = max(nextMain.r, 0.0f);
        float nextCoherence = saturate(length(nextMain.gb));"""
new_support_block = """float4 nextMain = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, clampedNextUV, 0);
        float4 nextAux = Texture2DSampleLevel(
            AuxTexture, AuxTextureSampler, clampedNextUV, 0);

        // Gather several narrow lanes normal to the current streamline.
        // This closes lateral holes around a curved filament without
        // isotropically blurring the density field.
        float2 nextNormal = float2(
            -midpointDirection.y, midpointDirection.x);
        float2 laneOffset = nextNormal * safeTexel
            * max(DirectionSearchPx, 0.5f);
        float2 laneUVL1 = clamp(
            clampedNextUV - laneOffset,
            halfTexel, 1.0f - halfTexel);
        float2 laneUVR1 = clamp(
            clampedNextUV + laneOffset,
            halfTexel, 1.0f - halfTexel);
        float2 laneUVL2 = clamp(
            clampedNextUV - laneOffset * 2.0f,
            halfTexel, 1.0f - halfTexel);
        float2 laneUVR2 = clamp(
            clampedNextUV + laneOffset * 2.0f,
            halfTexel, 1.0f - halfTexel);
        float4 laneMainL1 = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, laneUVL1, 0);
        float4 laneMainR1 = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, laneUVR1, 0);
        float4 laneMainL2 = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, laneUVL2, 0);
        float4 laneMainR2 = Texture2DSampleLevel(
            MainTexture, MainTextureSampler, laneUVR2, 0);

        float4 supportMain = nextMain;
        float nextDensity = max(nextMain.r, 0.0f);
        float candidate = max(laneMainL1.r, 0.0f) * 0.82f;
        if (candidate > nextDensity)
        {
            nextDensity = candidate;
            supportMain = laneMainL1;
        }
        candidate = max(laneMainR1.r, 0.0f) * 0.82f;
        if (candidate > nextDensity)
        {
            nextDensity = candidate;
            supportMain = laneMainR1;
        }
        candidate = max(laneMainL2.r, 0.0f) * 0.52f;
        if (candidate > nextDensity)
        {
            nextDensity = candidate;
            supportMain = laneMainL2;
        }
        candidate = max(laneMainR2.r, 0.0f) * 0.52f;
        if (candidate > nextDensity)
        {
            nextDensity = candidate;
            supportMain = laneMainR2;
        }
        float nextCoherence = saturate(length(supportMain.gb));"""
if old_support_block not in streamline_code:
    raise RuntimeError("Could not install V2 cross-flow streamline gather")
streamline_code = streamline_code.replace(
    old_support_block,
    new_support_block,
)
streamline_code = streamline_code.replace(
    "float depthDifference = abs(nextMain.a - seedMeanDepth);",
    "float depthDifference = abs(supportMain.a - seedMeanDepth);",
)


depth_lighting_code = r"""
float2 safeUV = saturate(UV);
float4 mainField = Texture2DSampleLevel(
    MainTexture, MainTextureSampler, safeUV, 0);
float4 auxField = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, safeUV, 0);
float coverage = saturate(auxField.a);

uint fieldWidth = 1;
uint fieldHeight = 1;
MainTexture.GetDimensions(fieldWidth, fieldHeight);
float2 texelSize = 1.0f / max(
    float2(fieldWidth, fieldHeight), float2(1.0f, 1.0f));
float2 depthOffset = texelSize * 2.0f;

float2 uvLeft = clamp(
    safeUV - float2(depthOffset.x, 0.0f),
    texelSize * 0.5f, 1.0f - texelSize * 0.5f);
float2 uvRight = clamp(
    safeUV + float2(depthOffset.x, 0.0f),
    texelSize * 0.5f, 1.0f - texelSize * 0.5f);
float2 uvUp = clamp(
    safeUV - float2(0.0f, depthOffset.y),
    texelSize * 0.5f, 1.0f - texelSize * 0.5f);
float2 uvDown = clamp(
    safeUV + float2(0.0f, depthOffset.y),
    texelSize * 0.5f, 1.0f - texelSize * 0.5f);

float4 auxLeft = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, uvLeft, 0);
float4 auxRight = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, uvRight, 0);
float4 auxUp = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, uvUp, 0);
float4 auxDown = Texture2DSampleLevel(
    AuxTexture, AuxTextureSampler, uvDown, 0);

float centerFront = max(auxField.g, 0.0f);
float depthLeft = lerp(
    centerFront, max(auxLeft.g, 0.0f), saturate(auxLeft.a));
float depthRight = lerp(
    centerFront, max(auxRight.g, 0.0f), saturate(auxRight.a));
float depthUp = lerp(
    centerFront, max(auxUp.g, 0.0f), saturate(auxUp.a));
float depthDown = lerp(
    centerFront, max(auxDown.g, 0.0f), saturate(auxDown.a));

float normalStrength = max(DepthRangeScale, 0.0f) * 18.0f;
float2 depthGradient = 0.5f * float2(
    depthRight - depthLeft,
    depthDown - depthUp);
float3 depthNormal = normalize(float3(
    -depthGradient * normalStrength, 1.0f));
float3 screenLight = normalize(float3(-0.55f, -0.75f, 0.62f));
float normalLight = smoothstep(
    0.15f, 0.85f, saturate(dot(depthNormal, screenLight)));
float surfaceLighting = lerp(0.58f, 1.12f, normalLight);

float scaledDepth = saturate(
    max(mainField.a, 0.0f) * max(DepthRangeScale, 0.0f));
float nearFar = (0.5f - scaledDepth) * 2.0f;
float thickness = 1.0f - exp(
    -max(auxField.r, 0.0f) * max(SigmaScale, 0.0f));
float frontSeparation = 1.0f - exp(
    -max(mainField.a - auxField.g, 0.0f)
    * max(DepthRangeScale, 0.0f) * 20.0f);
float selfOcclusion = saturate(
    thickness * max(ThicknessShadow, 0.0f)
    + frontSeparation * max(LayerShadow, 0.0f));
float rangeCue = 1.0f + nearFar * DepthContrast;
float cue = clamp(
    surfaceLighting * (1.0f - selfOcclusion) * rangeCue,
    0.35f,
    1.15f);
return lerp(
    1.0f,
    lerp(1.0f, cue, coverage),
    saturate(CueStrength));
""".strip()


compose_code = r"""
float filament = max(Filament, 0.0f);
float medium = max(BodyScales.y, 0.0f);
float body = max(BodyScales.z, 0.0f);

// An isolated raw splat produces no bidirectional/one-sided streamline
// support once IsolatedCoreScale is zero. Gate the soft scales with the
// resulting connected support so blurred orphan particles cannot reappear.
float connectivity = smoothstep(0.0015f, 0.025f, filament);
float mediumGate = sqrt(saturate(connectivity));
float bodyGate = pow(saturate(connectivity), 0.35f);
return float3(
    filament,
    medium * mediumGate,
    body * bodyGate);
""".strip()


scalar_defaults = dict(builder_scope["SCALAR_DEFAULTS"])
scalar_defaults.update(
    {
        "G5_StreamlineStepPx": 4.0,
        "G5_StreamlineSteps": 8.0,
        "G5_DirectionSearchPx": 2.75,
        "G5_CoherenceMin": 0.12,
        "G5_DepthFalloff": 55.0,
        "G5_DepthSigmaScale": 48.0,
        "G5_CurvatureMinDot": 0.35,
        "G5_TaperPower": 1.20,
        "G5_TwoSidedness": 0.60,
        "G5_IsolatedCoreScale": 0.0,
        "G5_FilamentGain": 1.15,
        "AS_MediumRadiusPx": 14.0,
        "AS_BodyRadiusPx": 48.0,
        "AS_FilamentWeight": 0.22,
        "AS_MediumWeight": 0.52,
        "AS_BodyWeight": 0.26,
        "AS_DetailStrength": 0.03,
        "AS_EdgeStrength": 0.015,
        "AS_BlackPoint": 0.008,
        "AS_DensityGain": 1.30,
        "AS_Contrast": 0.88,
        "AS_Extinction": 1.25,
        "AS_OpacityScale": 0.76,
        "AS_EmissiveStrength": 0.90,
        "G5_DepthRangeScale": 12.0,
        "G5_DepthContrast": 0.08,
        "G5_SigmaScale": 96.0,
        "G5_ThicknessShadow": 0.42,
        "G5_LayerShadow": 0.34,
        "G5_DepthCueStrength": 1.0,
    }
)

builder_scope["STREAMLINE_CODE"] = streamline_code
builder_scope["DEPTH_CUE_CODE"] = depth_lighting_code
builder_scope["COMPOSE_CODE"] = compose_code
builder_scope["SCALAR_DEFAULTS"] = scalar_defaults

builder_scope["unreal"].EditorAssetLibrary.make_directory(
    builder_scope["FUNCTION_FOLDER"]
)
streamline_function, depth_function = builder_scope["build_functions"]()
material_result, instance = builder_scope["build_material"]()

material_library = unreal.MaterialEditingLibrary
material_library.set_material_instance_vector_parameter_value(
    instance,
    "AS_SmokeColor",
    unreal.LinearColor(0.64, 0.69, 0.76, 1.0),
)
if not unreal.EditorAssetLibrary.save_asset(
    builder_scope["INSTANCE_PATH"], False
):
    raise RuntimeError("Failed to save G5 visual V2 material instance")

result = {
    "streamlineFunction": streamline_function.get_path_name(),
    "depthLightingFunction": depth_function.get_path_name(),
    "material": builder_scope["MATERIAL_PATH"],
    "instance": instance.get_path_name(),
    "materialGate": material_result,
    "scalarDefaults": scalar_defaults,
    "smokeColor": [0.64, 0.69, 0.76, 1.0],
    "historyUsed": False,
    "visualChanges": {
        "crossFlowLanes": 5,
        "isolatedCoreScale": 0.0,
        "bodyConnectivityGate": True,
        "frontDepthNormalLighting": True,
        "sigmaAndLayerOcclusion": True,
    },
}
print("G5_VISUAL_REVISION_V2=" + json.dumps(result, sort_keys=True))
