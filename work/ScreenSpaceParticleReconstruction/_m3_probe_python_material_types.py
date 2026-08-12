import json
import unreal


def main():
    names = [
        name
        for name in dir(unreal)
        if "CustomInput" in name
        or "CustomOutput" in name
        or "CustomMaterialOutput" in name
        or "FunctionInputType" in name
    ]
    rows = {"names": names}
    for name in names:
        value = getattr(unreal, name)
        rows[name] = {
            "repr": repr(value),
            "members": [
                member
                for member in dir(value)
                if not member.startswith("_")
            ],
        }
        try:
            instance = value()
            rows[name]["instance"] = repr(instance)
        except Exception as exc:
            rows[name]["constructError"] = str(exc)
    print("M3_PYTHON_TYPES=" + json.dumps(rows, sort_keys=True))


main()
