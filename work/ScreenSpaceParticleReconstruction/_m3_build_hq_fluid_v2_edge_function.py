import json
import unreal


FOLDER = "/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQFluidV2"
PATH = FOLDER + "/MF_SSPR_ScreenEdgeMask"


def connect(source, source_output, target, target_input):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError("Failed edge-mask function connection")


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(PATH):
        raise RuntimeError("Refusing to rebuild published V2 edge function")
    function = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MF_SSPR_ScreenEdgeMask",
        FOLDER,
        unreal.MaterialFunction,
        unreal.MaterialFunctionFactoryNew(),
    )
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Failed to create V2 edge-mask function")
    function.set_editor_property(
        "description",
        "SSPR M3 V2: fade reconstructed density inside the screen boundary without clamped edge smearing.",
    )
    function.set_editor_property("expose_to_library", True)

    nodes = {}
    specs = (
        ("UV", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("TexelSize", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR2),
        ("FadeWidthPx", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR),
    )
    for index, (name, input_type) in enumerate(specs):
        node = unreal.MaterialEditingLibrary.create_material_expression_in_function(
            function, unreal.MaterialExpressionFunctionInput, -820, -160 + index * 170
        )
        node.set_editor_property("input_name", name)
        node.set_editor_property("input_type", input_type)
        node.set_editor_property("sort_priority", index)
        node.set_editor_property("use_preview_value_as_default", True)
        nodes[name] = node

    custom = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionCustom, -230, 10
    )
    custom.set_editor_property("description", "SSPR M3 V2 Screen Edge Mask")
    custom.set_editor_property(
        "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1
    )
    custom_inputs = []
    for name, _ in specs:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        custom_inputs.append(item)
    custom.set_editor_property("inputs", custom_inputs)
    custom.set_editor_property(
        "code",
        """
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 distanceToEdgePx = min(UV, 1.0f - UV) / safeTexel;
float edgeDistance = min(distanceToEdgePx.x, distanceToEdgePx.y);
float width = max(FadeWidthPx, 1.0f);
float t = saturate(edgeDistance / width);
return t * t * (3.0f - 2.0f * t);
""".strip(),
    )
    for name in nodes:
        connect(nodes[name], "", custom, name)

    output = unreal.MaterialEditingLibrary.create_material_expression_in_function(
        function, unreal.MaterialExpressionFunctionOutput, 330, 10
    )
    output.set_editor_property("output_name", "Mask")
    output.set_editor_property("sort_priority", 0)
    output_inputs = [
        str(value)
        for value in unreal.MaterialEditingLibrary.get_material_expression_input_names(
            output
        )
    ]
    if not output_inputs:
        raise RuntimeError("V2 edge-mask output exposes no pin")
    connect(custom, "", output, output_inputs[0])

    unreal.MaterialEditingLibrary.layout_material_function_expressions(function)
    unreal.MaterialEditingLibrary.update_material_function(function)
    if not unreal.EditorAssetLibrary.save_asset(PATH, False):
        raise RuntimeError("Failed to save V2 edge-mask function")
    print(
        "M3_HQ_FLUID_V2_EDGE="
        + json.dumps(
            {
                "path": function.get_path_name(),
                "expressions": len(
                    unreal.MaterialEditingLibrary.get_material_function_expressions(
                        function
                    )
                ),
            },
            sort_keys=True,
        )
    )


main()
