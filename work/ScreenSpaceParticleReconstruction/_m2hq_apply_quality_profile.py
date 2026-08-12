import json
import unreal


WIDTH = 2048
HEIGHT = 1152
SYSTEM_PACKAGE = "/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2"
SYSTEM = SYSTEM_PACKAGE + ".NS_SSPR_ProjTest_M2"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
BP_PATH = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
FOLDER = "/Game/SSPR_Validation/M2"
RT_NAMES = (
    "RT_SSPR_Current",
    "RT_SSPR_HistoryA",
    "RT_SSPR_HistoryB",
    "RT_SSPR_Core",
    "RT_SSPR_BlurSmall",
    "RT_SSPR_BlurLarge",
    "RT_SSPR_Density",
    "RT_SSPR_Smoke",
)

SMALL_CODE = r"""
uint width = 1;
uint height = 1;
SourceTexture.GetDimensions(width, height);
float2 textureSize = max(float2(width, height), 1.0f);
float2 invResolution = 1.0f / textureSize;
float2 halfTexel = 0.5f * invResolution;
float2 upper = 1.0f - halfTexel;
float sampleStep = max(RadiusPx, 0.0f) / 2.0f;
float result = 0.0f;
float totalWeight = 0.0f;

[unroll]
for (int y = -2; y <= 2; ++y)
{
    [unroll]
    for (int x = -2; x <= 2; ++x)
    {
        float2 kernelPosition = float2(x, y);
        float weight = exp(
            -dot(kernelPosition, kernelPosition) / (2.0f * 1.10f * 1.10f));
        float2 sampleUV =
            UV + kernelPosition * sampleStep * invResolution;
        bool inBounds =
            all(sampleUV >= halfTexel) && all(sampleUV <= upper);
        result += inBounds
            ? Texture2DSampleLevel(
                SourceTexture,
                SourceTextureSampler,
                clamp(sampleUV, halfTexel, upper),
                0).r * weight
            : 0.0f;
        totalWeight += weight;
    }
}
return float3(
    saturate(result / max(totalWeight, 1.0e-6f)),
    0.0f,
    0.0f);
""".strip()

LARGE_CODE = r"""
uint width = 1;
uint height = 1;
SourceTexture.GetDimensions(width, height);
float2 textureSize = max(float2(width, height), 1.0f);
float2 invResolution = 1.0f / textureSize;
float2 halfTexel = 0.5f * invResolution;
float2 upper = 1.0f - halfTexel;
float sampleStep = max(RadiusPx, 0.0f) / 3.0f;
float result = 0.0f;
float totalWeight = 0.0f;

[unroll]
for (int y = -3; y <= 3; ++y)
{
    [unroll]
    for (int x = -3; x <= 3; ++x)
    {
        float2 kernelPosition = float2(x, y);
        float weight = exp(
            -dot(kernelPosition, kernelPosition) / (2.0f * 1.55f * 1.55f));
        float2 sampleUV =
            UV + kernelPosition * sampleStep * invResolution;
        bool inBounds =
            all(sampleUV >= halfTexel) && all(sampleUV <= upper);
        result += inBounds
            ? Texture2DSampleLevel(
                SourceTexture,
                SourceTextureSampler,
                clamp(sampleUV, halfTexel, upper),
                0).r * weight
            : 0.0f;
        totalWeight += weight;
    }
}
return float3(
    saturate(result / max(totalWeight, 1.0e-6f)),
    0.0f,
    0.0f);
""".strip()

CARD_COLOR_CODE = r"""
uint width = 1;
uint height = 1;
DensityTexture.GetDimensions(width, height);
float2 textureSize = max(float2(width, height), 1.0f);
float2 halfTexel = 0.5f / textureSize;
float2 safeUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, safeUV, 0).r;
float2 edgeDistancePx = min(UV, 1.0f - UV) * textureSize;
float edgeMask = smoothstep(
    0.0f, 8.0f, min(edgeDistancePx.x, edgeDistancePx.y));
density *= edgeMask;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
float3 color = max(SmokeColor.rgb, 0.0f);
return color * alpha * max(EmissiveStrength, 0.0f);
""".strip()

CARD_OPACITY_CODE = r"""
uint width = 1;
uint height = 1;
DensityTexture.GetDimensions(width, height);
float2 textureSize = max(float2(width, height), 1.0f);
float2 halfTexel = 0.5f / textureSize;
float2 safeUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, safeUV, 0).r;
float2 edgeDistancePx = min(UV, 1.0f - UV) * textureSize;
float edgeMask = smoothstep(
    0.0f, 8.0f, min(edgeDistancePx.x, edgeDistancePx.y));
density *= edgeMask;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
return saturate(alpha * max(OpacityScale, 0.0f));
""".strip()


rt_results = {}
for name in RT_NAMES:
    path = FOLDER + "/" + name
    rt = unreal.load_asset(path)
    if not isinstance(rt, unreal.TextureRenderTarget2D):
        raise RuntimeError("Missing M2 RT: " + path)
    rt.set_editor_property("size_x", WIDTH)
    rt.set_editor_property("size_y", HEIGHT)
    rt.set_editor_property(
        "render_target_format",
        (
            unreal.TextureRenderTargetFormat.RTF_RGBA16F
            if name == "RT_SSPR_Smoke"
            else unreal.TextureRenderTargetFormat.RTF_R16F
        ),
    )
    rt.set_editor_property(
        "clear_color",
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    )
    rt.set_editor_property("auto_generate_mips", False)
    rt.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
    rt.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    rt.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    rt_results[name] = {
        "size": [
            int(rt.get_editor_property("size_x")),
            int(rt.get_editor_property("size_y")),
        ],
        "format": str(rt.get_editor_property("render_target_format")),
        "filter": str(rt.get_editor_property("filter")),
    }

grid_objects = [
    grid
    for grid in unreal.ObjectIterator(
        unreal.NiagaraDataInterfaceGrid2DCollection
    )
    if SYSTEM_PACKAGE in grid.get_path_name()
]
if not grid_objects:
    raise RuntimeError("No M2 Grid2DCollection objects found")

source_grid = next(
    (
        grid
        for grid in grid_objects
        if grid.get_path_name().endswith(
            ":NiagaraDataInterfaceGrid2DCollection_0"
        )
    ),
    None,
)
if source_grid is None:
    raise RuntimeError("M2 user Grid2DCollection default was not found")
source_binding = source_grid.get_editor_property(
    "render_target_user_parameter"
)
grid_results = []
for grid in grid_objects:
    grid.set_editor_property("num_cells_x", WIDTH)
    grid.set_editor_property("num_cells_y", HEIGHT)
    grid.set_editor_property("num_cells_max_axis", WIDTH)
    grid.set_editor_property("set_grid_from_max_axis", False)
    grid.set_editor_property("num_attributes", 1)
    grid.set_editor_property("clear_before_non_iteration_stage", True)
    grid.set_editor_property("override_format", False)
    grid.set_editor_property("render_target_user_parameter", source_binding)
    grid_results.append(
        {
            "path": grid.get_path_name(),
            "size": [
                int(grid.get_editor_property("num_cells_x")),
                int(grid.get_editor_property("num_cells_y")),
            ],
        }
    )

scratch = unreal.NiagaraScratchPadService
writer_code = str(
    scratch.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
writer_code = writer_code.replace(
    "const int MaxTrailSteps = 20;",
    "const int MaxTrailSteps = 128;",
)
writer_code = writer_code.replace(
    "const int RadiusSteps = 4;",
    "const int RadiusSteps = 8;",
)
if (
    "const int MaxTrailSteps = 128;" not in writer_code
    or "const int RadiusSteps = 8;" not in writer_code
):
    raise RuntimeError("Writer quality-loop replacement failed")
if not scratch.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    MODULE,
    HLSL_NODE,
    writer_code,
):
    raise RuntimeError("Failed to store HQ Writer HLSL")

applied = bool(scratch.apply_changes(SYSTEM))
compile_messages = [
    str(item)
    for item in scratch.get_compile_messages(SYSTEM, False)
]
system_saved = bool(
    unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False)
)

material_updates = {
    "M_SSPR_BlurSmall": {
        "SSPR M2-B fixed 9 tap small blur": SMALL_CODE,
    },
    "M_SSPR_BlurLarge": {
        "SSPR M2-B fixed 13 tap large blur": LARGE_CODE,
    },
    "M_SSPR_SmokeCard": {
        "SSPR M2-C smoke color": CARD_COLOR_CODE,
        "SSPR M2-C smoke opacity": CARD_OPACITY_CODE,
    },
}
material_results = {}
lib = unreal.MaterialEditingLibrary
for material_name, custom_specs in material_updates.items():
    path = FOLDER + "/" + material_name
    material = unreal.load_asset(path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing M2 material: " + path)
    found = []
    for expression in lib.get_material_expressions(material):
        if not isinstance(expression, unreal.MaterialExpressionCustom):
            continue
        description = str(expression.get_editor_property("description"))
        if description not in custom_specs:
            continue
        expression.set_editor_property(
            "code",
            custom_specs[description],
        )
        found.append(description)
    missing = sorted(set(custom_specs) - set(found))
    if missing:
        raise RuntimeError(
            material_name + " missing Custom nodes: " + repr(missing)
        )
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save material: " + path)
    material_results[material_name] = sorted(found)

bp = unreal.load_asset(BP_PATH)
if bp is None:
    raise RuntimeError("M2 orchestrator Blueprint is missing")
bp_defaults = {
    "SplatRadiusPx": "0.75",
    "TrailTimeSeconds": "0.075",
    "MaxTrailPx": "96.0",
    "SmallBlurRadiusPx": "8.0",
    "LargeBlurRadiusPx": "20.0",
    "CoreWeight": "0.60",
    "SmallBlurWeight": "0.90",
    "LargeBlurWeight": "0.45",
}
bp_default_results = {
    name: bool(
        unreal.BlueprintService.set_variable_default_value(
            BP_PATH,
            name,
            value,
        )
    )
    for name, value in bp_defaults.items()
}
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
bp_saved = bool(unreal.EditorAssetLibrary.save_asset(BP_PATH, False))

result = {
    "qualityResolution": [WIDTH, HEIGHT],
    "renderTargets": rt_results,
    "grids": grid_results,
    "writer": {
        "maxTrailSteps": 128,
        "radiusSteps": 8,
        "applied": applied,
        "compileMessages": compile_messages,
        "saved": system_saved,
    },
    "materials": material_results,
    "blueprintDefaults": bp_default_results,
    "blueprintSaved": bp_saved,
}
print("M2HQ_APPLY=" + json.dumps(result, sort_keys=True))
if (
    not applied
    or compile_messages
    or not system_saved
    or not all(bp_default_results.values())
    or not bp_saved
):
    raise RuntimeError("M2 HQ profile failed: " + repr(result))
