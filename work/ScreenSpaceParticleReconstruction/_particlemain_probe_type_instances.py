import json
import unreal

result = {}
try:
    type_definition = unreal.NiagaraTypeDefinition()
    type_definition.set_editor_property(
        "class_struct_or_enum",
        unreal.NiagaraDataInterfaceGrid2DCollection.static_class(),
    )
    result["typeDefinition"] = {
        "repr": repr(type_definition),
        "str": str(type_definition),
        "export": type_definition.export_text(),
        "dict": type_definition.to_dict(),
        "tuple": list(type_definition.to_tuple()),
        "methods": [
            name
            for name in dir(type_definition)
            if not name.startswith("_")
        ],
    }
    handle = unreal.NiagaraTypeDefinitionHandle()
    result["handle"] = {
        "repr": repr(handle),
        "export": handle.export_text(),
        "dict": handle.to_dict(),
        "tuple": list(handle.to_tuple()),
        "methods": [
            name
            for name in dir(handle)
            if not name.startswith("_")
        ],
    }
except Exception as exc:
    result["error"] = repr(exc)

print(
    "PARTICLE_TYPE_INSTANCES="
    + json.dumps(result, sort_keys=True)
)
