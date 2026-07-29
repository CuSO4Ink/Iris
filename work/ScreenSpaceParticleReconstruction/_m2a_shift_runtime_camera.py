import json
import unreal

manager = None
for candidate in unreal.ObjectIterator(unreal.PlayerCameraManager):
    try:
        world = candidate.get_world()
        if world and "UEDPIE" in world.get_path_name():
            manager = candidate
            break
    except Exception:
        pass
if manager is None:
    raise RuntimeError("PIE PlayerCameraManager not found")

controller = None
for candidate in unreal.ObjectIterator(unreal.PlayerController):
    try:
        world = candidate.get_world()
        if world and "UEDPIE" in world.get_path_name():
            controller = candidate
            break
    except Exception:
        pass
if controller is None:
    raise RuntimeError("PIE PlayerController not found")

view_target = controller.get_view_target()
if view_target is None:
    raise RuntimeError("PlayerController has no view target")

before_target = view_target.get_actor_location()
before_camera = manager.get_camera_location()
after_target = before_target + unreal.Vector(0.0, 100.0, 0.0)
view_target.set_actor_location(after_target, False, False)

print(
    "M2A_CAMERA_SHIFT "
    + json.dumps(
        {
            "manager": manager.get_path_name(),
            "viewTarget": view_target.get_path_name(),
            "targetBefore": str(before_target),
            "targetAfter": str(after_target),
            "cameraBefore": str(before_camera),
        },
        ensure_ascii=False,
    )
)
