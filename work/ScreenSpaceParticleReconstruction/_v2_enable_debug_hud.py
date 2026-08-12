import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
command = (
    "fx.Niagara.Debug.Hud Enabled=1 OverviewEnabled=1 OverviewMode=0 "
    "FiltersEnabled=1 SystemFilter=*AnisotropicSplat* "
    "SystemDebugVerbosity=2 SystemEmitterVerbosity=2 "
    "DataInterfaceVerbosity=2 ShowRegisteredComponents=1"
)
unreal.SystemLibrary.execute_console_command(world, command)
print("V2_DEBUG_HUD=" + command)
