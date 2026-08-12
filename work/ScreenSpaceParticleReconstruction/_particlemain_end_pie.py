import unreal

def main():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    was_playing = bool(level_editor.is_in_play_in_editor())
    if was_playing:
        level_editor.editor_request_end_play()

    result = {
        "was_playing": was_playing,
        "end_requested": was_playing,
    }
    print(result)


main()
