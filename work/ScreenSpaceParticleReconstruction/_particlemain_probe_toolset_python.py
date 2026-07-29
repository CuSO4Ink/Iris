import json
import unreal

names = []
toolset = getattr(unreal, "NiagaraToolset_System", None)
if toolset is not None:
    names = [
        name
        for name in dir(toolset)
        if any(
            token in name.lower()
            for token in (
                "user",
                "renderer",
                "variable",
                "stack",
            )
        )
    ]
print(
    "PARTICLE_TOOLSET_PYTHON="
    + json.dumps(
        {
            "exists": toolset is not None,
            "names": names,
        },
        sort_keys=True,
    )
)
