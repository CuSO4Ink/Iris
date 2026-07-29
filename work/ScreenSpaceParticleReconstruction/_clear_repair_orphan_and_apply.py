import json
import unreal

SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
BROKEN_NODE = "B47EA575449F2A202ABE6A81F7C87E33"
CALL_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest:"
    "ProjParticles_0.NiagaraScriptSource_0.NiagaraGraph_0."
    "NiagaraNodeFunctionCall_6"
)
ACTIVE_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest:"
    "SSPR_WriteOccupancy"
)
ORPHAN_PATH = (
    "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest:"
    "ProjParticles_0.NiagaraScratchPadContainer_0.SSPR_WriteOccupancy"
)


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


call_node = find_by_path(unreal.EdGraphNode, CALL_PATH)
active_script = find_by_path(unreal.NiagaraScript, ACTIVE_PATH)
orphan_script = find_by_path(unreal.NiagaraScript, ORPHAN_PATH)
if not call_node or not active_script or not orphan_script:
    raise RuntimeError(
        "Repair targets missing: "
        f"call={bool(call_node)} active={bool(active_script)} "
        f"orphan={bool(orphan_script)}"
    )

current_script = call_node.get_editor_property("function_script")
if current_script != active_script:
    raise RuntimeError(
        "Unexpected writer function script before repair: "
        + (current_script.get_path_name() if current_script else "None")
    )

notify_never = getattr(unreal.PropertyAccessChangeNotifyMode, "NEVER", None)
if notify_never is None:
    raise RuntimeError("PropertyAccessChangeNotifyMode.NEVER is unavailable")

deleted = False
try:
    call_node.set_editor_property("function_script", orphan_script, notify_never)
    if call_node.get_editor_property("function_script") != orphan_script:
        raise RuntimeError("Temporary orphan routing did not stick")
    deleted = bool(
        unreal.NiagaraScratchPadService.delete_node(
            SYSTEM, EMITTER, MODULE, BROKEN_NODE
        )
    )
    if not deleted:
        raise RuntimeError("Failed to delete corrupt orphan MapGet node")
finally:
    call_node.set_editor_property("function_script", active_script, notify_never)

if call_node.get_editor_property("function_script") != active_script:
    raise RuntimeError("Writer function script was not restored")

applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(SYSTEM, False)
]
result = {
    "deletedBrokenOrphanNode": deleted,
    "restoredWriterScript": (
        call_node.get_editor_property("function_script").get_path_name()
        == ACTIVE_PATH
    ),
    "applied": applied,
    "compileMessages": messages,
}
print("CLEAR_REPAIR=" + json.dumps(result, sort_keys=True))
if not applied or messages:
    raise RuntimeError("Repair/apply failed: " + " | ".join(messages))
