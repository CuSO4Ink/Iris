import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "fx.ForceNiagaraTranslatorDump 1")
try:
    service = unreal.NiagaraScratchPadService
    emitter = "ProjParticles"
    module = "SSPR_WriteOccupancy"
    node = "1877D2CA4F034875E12FFB8B17F65DEE"
    code = str(service.get_custom_hlsl_code(SYSTEM_PATH, emitter, module, node))
    marker = "// CODEX_FORCE_TRANSLATOR_DUMP"
    if marker in code:
        code = code.replace(marker, marker + "_")
    else:
        code = code + "\n" + marker
    if not service.set_custom_hlsl_code(SYSTEM_PATH, emitter, module, node, code):
        raise RuntimeError("Failed to invalidate writer HLSL")
    applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM_PATH))
    messages = [
        str(item)
        for item in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM_PATH, False
        )
    ]
    print("HLSL_DUMP_COMPILE=" + repr({"applied": applied, "messages": messages}))
finally:
    unreal.SystemLibrary.execute_console_command(world, "fx.ForceNiagaraTranslatorDump 0")
