import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
SOURCE_GRID_PATH = SYSTEM_PATH + ":NiagaraDataInterfaceGrid2DCollection_0"


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


source_grid = find_by_path(
    unreal.NiagaraDataInterfaceGrid2DCollection, SOURCE_GRID_PATH
)
if source_grid is None:
    raise RuntimeError("Source Grid2DCollection is missing")
source_binding = source_grid.get_editor_property("render_target_user_parameter")

patched = []
for grid in unreal.ObjectIterator(unreal.NiagaraDataInterfaceGrid2DCollection):
    path = grid.get_path_name()
    if SYSTEM_PATH not in path or ".NiagaraGraph_0." not in path:
        continue
    if (
        grid.get_editor_property("num_cells_x") != 256
        or grid.get_editor_property("num_cells_y") != 256
        or grid.get_editor_property("num_attributes") != 1
    ):
        continue
    grid.set_editor_property("render_target_user_parameter", source_binding)
    grid.set_editor_property("clear_before_non_iteration_stage", True)
    patched.append(path)

if not patched:
    raise RuntimeError("No 256x256 module-local Grid2DCollection was found")

applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM_PATH))
messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(
        SYSTEM_PATH, False
    )
]
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PATH, False))
result = {
    "patched": patched,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
}
print("LOCAL_GRID_FINALIZED=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Grid module recompilation failed: " + repr(result))
