import json
import unreal


ACTOR_LABEL = "SSPR_M2A_TemporalOrchestrator"


def vector_data(value):
    return {"x": value.x, "y": value.y, "z": value.z}


def rotator_data(value):
    return {"pitch": value.pitch, "yaw": value.yaw, "roll": value.roll}


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

pivot = None
card = None
for component in actor.get_components_by_class(unreal.ActorComponent):
    if component.get_name() == "SmokeCardPivot":
        pivot = component
    elif component.get_name() == "SmokeCard":
        card = component

if pivot is None or card is None:
    raise RuntimeError(
        "Smoke card components missing: pivot={}, card={}".format(pivot, card)
    )

camera_manager = None
for candidate in unreal.ObjectIterator(unreal.PlayerCameraManager):
    try:
        world = candidate.get_world()
        if world and "UEDPIE" in world.get_path_name():
            camera_manager = candidate
            break
    except Exception:
        pass

card_location = card.get_world_location()
pivot_location = pivot.get_world_location()
pivot_rotation = pivot.get_world_rotation()
camera_location = None
camera_rotation = None
camera_distance = None
forward_alignment = None
if camera_manager:
    camera_location = camera_manager.get_camera_location()
    camera_rotation = camera_manager.get_camera_rotation()
    offset = pivot_location - camera_location
    camera_distance = offset.length()
    if camera_distance > 0.001:
        camera_forward = camera_rotation.get_forward_vector()
        forward_alignment = (
            offset.x * camera_forward.x
            + offset.y * camera_forward.y
            + offset.z * camera_forward.z
        ) / camera_distance

material = card.get_material(0)
static_mesh = card.get_editor_property("static_mesh")

recently_rendered = None
last_render_time = None
try:
    recently_rendered = card.was_recently_rendered(1.0)
except Exception:
    pass
try:
    last_render_time = card.get_last_render_time()
except Exception:
    pass

result = {
    "actor": actor.get_path_name(),
    "pivot": {
        "path": pivot.get_path_name(),
        "world_location": vector_data(pivot_location),
        "world_rotation": rotator_data(pivot_rotation),
    },
    "card": {
        "path": card.get_path_name(),
        "world_location": vector_data(card_location),
        "world_rotation": rotator_data(card.get_world_rotation()),
        "world_scale": vector_data(card.get_world_scale()),
        "visible": bool(card.is_visible()),
        "active": bool(card.is_active()),
        "mesh": static_mesh.get_path_name() if static_mesh else None,
        "material": material.get_path_name() if material else None,
        "recently_rendered": recently_rendered,
        "last_render_time": last_render_time,
    },
    "camera": {
        "path": camera_manager.get_path_name() if camera_manager else None,
        "location": vector_data(camera_location) if camera_location else None,
        "rotation": rotator_data(camera_rotation) if camera_rotation else None,
        "pivot_distance": camera_distance,
        "forward_alignment": forward_alignment,
    },
    "pie_niagara": [],
}
for component in unreal.ObjectIterator(unreal.NiagaraComponent):
    try:
        world = component.get_world()
        if not world or "UEDPIE" not in world.get_path_name():
            continue
        asset = component.get_editor_property("asset")
        result["pie_niagara"].append(
            {
                "path": component.get_path_name(),
                "asset": asset.get_path_name() if asset else None,
                "active": bool(component.is_active()),
                "auto_activate": bool(
                    component.get_editor_property("auto_activate")
                ),
                "tick_enabled": bool(
                    component.is_component_tick_enabled()
                ),
            }
        )
    except Exception:
        pass
print("M2CARD_RUNTIME=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
