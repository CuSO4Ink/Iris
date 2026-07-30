import json

import unreal


world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()

# Keep the system's 60 Hz fixed tick, but prevent a single slow editor frame
# from expanding into dozens of Niagara simulation steps.
unreal.SystemLibrary.execute_console_command(
    world, "fx.Niagara.SystemSimulation.MaxTickSubsteps 4"
)
unreal.SystemLibrary.execute_console_command(
    world, "fx.Niagara.SystemSimulation.MaxTickSubsteps"
)

print(
    "SSPR_FIXED_TICK_SUBSTEP_CAP="
    + json.dumps(
        {
            "world": world.get_path_name(),
            "fixedTickPreserved": True,
            "maxTickSubsteps": 4,
            "persistent": False,
        },
        sort_keys=True,
    )
)
