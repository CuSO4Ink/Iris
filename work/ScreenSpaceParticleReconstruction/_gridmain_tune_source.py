import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/GridTrails/"
    "NS_SSPR_GridTrails_Main.NS_SSPR_GridTrails_Main"
)
EMITTER = "SourceParticles"


def call(tool_name, arguments):
    result = execute_tool(tool_name, json.dumps(arguments))
    if not isinstance(result, dict):
        raise RuntimeError(tool_name + " returned an invalid result")
    return result


def stack_ref(script, module, input_stack):
    return {
        "system": {"refPath": SYSTEM},
        "emitterName": EMITTER,
        "scriptName": script,
        "moduleName": module,
        "rendererIndex": -1,
        "inputNameStack": input_stack,
    }


def set_float(script, module, input_stack, value):
    result = call(
        "NiagaraToolsets.NiagaraToolset_System.SetStackInputData",
        {
            "stackInputRef": stack_ref(script, module, input_stack),
            "inputData": {
                "struct": {"refPath": "/Script/Niagara.NiagaraFloat"},
                "value": {"value": float(value)},
            },
        },
    )
    return {
        "script": script,
        "module": module,
        "input": input_stack,
        "requested": float(value),
        "result": result,
    }


def set_module_enabled(script, module, enabled):
    result = call(
        "NiagaraToolsets.NiagaraToolset_System.SetModuleEnabled",
        {
            "moduleRef": stack_ref(script, module, []),
            "bEnabled": bool(enabled),
        },
    )
    return {
        "script": script,
        "module": module,
        "enabled": bool(enabled),
        "result": result,
    }


changes = []
changes.append(set_float("EmitterUpdateScript", "SpawnRate", ["SpawnRate"], 5000.0))
changes.append(
    set_float(
        "ParticleSpawnScript",
        "InitializeParticle",
        ["Lifetime", "Minimum"],
        5.0,
    )
)
changes.append(
    set_float(
        "ParticleSpawnScript",
        "InitializeParticle",
        ["Lifetime", "Maximum"],
        5.0,
    )
)
changes.append(
    set_float(
        "ParticleSpawnScript",
        "SphereLocation",
        ["Sphere Radius"],
        50.0,
    )
)
changes.append(
    set_float(
        "ParticleSpawnScript",
        "CurlNoiseForce",
        ["Noise Strength"],
        350.0,
    )
)
changes.append(
    set_float(
        "ParticleSpawnScript",
        "CurlNoiseForce",
        ["Noise Frequency"],
        0.06,
    )
)
changes.append(
    set_float(
        "ParticleUpdateScript",
        "CurlNoiseForce001",
        ["Noise Strength"],
        500.0,
    )
)
changes.append(
    set_float(
        "ParticleUpdateScript",
        "CurlNoiseForce001",
        ["Noise Frequency"],
        0.06,
    )
)
changes.append(set_float("ParticleUpdateScript", "Drag", ["Drag"], 1.0))
changes.append(
    set_float(
        "ParticleUpdateScript",
        "Fluids_Gas_Source",
        ["Density"],
        1.0,
    )
)
changes.append(
    set_module_enabled("ParticleSpawnScript", "AddVelocityInCone", False)
)
changes.append(
    set_module_enabled("ParticleUpdateScript", "GravityForce", False)
)
changes.append(
    set_module_enabled("ParticleUpdateScript", "Collision001", False)
)

applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM))
compile_messages = [
    str(item)
    for item in unreal.NiagaraScratchPadService.get_compile_messages(
        SYSTEM, False
    )
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(
        "/Game/SSPR_Validation/M2/GridTrails/NS_SSPR_GridTrails_Main",
        False,
    )
)

print(
    "GRIDMAIN_TUNE="
    + json.dumps(
        {
            "system": SYSTEM,
            "changes": changes,
            "applied": applied,
            "compileMessages": compile_messages,
            "saved": saved,
        },
        sort_keys=True,
    )
)
if not applied or compile_messages or not saved:
    raise RuntimeError(
        "GridTrails source tuning failed verification: "
        + repr(
            {
                "applied": applied,
                "compileMessages": compile_messages,
                "saved": saved,
            }
        )
    )
