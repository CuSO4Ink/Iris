import json
import unreal

result = {}
grid_class = unreal.NiagaraDataInterfaceGrid2DCollection.static_class()

definition = unreal.NiagaraTypeDefinition()
try:
    definition.set_editor_property(
        "class_struct_or_enum", grid_class
    )
    result["definitionSet"] = definition.export_text()
except Exception as exc:
    result["definitionSetError"] = repr(exc)

for label, factory in (
    (
        "definitionKw",
        lambda: unreal.NiagaraTypeDefinition(
            class_struct_or_enum=grid_class
        ),
    ),
    (
        "variableTypeDefKw",
        lambda: unreal.NiagaraVariableBase(
            name="User.Probe", type_def=definition
        ),
    ),
    (
        "variableDefinitionKw",
        lambda: unreal.NiagaraVariableBase(
            name="User.Probe", type_definition=definition
        ),
    ),
):
    try:
        value = factory()
        result[label] = value.export_text()
        try:
            result[label + "TypeDef"] = (
                value.type_def().export_text()
            )
        except Exception as exc:
            result[label + "TypeDefError"] = repr(exc)
    except Exception as exc:
        result[label + "Error"] = repr(exc)

print("BINDING_CONSTRUCT_TYPES=" + json.dumps(result, sort_keys=True))
