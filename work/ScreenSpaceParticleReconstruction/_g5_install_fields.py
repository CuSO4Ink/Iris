import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
SYSTEM_PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
RASTER_MODULE = "SSPR_RasterizeWhiteParticles"
RESOLVE_MODULE = "SSPR_ResolveGridToSimRT"
USER_RASTER = "User.SSPR_DensityRaster"
USER_MAIN_RT = "User.SSPR_SimRT"
USER_AUX_RT = "User.SSPR_AuxRT"
SERVICE = unreal.NiagaraScratchPadService


def require(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))
    return str(result.node_id)


def module_nodes(module):
    rows = list(SERVICE.list_nodes(SYSTEM, EMITTER, module))
    return {
        "hlsl": next(
            str(node.node_id)
            for node in rows
            if str(node.node_type) == "CustomHlsl"
        ),
        "map_get": next(
            str(node.node_id)
            for node in rows
            if str(node.node_type) == "MapGet"
        ),
    }


def pin_names(module, node_id):
    return {
        str(pin.pin_name)
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, module, node_id
        )
    }


def ensure_pin(module, node_id, direction, type_name, pin_name):
    if pin_name in pin_names(module, node_id):
        return False
    require(
        SERVICE.add_pin(
            SYSTEM,
            EMITTER,
            module,
            node_id,
            direction,
            type_name,
            pin_name,
        ),
        "Add pin {}/{}".format(module, pin_name),
    )
    return True


def connection_set(module):
    return {
        (
            str(item.from_node_id),
            str(item.from_pin),
            str(item.to_node_id),
            str(item.to_pin),
        )
        for item in SERVICE.list_connections(SYSTEM, EMITTER, module)
    }


def ensure_connection(module, from_node, from_pin, to_node, to_pin):
    wanted = (from_node, from_pin, to_node, to_pin)
    if wanted in connection_set(module):
        return False
    if not SERVICE.connect_pins(
        SYSTEM,
        EMITTER,
        module,
        from_node,
        from_pin,
        to_node,
        to_pin,
    ):
        raise RuntimeError(
            "Connect failed in {}: {} -> {}".format(
                module, from_pin, to_pin
            )
        )
    return True


changes = []

# Author the six-channel integer raster and the independent current-frame
# auxiliary target before compiling graph code that references them.
grid_result = SERVICE.create_rasterization_grid3d_user_parameter(
    SYSTEM,
    USER_RASTER,
    2048,
    2048,
    1,
    6,
    65535.0,
    0,
    True,
)
require(grid_result, "Configure six-attribute RasterizationGrid3D")

aux_result = SERVICE.create_internal_render_target2d_user_parameter(
    SYSTEM, USER_AUX_RT, 2048, 2048
)
require(aux_result, "Create G5 auxiliary render target")

# Raster: current-frame density, double-angle direction tensor, two depth
# moments, and a nearest-depth reduction. No history is sampled or written.
raster = module_nodes(RASTER_MODULE)
for type_name, pin_name in (
    ("float", "User.SSPR_DepthNearUU"),
    ("float", "User.SSPR_DepthFarUU"),
    ("float", "User.SSPR_FrontDepthWeightThreshold"),
):
    if ensure_pin(
        RASTER_MODULE,
        raster["map_get"],
        "Output",
        type_name,
        pin_name,
    ):
        changes.append("raster-mapget:" + pin_name)

for type_name, pin_name in (
    ("float", "DepthNearUU"),
    ("float", "DepthFarUU"),
    ("float", "FrontDepthWeightThreshold"),
):
    if ensure_pin(
        RASTER_MODULE,
        raster["hlsl"],
        "Input",
        type_name,
        pin_name,
    ):
        changes.append("raster-hlsl:" + pin_name)

for from_pin, to_pin in (
    ("User.SSPR_DepthNearUU", "DepthNearUU"),
    ("User.SSPR_DepthFarUU", "DepthFarUU"),
    (
        "User.SSPR_FrontDepthWeightThreshold",
        "FrontDepthWeightThreshold",
    ),
):
    ensure_connection(
        RASTER_MODULE,
        raster["map_get"],
        from_pin,
        raster["hlsl"],
        to_pin,
    )

raster_code = r"""// G5.1/G5.2 current-frame field splat.
// Attribute layout:
// 0 density Q10, 1/2 density-weighted double-angle tensor Q10,
// 3/4 normalized depth first/second moments Q16,
// 5 maximum inverse normalized depth using the DI precision (65535).
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
const int MaxLongSteps = 24;
const int MaxCrossSteps = 5;
for (int longIndex = -MaxLongSteps;
     longIndex <= MaxLongSteps;
     ++longIndex)
{
    bool activeU = abs(longIndex) <= activeLong;
    float u = (float)longIndex;
    for (int crossIndex = -MaxCrossSteps;
         crossIndex <= MaxCrossSteps;
         ++crossIndex)
    {
        bool activeV = abs(crossIndex) <= activeCross;
        float v = (float)crossIndex;
        float gaussianExponent = -0.5f * (
            (u * u) / max(sigmaLong * sigmaLong, 0.0001f) +
            (v * v) / max(sigmaShort * sigmaShort, 0.0001f));
        float weight = exp(gaussianExponent);
        bool insideKernel =
            activeU && activeV &&
            abs(u) <= cutoff * sigmaLong &&
            abs(v) <= cutoff * sigmaShort;
        int2 pixel = int2(round(
            centerPx + tangent * u + normal * v));
        bool insideGrid =
            pixel.x >= 0 && pixel.x < safeW &&
            pixel.y >= 0 && pixel.y < safeH;

        float contribution = weight * densityPerParticle;
        int densityInt = (int)round(
            contribution * DensityQuantization);
        int tensorCos2Int = (int)round(
            contribution * tensorCos2 * DensityQuantization);
        int tensorSin2Int = (int)round(
            contribution * tensorSin2 * DensityQuantization);
        int depthMoment1Int = (int)round(
            contribution * depthNorm * MomentQuantization);
        int depthMoment2Int = (int)round(
            contribution * depthNorm * depthNorm *
            MomentQuantization);

        if (validSize && validUV && insideKernel && insideGrid &&
            densityInt > 0)
        {
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
OutMark = validSize && validUV ? longLengthPx : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    RASTER_MODULE,
    raster["hlsl"],
    raster_code,
):
    raise RuntimeError("Failed to install G5 field raster HLSL")

# Resolve the six integer attributes into two current-frame RGBA16F targets.
resolve = module_nodes(RESOLVE_MODULE)
if ensure_pin(
    RESOLVE_MODULE,
    resolve["map_get"],
    "Output",
    "RenderTarget2D",
    USER_AUX_RT,
):
    changes.append("resolve-mapget:" + USER_AUX_RT)
if ensure_pin(
    RESOLVE_MODULE,
    resolve["hlsl"],
    "Input",
    "RenderTarget2D",
    "AuxRT",
):
    changes.append("resolve-hlsl:AuxRT")
ensure_connection(
    RESOLVE_MODULE,
    resolve["map_get"],
    USER_AUX_RT,
    resolve["hlsl"],
    "AuxRT",
)

resolve_code = r"""// G5.1/G5.2 field resolve. Both targets are fully overwritten.
int DispatchW = 1;
int DispatchH = 1;
TrajectoryGrid.GetNumCells(DispatchW, DispatchH);
int CellX = 0;
int CellY = 0;
TrajectoryGrid.ExecutionIndexToGridIndex(CellX, CellY);

int RasterW = 1;
int RasterH = 1;
int RasterD = 1;
DensityRaster.GetNumCells(RasterW, RasterH, RasterD);
bool ValidRaster =
    RasterW > 0 && RasterH > 0 && RasterD > 0 &&
    CellX >= 0 && CellX < RasterW &&
    CellY >= 0 && CellY < RasterH;

int DensityInt = 0;
int TensorCos2Int = 0;
int TensorSin2Int = 0;
int DepthMoment1Int = 0;
int DepthMoment2Int = 0;
int FrontInverseDepthInt = 0;
if (ValidRaster)
{
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 0, DensityInt);
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 1, TensorCos2Int);
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 2, TensorSin2Int);
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 3, DepthMoment1Int);
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 4, DepthMoment2Int);
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 5, FrontInverseDepthInt);
}

const float DensityQuantization = 1024.0f;
const float MomentQuantization = 65536.0f;
const float FrontDepthQuantization = 65535.0f;
float Density = max((float)DensityInt / DensityQuantization, 0.0f);
float SafeDensityInt = max((float)DensityInt, 1.0f);
float2 Tensor = float2(
    (float)TensorCos2Int,
    (float)TensorSin2Int) / SafeDensityInt;
float Moment1 = (float)DepthMoment1Int / MomentQuantization;
float Moment2 = (float)DepthMoment2Int / MomentQuantization;
float MeanDepth = Density > 0.0f
    ? saturate(Moment1 / Density)
    : 0.0f;
float MeanDepthSquared = Density > 0.0f
    ? max(Moment2 / Density, 0.0f)
    : 0.0f;
float DepthSigma = sqrt(max(
    MeanDepthSquared - MeanDepth * MeanDepth,
    0.0f));
float FrontDepth = FrontInverseDepthInt > 0
    ? saturate(
        1.0f -
        (float)FrontInverseDepthInt / FrontDepthQuantization)
    : MeanDepth;
float Coverage = Density > 0.0f ? 1.0f : 0.0f;

int MainW = 1;
int MainH = 1;
SimRT.GetRenderTargetSize(MainW, MainH);
int AuxW = 1;
int AuxH = 1;
AuxRT.GetRenderTargetSize(AuxW, AuxH);
bool ValidMain = MainW > 0 && MainH > 0;
bool ValidAux = AuxW > 0 && AuxH > 0;
int MainX = ValidRaster && ValidMain
    ? clamp((int)(((float)CellX + 0.5f) *
        (float)MainW / (float)RasterW), 0, MainW - 1)
    : 0;
int MainY = ValidRaster && ValidMain
    ? clamp((int)(((float)CellY + 0.5f) *
        (float)MainH / (float)RasterH), 0, MainH - 1)
    : 0;
int AuxX = ValidRaster && ValidAux
    ? clamp((int)(((float)CellX + 0.5f) *
        (float)AuxW / (float)RasterW), 0, AuxW - 1)
    : 0;
int AuxY = ValidRaster && ValidAux
    ? clamp((int)(((float)CellY + 0.5f) *
        (float)AuxH / (float)RasterH), 0, AuxH - 1)
    : 0;

SimRT.SetRenderTargetValue(
    ValidRaster && ValidMain,
    MainX,
    MainY,
    float4(Density, Tensor.x, Tensor.y, MeanDepth));
AuxRT.SetRenderTargetValue(
    ValidRaster && ValidAux,
    AuxX,
    AuxY,
    float4(DepthSigma, FrontDepth, 0.0f, Coverage));
OutMark = Density;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    RESOLVE_MODULE,
    resolve["hlsl"],
    resolve_code,
):
    raise RuntimeError("Failed to install G5 field resolve HLSL")

# Keep both current-frame targets bilinear and mip-free for deterministic
# screen-space alignment. The service authors RGBA16F and 2048x2048.
aux_interfaces = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        SYSTEM not in path
        or data_interface.get_class().get_name()
        != "NiagaraDataInterfaceRenderTarget2D"
        or "SSPR_AuxRT" not in path
    ):
        continue
    data_interface.set_editor_property(
        "mip_map_generation",
        unreal.NiagaraMipMapGeneration.DISABLED,
    )
    data_interface.set_editor_property(
        "mip_map_generation_type",
        unreal.NiagaraMipMapGenerationType.LINEAR,
    )
    data_interface.set_editor_property(
        "override_render_target_filter",
        unreal.TextureFilter.TF_BILINEAR,
    )
    aux_interfaces.append(path)

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False))
result = {
    "changes": changes,
    "grid": {
        "cells": [2048, 2048, 1],
        "attributes": 6,
        "precision": 65535,
        "clearBeforeNonIterationStage": True,
    },
    "mainRT": {
        "variable": USER_MAIN_RT,
        "layout": [
            "density",
            "tensorCos2",
            "tensorSin2",
            "meanNormalizedViewDepth",
        ],
    },
    "auxRT": {
        "variable": USER_AUX_RT,
        "size": [2048, 2048],
        "format": "RGBA16F",
        "filter": "Bilinear",
        "mips": "Disabled",
        "layout": [
            "depthSigma",
            "frontNormalizedViewDepth",
            "reserved",
            "coverage",
        ],
        "interfaces": aux_interfaces,
    },
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print("G5_FIELDS=" + json.dumps(result, sort_keys=True))
if not applied or messages or not saved or not aux_interfaces:
    raise RuntimeError("G5 field install gate failed: " + repr(result))
