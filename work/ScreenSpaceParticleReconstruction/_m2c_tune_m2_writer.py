import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/M2/"
    "NS_SSPR_ProjTest_M2.NS_SSPR_ProjTest_M2"
)
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
service = unreal.NiagaraScratchPadService

code = str(
    service.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
expected = (
    "const float TrailTime = 0.040f;",
    "const float MaxTrailPx = 12.0f;",
    "const int MaxTrailSteps = 12;",
)
missing = [text for text in expected if text not in code]
if missing:
    raise RuntimeError(
        "Unexpected M2 writer constants; refusing blind replacement: "
        + repr(missing)
    )

tuned = code
tuned = tuned.replace(
    "const float TrailTime = 0.040f;",
    "const float TrailTime = 0.075f;",
)
tuned = tuned.replace(
    "const float MaxTrailPx = 12.0f;",
    "const float MaxTrailPx = 20.0f;",
)
tuned = tuned.replace(
    "const int MaxTrailSteps = 12;",
    "const int MaxTrailSteps = 20;",
)
if tuned == code:
    raise RuntimeError("M2 writer tuning made no changes")

if not service.set_custom_hlsl_code(
    SYSTEM,
    EMITTER,
    MODULE,
    HLSL_NODE,
    tuned,
):
    raise RuntimeError("Failed to set tuned M2 writer")
applied = bool(service.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in service.get_compile_messages(SYSTEM, False)
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(
        "/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2",
        False,
    )
)
stored = str(
    service.get_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        HLSL_NODE,
    )
)
result = {
    "applied": applied,
    "messages": messages,
    "saved": saved,
    "trailTime": "const float TrailTime = 0.075f;" in stored,
    "maxTrail": "const float MaxTrailPx = 20.0f;" in stored,
    "steps": "const int MaxTrailSteps = 20;" in stored,
    "containsHistoryRead": "LoadRenderTargetValue" in stored,
}
print("M2C_WRITER_TUNING=" + json.dumps(result, sort_keys=True))
if (
    not applied
    or messages
    or not saved
    or not result["trailTime"]
    or not result["maxTrail"]
    or not result["steps"]
    or result["containsHistoryRead"]
):
    raise RuntimeError("M2 writer tuning verification failed: " + repr(result))
