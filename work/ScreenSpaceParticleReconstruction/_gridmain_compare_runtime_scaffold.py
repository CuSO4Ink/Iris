import json
import unreal


SYSTEMS = [
    (
        "reference",
        "/Game/SSPR_Validation/M2/NewNiagaraSystem.NewNiagaraSystem",
    ),
    (
        "main",
        "/Game/SSPR_Validation/M2/GridTrails/"
        "NS_SSPR_GridTrails_Main.NS_SSPR_GridTrails_Main",
    ),
]

world = unreal.EditorLevelLibrary.get_editor_world()
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def target_paths():
    return {
        target.get_path_name()
        for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D)
    }


def read_stats(target):
    raw = unreal.RenderingLibrary.read_render_target_raw(world, target, True)
    if raw is None:
        return {"read": False}
    maxima = [0.0, 0.0, 0.0, 0.0]
    nonzero = [0, 0, 0, 0]
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
    return {
        "read": True,
        "samples": len(raw),
        "max": maxima,
        "nonzero": nonzero,
    }


results = []
for label, system_path in SYSTEMS:
    before = target_paths()
    system = unreal.load_object(None, system_path)
    if system is None:
        raise RuntimeError("Missing Niagara system: " + system_path)
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.NiagaraActor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
    component.set_asset(system)
    component.set_force_solo(True)
    component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.TICK_DELTA_TIME)
    component.set_component_tick_enabled(True)
    component.reinitialize_system()
    component.activate(True)
    component.advance_simulation(30, 1.0 / 30.0)

    new_targets = []
    for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
        path = target.get_path_name()
        if path in before:
            continue
        try:
            size_x = int(target.get_editor_property("size_x"))
            size_y = int(target.get_editor_property("size_y"))
            target_format = str(
                target.get_editor_property("render_target_format")
            )
        except Exception:
            continue
        if size_x != 512 or size_y != 512:
            continue
        new_targets.append(
            {
                "path": path,
                "format": target_format,
                "stats": read_stats(target),
            }
        )
    results.append(
        {
            "label": label,
            "system": system_path,
            "active": bool(component.is_active()),
            "targets": new_targets,
        }
    )
    actor_subsystem.destroy_actor(actor)

print("GRIDMAIN_RUNTIME_COMPARE=" + json.dumps(results, sort_keys=True))
