import json
import unreal


world = unreal.EditorLevelLibrary.get_editor_world()
rows = []
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
        size_x != 512
        or size_y != 512
        or "RTF_RGBA16F" not in target_format
        or target.get_outer() != world
    ):
        continue
    raw = unreal.RenderingLibrary.read_render_target_raw(world, target, True)
    maxima = [0.0, 0.0, 0.0, 0.0]
    nonzero = [0, 0, 0, 0]
    if raw is not None:
        for color in raw:
            values = (
                float(color.r),
                float(color.g),
                float(color.b),
                float(color.a),
            )
            for index, value in enumerate(values):
                maxima[index] = max(maxima[index], value)
                nonzero[index] += int(abs(value) > 0.0001)
    rows.append(
        {
            "path": target.get_path_name(),
            "max": maxima,
            "nonzero": nonzero,
            "samples": len(raw) if raw is not None else 0,
        }
    )
print("GRIDMAIN_ALL_TARGETS=" + json.dumps(rows, sort_keys=True))
