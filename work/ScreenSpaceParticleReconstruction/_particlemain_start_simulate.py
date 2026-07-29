import json
import unreal


def main():
    subsystem = unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    )
    subsystem.editor_request_begin_play()
    started = bool(subsystem.is_in_play_in_editor())
    print(
        "PARTICLE_SIMULATE_START="
        + json.dumps(
            {
                "started": started,
                "inPIE": bool(subsystem.is_in_play_in_editor()),
            },
            sort_keys=True,
        )
    )


main()
