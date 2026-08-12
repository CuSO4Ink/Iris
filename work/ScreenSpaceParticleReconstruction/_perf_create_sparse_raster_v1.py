import json
import unreal


SOURCE_PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
TARGET_PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance/"
    "NS_SSPR_AnisotropicSplat_PerfSparseV1"
)
SOURCE = SOURCE_PACKAGE + ".NS_SSPR_AnisotropicSplat_Main"
TARGET = TARGET_PACKAGE + ".NS_SSPR_AnisotropicSplat_PerfSparseV1"
EMITTER = "Fountain"
RASTER_MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService


def custom_hlsl_node(system_path, module_name):
    nodes = SERVICE.list_nodes(system_path, EMITTER, module_name)
    for node in nodes:
        if str(node.node_type) == "CustomHlsl":
            return str(node.node_id)
    raise RuntimeError(
        "Missing Custom HLSL node: {} / {}".format(
            system_path, module_name
        )
    )


if unreal.EditorAssetLibrary.does_asset_exist(TARGET_PACKAGE):
    raise RuntimeError(
        "Refusing to overwrite existing performance candidate: "
        + TARGET_PACKAGE
    )

unreal.EditorAssetLibrary.make_directory(
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance"
)
duplicated = unreal.EditorAssetLibrary.duplicate_asset(
    SOURCE_PACKAGE, TARGET_PACKAGE
)
if not isinstance(duplicated, unreal.NiagaraSystem):
    raise RuntimeError("Failed to duplicate the V2 Niagara System")

raster_node = custom_hlsl_node(TARGET, RASTER_MODULE)
source_code = SERVICE.get_custom_hlsl_code(
    TARGET, EMITTER, RASTER_MODULE, raster_node
)
required_source_tokens = (
    "MaxLongSteps = 24",
    "MaxCrossSteps = 5",
    "InterlockedAddIntGridValue",
    "InterlockedMaxFloatGridValue",
)
missing_source_tokens = [
    token for token in required_source_tokens if token not in source_code
]
if missing_source_tokens:
    raise RuntimeError(
        "Duplicated source Raster HLSL is not the expected G5 baseline: "
        + repr(missing_source_tokens)
    )

raster_code = r"""// G5.3 performance candidate: mass-conserving sparse Gaussian splat.
// Keeps current-frame projection, six field attributes, Q10/Q16 quantization,
// 2048 raster resolution, and the full particle population. The dense 49x11
// candidate rectangle is represented by at most 25x5 weighted samples.
int W = 1;
int H = 1;
int D = 1;
DensityRaster.GetNumCells(W, H, D);
bool validSize = W > 0 && H > 0 && D > 0;

float4 clip = mul(float4(WorldPos, 1.0f), View.WorldToClip);
bool inFront = clip.w > 0.0001f;
float2 ndc = inFront
    ? clip.xy / clip.w
    : float2(0.0f, 0.0f);
float2 currentUV = ndc * float2(0.5f, -0.5f) + 0.5f;
bool validUV =
    inFront &&
    currentUV.x >= 0.0f && currentUV.x < 1.0f &&
    currentUV.y >= 0.0f && currentUV.y < 1.0f;

int safeW = max(W, 1);
int safeH = max(H, 1);
float2 gridSize = float2(safeW, safeH);
float2 centerPx = currentUV * gridSize;
float2 deltaPx = ScreenDeltaUV * gridSize;
float speedPx = length(deltaPx);

float minLength = max(MinLengthPx, 0.25f);
float maxLength = max(MaxLengthPx, minLength);
float velocityLengthScale = max(VelocityLengthScale, 0.0f);
float longLengthPx = clamp(
    minLength + speedPx * velocityLengthScale,
    minLength,
    maxLength);
float cutoff = max(GaussianCutoffSigma, 1.0f);
float sigmaShort = max(WidthPx, 0.35f);
float sigmaLong = max(longLengthPx / (2.0f * cutoff), sigmaShort);

float minDirectionSpeed = max(MinDirectionSpeedPx, 0.0001f);
float densityPerParticle = max(DensityPerParticle, 0.0f);
float2 tangent = speedPx > minDirectionSpeed
    ? deltaPx / speedPx
    : float2(1.0f, 0.0f);
float2 normal = float2(-tangent.y, tangent.x);
float tensorCos2 = tangent.x * tangent.x - tangent.y * tangent.y;
float tensorSin2 = 2.0f * tangent.x * tangent.y;

float depthRange = max(DepthFarUU - DepthNearUU, 1.0f);
float depthNorm = saturate((clip.w - DepthNearUU) / depthRange);
float frontThreshold = saturate(FrontDepthWeightThreshold);

float halfLength = min(0.5f * longLengthPx, 24.0f);
float halfWidth = min(cutoff * sigmaShort, 5.0f);
int activeLong = (int)ceil(halfLength);
int activeCross = (int)ceil(halfWidth);

const float DensityQuantization = 1024.0f;
const float MomentQuantization = 65536.0f;
const int DenseMaxLongSteps = 24;
const int DenseMaxCrossSteps = 5;
const int SparseMaxLongHalfSamples = 12;
const int SparseMaxCrossHalfSamples = 2;

if (validSize && validUV && densityPerParticle > 0.0f)
{
    float invSigmaLong2 =
        1.0f / max(sigmaLong * sigmaLong, 0.0001f);
    float invSigmaShort2 =
        1.0f / max(sigmaShort * sigmaShort, 0.0001f);
    float cutoffLong = cutoff * sigmaLong;
    float cutoffCross = cutoff * sigmaShort;

    // Compute the exact separable weight sum of the previous dense integer
    // kernel. The sparse representation is normalized to this value, so total
    // density/tensor/depth mass per particle is preserved before quantization.
    float denseWeightSumLong = 0.0f;
    for (int denseLongIndex = -DenseMaxLongSteps;
         denseLongIndex <= DenseMaxLongSteps;
         ++denseLongIndex)
    {
        float denseU = (float)denseLongIndex;
        if (abs(denseLongIndex) <= activeLong &&
            abs(denseU) <= cutoffLong)
        {
            denseWeightSumLong += exp(
                -0.5f * denseU * denseU * invSigmaLong2);
        }
    }

    float denseWeightSumCross = 0.0f;
    for (int denseCrossIndex = -DenseMaxCrossSteps;
         denseCrossIndex <= DenseMaxCrossSteps;
         ++denseCrossIndex)
    {
        float denseV = (float)denseCrossIndex;
        if (abs(denseCrossIndex) <= activeCross &&
            abs(denseV) <= cutoffCross)
        {
            denseWeightSumCross += exp(
                -0.5f * denseV * denseV * invSigmaShort2);
        }
    }

    int maxLongIndex = min(
        activeLong,
        min(DenseMaxLongSteps, (int)floor(cutoffLong)));
    int maxCrossIndex = min(
        activeCross,
        min(DenseMaxCrossSteps, (int)floor(cutoffCross)));
    int sparseLongHalfSamples = min(
        SparseMaxLongHalfSamples,
        max(0, (int)ceil((float)maxLongIndex * 0.5f)));
    int sparseCrossHalfSamples = min(
        SparseMaxCrossHalfSamples,
        maxCrossIndex);

    // Treat samples as cell centers. For the common maximum footprint this is
    // approximately 1.96 px longitudinally and 1.4 px transversely.
    float sparseLongStep =
        ((float)maxLongIndex + 0.5f) /
        ((float)sparseLongHalfSamples + 0.5f);
    float sparseCrossStep =
        ((float)maxCrossIndex + 0.5f) /
        ((float)sparseCrossHalfSamples + 0.5f);

    float sparseWeightSumLong = 0.0f;
    for (int sparseLongIndex = -SparseMaxLongHalfSamples;
         sparseLongIndex <= SparseMaxLongHalfSamples;
         ++sparseLongIndex)
    {
        if (abs(sparseLongIndex) <= sparseLongHalfSamples)
        {
            float u = (float)sparseLongIndex * sparseLongStep;
            sparseWeightSumLong += exp(
                -0.5f * u * u * invSigmaLong2);
        }
    }

    float sparseWeightSumCross = 0.0f;
    for (int sparseCrossIndex = -SparseMaxCrossHalfSamples;
         sparseCrossIndex <= SparseMaxCrossHalfSamples;
         ++sparseCrossIndex)
    {
        if (abs(sparseCrossIndex) <= sparseCrossHalfSamples)
        {
            float v = (float)sparseCrossIndex * sparseCrossStep;
            sparseWeightSumCross += exp(
                -0.5f * v * v * invSigmaShort2);
        }
    }

    float massScale =
        (denseWeightSumLong * denseWeightSumCross) /
        max(
            sparseWeightSumLong * sparseWeightSumCross,
            0.0001f);

    for (int sparseLongIndex = -SparseMaxLongHalfSamples;
         sparseLongIndex <= SparseMaxLongHalfSamples;
         ++sparseLongIndex)
    {
        if (abs(sparseLongIndex) <= sparseLongHalfSamples)
        {
            float u = (float)sparseLongIndex * sparseLongStep;
            float weightLong = exp(
                -0.5f * u * u * invSigmaLong2);
            for (int sparseCrossIndex = -SparseMaxCrossHalfSamples;
                 sparseCrossIndex <= SparseMaxCrossHalfSamples;
                 ++sparseCrossIndex)
            {
                if (abs(sparseCrossIndex) <= sparseCrossHalfSamples)
                {
                    float v =
                        (float)sparseCrossIndex * sparseCrossStep;
                    float weightCross = exp(
                        -0.5f * v * v * invSigmaShort2);
                    float weight = weightLong * weightCross;
                    float contribution =
                        weight * massScale * densityPerParticle;
                    int densityInt = (int)round(
                        contribution * DensityQuantization);

                    int2 pixel = int2(round(
                        centerPx + tangent * u + normal * v));
                    bool insideGrid =
                        pixel.x >= 0 && pixel.x < safeW &&
                        pixel.y >= 0 && pixel.y < safeH;
                    if (insideGrid && densityInt > 0)
                    {
                        int tensorCos2Int = (int)round(
                            contribution * tensorCos2 *
                            DensityQuantization);
                        int tensorSin2Int = (int)round(
                            contribution * tensorSin2 *
                            DensityQuantization);
                        int depthMoment1Int = (int)round(
                            contribution * depthNorm *
                            MomentQuantization);
                        int depthMoment2Int = (int)round(
                            contribution * depthNorm * depthNorm *
                            MomentQuantization);
                        int previousValue = 0;
                        DensityRaster.InterlockedAddIntGridValue(
                            pixel.x, pixel.y, 0, 0,
                            densityInt, previousValue);
                        DensityRaster.InterlockedAddIntGridValue(
                            pixel.x, pixel.y, 0, 1,
                            tensorCos2Int, previousValue);
                        DensityRaster.InterlockedAddIntGridValue(
                            pixel.x, pixel.y, 0, 2,
                            tensorSin2Int, previousValue);
                        DensityRaster.InterlockedAddIntGridValue(
                            pixel.x, pixel.y, 0, 3,
                            depthMoment1Int, previousValue);
                        DensityRaster.InterlockedAddIntGridValue(
                            pixel.x, pixel.y, 0, 4,
                            depthMoment2Int, previousValue);
                        if (weight >= frontThreshold)
                        {
                            DensityRaster.InterlockedMaxFloatGridValue(
                                pixel.x, pixel.y, 0, 5,
                                1.0f - depthNorm, previousValue);
                        }
                    }
                }
            }
        }
    }
}
OutMark = validSize && validUV ? longLengthPx : 0.0f;"""

if not SERVICE.set_custom_hlsl_code(
    TARGET,
    EMITTER,
    RASTER_MODULE,
    raster_node,
    raster_code,
):
    raise RuntimeError("Failed to install sparse Raster HLSL")

applied = bool(SERVICE.apply_changes(TARGET))
messages = [
    str(value) for value in SERVICE.get_compile_messages(TARGET, False)
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(TARGET_PACKAGE, False)
)
installed_code = SERVICE.get_custom_hlsl_code(
    TARGET, EMITTER, RASTER_MODULE, raster_node
)
result = {
    "source": SOURCE_PACKAGE,
    "target": TARGET_PACKAGE,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
    "denseCandidateSamples": 49 * 11,
    "sparseMaxSamples": 25 * 5,
    "particlePopulationChanged": False,
    "resolutionChanged": False,
    "fixedTick": bool(
        duplicated.get_editor_property("fixed_tick_delta")
    ),
    "fixedTickDeltaTime": float(
        duplicated.get_editor_property("fixed_tick_delta_time")
    ),
    "codeGate": {
        "massConserving": "massScale" in installed_code,
        "earlyProjectionCull": (
            "if (validSize && validUV" in installed_code
        ),
        "sixFieldAtomics": all(
            "pixel.x, pixel.y, 0, {}".format(index)
            in installed_code
            for index in range(6)
        ),
        "noHistory": "History" not in installed_code,
    },
}
print(
    "PERF_SPARSE_RASTER_V1="
    + json.dumps(result, sort_keys=True)
)
if (
    not applied
    or not saved
    or messages
    or not result["fixedTick"]
    or not all(result["codeGate"].values())
):
    raise RuntimeError(
        "Performance candidate gate failed: " + repr(result)
    )
