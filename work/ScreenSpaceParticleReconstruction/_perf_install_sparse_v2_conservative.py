import ast
import hashlib
import json
import unreal

TARGET_PACKAGE = (
    "/Game/SSPR_Validation/Performance/DenseG5SparseV2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
TARGET = TARGET_PACKAGE + ".NS_SSPR_AnisotropicSplat_Main"
EMITTER = "Fountain"
RASTER_MODULE = "SSPR_RasterizeWhiteParticles"
SPARSE_V1_SCRIPT = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_perf_create_sparse_raster_v1.py"
)
SERVICE = unreal.NiagaraScratchPadService


def custom_hlsl_node(system_path, module_name):
    for node in SERVICE.list_nodes(system_path, EMITTER, module_name):
        if str(node.node_type) == "CustomHlsl":
            return str(node.node_id)
    raise RuntimeError(
        "Missing Custom HLSL node: {} / {}".format(
            system_path, module_name
        )
    )


def source_sparse_code():
    with open(SPARSE_V1_SCRIPT, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), SPARSE_V1_SCRIPT)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "raster_code"
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("Sparse V1 raster_code literal was not found")


registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(
    ["/Game/SSPR_Validation/Performance/DenseG5SparseV2"],
    True,
    False,
)
candidate = unreal.load_asset(TARGET_PACKAGE)
if not isinstance(candidate, unreal.NiagaraSystem):
    raise RuntimeError("Raw-copy Sparse V2 candidate failed to load")
if candidate.get_path_name() != TARGET:
    raise RuntimeError(
        "Raw-copy candidate loaded under an unexpected path: "
        + candidate.get_path_name()
    )

raster_node = custom_hlsl_node(TARGET, RASTER_MODULE)
dense_code = SERVICE.get_custom_hlsl_code(
    TARGET, EMITTER, RASTER_MODULE, raster_node
)
for token in (
    "MaxLongSteps = 24",
    "MaxCrossSteps = 5",
    "InterlockedAddIntGridValue",
    "InterlockedMaxFloatGridValue",
):
    if token not in dense_code:
        raise RuntimeError(
            "Raw-copy candidate is not the expected Dense G5: " + token
        )

raster_code = source_sparse_code()
raster_code = raster_code.replace(
    "// G5.3 performance candidate: mass-conserving sparse Gaussian splat.",
    (
        "// G5.3 Sparse V2 conservative candidate: "
        "mass-conserving Gaussian splat."
    ),
)
raster_code = raster_code.replace(
    "represented by at most 25x5 weighted samples.",
    "represented by at most 33x7 weighted samples.",
)
raster_code = raster_code.replace(
    "const int SparseMaxLongHalfSamples = 12;",
    "const int SparseMaxLongHalfSamples = 16;",
)
raster_code = raster_code.replace(
    "const int SparseMaxCrossHalfSamples = 2;",
    "const int SparseMaxCrossHalfSamples = 3;",
)
raster_code = raster_code.replace(
    """bool validUV =
    inFront &&
    currentUV.x >= 0.0f && currentUV.x < 1.0f &&
    currentUV.y >= 0.0f && currentUV.y < 1.0f;""",
    "bool validUV = inFront;",
)
raster_code = raster_code.replace(
    """int activeLong = (int)ceil(halfLength);
int activeCross = (int)ceil(halfWidth);""",
    """int activeLong = (int)ceil(halfLength);
int activeCross = (int)ceil(halfWidth);
float conservativeExtent = halfLength + halfWidth + 1.0f;
bool overlapsGrid =
    centerPx.x >= -conservativeExtent &&
    centerPx.x < (float)safeW + conservativeExtent &&
    centerPx.y >= -conservativeExtent &&
    centerPx.y < (float)safeH + conservativeExtent;""",
)
raster_code = raster_code.replace(
    "if (validSize && validUV && densityPerParticle > 0.0f)",
    (
        "if (validSize && validUV && overlapsGrid && "
        "densityPerParticle > 0.0f)"
    ),
)
raster_code = raster_code.replace(
    "approximately 1.96 px longitudinally and 1.4 px transversely.",
    "at most approximately 1.49 px longitudinally and 1.57 px transversely.",
)

required_tokens = (
    "Sparse V2 conservative candidate",
    "SparseMaxLongHalfSamples = 16",
    "SparseMaxCrossHalfSamples = 3",
    "overlapsGrid",
    "massScale",
)
for token in required_tokens:
    if token not in raster_code:
        raise RuntimeError("Sparse V2 code assembly failed: " + token)

if not SERVICE.set_custom_hlsl_code(
    TARGET,
    EMITTER,
    RASTER_MODULE,
    raster_node,
    raster_code,
):
    raise RuntimeError("Failed to install Sparse V2 Raster HLSL")

applied = bool(SERVICE.apply_changes(TARGET))
messages = [
    str(value) for value in SERVICE.get_compile_messages(TARGET, False)
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(TARGET_PACKAGE, False)
)
installed_code = SERVICE.get_custom_hlsl_code(
    TARGET, EMITTER, RASTER_MODULE, raster_node
)
result = {
    "target": TARGET,
    "rawCopyLoaded": True,
    "applied": applied,
    "saved": saved,
    "compileMessages": messages,
    "denseCodeSha256": hashlib.sha256(
        dense_code.encode("utf-8")
    ).hexdigest(),
    "sparseCodeSha256": hashlib.sha256(
        raster_code.encode("utf-8")
    ).hexdigest(),
    "installedMatches": installed_code == raster_code,
    "denseMaxSamples": 49 * 11,
    "sparseMaxSamples": 33 * 7,
    "maxAtomicReduction": 1.0 - (33.0 * 7.0) / (49.0 * 11.0),
    "particlePopulationChanged": False,
    "resolutionChanged": False,
    "fixedTick": bool(
        candidate.get_editor_property("fixed_tick_delta")
    ),
    "fixedTickDeltaTime": float(
        candidate.get_editor_property("fixed_tick_delta_time")
    ),
}
print(
    "PERF_INSTALL_SPARSE_V2_CONSERVATIVE="
    + json.dumps(result, sort_keys=True)
)
if (
    not applied
    or messages
    or not saved
    or not result["installedMatches"]
    or not result["fixedTick"]
):
    raise RuntimeError(
        "Sparse V2 installation gate failed: " + repr(result)
    )
