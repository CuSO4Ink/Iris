import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
SOURCE_RT_DI_PATH = SYSTEM_PATH + ":NiagaraDataInterfaceRenderTarget2D_1"


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


source_rt_di = find_by_path(
    unreal.NiagaraDataInterfaceRenderTarget2D, SOURCE_RT_DI_PATH
)
if source_rt_di is None:
    raise RuntimeError("Source RenderTarget2D DI is missing")
source_binding = source_rt_di.get_editor_property("render_target_user_parameter")

patched = []
for rt_di in unreal.ObjectIterator(unreal.NiagaraDataInterfaceRenderTarget2D):
    path = rt_di.get_path_name()
    if SYSTEM_PATH not in path or ".NiagaraGraph_0." not in path:
        continue
    size = rt_di.get_editor_property("size")
    if int(size.x) != 256 or int(size.y) != 256:
        continue
    rt_di.set_editor_property("render_target_user_parameter", source_binding)
    rt_di.set_editor_property("inherit_user_parameter_settings", True)
    patched.append(path)

if not patched:
    raise RuntimeError("No 256x256 module-local RenderTarget2D DI was found")

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
print("LOCAL_RT_FINALIZED=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("RenderTarget2D module recompilation failed: " + repr(result))
