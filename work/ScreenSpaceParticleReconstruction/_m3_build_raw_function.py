import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
FUNCTION_FOLDER = ROOT + "/Functions"
FUNCTION_PACKAGE = FUNCTION_FOLDER + "/MF_SSPR_RawDensity"
MATERIAL_PACKAGE = ROOT + "/M_SSPR_ParticleTrails_Display"
ARCHIVE_FOLDER = ROOT + "/Archive"
ARCHIVE_PACKAGE = ARCHIVE_FOLDER + "/M_SSPR_ParticleTrails_Display_M2Frozen"
PROBE_PACKAGE = FUNCTION_FOLDER + "/M_SSPR_RawDensity_Probe"


def create_or_reset_function():
    lib = unreal.MaterialEditingLibrary
    function = unreal.load_asset(FUNCTION_PACKAGE)
    created = False
    if function is None:
        function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "MF_SSPR_RawDensity",
            FUNCTION_FOLDER,
            unreal.MaterialFunction,
            unreal.MaterialFunctionFactoryNew(),
        )
        created = function is not None
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Failed to create RawDensity material function")
    lib.delete_all_material_expressions_in_function(function)
    function.set_editor_property(
        "description",
        "SSPR M3: sample Niagara trajectory density with viewport UV.",
    )
    function.set_editor_property("expose_to_library", True)
    return function, created


def add_input(function, name, input_type, sort_priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function,
        unreal.MaterialExpressionFunctionInput,
        x,
        y,
    )
    if node is None:
        raise RuntimeError("Failed to create function input " + name)
    node.set_editor_property("input_name", name)
    node.set_editor_property("input_type", input_type)
    node.set_editor_property("sort_priority", sort_priority)
    node.set_editor_property("use_preview_value_as_default", True)
    return node


def add_output(function, name, sort_priority, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function,
        unreal.MaterialExpressionFunctionOutput,
        x,
        y,
    )
    if node is None:
        raise RuntimeError("Failed to create function output " + name)
    node.set_editor_property("output_name", name)
    node.set_editor_property("sort_priority", sort_priority)
    return node


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(
            "Failed material connection {} -> {}".format(
                source_output, target_input
            )
        )


def build_function():
    lib = unreal.MaterialEditingLibrary
    function, created = create_or_reset_function()
    source_texture = add_input(
        function,
        "SourceTexture",
        unreal.FunctionInputType.FUNCTION_INPUT_TEXTURE2D,
        0,
        -900,
        -120,
    )
    uv = add_input(
        function,
        "UV",
        unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2,
        1,
        -900,
        40,
    )
    gain = add_input(
        function,
        "Gain",
        unreal.FunctionInputType.FUNCTION_INPUT_SCALAR,
        2,
        -900,
        200,
    )

    custom = lib.create_material_expression_in_function(
        function,
        unreal.MaterialExpressionCustom,
        -360,
        20,
    )
    if custom is None:
        raise RuntimeError("Failed to create RawDensity Custom expression")
    custom.set_editor_property("description", "SSPR Raw Density Sample")
    custom.set_editor_property(
        "code",
        "float2 SafeUV = saturate(UV);\n"
        "float Density = Texture2DSampleLevel("
        "SourceTexture, SourceTextureSampler, SafeUV, 0).r;\n"
        "return max(Density, 0.0f) * max(Gain, 0.0f);",
    )
    custom.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1
    )
    custom_inputs = []
    for name in ("SourceTexture", "UV", "Gain"):
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)

    density_output = add_output(function, "Density", 0, 260, 20)
    output_inputs = [
        str(name)
        for name in lib.get_material_expression_input_names(density_output)
    ]
    if not output_inputs:
        raise RuntimeError("RawDensity FunctionOutput exposes no input")

    connect(source_texture, "", custom, "SourceTexture")
    connect(uv, "", custom, "UV")
    connect(gain, "", custom, "Gain")
    connect(custom, "", density_output, output_inputs[0])

    lib.layout_material_function_expressions(function)
    lib.update_material_function(function)
    saved = bool(
        unreal.EditorAssetLibrary.save_asset(FUNCTION_PACKAGE, False)
    )
    return function, created, saved, {
        "customInputs": [
            str(name)
            for name in lib.get_material_expression_input_names(custom)
        ],
        "outputInputs": output_inputs,
        "expressionCount": len(lib.get_material_function_expressions(function)),
    }


def validate_with_probe(function):
    lib = unreal.MaterialEditingLibrary
    if unreal.EditorAssetLibrary.does_asset_exist(PROBE_PACKAGE):
        unreal.EditorAssetLibrary.delete_asset(PROBE_PACKAGE)
    probe = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_RawDensity_Probe",
        FUNCTION_FOLDER,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(probe, unreal.Material):
        raise RuntimeError("Failed to create RawDensity probe material")
    try:
        probe.set_editor_property(
            "material_domain", unreal.MaterialDomain.MD_SURFACE
        )
        try:
            probe.set_editor_property(
                "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
            )
        except Exception:
            pass
        default_texture = unreal.load_asset(
            "/Engine/EngineResources/Black.Black"
        )
        texture_object = lib.create_material_expression(
            probe,
            unreal.MaterialExpressionTextureObjectParameter,
            -900,
            -120,
        )
        texture_object.set_editor_property(
            "parameter_name", "TrajectoryTexture"
        )
        texture_object.set_editor_property("texture", default_texture)
        screen = lib.create_material_expression(
            probe, unreal.MaterialExpressionScreenPosition, -900, 40
        )
        gain = lib.create_material_expression(
            probe, unreal.MaterialExpressionConstant, -900, 200
        )
        gain.set_editor_property("r", 1.0)

        call_info = unreal.MaterialNodeService.create_function_call(
            PROBE_PACKAGE,
            FUNCTION_PACKAGE,
            -300,
            20,
        )
        if not str(call_info.id):
            raise RuntimeError("Failed to create RawDensity function call")
        call = next(
            (
                expression
                for expression in lib.get_material_expressions(probe)
                if isinstance(
                    expression,
                    unreal.MaterialExpressionMaterialFunctionCall,
                )
            ),
            None,
        )
        if call is None:
            raise RuntimeError("RawDensity function call is missing")
        call_inputs = [
            str(name)
            for name in lib.get_material_expression_input_names(call)
        ]
        call_outputs = [
            str(name)
            for name in lib.get_material_expression_output_names(call)
        ]
        if not all(
            required in call_inputs
            for required in ("SourceTexture", "UV", "Gain")
        ):
            raise RuntimeError("Unexpected RawDensity inputs: " + repr(call_inputs))
        if "Density" not in call_outputs:
            raise RuntimeError("Unexpected RawDensity outputs: " + repr(call_outputs))

        connect(texture_object, "", call, "SourceTexture")
        connect(screen, "ViewportUV", call, "UV")
        connect(gain, "", call, "Gain")
        if not lib.connect_material_property(
            call, "Density", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        ):
            raise RuntimeError("Failed to connect RawDensity probe output")
        lib.layout_material_expressions(probe)
        lib.recompile_material(probe)
        saved = bool(
            unreal.EditorAssetLibrary.save_asset(PROBE_PACKAGE, False)
        )
        diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
            PROBE_PACKAGE
        )
        result = {
            "saved": saved,
            "callInputs": call_inputs,
            "callOutputs": call_outputs,
            "compiled": bool(diagnostics.is_compiled_ok),
            "compileErrors": [str(item) for item in diagnostics.compile_errors],
        }
        if not saved or not result["compiled"] or result["compileErrors"]:
            raise RuntimeError("RawDensity probe failed: " + repr(result))
        return result
    finally:
        if unreal.EditorAssetLibrary.does_asset_exist(PROBE_PACKAGE):
            unreal.EditorAssetLibrary.delete_asset(PROBE_PACKAGE)


def main():
    unreal.EditorAssetLibrary.make_directory(FUNCTION_FOLDER)
    unreal.EditorAssetLibrary.make_directory(ARCHIVE_FOLDER)
    archived = False
    if not unreal.EditorAssetLibrary.does_asset_exist(ARCHIVE_PACKAGE):
        archived = bool(
            unreal.EditorAssetLibrary.duplicate_asset(
                MATERIAL_PACKAGE, ARCHIVE_PACKAGE
            )
        )
        if not archived:
            raise RuntimeError("Failed to archive the frozen M2 display material")

    function, created, saved, graph = build_function()
    probe = validate_with_probe(function)
    result = {
        "function": function.get_path_name(),
        "created": created,
        "saved": saved,
        "archivedM2Material": archived
        or unreal.EditorAssetLibrary.does_asset_exist(ARCHIVE_PACKAGE),
        "graph": graph,
        "probe": probe,
    }
    print("M3_RAW_FUNCTION=" + json.dumps(result, sort_keys=True))
    if not saved:
        raise RuntimeError("RawDensity function was not saved")


main()
