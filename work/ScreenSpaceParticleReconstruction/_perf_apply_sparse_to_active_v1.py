import hashlib
import json
import unreal


ACTIVE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
ACTIVE_PACKAGE = ACTIVE.split(".", 1)[0]
CANDIDATE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Performance/"
    "NS_SSPR_AnisotropicSplat_PerfSparseV1."
    "NS_SSPR_AnisotropicSplat_PerfSparseV1"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService


def custom_node(system_path):
    for node in SERVICE.list_nodes(
        system_path, EMITTER, MODULE
    ):
        if str(node.node_type) == "CustomHlsl":
            return str(node.node_id)
    raise RuntimeError(
        "Missing Raster Custom HLSL node: " + system_path
    )


active_node = custom_node(ACTIVE)
candidate_node = custom_node(CANDIDATE)
dense_code = SERVICE.get_custom_hlsl_code(
    ACTIVE, EMITTER, MODULE, active_node
)
sparse_code = SERVICE.get_custom_hlsl_code(
    CANDIDATE, EMITTER, MODULE, candidate_node
)
if (
    "MaxLongSteps = 24" not in dense_code
    or "MaxCrossSteps = 5" not in dense_code
):
    raise RuntimeError(
        "Active system is not on the expected dense baseline"
    )
for token in (
    "G5.3 performance candidate",
    "massScale",
    "SparseMaxLongHalfSamples = 12",
    "SparseMaxCrossHalfSamples = 2",
):
    if token not in sparse_code:
        raise RuntimeError(
            "Sparse candidate is missing token: " + token
        )

restored_after_failure = False
try:
    if not SERVICE.set_custom_hlsl_code(
        ACTIVE,
        EMITTER,
        MODULE,
        active_node,
        sparse_code,
    ):
        raise RuntimeError(
            "Failed to set active sparse Raster HLSL"
        )
    applied = bool(SERVICE.apply_changes(ACTIVE))
    messages = [
        str(value)
        for value in SERVICE.get_compile_messages(ACTIVE, False)
    ]
    saved = bool(
        unreal.EditorAssetLibrary.save_asset(
            ACTIVE_PACKAGE, False
        )
    )
    if not applied or messages or not saved:
        raise RuntimeError(
            "Sparse active compile/save failed: "
            + repr(
                {
                    "applied": applied,
                    "messages": messages,
                    "saved": saved,
                }
            )
        )
except Exception:
    SERVICE.set_custom_hlsl_code(
        ACTIVE,
        EMITTER,
        MODULE,
        active_node,
        dense_code,
    )
    SERVICE.apply_changes(ACTIVE)
    unreal.EditorAssetLibrary.save_asset(
        ACTIVE_PACKAGE, False
    )
    restored_after_failure = True
    raise

installed = SERVICE.get_custom_hlsl_code(
    ACTIVE, EMITTER, MODULE, active_node
)
result = {
    "active": ACTIVE_PACKAGE,
    "recoveryAssets": [
        (
            "/Game/SSPR_Validation/Versions/"
            "V3_AnisotropicSplat_20260730/"
            "NS_SSPR_AnisotropicSplat_V3"
        ),
        CANDIDATE.split(".", 1)[0],
    ],
    "denseCodeSha256": hashlib.sha256(
        dense_code.encode("utf-8")
    ).hexdigest(),
    "sparseCodeSha256": hashlib.sha256(
        sparse_code.encode("utf-8")
    ).hexdigest(),
    "installedMatchesCandidate": installed == sparse_code,
    "restoredAfterFailure": restored_after_failure,
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
    "particlePopulationChanged": False,
    "resolutionChanged": False,
}
print(
    "PERF_APPLY_SPARSE_TO_ACTIVE_V1="
    + json.dumps(result, sort_keys=True)
)
if (
    not result["installedMatchesCandidate"]
    or not applied
    or messages
    or not saved
):
    raise RuntimeError(
        "Active sparse install gate failed: " + repr(result)
    )
