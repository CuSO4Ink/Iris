import json
import unreal

system = unreal.load_object(
    None,
    (
        "/Game/SSPR_Validation/M2/ParticleTrails/"
        "NS_SSPR_ParticleTrails_Main."
        "NS_SSPR_ParticleTrails_Main"
    ),
)
result = {
    "objectMethods": [
        name
        for name in dir(system)
        if any(
            token in name.lower()
            for token in ("root", "flag", "standalone")
        )
    ],
    "hasObjectFlags": hasattr(unreal, "ObjectFlags"),
}
print("PARTICLE_ROOTING_API=" + json.dumps(result, sort_keys=True))
