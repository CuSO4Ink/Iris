import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
SERVICE = unreal.NiagaraScratchPadService
TARGETS = {
    "SSPR_InitAttrs",
    "SSPR_Projection",
    "SSPR_RasterizeWhiteParticles",
    "SSPR_ResetVelocityAfterSolve",
    "SSPR_ResolveGridToSimRT",
    "SSPR_DisplayCardSetup",
}


available = [
    str(value) for value in SERVICE.list_scratch_modules(SYSTEM, EMITTER)
]
modules = {}
for module in available:
    if module not in TARGETS:
        continue
    rows = []
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, module):
        if str(node.node_type) != "CustomHlsl":
            continue
        node_id = str(node.node_id)
        rows.append(
            {
                "id": node_id,
                "hlsl": str(
                    SERVICE.get_custom_hlsl_code(
                        SYSTEM, EMITTER, module, node_id
                    )
                ),
                "pins": [
                    {
                        "name": str(pin.pin_name),
                        "direction": str(pin.direction),
                        "type": str(pin.type_name),
                        "connected": bool(pin.is_connected),
                    }
                    for pin in SERVICE.get_node_pins(
                        SYSTEM, EMITTER, module, node_id
                    )
                ],
            }
        )
    modules[module] = rows

print(
    "V2_CORE="
    + json.dumps(
        {
            "availableModules": available,
            "modules": modules,
            "compileMessages": [
                str(item)
                for item in SERVICE.get_compile_messages(SYSTEM, False)
            ],
        },
        sort_keys=True,
    )
)
