import json
import unreal

FOLDER = "/Game/SSPR_Validation/M2"
SOURCE_RT = "/Game/SSPR_Validation/RT_SSPR_Occupancy"
RT_NAMES = (
    "RT_SSPR_Current",
    "RT_SSPR_HistoryA",
    "RT_SSPR_HistoryB",
)
MATERIAL_NAME = "M_SSPR_TemporalCombine"


def load_or_create_rt(name):
    path = FOLDER + "/" + name
    existing = unreal.load_asset(path)
    if existing:
        if not isinstance(existing, unreal.TextureRenderTarget2D):
            raise RuntimeError(path + " exists with the wrong class")
        rt = existing
        created = False
    else:
        rt = unreal.EditorAssetLibrary.duplicate_asset(
            SOURCE_RT,
            path,
        )
        if rt is None:
            raise RuntimeError("Failed to create " + path)
        created = True

    rt.set_editor_property("size_x", 256)
    rt.set_editor_property("size_y", 256)
    rt.set_editor_property(
        "render_target_format",
        unreal.TextureRenderTargetFormat.RTF_R16F,
    )
    rt.set_editor_property("clear_color", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
    rt.set_editor_property("auto_generate_mips", False)
    rt.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return rt, created


def create_temporal_material(current_rt, history_rt):
    path = FOLDER + "/" + MATERIAL_NAME
    existing = unreal.load_asset(path)
    if existing:
        if not isinstance(existing, unreal.Material):
            raise RuntimeError(path + " exists with the wrong class")
        material = existing
        created = False
        expressions = list(
            unreal.MaterialEditingLibrary.get_material_expressions(material)
        )
        if expressions:
            custom_nodes = [
                expression
                for expression in expressions
                if isinstance(expression, unreal.MaterialExpressionCustom)
            ]
            if (
                len(custom_nodes) != 1
                or "SSPR temporal reprojection"
                not in custom_nodes[0].get_editor_property("description")
            ):
                raise RuntimeError(
                    path
                    + " already contains an unexpected material graph; "
                    + "refusing to overwrite it"
                )
            unreal.MaterialEditingLibrary.recompile_material(material)
            if not unreal.EditorAssetLibrary.save_asset(path, False):
                raise RuntimeError("Failed to save existing " + path)
            return material, created
    else:
        factory = unreal.MaterialFactoryNew()
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_NAME,
            FOLDER,
            unreal.Material,
            factory,
        )
        if material is None:
            raise RuntimeError("Failed to create " + path)
        created = True

    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    try:
        material.set_editor_property(
            "shading_model",
            unreal.MaterialShadingModel.MSM_UNLIT,
        )
    except Exception:
        pass

    lib = unreal.MaterialEditingLibrary

    current_param = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -1050,
        -350,
    )
    current_param.set_editor_property("parameter_name", "CurrentTexture")
    current_param.set_editor_property("texture", current_rt)
    current_param.set_editor_property(
        "sampler_type",
        unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )

    history_param = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        -1050,
        -150,
    )
    history_param.set_editor_property("parameter_name", "HistoryTexture")
    history_param.set_editor_property("texture", history_rt)
    history_param.set_editor_property(
        "sampler_type",
        unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )

    uv = lib.create_material_expression(
        material,
        unreal.MaterialExpressionTextureCoordinate,
        -1050,
        50,
    )
    uv.set_editor_property("coordinate_index", 0)

    scalar_specs = (
        ("DeltaSeconds", 1.0 / 60.0, -1050, 200),
        ("DecayRate", 6.0, -1050, 300),
        ("RepresentativeDepth", 1000.0, -1050, 400),
        ("HistoryValid", 0.0, -1050, 500),
        ("ReprojectionEnabled", 1.0, -1050, 600),
    )
    scalars = {}
    for name, value, x, y in scalar_specs:
        expression = lib.create_material_expression(
            material,
            unreal.MaterialExpressionScalarParameter,
            x,
            y,
        )
        expression.set_editor_property("parameter_name", name)
        expression.set_editor_property("default_value", value)
        scalars[name] = expression

    custom = lib.create_material_expression(
        material,
        unreal.MaterialExpressionCustom,
        -450,
        0,
    )
    custom.set_editor_property("description", "SSPR temporal reprojection and decay")
    custom.set_editor_property(
        "output_type",
        unreal.CustomMaterialOutputType.CMOT_FLOAT3,
    )

    input_names = (
        "CurrentTexture",
        "HistoryTexture",
        "UV",
        "DeltaSeconds",
        "DecayRate",
        "RepresentativeDepth",
        "HistoryValid",
        "ReprojectionEnabled",
    )
    custom_inputs = []
    for input_name in input_names:
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", input_name)
        custom_inputs.append(entry)
    custom.set_editor_property("inputs", custom_inputs)

    custom.set_editor_property(
        "code",
        r"""
float currentDensity = Texture2DSampleLevel(
    CurrentTexture, CurrentTextureSampler, UV, 0).r;

float2 screenPosition = float2(
    UV.x * 2.0f - 1.0f,
    1.0f - UV.y * 2.0f);
float deviceZ = ConvertToDeviceZ(max(RepresentativeDepth, 1.0f));
float4 previousClip = mul(
    float4(screenPosition, deviceZ, 1.0f),
    View.ClipToPrevClip);
float safeW = max(abs(previousClip.w), 1.0e-5f);
float2 previousScreen = previousClip.xy / safeW;
float2 reprojectedUV = previousScreen * float2(0.5f, -0.5f) + 0.5f;
float2 historyUV = lerp(UV, reprojectedUV, saturate(ReprojectionEnabled));

bool historyInBounds =
    historyUV.x >= 0.0f && historyUV.x <= 1.0f &&
    historyUV.y >= 0.0f && historyUV.y <= 1.0f;
float historyDensity = historyInBounds
    ? Texture2DSampleLevel(
        HistoryTexture, HistoryTextureSampler, historyUV, 0).r
    : 0.0f;

float decay = exp(
    -max(DecayRate, 0.0f) *
    clamp(DeltaSeconds, 0.0f, 0.25f));
float validHistory = historyDensity * decay * saturate(HistoryValid);
float combinedDensity = max(currentDensity, validHistory);
return float3(combinedDensity, 0.0f, 0.0f);
""".strip(),
    )

    connections = (
        (current_param, "", custom, "CurrentTexture"),
        (history_param, "", custom, "HistoryTexture"),
        (uv, "", custom, "UV"),
        (scalars["DeltaSeconds"], "", custom, "DeltaSeconds"),
        (scalars["DecayRate"], "", custom, "DecayRate"),
        (
            scalars["RepresentativeDepth"],
            "",
            custom,
            "RepresentativeDepth",
        ),
        (scalars["HistoryValid"], "", custom, "HistoryValid"),
        (
            scalars["ReprojectionEnabled"],
            "",
            custom,
            "ReprojectionEnabled",
        ),
    )
    for source, source_output, target, target_input in connections:
        if not lib.connect_material_expressions(
            source,
            source_output,
            target,
            target_input,
        ):
            raise RuntimeError("Failed material connection: " + target_input)

    if not lib.connect_material_property(
        custom,
        "",
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    ):
        raise RuntimeError("Failed to connect temporal output to Emissive")

    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save " + path)
    return material, created


unreal.EditorAssetLibrary.make_directory(FOLDER)

# A previous interrupted creation can leave only the first unsaved RT package.
# It is safe to remove exactly that partial asset before duplicating the known
# writable M1 render target.
partial_current = FOLDER + "/RT_SSPR_Current"
if (
    unreal.EditorAssetLibrary.does_asset_exist(partial_current)
    and not unreal.EditorAssetLibrary.does_asset_exist(
        FOLDER + "/RT_SSPR_HistoryA"
    )
    and not unreal.EditorAssetLibrary.does_asset_exist(
        FOLDER + "/RT_SSPR_HistoryB"
    )
    and not unreal.EditorAssetLibrary.does_asset_exist(
        FOLDER + "/" + MATERIAL_NAME
    )
):
    if not unreal.EditorAssetLibrary.delete_asset(partial_current):
        raise RuntimeError("Failed to remove the interrupted Current RT")

rts = {}
created_assets = []
for rt_name in RT_NAMES:
    rt, created = load_or_create_rt(rt_name)
    rts[rt_name] = rt
    if created:
        created_assets.append(rt.get_path_name())

material, material_created = create_temporal_material(
    rts["RT_SSPR_Current"],
    rts["RT_SSPR_HistoryA"],
)
if material_created:
    created_assets.append(material.get_path_name())

result = {
    "created": created_assets,
    "renderTargets": {
        name: {
            "path": rt.get_path_name(),
            "size": [
                int(rt.get_editor_property("size_x")),
                int(rt.get_editor_property("size_y")),
            ],
            "format": str(rt.get_editor_property("render_target_format")),
        }
        for name, rt in rts.items()
    },
    "material": material.get_path_name(),
    "expressionCount": len(
        unreal.MaterialEditingLibrary.get_material_expressions(material)
    ),
}
print("M2A_ASSETS=" + json.dumps(result, sort_keys=True))
