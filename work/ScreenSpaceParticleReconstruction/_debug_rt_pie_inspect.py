import json
import unreal

DEBUG_PREFIX = (
    "/Game/SSPR_Validation/Debug/"
    "NS_SSPR_RTWriteProbe_"
)
rows = []
for component in unreal.ObjectIterator(unreal.NiagaraComponent):
    asset = component.get_asset()
    if asset is None or not asset.get_path_name().startswith(
        DEBUG_PREFIX
    ):
        continue
    world = component.get_world()
    owner = component.get_owner()
    rows.append(
        {
            "component": component.get_path_name(),
            "asset": asset.get_path_name(),
            "world": world.get_path_name() if world else None,
            "owner": owner.get_path_name() if owner else None,
            "active": bool(component.is_active()),
            "tick": bool(component.is_component_tick_enabled()),
        }
    )
print("RT_PIE_COMPONENTS=" + json.dumps(rows, sort_keys=True))
