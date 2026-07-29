import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
TARGET_NAME = "SSPR_TrajectoryRT_PIE"
MATERIAL_PATH = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display."
    "M_SSPR_ParticleTrails_Display"
)
material = unreal.load_object(None, MATERIAL_PATH)
rows = []
for component in unreal.ObjectIterator(
    unreal.NiagaraComponent
):
    asset = component.get_asset()
    world = component.get_world()
    if (
        asset is None
        or asset.get_path_name() != SYSTEM
        or world is None
        or "UEDPIE_" not in component.get_path_name()
    ):
        continue
    target = next(
        (
            item
            for item in unreal.ObjectIterator(
                unreal.TextureRenderTarget2D
            )
            if item.get_name() == TARGET_NAME
            and component.get_path_name()
            in item.get_path_name()
        ),
        None,
    )
    if target is None:
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
    mid.set_texture_parameter_value(
        "TrajectoryTexture", target
    )
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
    )
    rows.append(
        {
            "component": component.get_path_name(),
            "target": target.get_path_name(),
            "active": bool(component.is_active()),
            "nonzero": nonzero,
            "redMax": max(
                (int(color.r) for color in colors),
                default=0,
            ),
        }
    )

print(
    "PARTICLE_PIE_FIELD="
    + json.dumps(rows, sort_keys=True)
)
if not any(row["nonzero"] > 0 for row in rows):
    raise RuntimeError("PIE trajectory field is empty: " + repr(rows))
