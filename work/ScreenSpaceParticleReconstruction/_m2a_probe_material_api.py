import json
import unreal

classes = [
    unreal.Material,
    unreal.MaterialExpressionCustom,
    unreal.MaterialExpressionTextureObjectParameter,
    unreal.MaterialExpressionTextureCoordinate,
    unreal.MaterialExpressionScalarParameter,
]

result = {}
for cls in classes:
    result[cls.__name__] = {
        "doc": str(cls.__doc__ or "")[:4000],
        "members": [
            name
            for name in dir(cls)
            if any(
                token in name.lower()
                for token in (
                    "input",
                    "output",
                    "code",
                    "parameter",
                    "texture",
                    "material",
                )
            )
        ],
    }

result["CustomInput"] = {
    "doc": str(unreal.CustomInput.__doc__ or "")[:4000],
    "members": dir(unreal.CustomInput),
}
print("M2A_MATERIAL_API=" + json.dumps(result, sort_keys=True))
