import json
import unreal


ACTOR_LABEL = "SSPR_GridTrails_Main"
TARGET_SIZE = (512, 512)
EXPORT_NAME = "SSPR_GridTrails_Main_SimRT"

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    (
        candidate
        for candidate in actor_subsystem.get_all_level_actors()
        if candidate.get_actor_label() == ACTOR_LABEL
    ),
    None,
)
if actor is None:
    raise RuntimeError("GridTrails validation actor is missing")
components = actor.get_components_by_class(unreal.NiagaraComponent)
if not components:
    raise RuntimeError("GridTrails Niagara component is missing")
component = components[0]
component.advance_simulation(30, 1.0 / 30.0)

world = unreal.EditorLevelLibrary.get_editor_world()
candidate_targets = []
for candidate in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
    try:
        size = (
            int(candidate.get_editor_property("size_x")),
            int(candidate.get_editor_property("size_y")),
        )
        target_format = str(
            candidate.get_editor_property("render_target_format")
        )
    except Exception:
        continue
    if (
        size == TARGET_SIZE
        and "RTF_RGBA16F" in target_format
        and candidate.get_outer() == world
    ):
        candidate_targets.append(candidate)
if not candidate_targets:
    raise RuntimeError("Niagara-owned 512x512 RGBA16F SimRT was not found")

threshold = 0.0001
target_results = []
for candidate in candidate_targets:
    candidate_raw = unreal.RenderingLibrary.read_render_target_raw(
        world, candidate, True
    )
    if candidate_raw is None:
        continue
    candidate_max = [0.0, 0.0, 0.0, 0.0]
    candidate_sum = [0.0, 0.0, 0.0, 0.0]
    candidate_nonzero = [0, 0, 0, 0]
    for color in candidate_raw:
        values = (
            float(color.r),
            float(color.g),
            float(color.b),
            float(color.a),
        )
        for index, value in enumerate(values):
            candidate_max[index] = max(candidate_max[index], value)
            candidate_sum[index] += value
            candidate_nonzero[index] += int(abs(value) > threshold)
    target_results.append(
        {
            "target": candidate,
            "raw": candidate_raw,
            "max": candidate_max,
            "sum": candidate_sum,
            "nonzero": candidate_nonzero,
        }
    )
if not target_results:
    raise RuntimeError("Failed to read Niagara-owned SimRT candidates")

# Reinitialization and temporary comparison actors can leave stale managed
# render targets under the editor world until GC. The active GridTrails target
# is the candidate currently carrying simulation data.
selected = max(
    target_results,
    key=lambda row: sum(row["nonzero"]),
)
target = selected["target"]
raw = selected["raw"]
channel_max = selected["max"]
channel_sum = selected["sum"]
nonzero = selected["nonzero"]

count = len(raw)
means = [value / count if count else 0.0 for value in channel_sum]
export_dir = unreal.Paths.project_saved_dir()
unreal.RenderingLibrary.export_render_target(
    component,
    target,
    export_dir,
    EXPORT_NAME,
)

result = {
    "actor": actor.get_path_name(),
    "component": component.get_path_name(),
    "target": target.get_path_name(),
    "size": list(TARGET_SIZE),
    "format": str(target.get_editor_property("render_target_format")),
    "samples": count,
    "channelMax": channel_max,
    "channelMean": means,
    "channelNonzero": nonzero,
    "exportBase": export_dir + EXPORT_NAME,
    "active": bool(component.is_active()),
}
print("GRIDMAIN_RUNTIME_OUTPUT=" + json.dumps(result, sort_keys=True))
if count != TARGET_SIZE[0] * TARGET_SIZE[1] or max(channel_max) <= threshold:
    raise RuntimeError("GridTrails SimRT is empty: " + repr(result))
