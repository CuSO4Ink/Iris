import json
import unreal

FOLDER = "/Game/SSPR_Validation/M2"
SOURCE_RT = "/Game/SSPR_Validation/M2/RT_SSPR_Density"
SMOKE_RT_PATH = FOLDER + "/RT_SSPR_Smoke"
MATERIAL_PATH = FOLDER + "/M_SSPR_SmokeResolve"

smoke_rt = unreal.load_asset(SMOKE_RT_PATH)
rt_created = False
if smoke_rt is None:
    smoke_rt = unreal.EditorAssetLibrary.duplicate_asset(
        SOURCE_RT,
        SMOKE_RT_PATH,
    )
    rt_created = True
if not isinstance(smoke_rt, unreal.TextureRenderTarget2D):
    raise RuntimeError("Smoke RT is missing or has the wrong class")
smoke_rt.set_editor_property("size_x", 256)
smoke_rt.set_editor_property("size_y", 256)
smoke_rt.set_editor_property(
    "render_target_format",
    unreal.TextureRenderTargetFormat.RTF_RGBA8,
)
smoke_rt.set_editor_property(
    "clear_color",
    unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
)
smoke_rt.set_editor_property("auto_generate_mips", False)
smoke_rt.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
if not unreal.EditorAssetLibrary.save_asset(SMOKE_RT_PATH, False):
    raise RuntimeError("Failed to save Smoke RT")

density_rt = unreal.load_asset(SOURCE_RT)
if not isinstance(density_rt, unreal.TextureRenderTarget2D):
    raise RuntimeError("Density RT is missing")

lib = unreal.MaterialEditingLibrary
material = unreal.load_asset(MATERIAL_PATH)
material_created = False
if material is None:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_SmokeResolve",
        FOLDER,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    material_created = True
if not isinstance(material, unreal.Material):
    raise RuntimeError("Smoke Resolve material is missing or invalid")

expressions = list(lib.get_material_expressions(material))
if expressions:
    descriptions = sorted(
        str(item.get_editor_property("description"))
        for item in expressions
        if isinstance(item, unreal.MaterialExpressionCustom)
    )
    if descriptions != [
        "SSPR M2-C smoke color",
        "SSPR M2-C smoke opacity",
    ]:
        raise RuntimeError(
            "Smoke Resolve contains an unexpected graph; refusing overwrite"
        )
else:
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property(
        "blend_mode",
        unreal.BlendMode.BLEND_TRANSLUCENT,
    )
    try:
        material.set_editor_property(
            "shading_model",
            unreal.MaterialShadingModel.MSM_UNLIT,
        )
    except Exception:
        pass
    try:
        material.set_editor_property("two_sided", True)
    except Exception:
        pass

    density_param = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -1100,
        -300,
    )
    density_param.set_editor_property("parameter_name", "DensityTexture")
    density_param.set_editor_property("texture", density_rt)
    density_param.set_editor_property(
        "sampler_type",
        unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )

    uv = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureCoordinate,
        -1100,
        -100,
    )
    uv.set_editor_property("coordinate_index", 0)

    scalar_specs = (
        ("Extinction", 2.6, -1100, 80),
        ("DensityScale", 1.0, -1100, 190),
        ("OpacityScale", 0.82, -1100, 300),
        ("EmissiveStrength", 1.0, -1100, 410),
        ("BlackPoint", 0.015, -1100, 520),
    )
    scalar_nodes = {}
    for name, default_value, x, y in scalar_specs:
        expression = lib.create_material_expression(
            material,
            unreal.MaterialExpressionScalarParameter,
            x,
            y,
        )
        expression.set_editor_property("parameter_name", name)
        expression.set_editor_property("default_value", default_value)
        scalar_nodes[name] = expression

    color_param = lib.create_material_expression(
        material,
        unreal.MaterialExpressionVectorParameter,
        -1100,
        650,
    )
    color_param.set_editor_property("parameter_name", "SmokeColor")
    color_param.set_editor_property(
        "default_value",
        unreal.LinearColor(0.62, 0.72, 0.82, 1.0),
    )

    color_custom = lib.create_material_expression(
        material,
        unreal.MaterialExpressionCustom,
        -340,
        -120,
    )
    color_custom.set_editor_property("description", "SSPR M2-C smoke color")
    color_custom.set_editor_property(
        "output_type",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
    )
    color_input_names = (
        "DensityTexture",
        "UV",
        "Extinction",
        "DensityScale",
        "EmissiveStrength",
        "BlackPoint",
        "SmokeColor",
    )
    color_inputs = []
    for input_name in color_input_names:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", input_name)
        color_inputs.append(item)
    color_custom.set_editor_property("inputs", color_inputs)
    color_custom.set_editor_property(
        "code",
        r"""
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, UV, 0).r;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
float3 color = max(SmokeColor.rgb, 0.0f);
return color * alpha * max(EmissiveStrength, 0.0f);
""".strip(),
    )

    opacity_custom = lib.create_material_expression(
        material,
        unreal.MaterialExpressionCustom,
        -340,
        260,
    )
    opacity_custom.set_editor_property(
        "description",
        "SSPR M2-C smoke opacity",
    )
    opacity_custom.set_editor_property(
        "output_type",
        unreal.CustomMaterialOutputType.CMOT_FLOAT1,
    )
    opacity_input_names = (
        "DensityTexture",
        "UV",
        "Extinction",
        "DensityScale",
        "OpacityScale",
        "BlackPoint",
    )
    opacity_inputs = []
    for input_name in opacity_input_names:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", input_name)
        opacity_inputs.append(item)
    opacity_custom.set_editor_property("inputs", opacity_inputs)
    opacity_custom.set_editor_property(
        "code",
        r"""
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, UV, 0).r;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
return saturate(alpha * max(OpacityScale, 0.0f));
""".strip(),
    )

    for custom, names in (
        (color_custom, color_input_names),
        (opacity_custom, opacity_input_names),
    ):
        for input_name in names:
            if input_name == "DensityTexture":
                source = density_param
            elif input_name == "UV":
                source = uv
            elif input_name == "SmokeColor":
                source = color_param
            else:
                source = scalar_nodes[input_name]
            if not lib.connect_material_expressions(
                source,
                "",
                custom,
                input_name,
            ):
                raise RuntimeError("Failed Resolve input " + input_name)

    if not lib.connect_material_property(
        color_custom,
        "",
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    ):
        raise RuntimeError("Failed Resolve Emissive connection")
    if not lib.connect_material_property(
        opacity_custom,
        "",
        unreal.MaterialProperty.MP_OPACITY,
    ):
        raise RuntimeError("Failed Resolve Opacity connection")

    lib.layout_material_expressions(material)

lib.recompile_material(material)
if not unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False):
    raise RuntimeError("Failed to save Smoke Resolve material")

result = {
    "created": {
        "rt": rt_created,
        "material": material_created,
    },
    "renderTarget": {
        "path": smoke_rt.get_path_name(),
        "size": [
            int(smoke_rt.get_editor_property("size_x")),
            int(smoke_rt.get_editor_property("size_y")),
        ],
        "format": str(smoke_rt.get_editor_property("render_target_format")),
    },
    "material": {
        "path": material.get_path_name(),
        "expressions": len(lib.get_material_expressions(material)),
        "blendMode": str(material.get_editor_property("blend_mode")),
    },
}
print("M2C_ASSETS=" + json.dumps(result, sort_keys=True))
