import json
import unreal

methods = [
    name
    for name in dir(unreal.NiagaraScratchPadService)
    if any(
        token in name.lower()
        for token in (
            "remove",
            "delete",
            "input",
            "pin",
            "hlsl",
        )
    )
]
print(
    "PARTICLE_SCRATCH_REMOVE_API="
    + json.dumps(methods, sort_keys=True)
)
