import json
import unreal


MATERIAL_PATH = "/Game/SSPR_Validation/M2/ParticleTrails/M_SSPR_ParticleTrails_Display"


def main():
    material = unreal.load_asset(MATERIAL_PATH)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Display material is missing")
    texture = None
    if TARGET_MODE == "white":
        for candidate in (
            "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture",
            "/Engine/EngineResources/DefaultTexture.DefaultTexture",
        ):
            loaded = unreal.load_asset(candidate)
            if isinstance(loaded, unreal.Texture):
                texture = loaded
                break
    else:
        texture = unreal.load_asset("/Engine/EngineResources/Black.Black")
    if not isinstance(texture, unreal.Texture):
        raise RuntimeError("Diagnostic texture is unavailable")

    node = next(
        (
            expression
            for expression in unreal.MaterialEditingLibrary.get_material_expressions(
                material
            )
            if isinstance(expression, unreal.MaterialExpressionTextureObjectParameter)
            and str(expression.get_editor_property("parameter_name"))
            == "TrajectoryTexture"
        ),
        None,
    )
    if node is None:
        raise RuntimeError("TrajectoryTexture object parameter is missing")
    node.set_editor_property("texture", texture)
    unreal.MaterialEditingLibrary.recompile_material(material)
    saved = False
    if TARGET_MODE == "black":
        saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False))
    print(
        "M3_DEFAULT_TEXTURE_PROBE="
        + json.dumps(
            {
                "mode": TARGET_MODE,
                "texture": texture.get_path_name(),
                "saved": saved,
            },
            sort_keys=True,
        )
    )


main()
