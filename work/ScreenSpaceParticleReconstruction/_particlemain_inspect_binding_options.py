import json
import unreal

SYSTEMS = {
    "main": (
        "/Game/SSPR_Validation/M2/ParticleTrails/"
        "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
    ),
    "m1": (
        "/Game/SSPR_Validation/NS_SSPR_ProjTest."
        "NS_SSPR_ProjTest"
    ),
}


def safe_value(value):
    if isinstance(value, unreal.Object):
        return value.get_path_name()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


result = {"systems": {}, "classes": {}}
for label, path in SYSTEMS.items():
    system = unreal.load_object(None, path)
    entry = {
        "path": path,
        "loaded": isinstance(system, unreal.NiagaraSystem),
    }
    if isinstance(system, unreal.NiagaraSystem):
        try:
            variables = unreal.NiagaraToolset_System.get_user_variables(system)
            entry["userVariables"] = [str(item) for item in variables]
        except Exception as exc:
            entry["userVariablesError"] = repr(exc)
    result["systems"][label] = entry

for class_name in (
    "NiagaraGrid2DCollectionRendererProperties",
    "NiagaraSpriteRendererProperties",
    "NiagaraDataInterfaceGrid2DCollection",
):
    cls = getattr(unreal, class_name, None)
    class_entry = {"exists": cls is not None}
    if cls is not None:
        class_entry["class"] = str(cls)
        try:
            default = unreal.get_default_object(cls)
            class_entry["default"] = default.get_path_name()
            class_entry["properties"] = sorted(
                [
                    name
                    for name in dir(default)
                    if not name.startswith("_")
                    and any(
                        token in name.lower()
                        for token in (
                            "material",
                            "binding",
                            "source",
                            "render",
                            "grid",
                            "texture",
                            "parameter",
                        )
                    )
                ]
            )
        except Exception as exc:
            class_entry["defaultError"] = repr(exc)
    result["classes"][class_name] = class_entry

print("PARTICLE_BINDING_OPTIONS=" + json.dumps(result, sort_keys=True))
