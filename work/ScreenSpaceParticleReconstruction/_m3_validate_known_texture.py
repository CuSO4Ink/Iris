import json
import unreal


MATERIAL_PATHS = {
    "base": (
        "/Game/SSPR_Validation/M2/ParticleTrails/"
        "M_SSPR_ParticleTrails_Display.M_SSPR_ParticleTrails_Display"
    ),
    "hqInstance": (
        "/Game/SSPR_Validation/M2/ParticleTrails/"
        "MI_SSPR_ParticleTrails_HQ_Default."
        "MI_SSPR_ParticleTrails_HQ_Default"
    ),
}


def main():
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    white = unreal.load_asset(
        "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"
    )
    if world is None or not isinstance(white, unreal.Texture):
        raise RuntimeError("Known-texture validation inputs are missing")
    result = {}
    for material_name, material_path in MATERIAL_PATHS.items():
        material = unreal.load_asset(material_path)
        if not isinstance(material, unreal.MaterialInterface):
            raise RuntimeError("Known-texture material is missing: " + material_path)
        preview = unreal.RenderingLibrary.create_render_target2d(
            world,
            128,
            128,
            unreal.TextureRenderTargetFormat.RTF_RGBA8,
            unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
            False,
            False,
        )
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, material)
        if preview is None or mid is None:
            raise RuntimeError("Known-texture validation resources failed")
        mid.set_texture_parameter_value("TrajectoryTexture", white)
        material_result = {}
        for mode_name, debug_raw in (("processed", 0.0), ("raw", 1.0)):
            mid.set_scalar_parameter_value("DebugRaw", debug_raw)
            unreal.RenderingLibrary.clear_render_target2d(
                world, preview, unreal.LinearColor(0.0, 0.0, 0.0, 0.0)
            )
            unreal.RenderingLibrary.draw_material_to_render_target(world, preview, mid)
            colors = unreal.RenderingLibrary.read_render_target(world, preview, True)
            if colors is None:
                raise RuntimeError("Known-texture readback failed")
            red = [int(color.r) for color in colors]
            green = [int(color.g) for color in colors]
            blue = [int(color.b) for color in colors]
            alpha = [int(color.a) for color in colors]
            material_result[mode_name] = {
                "samples": len(colors),
                "nonzeroRGB": sum(
                    1
                    for r, g, b in zip(red, green, blue)
                    if r > 0 or g > 0 or b > 0
                ),
                "redMax": max(red) if red else 0,
                "greenMax": max(green) if green else 0,
                "blueMax": max(blue) if blue else 0,
                "alphaMax": max(alpha) if alpha else 0,
            }
        result[material_name] = material_result
    print("M3_KNOWN_TEXTURE_VALIDATION=" + json.dumps(result, sort_keys=True))
    if any(
        mode_value["nonzeroRGB"] == 0
        for material_value in result.values()
        for mode_value in material_value.values()
    ):
        raise RuntimeError("M3 material is black with a known-white texture: " + repr(result))


main()
