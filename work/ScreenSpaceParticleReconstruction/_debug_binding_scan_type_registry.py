import json
import warnings
import unreal

matches = []
errors = []
for index in range(0, 512):
    try:
        handle = unreal.NiagaraTypeDefinitionHandle()
        handle.import_text(
            "(RegisteredTypeIndex=" + str(index) + ")"
        )
        variable = unreal.NiagaraVariableBase()
        variable.import_text(
            "(Name=\"Probe\",TypeDefHandle=(RegisteredTypeIndex="
            + str(index)
            + "))"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            definition = variable.get_editor_property("type_def")
        text = definition.export_text()
        if (
            "Grid2DCollection" in text
            or "Texture" in text
            or "RenderTarget" in text
        ):
            matches.append({"index": index, "type": text})
    except Exception as exc:
        errors.append({"index": index, "error": repr(exc)})
        if len(errors) >= 5:
            break

print(
    "BINDING_TYPE_REGISTRY="
    + json.dumps(
        {"matches": matches, "errors": errors},
        sort_keys=True,
    )
)
