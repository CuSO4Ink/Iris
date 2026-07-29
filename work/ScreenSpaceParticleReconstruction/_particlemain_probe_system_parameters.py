import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
system = unreal.load_object(None, SYSTEM)
result = {
    "members": [
        name
        for name in dir(system)
        if any(
            token in name.lower()
            for token in (
                "parameter",
                "exposed",
                "variable",
                "store",
            )
        )
    ]
}
for property_name in (
    "exposed_parameters",
    "exposed_parameters_deprecated",
):
    try:
        value = system.get_editor_property(property_name)
        result[property_name] = {
            "repr": repr(value),
            "export": (
                value.export_text()
                if hasattr(value, "export_text")
                else str(value)
            ),
            "members": [
                name
                for name in dir(value)
                if any(
                    token in name.lower()
                    for token in (
                        "parameter",
                        "variable",
                        "store",
                        "get",
                    )
                )
            ],
        }
    except Exception as exc:
        result[property_name] = {"error": repr(exc)}

print(
    "PARTICLE_SYSTEM_PARAMETERS="
    + json.dumps(result, sort_keys=True)
)
