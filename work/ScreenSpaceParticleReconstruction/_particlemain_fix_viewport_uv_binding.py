import json
import unreal


MATERIAL = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display.M_SSPR_ParticleTrails_Display"
)


def main():
    material = unreal.load_object(None, MATERIAL)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Display material is missing")

    lib = unreal.MaterialEditingLibrary
    expressions = list(lib.get_material_expressions(material))
    screen_position = next(
        (
            expression
            for expression in expressions
            if isinstance(expression, unreal.MaterialExpressionScreenPosition)
        ),
        None,
    )
    texture_sample = next(
        (
            expression
            for expression in expressions
            if isinstance(
                expression,
                unreal.MaterialExpressionTextureSampleParameter2D,
            )
            and str(expression.get_editor_property("parameter_name"))
            == "TrajectoryTexture"
        ),
        None,
    )
    if screen_position is None or texture_sample is None:
        raise RuntimeError("Required screen-position or texture node is missing")

    input_names = [
        str(name)
        for name in lib.get_material_expression_input_names(texture_sample)
    ]
    if "UVs" not in input_names:
        raise RuntimeError("Texture sample has no UE 5.8 UVs input: " + repr(input_names))

    connected = bool(
        lib.connect_material_expressions(
            screen_position,
            "ViewportUV",
            texture_sample,
            "UVs",
        )
    )
    lib.recompile_material(material)
    saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL, False))
    connected_inputs = [
        expression.get_class().get_name()
        for expression in lib.get_inputs_for_material_expression(
            material, texture_sample
        )
        if expression is not None
    ]
    result = {
        "material": material.get_path_name(),
        "connected": connected,
        "saved": saved,
        "textureInputNames": input_names,
        "textureConnectedInputs": connected_inputs,
    }
    print(
        "PARTICLE_VIEWPORT_UV_FIXED="
        + json.dumps(result, sort_keys=True)
    )
    if (
        not connected
        or not saved
        or "MaterialExpressionScreenPosition" not in connected_inputs
    ):
        raise RuntimeError("Viewport UV binding fix failed: " + repr(result))


main()
