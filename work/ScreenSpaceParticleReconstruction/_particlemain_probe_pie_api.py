import json
import unreal


subsystem = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
)
print(
    "PARTICLE_PIE_API="
    + json.dumps(
        [
            name
            for name in dir(subsystem)
            if any(
                token in name.lower()
                for token in (
                    "play",
                    "simulate",
                    "pie",
                    "editor",
                )
            )
        ],
        sort_keys=True,
    )
)
