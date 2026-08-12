import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world,
    "fx.Niagara.DumpComponents full filter=NS_SSPR_AnisotropicSplat_Main",
)
print("V2_DUMP_COMPONENTS=issued")
