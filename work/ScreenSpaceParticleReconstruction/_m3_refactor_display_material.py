import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
MATERIAL_PATH = ROOT + "/M_SSPR_ParticleTrails_Display"
ARCHIVE_PATH = ROOT + "/Archive/M_SSPR_ParticleTrails_Display_M2Frozen"
RAW_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_RawDensity"
MULTISCALE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_MultiScaleDensity"
SHAPE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
RESOLVE_PATH = ROOT + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"


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


def create_function_call(function_path, x, y):
    lib = unreal.MaterialEditingLibrary
    material = unreal.load_asset(MATERIAL_PATH)
    before = {
        expression.get_path_name()
        for expression in lib.get_material_expressions(material)
    }
    info = unreal.MaterialNodeService.create_function_call(
        MATERIAL_PATH, function_path, x, y
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
                {
                    "name": name,
                    "type": expression.get_class().get_name(),
                }
            )
    return sorted(result, key=lambda row: (row["name"], row["type"]))


def main():
    if not unreal.EditorAssetLibrary.does_asset_exist(ARCHIVE_PATH):
        raise RuntimeError("Frozen M2 material archive is missing")
    for path in (RAW_PATH, MULTISCALE_PATH, SHAPE_PATH, RESOLVE_PATH):
        if not isinstance(unreal.load_asset(path), unreal.MaterialFunction):
            raise RuntimeError("Required material function is missing: " + path)

    material = unreal.load_asset(MATERIAL_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Production display material is missing")
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
    if not isinstance(default_texture, unreal.Texture):
        raise RuntimeError("Default texture is unavailable")
    texture = lib.create_material_expression(
        material, unreal.MaterialExpressionTextureObjectParameter, -2100, -520
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
        material, unreal.MaterialExpressionScreenPosition, -2100, -330
    )
    texel = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -2100, -130
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
        "SmallRadiusPx": scalar(
            material, "SmallRadiusPx", 3.0, -2100, 80, "10 Reconstruction"
        ),
        "LargeRadiusPx": scalar(
            material, "LargeRadiusPx", 6.0, -2100, 220, "10 Reconstruction"
        ),
        "CoreWeight": scalar(
            material, "CoreWeight", 0.45, -1320, 280, "10 Reconstruction"
        ),
        "SmallWeight": scalar(
            material, "SmallWeight", 0.35, -1320, 420, "10 Reconstruction"
        ),
        "LargeWeight": scalar(
            material, "LargeWeight", 0.20, -1320, 560, "10 Reconstruction"
        ),
        "DetailStrength": scalar(
            material, "DetailStrength", 0.15, -1320, 700, "20 Density Shape"
        ),
        "EdgeStrength": scalar(
            material, "EdgeStrength", 0.08, -1320, 840, "20 Density Shape"
        ),
        "BlackPoint": scalar(
            material, "BlackPoint", 0.0001, -1320, 980, "20 Density Shape"
        ),
        "TrajectoryGain": scalar(
            material, "TrajectoryGain", 1.5, -1320, 1120, "20 Density Shape"
        ),
        "Contrast": scalar(
            material, "Contrast", 0.8, -1320, 1260, "20 Density Shape"
        ),
        "Extinction": scalar(
            material, "Extinction", 3.2, 30, 420, "30 Smoke Resolve"
        ),
        "OpacityScale": scalar(
            material, "OpacityScale", 0.9, 30, 560, "30 Smoke Resolve"
        ),
        "EmissiveStrength": scalar(
            material, "EmissiveStrength", 1.0, 30, 700, "30 Smoke Resolve"
        ),
        "DebugRaw": scalar(
            material, "DebugRaw", 0.0, -520, 610, "90 Debug"
        ),
    }

    smoke_color = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, 30, 250
    )
    smoke_color.set_editor_property("parameter_name", "SmokeColor")
    smoke_color.set_editor_property(
        "default_value", unreal.LinearColor(0.78, 0.84, 0.92, 1.0)
    )
    try:
        smoke_color.set_editor_property("group", "30 Smoke Resolve")
    except Exception:
        pass

    raw = create_function_call(RAW_PATH, -1320, -500)
    multiscale = create_function_call(MULTISCALE_PATH, -1320, -160)
    shape = create_function_call(SHAPE_PATH, -520, -60)
    density_select = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 30, -40
    )
    resolve = create_function_call(RESOLVE_PATH, 620, 60)

    connect(texture, "", raw, "SourceTexture")
    connect(screen, "ViewportUV", raw, "UV")
    connect(params["TrajectoryGain"], "", raw, "Gain")

    connect(texture, "", multiscale, "SourceTexture")
    connect(screen, "ViewportUV", multiscale, "UV")
    connect(texel, "", multiscale, "TexelSize")
    connect(params["SmallRadiusPx"], "", multiscale, "SmallRadiusPx")
    connect(params["LargeRadiusPx"], "", multiscale, "LargeRadiusPx")

    connect(multiscale, "Scales", shape, "Scales")
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

    connect(density_select, "", resolve, "Density")
    connect(smoke_color, "", resolve, "SmokeColor")
    for name in ("Extinction", "OpacityScale", "EmissiveStrength"):
        connect(params[name], "", resolve, name)

    if not lib.connect_material_property(
        resolve, "Color", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Failed production emissive connection")
    if not lib.connect_material_property(
        resolve, "Opacity", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Failed production opacity connection")

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
    saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False))
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)
    result = {
        "path": material.get_path_name(),
        "archivedM2": unreal.EditorAssetLibrary.does_asset_exist(ARCHIVE_PATH),
        "saved": saved,
        "compiled": bool(diagnostics.is_compiled_ok),
        "compileErrors": [str(item) for item in diagnostics.compile_errors],
        "expressionCount": len(lib.get_material_expressions(material)),
        "usageEnabled": usage_enabled,
        "parameters": parameter_summary(material),
    }
    print("M3_DISPLAY_MATERIAL=" + json.dumps(result, sort_keys=True))
    if not saved or not result["compiled"] or result["compileErrors"]:
        raise RuntimeError("M3 production material failed: " + repr(result))


main()
