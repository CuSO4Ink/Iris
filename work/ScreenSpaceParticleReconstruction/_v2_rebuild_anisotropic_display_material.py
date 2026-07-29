import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_Display"
INSTANCE_PATH = ROOT + "/MI_SSPR_AnisotropicSplat_HQ"
FUNCTION_ROOT = ROOT + "/Functions/AnisotropicSplat"
RAW_PATH = FUNCTION_ROOT + "/MF_SSPR_RawAnisotropicDensity"
BODY_PATH = FUNCTION_ROOT + "/MF_SSPR_MipBodyDensity"
BLEND_PATH = FUNCTION_ROOT + "/MF_SSPR_FilamentBodyBlend"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
RESOLVE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"
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
            result.append(name)
    return sorted(result)


def main():
    for path in (
        RAW_PATH,
        BODY_PATH,
        BLEND_PATH,
        SHAPE_PATH,
        RESOLVE_PATH,
        LIGHTING_PATH,
        EDGE_PATH,
    ):
        if not isinstance(unreal.load_asset(path), unreal.MaterialFunction):
            raise RuntimeError("Missing material function: " + path)

    material = unreal.load_asset(MATERIAL_PATH)
    instance = unreal.load_asset(INSTANCE_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing V2 material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("Missing V2 material instance")

    lib = unreal.MaterialEditingLibrary
    for expression in list(lib.get_material_expressions(material)):
        lib.delete_material_expression(material, expression)

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

    default_texture = unreal.load_asset("/Engine/EngineResources/Black.Black")
    texture = lib.create_material_expression(
        material, unreal.MaterialExpressionTextureObjectParameter, -2920, -700
    )
    texture.set_editor_property("parameter_name", "TrajectoryTexture")
    texture.set_editor_property("texture", default_texture)
    try:
        texture.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
        )
        texture.set_editor_property("group", "00 Niagara Input")
    except Exception:
        pass

    screen = lib.create_material_expression(
        material, unreal.MaterialExpressionScreenPosition, -2920, -480
    )
    texel = vector(
        material,
        "SSPR_InvTextureSize",
        unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
        -2920,
        -260,
        "00 Niagara Input",
    )

    params = {
        "AS_InputGain": scalar(material, "AS_InputGain", 1.0, -2920, 20, "10 Filament Input"),
        "AS_MediumRadiusPx": scalar(material, "AS_MediumRadiusPx", 8.0, -2920, 180, "20 Mip Body"),
        "AS_BodyRadiusPx": scalar(material, "AS_BodyRadiusPx", 28.0, -2920, 340, "20 Mip Body"),
        "AS_MediumMipBias": scalar(material, "AS_MediumMipBias", -0.25, -2920, 500, "20 Mip Body"),
        "AS_BodyMipBias": scalar(material, "AS_BodyMipBias", 0.15, -2920, 660, "20 Mip Body"),
        "AS_RidgeStrength": scalar(material, "AS_RidgeStrength", 0.75, -2020, 540, "30 Layer Blend"),
        "AS_FilamentWeight": scalar(material, "AS_FilamentWeight", 0.58, -1250, 200, "30 Layer Blend"),
        "AS_MediumWeight": scalar(material, "AS_MediumWeight", 0.27, -1250, 350, "30 Layer Blend"),
        "AS_BodyWeight": scalar(material, "AS_BodyWeight", 0.15, -1250, 500, "30 Layer Blend"),
        "AS_DetailStrength": scalar(material, "AS_DetailStrength", 0.18, -1250, 650, "40 Density Shape"),
        "AS_EdgeStrength": scalar(material, "AS_EdgeStrength", 0.04, -1250, 800, "40 Density Shape"),
        "AS_BlackPoint": scalar(material, "AS_BlackPoint", 0.002, -1250, 950, "40 Density Shape"),
        "AS_DensityGain": scalar(material, "AS_DensityGain", 1.20, -1250, 1100, "40 Density Shape"),
        "AS_Contrast": scalar(material, "AS_Contrast", 0.72, -1250, 1250, "40 Density Shape"),
        "AS_EdgeFadeWidthPx": scalar(material, "AS_EdgeFadeWidthPx", 20.0, -480, 1060, "45 Boundary"),
        "AS_LightingMipLevel": scalar(material, "AS_LightingMipLevel", 3.0, -480, 300, "50 Volume Lighting"),
        "AS_LightingGradientRadius": scalar(material, "AS_LightingGradientRadius", 1.25, -480, 450, "50 Volume Lighting"),
        "AS_LightingGradientStrength": scalar(material, "AS_LightingGradientStrength", 10.0, -480, 600, "50 Volume Lighting"),
        "AS_AmbientLight": scalar(material, "AS_AmbientLight", 0.45, -480, 750, "50 Volume Lighting"),
        "AS_LightStrength": scalar(material, "AS_LightStrength", 0.65, -480, 900, "50 Volume Lighting"),
        "AS_Extinction": scalar(material, "AS_Extinction", 2.20, 520, 390, "60 Smoke Resolve"),
        "AS_OpacityScale": scalar(material, "AS_OpacityScale", 0.85, 520, 540, "60 Smoke Resolve"),
        "AS_EmissiveStrength": scalar(material, "AS_EmissiveStrength", 0.85, 520, 690, "60 Smoke Resolve"),
        "AS_DebugRaw": scalar(material, "AS_DebugRaw", 0.0, 120, 1050, "90 Debug"),
    }
    smoke_color = vector(
        material,
        "AS_SmokeColor",
        unreal.LinearColor(0.50, 0.56, 0.65, 1.0),
        520,
        220,
        "60 Smoke Resolve",
    )
    light_direction = vector(
        material,
        "AS_LightDirection",
        unreal.LinearColor(-0.65, -0.75, 0.0, 0.0),
        -480,
        140,
        "50 Volume Lighting",
    )

    raw = create_function_call(MATERIAL_PATH, RAW_PATH, -2020, -650)
    mip_body = create_function_call(MATERIAL_PATH, BODY_PATH, -2020, -180)
    blend = create_function_call(MATERIAL_PATH, BLEND_PATH, -1250, -400)
    shape = create_function_call(MATERIAL_PATH, SHAPE_PATH, -480, -360)
    debug_select = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 120, -260
    )
    edge = create_function_call(MATERIAL_PATH, EDGE_PATH, 120, 850)
    masked_density = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 520, -220
    )
    lighting = create_function_call(MATERIAL_PATH, LIGHTING_PATH, 120, 250)
    resolve = create_function_call(MATERIAL_PATH, RESOLVE_PATH, 950, -80)
    lit_color = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1510, -80
    )

    connect(texture, "", raw, "SourceTexture")
    connect(screen, "ViewportUV", raw, "UV")
    connect(texel, "", raw, "TexelSize")
    connect(params["AS_InputGain"], "", raw, "InputGain")

    connect(texture, "", mip_body, "SourceTexture")
    connect(screen, "ViewportUV", mip_body, "UV")
    connect(texel, "", mip_body, "TexelSize")
    for input_name, param_name in (
        ("MediumRadiusPx", "AS_MediumRadiusPx"),
        ("BodyRadiusPx", "AS_BodyRadiusPx"),
        ("MediumMipBias", "AS_MediumMipBias"),
        ("BodyMipBias", "AS_BodyMipBias"),
    ):
        connect(params[param_name], "", mip_body, input_name)

    connect(raw, "Density", blend, "RawDensity")
    connect(mip_body, "BodyScales", blend, "BodyScales")
    connect(params["AS_RidgeStrength"], "", blend, "RidgeStrength")

    connect(blend, "Layers", shape, "Scales")
    for input_name, param_name in (
        ("CoreWeight", "AS_FilamentWeight"),
        ("SmallWeight", "AS_MediumWeight"),
        ("LargeWeight", "AS_BodyWeight"),
        ("DetailStrength", "AS_DetailStrength"),
        ("EdgeStrength", "AS_EdgeStrength"),
        ("BlackPoint", "AS_BlackPoint"),
        ("DensityGain", "AS_DensityGain"),
        ("Contrast", "AS_Contrast"),
    ):
        connect(params[param_name], "", shape, input_name)

    connect(shape, "Density", debug_select, "A")
    connect(raw, "Density", debug_select, "B")
    connect(params["AS_DebugRaw"], "", debug_select, "Alpha")

    connect(screen, "ViewportUV", edge, "UV")
    connect(texel, "", edge, "TexelSize")
    connect(params["AS_EdgeFadeWidthPx"], "", edge, "FadeWidthPx")
    connect(debug_select, "", masked_density, "A")
    connect(edge, "Mask", masked_density, "B")

    connect(texture, "", lighting, "SourceTexture")
    connect(screen, "ViewportUV", lighting, "UV")
    connect(texel, "", lighting, "TexelSize")
    for input_name, param_name in (
        ("LightingMipLevel", "AS_LightingMipLevel"),
        ("GradientRadius", "AS_LightingGradientRadius"),
        ("GradientStrength", "AS_LightingGradientStrength"),
        ("Ambient", "AS_AmbientLight"),
        ("LightStrength", "AS_LightStrength"),
    ):
        connect(params[param_name], "", lighting, input_name)
    connect(light_direction, "", lighting, "LightDirection")

    connect(masked_density, "", resolve, "Density")
    connect(smoke_color, "", resolve, "SmokeColor")
    connect(params["AS_Extinction"], "", resolve, "Extinction")
    connect(params["AS_OpacityScale"], "", resolve, "OpacityScale")
    connect(params["AS_EmissiveStrength"], "", resolve, "EmissiveStrength")

    connect(resolve, "Color", lit_color, "A")
    connect(lighting, "Lighting", lit_color, "B")
    if not lib.connect_material_property(
        lit_color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Failed emissive connection")
    if not lib.connect_material_property(
        resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed opacity connection")

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
        raise RuntimeError("Failed to save V2 display material")
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    if not diagnostics.is_compiled_ok or diagnostics.compile_errors:
        raise RuntimeError(
            "V2 display material compile failed: "
            + repr([str(value) for value in diagnostics.compile_errors])
        )

    instance.set_editor_property("parent", material)
    try:
        lib.clear_all_material_instance_parameters(instance)
    except Exception:
        pass
    scalar_defaults = {
        name: float(node.get_editor_property("default_value"))
        for name, node in params.items()
    }
    for name, value in scalar_defaults.items():
        lib.set_material_instance_scalar_parameter_value(instance, name, value)
    lib.set_material_instance_vector_parameter_value(
        instance,
        "SSPR_InvTextureSize",
        unreal.LinearColor(1.0 / 2048.0, 1.0 / 2048.0, 0.0, 0.0),
    )
    lib.set_material_instance_vector_parameter_value(
        instance,
        "AS_SmokeColor",
        unreal.LinearColor(0.50, 0.56, 0.65, 1.0),
    )
    lib.set_material_instance_vector_parameter_value(
        instance,
        "AS_LightDirection",
        unreal.LinearColor(-0.65, -0.75, 0.0, 0.0),
    )
    if not unreal.EditorAssetLibrary.save_asset(INSTANCE_PATH, False):
        raise RuntimeError("Failed to save V2 material instance")

    print("V2_ANISOTROPIC_MATERIAL=" + json.dumps({
        "material": material.get_path_name(),
        "instance": instance.get_path_name(),
        "compiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [str(value) for value in diagnostics.compile_errors],
        "expressionCount": len(lib.get_material_expressions(material)),
        "parameters": parameter_summary(material),
    }, sort_keys=True))


main()
