import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
MATERIAL_PATH = ROOT + "/M_SSPR_ParticleTrails_FluidV2"
INSTANCE_PATH = ROOT + "/MI_SSPR_ParticleTrails_FluidV2_HQ"
RAW_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_RawDensity"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
RESOLVE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"
PYRAMID_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity"
LIGHTING_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_DensityGradientLighting"
EDGE_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_ScreenEdgeMask"


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed connection {} -> {}".format(source_output, target_input)
        )


def scalar(material, name, value, x, y, group):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    try:
        node.set_editor_property("group", group)
    except Exception:
        pass
    return node


def create_function_call(material_path, function_path, x, y):
    lib = unreal.MaterialEditingLibrary
    material = unreal.load_asset(material_path)
    before = {
        expression.get_path_name()
        for expression in lib.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        material_path, function_path, x, y
    )
    if not str(info.id):
        raise RuntimeError("Failed function call " + function_path)
    candidates = [
        expression
        for expression in lib.get_material_expressions(material)
        if expression.get_path_name() not in before
        and isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
    ]
    if len(candidates) != 1:
        raise RuntimeError("Could not identify function call " + function_path)
    return candidates[0]


def parameter_summary(material):
    result = []
    for expression in unreal.MaterialEditingLibrary.get_material_expressions(material):
        try:
            name = str(expression.get_editor_property("parameter_name"))
        except Exception:
            continue
        if name and name != "None":
            result.append(
                {"name": name, "type": expression.get_class().get_name()}
            )
    return sorted(result, key=lambda row: (row["name"], row["type"]))


def main():
    for path in (
        RAW_PATH,
        SHAPE_PATH,
        RESOLVE_PATH,
        PYRAMID_PATH,
        LIGHTING_PATH,
        EDGE_PATH,
    ):
        if not isinstance(unreal.load_asset(path), unreal.MaterialFunction):
            raise RuntimeError("Required V2 material function is missing: " + path)
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        raise RuntimeError("Refusing to rebuild published V2 material in place")
    if unreal.EditorAssetLibrary.does_asset_exist(INSTANCE_PATH):
        raise RuntimeError("V2 material instance unexpectedly already exists")

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_ParticleTrails_FluidV2",
        ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Failed to create V2 display material")

    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    try:
        material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )
    except Exception:
        pass
    material.set_editor_property("two_sided", True)
    material.set_editor_property("disable_depth_test", True)

    lib = unreal.MaterialEditingLibrary
    default_texture = unreal.load_asset("/Engine/EngineResources/Black.Black")
    texture = lib.create_material_expression(
        material, unreal.MaterialExpressionTextureObjectParameter, -2550, -620
    )
    texture.set_editor_property("parameter_name", "TrajectoryTexture")
    texture.set_editor_property("texture", default_texture)
    try:
        texture.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
        )
        texture.set_editor_property("group", "00 Input")
    except Exception:
        pass

    screen = lib.create_material_expression(
        material, unreal.MaterialExpressionScreenPosition, -2550, -420
    )
    texel = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -2550, -220
    )
    texel.set_editor_property("parameter_name", "SSPR_InvTextureSize")
    texel.set_editor_property(
        "default_value",
        unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
    )
    try:
        texel.set_editor_property("group", "00 Input")
    except Exception:
        pass

    params = {
        "SmallRadiusPx": scalar(material, "SmallRadiusPx", 10.0, -2550, 20, "10 Mip Reconstruction"),
        "LargeRadiusPx": scalar(material, "LargeRadiusPx", 36.0, -2550, 160, "10 Mip Reconstruction"),
        "SmallMipBias": scalar(material, "SmallMipBias", -0.25, -2550, 300, "10 Mip Reconstruction"),
        "LargeMipBias": scalar(material, "LargeMipBias", 0.20, -2550, 440, "10 Mip Reconstruction"),
        "CoreWeight": scalar(material, "CoreWeight", 0.03, -1580, 280, "20 Density Shape"),
        "SmallWeight": scalar(material, "SmallWeight", 0.32, -1580, 420, "20 Density Shape"),
        "LargeWeight": scalar(material, "LargeWeight", 0.65, -1580, 560, "20 Density Shape"),
        "DetailStrength": scalar(material, "DetailStrength", 0.035, -1580, 700, "20 Density Shape"),
        "EdgeStrength": scalar(material, "EdgeStrength", 0.015, -1580, 840, "20 Density Shape"),
        "BlackPoint": scalar(material, "BlackPoint", 0.0, -1580, 980, "20 Density Shape"),
        "TrajectoryGain": scalar(material, "TrajectoryGain", 14.0, -1580, 1120, "20 Density Shape"),
        "Contrast": scalar(material, "Contrast", 0.42, -1580, 1260, "20 Density Shape"),
        "EdgeFadeWidthPx": scalar(material, "EdgeFadeWidthPx", 24.0, -880, 1080, "25 Boundary"),
        "LightingMipLevel": scalar(material, "LightingMipLevel", 3.5, -880, 460, "30 Volume Lighting"),
        "LightingGradientRadius": scalar(material, "LightingGradientRadius", 1.25, -880, 600, "30 Volume Lighting"),
        "LightingGradientStrength": scalar(material, "LightingGradientStrength", 18.0, -880, 740, "30 Volume Lighting"),
        "AmbientLight": scalar(material, "AmbientLight", 0.42, -880, 880, "30 Volume Lighting"),
        "LightStrength": scalar(material, "LightStrength", 0.78, -880, 1020, "30 Volume Lighting"),
        "Extinction": scalar(material, "Extinction", 2.4, 180, 500, "40 Smoke Resolve"),
        "OpacityScale": scalar(material, "OpacityScale", 0.78, 180, 640, "40 Smoke Resolve"),
        "EmissiveStrength": scalar(material, "EmissiveStrength", 0.78, 180, 780, "40 Smoke Resolve"),
        "DebugRaw": scalar(material, "DebugRaw", 0.0, -120, 1100, "90 Debug"),
    }

    smoke_color = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, 180, 300
    )
    smoke_color.set_editor_property("parameter_name", "SmokeColor")
    smoke_color.set_editor_property(
        "default_value", unreal.LinearColor(0.48, 0.55, 0.68, 1.0)
    )
    light_direction = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -880, 300
    )
    light_direction.set_editor_property("parameter_name", "LightDirection")
    light_direction.set_editor_property(
        "default_value", unreal.LinearColor(-0.65, -0.75, 0.0, 0.0)
    )
    for node, group in (
        (smoke_color, "40 Smoke Resolve"),
        (light_direction, "30 Volume Lighting"),
    ):
        try:
            node.set_editor_property("group", group)
        except Exception:
            pass

    raw = create_function_call(MATERIAL_PATH, RAW_PATH, -1580, -600)
    pyramid = create_function_call(MATERIAL_PATH, PYRAMID_PATH, -1580, -200)
    shape = create_function_call(MATERIAL_PATH, SHAPE_PATH, -880, -160)
    density_select = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -120, -100
    )
    edge = create_function_call(MATERIAL_PATH, EDGE_PATH, -880, 1160)
    masked_density = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 280, -80
    )
    resolve = create_function_call(MATERIAL_PATH, RESOLVE_PATH, 650, 120)
    lighting = create_function_call(MATERIAL_PATH, LIGHTING_PATH, -120, 420)
    lit_color = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1260, 120
    )

    connect(texture, "", raw, "SourceTexture")
    connect(screen, "ViewportUV", raw, "UV")
    connect(params["TrajectoryGain"], "", raw, "Gain")

    connect(texture, "", pyramid, "SourceTexture")
    connect(screen, "ViewportUV", pyramid, "UV")
    connect(texel, "", pyramid, "TexelSize")
    for name in (
        "SmallRadiusPx",
        "LargeRadiusPx",
        "SmallMipBias",
        "LargeMipBias",
    ):
        connect(params[name], "", pyramid, name)

    connect(pyramid, "Scales", shape, "Scales")
    for input_name, parameter_name in (
        ("CoreWeight", "CoreWeight"),
        ("SmallWeight", "SmallWeight"),
        ("LargeWeight", "LargeWeight"),
        ("DetailStrength", "DetailStrength"),
        ("EdgeStrength", "EdgeStrength"),
        ("BlackPoint", "BlackPoint"),
        ("DensityGain", "TrajectoryGain"),
        ("Contrast", "Contrast"),
    ):
        connect(params[parameter_name], "", shape, input_name)

    connect(shape, "Density", density_select, "A")
    connect(raw, "Density", density_select, "B")
    connect(params["DebugRaw"], "", density_select, "Alpha")

    connect(screen, "ViewportUV", edge, "UV")
    connect(texel, "", edge, "TexelSize")
    connect(params["EdgeFadeWidthPx"], "", edge, "FadeWidthPx")
    connect(density_select, "", masked_density, "A")
    connect(edge, "Mask", masked_density, "B")

    connect(masked_density, "", resolve, "Density")
    connect(smoke_color, "", resolve, "SmokeColor")
    for name in ("Extinction", "OpacityScale", "EmissiveStrength"):
        connect(params[name], "", resolve, name)

    connect(texture, "", lighting, "SourceTexture")
    connect(screen, "ViewportUV", lighting, "UV")
    connect(texel, "", lighting, "TexelSize")
    connect(params["LightingMipLevel"], "", lighting, "LightingMipLevel")
    connect(params["LightingGradientRadius"], "", lighting, "GradientRadius")
    connect(params["LightingGradientStrength"], "", lighting, "GradientStrength")
    connect(light_direction, "", lighting, "LightDirection")
    connect(params["AmbientLight"], "", lighting, "Ambient")
    connect(params["LightStrength"], "", lighting, "LightStrength")

    connect(resolve, "Color", lit_color, "A")
    connect(lighting, "Lighting", lit_color, "B")
    if not lib.connect_material_property(
        lit_color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Failed V2 emissive connection")
    if not lib.connect_material_property(
        resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed V2 opacity connection")

    usage_enabled = False
    try:
        usage_enabled = bool(
            lib.set_material_usage(
                material, unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES
            )
        )
    except Exception:
        try:
            material.set_editor_property("used_with_niagara_sprites", True)
            usage_enabled = True
        except Exception:
            pass

    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False):
        raise RuntimeError("Failed to save V2 material")
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    if not diagnostics.is_compiled_ok or diagnostics.compile_errors:
        raise RuntimeError(
            "V2 material compile failed: "
            + repr([str(value) for value in diagnostics.compile_errors])
        )

    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_SSPR_ParticleTrails_FluidV2_HQ",
        ROOT,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Failed to create V2 HQ material instance")
    instance.set_editor_property("parent", material)
    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save V2 HQ material instance")

    print(
        "M3_HQ_FLUID_V2_MATERIAL="
        + json.dumps(
            {
                "material": material.get_path_name(),
                "instance": instance.get_path_name(),
                "compiled": bool(diagnostics.is_compiled_ok),
                "compileErrors": [
                    str(value) for value in diagnostics.compile_errors
                ],
                "expressions": len(lib.get_material_expressions(material)),
                "parameters": parameter_summary(material),
                "usageEnabled": usage_enabled,
            },
            sort_keys=True,
        )
    )


main()
