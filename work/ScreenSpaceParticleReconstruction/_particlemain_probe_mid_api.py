import json
import unreal

result = {
    "moduleNames": [
        name
        for name in dir(unreal)
        if "material" in name.lower()
        and "library" in name.lower()
    ],
    "materialLibraryMethods": [
        name
        for name in dir(unreal.MaterialLibrary)
        if any(
            token in name.lower()
            for token in ("create", "dynamic", "material")
        )
    ],
    "midMethods": [
        name
        for name in dir(unreal.MaterialInstanceDynamic)
        if any(
            token in name.lower()
            for token in ("create", "parent", "parameter")
        )
    ],
    "componentMethods": [
        name
        for name in dir(unreal.NiagaraComponent)
        if "dynamic_material" in name.lower()
    ],
}
print("PARTICLE_MID_API=" + json.dumps(result, sort_keys=True))
