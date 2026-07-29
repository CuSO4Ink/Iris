import json
import unreal

result = {}
for class_name in (
    "NiagaraTypeDefinition",
    "NiagaraTypeDefinitionHandle",
    "NiagaraVariable",
    "NiagaraVariableBase",
):
    cls = getattr(unreal, class_name, None)
    result[class_name] = {
        "exists": cls is not None,
        "members": (
            [
                name
                for name in dir(cls)
                if any(
                    token in name.lower()
                    for token in (
                        "type",
                        "class",
                        "register",
                        "index",
                    )
                )
            ]
            if cls is not None
            else []
        ),
    }
print(
    "PARTICLE_TYPE_DEFINITION_API="
    + json.dumps(result, sort_keys=True)
)
