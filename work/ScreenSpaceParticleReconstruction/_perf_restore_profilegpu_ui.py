import json
import unreal


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world, "r.ProfileGPU.ShowUI 1"
)
print(
    "PERF_PROFILEGPU_UI_RESTORED="
    + json.dumps({"showUI": True}, sort_keys=True)
)
