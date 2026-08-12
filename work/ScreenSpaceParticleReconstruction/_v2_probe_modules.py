import json
import unreal

system = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
modules = [
    str(value)
    for value in unreal.NiagaraScratchPadService.list_scratch_modules(
        system, "Fountain"
    )
]
print("V2_MODULES=" + json.dumps(modules))
