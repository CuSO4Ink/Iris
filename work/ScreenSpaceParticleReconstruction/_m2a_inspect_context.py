import json
import unreal

FOLDER = "/Game/SSPR_Validation"
SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"

assets = []
for data in unreal.EditorAssetLibrary.list_assets(FOLDER, recursive=True, include_folder=False):
    asset = unreal.load_asset(data)
    assets.append(
        {
            "path": str(data),
            "class": asset.get_class().get_name() if asset else None,
        }
    )

components = []
for component in unreal.ObjectIterator(unreal.NiagaraComponent):
    system = component.get_asset()
    if system and system.get_path_name() == SYSTEM:
        components.append(
            {
                "path": component.get_path_name(),
                "owner": (
                    component.get_owner().get_path_name()
                    if component.get_owner()
                    else None
                ),
                "active": bool(component.is_active()),
                "tick": bool(component.is_component_tick_enabled()),
            }
        )

result = {
    "assets": assets,
    "components": components,
    "world": (
        unreal.EditorLevelLibrary.get_editor_world().get_path_name()
        if unreal.EditorLevelLibrary.get_editor_world()
        else None
    ),
}
print("M2A_CONTEXT=" + json.dumps(result, sort_keys=True))
