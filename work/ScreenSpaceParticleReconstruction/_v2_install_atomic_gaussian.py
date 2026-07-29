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

# G2/G3 writer: screen-space motion-aligned Gaussian, accumulated with the
# RasterizationGrid3D fixed-point atomic API. Z is intentionally one cell.
raster = module_nodes(RASTER_MODULE)
for type_name, pin_name in (
    ("vec2", "Particles.SSPR_ScreenUV"),
    ("vec2", "Particles.SSPR_ScreenDeltaUV"),
    ("RasterizationGrid3D", USER_RASTER),
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
    ("vec2", "ScreenUV"),
    ("vec2", "ScreenDeltaUV"),
    ("RasterizationGrid3D", "DensityRaster"),
):
    if ensure_pin(
        RASTER_MODULE,
        raster["hlsl"],
        "Input",
        type_name,
        pin_name,
    ):
        changes.append("raster-hlsl:" + pin_name)

parameter_specs = (
    ("MinLengthPx", "float"),
    ("VelocityLengthScale", "float"),
    ("MaxLengthPx", "float"),
    ("WidthPx", "float"),
    ("GaussianCutoffSigma", "float"),
    ("DensityPerParticle", "float"),
    ("MinDirectionSpeedPx", "float"),
)
for parameter_name, type_name in parameter_specs:
    module_pin = "Module." + parameter_name
    if module_pin not in pin_names(RASTER_MODULE, raster["map_get"]):
        raster["map_get"] = require(
            SERVICE.add_module_input(
                SYSTEM,
                EMITTER,
                RASTER_MODULE,
                parameter_name,
                type_name,
            ),
            "Add raster parameter " + parameter_name,
        )
        changes.append("raster-parameter:" + parameter_name)
    if ensure_pin(
        RASTER_MODULE,
        raster["hlsl"],
        "Input",
        type_name,
        parameter_name,
    ):
        changes.append("raster-hlsl:" + parameter_name)
    user_pin = "User.SSPR_" + parameter_name
    if ensure_pin(
        RASTER_MODULE,
        raster["map_get"],
        "Output",
        type_name,
        user_pin,
    ):
        changes.append("raster-user-parameter:" + user_pin)
    # The initial prototype exposed local module inputs. The approved V2
    # baseline drives the same HLSL inputs from authored User parameters so
    # values are editable at system/component level and have real defaults.
    SERVICE.disconnect_pin(
        SYSTEM,
        EMITTER,
        RASTER_MODULE,
        raster["hlsl"],
        parameter_name,
    )
    ensure_connection(
        RASTER_MODULE,
        raster["map_get"],
        user_pin,
        raster["hlsl"],
        parameter_name,
    )

for from_pin, to_pin in (
    ("Particles.SSPR_ScreenUV", "ScreenUV"),
    ("Particles.SSPR_ScreenDeltaUV", "ScreenDeltaUV"),
    (USER_RASTER, "DensityRaster"),
):
    ensure_connection(
        RASTER_MODULE,
        raster["map_get"],
        from_pin,
        raster["hlsl"],
        to_pin,
    )

raster_code = r"""// V2 anisotropic Gaussian splat. Reproject the persisted
// particle position in this stage instead of trusting a cached screen UV.
// The cached screen displacement controls the long axis; atomic addition
// preserves overlap density. The grid is 2D in use, stored as 2048x2048x1.
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
float halfLength = min(0.5f * longLengthPx, 24.0f);
float halfWidth = min(cutoff * sigmaShort, 5.0f);
int activeLong = (int)ceil(halfLength);
int activeCross = (int)ceil(halfWidth);

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
        // RasterizationGrid3D stores signed integers internally. Quantize
        // explicitly so density remains fractional and deterministic even
        // though the subclass Precision property is not Python-exposed.
        const float DensityQuantization = 1024.0f;
        int contributionInt = (int)round(
            weight * densityPerParticle *
            DensityQuantization);
        if (validSize && validUV && insideKernel && insideGrid &&
            contributionInt > 0)
        {
            int previousValue = 0;
            DensityRaster.InterlockedAddIntGridValue(
                pixel.x, pixel.y, 0, 0,
                contributionInt, previousValue);
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
    raise RuntimeError("Failed to install anisotropic raster HLSL")

# Resolve keeps the existing Grid2D stage as a 2048x2048 dispatch domain, but
# samples the new atomic field. This preserves the Niagara-owned RGBA16F SimRT
# and its renderer material binding.
resolve = module_nodes(RESOLVE_MODULE)
if ensure_pin(
    RESOLVE_MODULE,
    resolve["map_get"],
    "Output",
    "RasterizationGrid3D",
    USER_RASTER,
):
    changes.append("resolve-mapget:" + USER_RASTER)
if ensure_pin(
    RESOLVE_MODULE,
    resolve["hlsl"],
    "Input",
    "RasterizationGrid3D",
    "DensityRaster",
):
    changes.append("resolve-hlsl:DensityRaster")
ensure_connection(
    RESOLVE_MODULE,
    resolve["map_get"],
    USER_RASTER,
    resolve["hlsl"],
    "DensityRaster",
)

resolve_code = r"""// Resolve atomic density into the existing Niagara-owned SimRT.
// TrajectoryGrid remains only the stable 2D dispatch domain for this stage.
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
if (ValidRaster)
{
    DensityRaster.GetIntGridValue(
        CellX, CellY, 0, 0, DensityInt);
}
float Density = (float)DensityInt / 1024.0f;

int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
bool ValidRT = RTW > 0 && RTH > 0;
int DstX = ValidRaster && ValidRT
    ? clamp((int)(((float)CellX + 0.5f) *
        (float)RTW / (float)RasterW), 0, RTW - 1)
    : 0;
int DstY = ValidRaster && ValidRT
    ? clamp((int)(((float)CellY + 0.5f) *
        (float)RTH / (float)RasterH), 0, RTH - 1)
    : 0;
SimRT.SetRenderTargetValue(
    ValidRaster && ValidRT,
    DstX,
    DstY,
    float4(Density, Density, Density, Density));
OutMark = Density;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    RESOLVE_MODULE,
    resolve["hlsl"],
    resolve_code,
):
    raise RuntimeError("Failed to install atomic resolve HLSL")

first_apply = bool(SERVICE.apply_changes(SYSTEM))
first_messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
if not first_apply or first_messages:
    raise RuntimeError(
        "Atomic Gaussian graph compile failed: " + repr(first_messages)
    )

# Apply the high-quality grid shape to every authored/default DI clone
# associated with this V2 system. Attribute count and reset value use the
# RasterizationGrid3D defaults (1 and 0). Accumulation is explicitly Q10 in
# HLSL, so it does not depend on the subclass Precision property.
raster_dis = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if (
        SYSTEM not in path
        or data_interface.get_class().get_name()
        != "NiagaraDataInterfaceRasterizationGrid3D"
    ):
        continue
    data_interface.set_editor_property(
        "num_cells", unreal.IntVector(2048, 2048, 1)
    )
    data_interface.set_editor_property(
        "clear_before_non_iteration_stage", True
    )
    raster_dis.append(path)

if not raster_dis:
    raise RuntimeError(
        "No V2 RasterizationGrid3D DI was generated for " + USER_RASTER
    )

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False))
result = {
    "changes": changes,
    "rasterDataInterfaces": raster_dis,
    "grid": [2048, 2048, 1],
    "densityQuantization": 1024,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}
print("V2_ATOMIC_GAUSSIAN=" + json.dumps(result, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("V2 atomic Gaussian gate failed: " + repr(result))
