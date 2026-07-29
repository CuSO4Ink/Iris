import json
import unreal


CVARS = (
    "r.AntiAliasingMethod",
    "r.PostProcessAAQuality",
    "r.TemporalAA.Quality",
    "r.TSR.Quality",
)


def read_values():
    return {
        name: int(unreal.SystemLibrary.get_console_variable_int_value(name))
        for name in CVARS
    }


def main():
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    if world is None:
        raise RuntimeError("Editor world is missing")

    before = read_values()
    commands = (
        "r.AntiAliasingMethod 0",
        "r.PostProcessAAQuality 0",
        "r.TemporalAA.Quality 0",
        "r.TSR.Quality 0",
    )
    for command in commands:
        unreal.SystemLibrary.execute_console_command(world, command)

    level_editor = unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    )
    level_editor.editor_invalidate_viewports()
    after = read_values()
    result = {
        "before": before,
        "after": after,
        "sessionOnly": True,
    }
    print(
        "PARTICLE_TEMPORAL_AA_DISABLED="
        + json.dumps(result, sort_keys=True)
    )
    if any(after[name] != 0 for name in CVARS):
        raise RuntimeError("Failed to disable temporal AA: " + repr(result))


main()
