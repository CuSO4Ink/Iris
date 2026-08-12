import gc
import json
import math
import unreal


SOURCE_SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
TEST_SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance/"
    "NS_SSPR_AnisotropicSplat_DuplicateControlV1."
    "NS_SSPR_AnisotropicSplat_DuplicateControlV1"
)
LABEL = "SSPR_ParticleTrails_Main"


def render_targets():
    result = {}
    for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
        try:
            if (
                int(target.get_editor_property("size_x")) == 2048
                and int(target.get_editor_property("size_y")) == 2048
                and "RGBA16F"
                in str(
                    target.get_editor_property(
                        "render_target_format"
                    )
                )
            ):
                result[target.get_path_name()] = target
        except Exception:
            pass
    return result


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
actor_subsystem = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
)
source_actor = next(
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label() == LABEL
)
source_component = source_actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
if source_component.get_asset().get_path_name() != SOURCE_SYSTEM:
    raise RuntimeError("Source validation actor is not restored")
test_asset = unreal.load_asset(TEST_SYSTEM)
if not isinstance(test_asset, unreal.NiagaraSystem):
    raise RuntimeError("Missing duplicate control asset")

before_targets = render_targets()
source_component.deactivate()
source_component.set_component_tick_enabled(False)
test_actor = None
rows = []
error = None
try:
    test_actor = actor_subsystem.spawn_actor_from_class(
        unreal.NiagaraActor,
        source_actor.get_actor_location(),
    )
    test_actor.set_actor_transform(
        source_actor.get_actor_transform(), False, False
    )
    test_actor.set_actor_label("SSPR_DuplicateControlV1_Probe")
    component = test_actor.get_components_by_class(
        unreal.NiagaraComponent
    )[0]
    component.set_asset(test_asset)
    component.set_force_solo(True)
    component.set_component_tick_enabled(True)
    component.reinitialize_system()
    component.activate(True)
    component.advance_simulation(360, 1.0 / 60.0)

    after_targets = render_targets()
    new_targets = [
        target
        for path, target in after_targets.items()
        if path not in before_targets
    ]
    if len(new_targets) != 2:
        raise RuntimeError(
            "Expected two probe RTs, got "
            + repr([value.get_path_name() for value in new_targets])
        )

    quadrants = (
        (0, 0, 1024, 1024),
        (1024, 0, 1024, 1024),
        (0, 1024, 1024, 1024),
        (1024, 1024, 1024, 1024),
    )
    for target in new_targets:
        stats = {
            name: {
                "min": 0.0,
                "max": 0.0,
                "nonzero": 0,
                "negative": 0,
                "nonfinite": 0,
            }
            for name in ("r", "g", "b", "a")
        }
        pixel_count = 0
        for x, y, width, height in quadrants:
            colors = unreal.RenderingLibrary.read_render_target_raw_pixel_area(
                world, target, x, y, width, height, False
            )
            pixel_count += len(colors)
            for name in ("r", "g", "b", "a"):
                values = [
                    float(getattr(color, name))
                    for color in colors
                ]
                finite = [
                    value for value in values
                    if math.isfinite(value)
                ]
                stats[name]["nonfinite"] += (
                    len(values) - len(finite)
                )
                if finite:
                    stats[name]["min"] = min(
                        stats[name]["min"], min(finite)
                    )
                    stats[name]["max"] = max(
                        stats[name]["max"], max(finite)
                    )
                    stats[name]["nonzero"] += sum(
                        abs(value) > 1.0e-7
                        for value in finite
                    )
                    stats[name]["negative"] += sum(
                        value < -1.0e-7 for value in finite
                    )
                del values
                del finite
            del colors
            gc.collect()
        rows.append(
            {
                "path": target.get_path_name(),
                "pixelCount": pixel_count,
                "channels": stats,
            }
        )
except Exception as value:
    error = repr(value)
finally:
    if test_actor is not None:
        actor_subsystem.destroy_actor(test_actor)
    source_component.set_component_tick_enabled(True)
    source_component.activate(True)

result = {
    "testSystem": TEST_SYSTEM,
    "rows": rows,
    "error": error,
    "sourceRestored": bool(source_component.is_active()),
}
print(
    "PERF_DUPLICATE_CONTROL_PROBE_V1="
    + json.dumps(result, sort_keys=True)
)
if (
    error is not None
    or len(rows) != 2
    or max(row["channels"]["r"]["nonzero"] for row in rows)
    < 1000
    or not result["sourceRestored"]
):
    raise RuntimeError(
        "Duplicate control probe failed: " + repr(result)
    )
