import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
EMITTER = "Fountain"

ok = bool(unreal.NiagaraEmitterService.set_sim_target(SYSTEM, EMITTER, "GPU"))
saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM, False))
messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(
        SYSTEM, False
    )
]
print(
    "PARTICLE_MAIN_GPU="
    + json.dumps(
        {"set": ok, "saved": saved, "compileMessages": messages},
        sort_keys=True,
    )
)
if not ok or not saved:
    raise RuntimeError("Failed to switch white-particle mainline to GPU")
