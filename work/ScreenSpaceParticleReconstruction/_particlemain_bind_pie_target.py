import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
TARGET_NAME = "SSPR_TrajectoryRT_PIE"
GRID_SIZE = 2048

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
    ):
        continue
    component_path = component.get_path_name()
    if "UEDPIE_" not in component_path:
        continue
    target = unreal.RenderingLibrary.create_render_target2d(
        world,
        GRID_SIZE,
        GRID_SIZE,
        unreal.TextureRenderTargetFormat.RTF_R32F,
        unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
        False,
        False,
    )
    if target is None:
        raise RuntimeError("Failed to create PIE trajectory target")
    target.rename(TARGET_NAME, component)
    component.set_variable_texture_render_target(
        "User.SSPR_TrajectoryRT", target
    )
    component.set_force_solo(False)
    component.set_auto_activate(True)
    component.reinitialize_system()
    component.activate(True)
    rows.append(
        {
            "component": component.get_path_name(),
            "world": world.get_path_name(),
            "target": target.get_path_name(),
            "active": bool(component.is_active()),
        }
    )

print(
    "PARTICLE_PIE_TARGET="
    + json.dumps(rows, sort_keys=True)
)
if not rows:
    raise RuntimeError("No PIE white-particle component found")
