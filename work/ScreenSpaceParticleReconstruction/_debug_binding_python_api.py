import json
import unreal

names = (
    "NiagaraMaterialAttributeBinding",
    "NiagaraRendererMaterialParameters",
    "NiagaraVariableBase",
    "NiagaraVariable",
    "NiagaraTypeDefinition",
    "NiagaraTypeDefinitionHandle",
)
result = {}
result["matchingUnrealNames"] = [
    name
    for name in dir(unreal)
    if "NiagaraType" in name or "NiagaraVariable" in name
]
for name in names:
    cls = getattr(unreal, name, None)
    row = {
        "exists": cls is not None,
        "class": str(cls),
    }
    if cls is not None:
        row["dir"] = [
            member
            for member in dir(cls)
            if not member.startswith("_")
        ]
        try:
            value = cls()
            row["constructed"] = repr(value)
            try:
                row["dict"] = value.to_dict()
            except Exception as exc:
                row["dictError"] = repr(exc)
            try:
                row["export"] = value.export_text()
            except Exception as exc:
                row["exportError"] = repr(exc)
            row["valueDir"] = [
                member
                for member in dir(value)
                if not member.startswith("_")
            ]
        except Exception as exc:
            row["constructError"] = repr(exc)
    result[name] = row

print("BINDING_PYTHON_API=" + json.dumps(result, sort_keys=True))
