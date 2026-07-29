import json
import unreal

FOLDER = "/Game/SSPR_Validation/M2"
SOURCE_RT = "/Game/SSPR_Validation/M2/RT_SSPR_Current"
RT_NAMES = (
    "RT_SSPR_Core",
    "RT_SSPR_BlurSmall",
    "RT_SSPR_BlurLarge",
    "RT_SSPR_Density",
)

lib = unreal.MaterialEditingLibrary


def load_or_create_rt(name):
    path = FOLDER + "/" + name
    asset = unreal.load_asset(path)
    created = False
    if asset is None:
        asset = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_RT, path)
        created = True
    if not isinstance(asset, unreal.TextureRenderTarget2D):
        raise RuntimeError(path + " is missing or has the wrong class")
    asset.set_editor_property("size_x", 256)
    asset.set_editor_property("size_y", 256)
    asset.set_editor_property(
        "render_target_format",
        unreal.TextureRenderTargetFormat.RTF_R16F,
    )
    asset.set_editor_property(
        "clear_color",
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
    )
    asset.set_editor_property("auto_generate_mips", False)
    asset.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return asset, created


def create_material(name, description, textures, scalars, code):
    path = FOLDER + "/" + name
    material = unreal.load_asset(path)
    created = False
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name,
            FOLDER,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        created = True
    if not isinstance(material, unreal.Material):
        raise RuntimeError(path + " is missing or has the wrong class")

    expressions = list(lib.get_material_expressions(material))
    if expressions:
        custom_nodes = [
            item
            for item in expressions
            if isinstance(item, unreal.MaterialExpressionCustom)
        ]
        if (
            len(custom_nodes) == 1
            and custom_nodes[0].get_editor_property("description") == description
        ):
            lib.recompile_material(material)
            if not unreal.EditorAssetLibrary.save_asset(path, False):
                raise RuntimeError("Failed to save existing " + path)
            return material, created
        raise RuntimeError(
            path + " has an unexpected graph; refusing to overwrite it"
        )

    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    try:
        material.set_editor_property(
            "shading_model",
            unreal.MaterialShadingModel.MSM_UNLIT,
        )
    except Exception:
        pass

    texture_nodes = {}
    y = -420
    for parameter_name, default_texture in textures:
        expression = lib.create_material_expression(
            material,
            unreal.MaterialExpressionTextureObjectParameter,
            -1050,
            y,
        )
        expression.set_editor_property("parameter_name", parameter_name)
        expression.set_editor_property("texture", default_texture)
        expression.set_editor_property(
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
        )
        texture_nodes[parameter_name] = expression
        y += 180

    uv = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureCoordinate,
        -1050,
        y,
    )
    uv.set_editor_property("coordinate_index", 0)
    y += 150

    scalar_nodes = {}
    for parameter_name, default_value in scalars:
        expression = lib.create_material_expression(
            material,
            unreal.MaterialExpressionScalarParameter,
            -1050,
            y,
        )
        expression.set_editor_property("parameter_name", parameter_name)
        expression.set_editor_property("default_value", float(default_value))
        scalar_nodes[parameter_name] = expression
        y += 110

    custom = lib.create_material_expression(
        material,
        unreal.MaterialExpressionCustom,
        -320,
        0,
    )
    custom.set_editor_property("description", description)
    custom.set_editor_property(
        "output_type",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
    )
    input_names = (
        [item[0] for item in textures]
        + ["UV"]
        + [item[0] for item in scalars]
    )
    inputs = []
    for input_name in input_names:
        custom_input = unreal.CustomInput()
        custom_input.set_editor_property("input_name", input_name)
        inputs.append(custom_input)
    custom.set_editor_property("inputs", inputs)
    custom.set_editor_property("code", code.strip())

    for parameter_name, expression in texture_nodes.items():
        if not lib.connect_material_expressions(
            expression, "", custom, parameter_name
        ):
            raise RuntimeError("Failed texture connection " + parameter_name)
    if not lib.connect_material_expressions(uv, "", custom, "UV"):
        raise RuntimeError("Failed UV connection")
    for parameter_name, expression in scalar_nodes.items():
        if not lib.connect_material_expressions(
            expression, "", custom, parameter_name
        ):
            raise RuntimeError("Failed scalar connection " + parameter_name)
    if not lib.connect_material_property(
        custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Failed to connect " + name + " to Emissive")

    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return material, created


unreal.EditorAssetLibrary.make_directory(FOLDER)
source_rt = unreal.load_asset(SOURCE_RT)
history_rt = unreal.load_asset(FOLDER + "/RT_SSPR_HistoryA")
if not isinstance(source_rt, unreal.TextureRenderTarget2D):
    raise RuntimeError("M2 Current RT is missing")
if not isinstance(history_rt, unreal.TextureRenderTarget2D):
    raise RuntimeError("M2 History RT is missing")

rts = {}
created_assets = []
for rt_name in RT_NAMES:
    rt, created = load_or_create_rt(rt_name)
    rts[rt_name] = rt
    if created:
        created_assets.append(rt.get_path_name())

core_material, created = create_material(
    "M_SSPR_CoreExtract",
    "SSPR M2-B core extraction",
    (("SourceTexture", history_rt),),
    (
        ("CoreLow", 0.08),
        ("CoreHigh", 0.58),
    ),
    r"""
float source = Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV, 0).r;
float lowValue = min(CoreLow, CoreHigh - 1.0e-4f);
float highValue = max(CoreHigh, lowValue + 1.0e-4f);
float core = smoothstep(lowValue, highValue, source);
return float3(core, 0.0f, 0.0f);
""",
)
if created:
    created_assets.append(core_material.get_path_name())

small_material, created = create_material(
    "M_SSPR_BlurSmall",
    "SSPR M2-B fixed 9 tap small blur",
    (("SourceTexture", history_rt),),
    (
        ("RadiusPx", 3.0),
        ("InvResolution", 1.0 / 256.0),
    ),
    r"""
float2 d = float2(
    max(RadiusPx, 0.0f) * max(InvResolution, 1.0e-6f),
    max(RadiusPx, 0.0f) * max(InvResolution, 1.0e-6f));
float result = Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV, 0).r * 0.25f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x, 0), 0).r * 0.125f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x, 0), 0).r * 0.125f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0,  d.y), 0).r * 0.125f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0, -d.y), 0).r * 0.125f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x,  d.y) * 0.7071f, 0).r * 0.0625f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x,  d.y) * 0.7071f, 0).r * 0.0625f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x, -d.y) * 0.7071f, 0).r * 0.0625f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x, -d.y) * 0.7071f, 0).r * 0.0625f;
return float3(saturate(result), 0.0f, 0.0f);
""",
)
if created:
    created_assets.append(small_material.get_path_name())

large_material, created = create_material(
    "M_SSPR_BlurLarge",
    "SSPR M2-B fixed 13 tap large blur",
    (("SourceTexture", history_rt),),
    (
        ("RadiusPx", 11.0),
        ("InvResolution", 1.0 / 256.0),
    ),
    r"""
float2 d = float2(
    max(RadiusPx, 0.0f) * max(InvResolution, 1.0e-6f),
    max(RadiusPx, 0.0f) * max(InvResolution, 1.0e-6f));
float2 h = d * 0.5f;
float result = Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV, 0).r * 0.16f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x, 0), 0).r * 0.10f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x, 0), 0).r * 0.10f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0,  d.y), 0).r * 0.10f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0, -d.y), 0).r * 0.10f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x,  d.y) * 0.7071f, 0).r * 0.07f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x,  d.y) * 0.7071f, 0).r * 0.07f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( d.x, -d.y) * 0.7071f, 0).r * 0.07f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-d.x, -d.y) * 0.7071f, 0).r * 0.07f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2( h.x, 0), 0).r * 0.04f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(-h.x, 0), 0).r * 0.04f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0,  h.y), 0).r * 0.04f;
result += Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, UV + float2(0, -h.y), 0).r * 0.04f;
return float3(saturate(result), 0.0f, 0.0f);
""",
)
if created:
    created_assets.append(large_material.get_path_name())

density_material, created = create_material(
    "M_SSPR_DensityCombine",
    "SSPR M2-B core small large density combine",
    (
        ("CoreTexture", rts["RT_SSPR_Core"]),
        ("SmallTexture", rts["RT_SSPR_BlurSmall"]),
        ("LargeTexture", rts["RT_SSPR_BlurLarge"]),
    ),
    (
        ("CoreWeight", 0.65),
        ("SmallBlurWeight", 0.75),
        ("LargeBlurWeight", 0.30),
        ("DensityGain", 1.0),
        ("DensityLow", 0.06),
        ("DensityHigh", 1.10),
        ("EdgeBreakStrength", 0.08),
        ("NoiseScale", 18.0),
    ),
    r"""
float core = Texture2DSampleLevel(
    CoreTexture, CoreTextureSampler, UV, 0).r;
float smallValue = Texture2DSampleLevel(
    SmallTexture, SmallTextureSampler, UV, 0).r;
float largeValue = Texture2DSampleLevel(
    LargeTexture, LargeTextureSampler, UV, 0).r;

float density = max(CoreWeight, 0.0f) * core;
density += max(SmallBlurWeight, 0.0f) * smallValue;
density += max(LargeBlurWeight, 0.0f) * largeValue;
density *= max(DensityGain, 0.0f);

float scale = max(NoiseScale, 0.1f);
float noiseValue = 0.5f + 0.5f *
    sin((UV.x * scale + View.GameTime * 0.23f) * 6.2831853f) *
    sin((UV.y * scale * 0.83f - View.GameTime * 0.19f) * 6.2831853f);
float edgeFactor = lerp(
    1.0f,
    lerp(0.70f, 1.10f, noiseValue),
    saturate(EdgeBreakStrength));
density *= edgeFactor;

float lowValue = min(DensityLow, DensityHigh - 1.0e-4f);
float highValue = max(DensityHigh, lowValue + 1.0e-4f);
float remapped = smoothstep(lowValue, highValue, density);
return float3(saturate(remapped), 0.0f, 0.0f);
""",
)
if created:
    created_assets.append(density_material.get_path_name())

materials = (
    core_material,
    small_material,
    large_material,
    density_material,
)
result = {
    "created": created_assets,
    "renderTargets": {
        name: {
            "path": asset.get_path_name(),
            "size": [
                int(asset.get_editor_property("size_x")),
                int(asset.get_editor_property("size_y")),
            ],
            "format": str(asset.get_editor_property("render_target_format")),
            "filter": str(asset.get_editor_property("filter")),
        }
        for name, asset in rts.items()
    },
    "materials": {
        asset.get_name(): {
            "path": asset.get_path_name(),
            "expressions": len(lib.get_material_expressions(asset)),
        }
        for asset in materials
    },
}
print("M2B_ASSETS=" + json.dumps(result, sort_keys=True))
