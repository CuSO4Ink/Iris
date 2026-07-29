import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)

system = unreal.load_asset(SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("V2 Niagara system is missing")

result = {}
for name in ("fixed_tick_delta", "fixed_tick_delta_time"):
    try:
        result[name] = system.get_editor_property(name)
    except Exception as error:
        result[name] = "ERROR: " + str(error)

print("V2_FIXED_TICK=" + json.dumps(result, sort_keys=True))
