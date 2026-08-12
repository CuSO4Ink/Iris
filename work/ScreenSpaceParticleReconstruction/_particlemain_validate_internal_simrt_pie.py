import json
import unreal


SYSTEM = "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
MATERIAL = "/Game/SSPR_Validation/M2/ParticleTrails/M_SSPR_ParticleTrails_Display.M_SSPR_ParticleTrails_Display"


def main():
    material = unreal.load_object(None, MATERIAL)
    if material is None:
        raise RuntimeError("Display material is missing")

    rows = []
    for component in unreal.ObjectIterator(unreal.NiagaraComponent):
        asset = component.get_asset()
        world = component.get_world()
        if (
            asset is None
            or asset.get_path_name() != SYSTEM
            or world is None
            or "UEDPIE_" not in component.get_path_name()
        ):
            continue

        candidates = []
        for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
            try:
                size_x = int(target.get_editor_property("size_x"))
                size_y = int(target.get_editor_property("size_y"))
                target_format = str(
                    target.get_editor_property("render_target_format")
                )
            except Exception:
                continue
            if (
                size_x != 2048
                or size_y != 2048
                or "RGBA16F" not in target_format
            ):
                continue
            if target.get_outer() != world:
                continue

            preview = unreal.RenderingLibrary.create_render_target2d(
                world,
                256,
                256,
                unreal.TextureRenderTargetFormat.RTF_RGBA8,
                unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
                False,
                False,
            )
            mid = unreal.MaterialLibrary.create_dynamic_material_instance(
                world, material
            )
            mid.set_texture_parameter_value("TrajectoryTexture", target)
            mid.set_scalar_parameter_value("TrajectoryGain", 1.0)
            unreal.RenderingLibrary.draw_material_to_render_target(
                world, preview, mid
            )
            colors = unreal.RenderingLibrary.read_render_target(
                world, preview, True
            )
            nonzero = sum(
                1
                for color in colors
                if int(color.r) > 0
                or int(color.g) > 0
                or int(color.b) > 0
                or int(color.a) > 0
            )
            candidates.append(
                {
                    "target": target.get_path_name(),
                    "format": target_format,
                    "nonzero": nonzero,
                    "redMax": max((int(c.r) for c in colors), default=0),
                    "alphaMax": max((int(c.a) for c in colors), default=0),
                }
            )

        rows.append(
            {
                "component": component.get_path_name(),
                "world": world.get_path_name(),
                "active": bool(component.is_active()),
                "candidates": candidates,
            }
        )

    result = {"rows": rows}
    print("PARTICLE_INTERNAL_PIE=" + json.dumps(result, sort_keys=True))
    if not any(
        candidate["nonzero"] > 0
        for row in rows
        for candidate in row["candidates"]
    ):
        raise RuntimeError("Niagara internal SimRT is empty: " + repr(result))


main()
