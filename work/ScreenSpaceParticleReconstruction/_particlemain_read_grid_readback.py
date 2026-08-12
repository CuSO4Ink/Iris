import json
import unreal

TARGET_NAME = "SSPR_ParticleGridReadback"
GRID_SIZE = 2048

target = next(
    (
        item
        for item in unreal.ObjectIterator(
            unreal.TextureRenderTarget2D
        )
        if item.get_name() == TARGET_NAME
    ),
    None,
)
if target is None:
    raise RuntimeError("Prepared Grid readback target was collected")
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
values = []
probe_raw = unreal.RenderingLibrary.read_render_target_raw_pixel(
    world, target, GRID_SIZE // 2, GRID_SIZE // 2, False
)
probe_color = unreal.RenderingLibrary.read_render_target_pixel(
    world, target, GRID_SIZE // 2, GRID_SIZE // 2
)
seed = 0x12345678
for _ in range(512):
    seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
    x = GRID_SIZE // 4 + (seed % (GRID_SIZE // 2))
    seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
    y = GRID_SIZE // 4 + (seed % (GRID_SIZE // 2))
    color = unreal.RenderingLibrary.read_render_target_raw_pixel(
        world, target, int(x), int(y), False
    )
    values.append(float(color.r))
stats = {
    "samples": len(values),
    "min": min(values) if values else None,
    "max": max(values) if values else None,
    "mean": sum(values) / len(values) if values else None,
    "nonzero": sum(value > 0.001 for value in values),
    "full": sum(value > 0.99 for value in values),
}
print(
    "GRID_READBACK_STATS="
    + json.dumps(
        {"target": target.get_path_name(), "stats": stats},
        sort_keys=True,
    )
)
print(
    "GRID_READBACK_PROBES="
    + repr(
        {
            "raw": [
                float(probe_raw.r),
                float(probe_raw.g),
                float(probe_raw.b),
                float(probe_raw.a),
            ],
            "color": [
                int(probe_color.r),
                int(probe_color.g),
                int(probe_color.b),
                int(probe_color.a),
            ],
        }
    )
)
