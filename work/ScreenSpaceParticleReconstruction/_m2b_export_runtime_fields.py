import json
import unreal

ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"
actor = None
for candidate in unreal.ObjectIterator(unreal.Actor):
    try:
        world = candidate.get_world()
        if (
            candidate.get_actor_label() == ACTOR_LABEL
            and world
            and "UEDPIE" in world.get_path_name()
        ):
            actor = candidate
            break
    except Exception:
        pass
if actor is None:
    raise RuntimeError("Runtime M2 orchestrator actor not found")

output_directory = unreal.Paths.project_saved_dir()
assets = (
    ("HistoryA", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryA.RT_SSPR_HistoryA"),
    ("HistoryB", "/Game/SSPR_Validation/M2/RT_SSPR_HistoryB.RT_SSPR_HistoryB"),
    ("Core", "/Game/SSPR_Validation/M2/RT_SSPR_Core.RT_SSPR_Core"),
    ("Small", "/Game/SSPR_Validation/M2/RT_SSPR_BlurSmall.RT_SSPR_BlurSmall"),
    ("Large", "/Game/SSPR_Validation/M2/RT_SSPR_BlurLarge.RT_SSPR_BlurLarge"),
    ("Density", "/Game/SSPR_Validation/M2/RT_SSPR_Density.RT_SSPR_Density"),
    ("Smoke", "/Game/SSPR_Validation/M2/RT_SSPR_Smoke.RT_SSPR_Smoke"),
)
outputs = {}
for label, asset_path in assets:
    render_target = unreal.load_object(None, asset_path)
    if render_target is None:
        raise RuntimeError("Missing field RT: " + asset_path)
    filename = "M2B_RUNTIME_" + label
    unreal.RenderingLibrary.export_render_target(
        actor,
        render_target,
        output_directory,
        filename,
    )
    outputs[label] = output_directory + filename

runtime = {
    "actor": actor.get_path_name(),
    "latest": (
        actor.get_editor_property("LatestHistory").get_path_name()
        if actor.get_editor_property("LatestHistory")
        else None
    ),
    "mids": {},
}
for variable_name in (
    "TemporalMID",
    "CoreMID",
    "SmallBlurMID",
    "LargeBlurMID",
    "DensityMID",
    "SmokeMID",
):
    value = actor.get_editor_property(variable_name)
    runtime["mids"][variable_name] = (
        value.get_path_name() if value else None
    )
print(
    "M2B_EXPORTS="
    + json.dumps(
        {"runtime": runtime, "outputs": outputs},
        ensure_ascii=False,
        sort_keys=True,
    )
)
