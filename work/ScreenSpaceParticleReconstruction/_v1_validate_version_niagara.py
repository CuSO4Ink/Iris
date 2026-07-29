import json
import unreal


SYSTEMS = {
    "v1": "/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main",
    "v2": "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main",
}


def main():
    result = {}
    for key, path in SYSTEMS.items():
        system = unreal.load_asset(path)
        if not isinstance(system, unreal.NiagaraSystem):
            raise RuntimeError(key + " Niagara system is missing")
        messages = [
            str(value)
            for value in unreal.NiagaraScratchPadService.get_compile_messages(
                path, False
            )
        ]
        result[key] = {
            "path": system.get_path_name(),
            "compileMessages": messages,
        }
        if messages:
            raise RuntimeError(key + " Niagara compile messages: " + repr(messages))
    print("SSPR_VERSION_NIAGARA_GATE=" + json.dumps(result, sort_keys=True))


main()
