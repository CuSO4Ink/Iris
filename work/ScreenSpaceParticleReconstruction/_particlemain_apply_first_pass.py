import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
SERVICE = unreal.NiagaraScratchPadService

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)
]
grids = []
for grid in unreal.ObjectIterator(
    unreal.NiagaraDataInterfaceGrid2DCollection
):
    path = grid.get_path_name()
    if "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main" in path:
        grids.append(path)

print(
    "PARTICLE_FIRST_APPLY="
    + json.dumps(
        {"applied": applied, "messages": messages, "grids": grids},
        sort_keys=True,
    )
)
if not applied or messages:
    raise RuntimeError(
        "White-particle first compile failed: " + repr(messages)
    )
