import ast
import hashlib
import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
SYSTEM_PACKAGE = SYSTEM.split(".", 1)[0]
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
ACTOR_LABEL = "SSPR_ParticleTrails_Main"
INSTALL_SOURCE = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_g5_install_fields.py"
)
EXPECTED_DENSE_SHA256 = (
    "69dc67f6e9a58fa457982b6dfee3889e11e04f838b5934b56cb3891bec20598c"
)
EXPECTED_SPARSE_SHA256 = (
    "761b87f75279b469d6cd5628dffe3a4c1df04eaa351943e602438c6b438e92b4"
)
SERVICE = unreal.NiagaraScratchPadService


def raster_custom_node():
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE):
        if str(node.node_type) == "CustomHlsl":
            return str(node.node_id)
    raise RuntimeError("Raster Custom HLSL node not found")


def load_dense_code():
    with open(INSTALL_SOURCE, encoding="utf-8") as source_file:
        tree = ast.parse(source_file.read(), INSTALL_SOURCE)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name)
            and target.id == "raster_code"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("raster_code not found in G5 install source")


dense_code = load_dense_code()
dense_sha256 = hashlib.sha256(
    dense_code.encode("utf-8")
).hexdigest()
if dense_sha256 != EXPECTED_DENSE_SHA256:
    raise RuntimeError(
        "Dense recovery code hash mismatch: " + dense_sha256
    )

custom_node = raster_custom_node()
before_code = SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, custom_node
)
before_sha256 = hashlib.sha256(
    before_code.encode("utf-8")
).hexdigest()
if before_sha256 not in (
    EXPECTED_SPARSE_SHA256,
    EXPECTED_DENSE_SHA256,
):
    raise RuntimeError(
        "Active Raster is neither recorded Sparse nor Dense: "
        + before_sha256
    )

if before_sha256 != EXPECTED_DENSE_SHA256:
    if not SERVICE.set_custom_hlsl_code(
        SYSTEM,
        EMITTER,
        MODULE,
        custom_node,
        dense_code,
    ):
        raise RuntimeError("Failed to restore Dense Raster HLSL")

applied = bool(SERVICE.apply_changes(SYSTEM))
compile_messages = [
    str(value)
    for value in SERVICE.get_compile_messages(SYSTEM, False)
]
saved = bool(
    unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False)
)
installed_code = SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, custom_node
)
installed_sha256 = hashlib.sha256(
    installed_code.encode("utf-8")
).hexdigest()
if (
    not applied
    or compile_messages
    or not saved
    or installed_sha256 != EXPECTED_DENSE_SHA256
):
    raise RuntimeError(
        "Dense restore compile/save gate failed: "
        + repr(
            {
                "applied": applied,
                "messages": compile_messages,
                "saved": saved,
                "installedSha256": installed_sha256,
            }
        )
    )

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
actors = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors()
actor = next(
    item
    for item in actors
    if item.get_actor_label() == ACTOR_LABEL
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]
if component.get_asset().get_path_name() != SYSTEM:
    raise RuntimeError("Active actor is not using the V2 System")

component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(180, 1.0 / 60.0)

result = {
    "system": SYSTEM_PACKAGE,
    "beforeSha256": before_sha256,
    "installedSha256": installed_sha256,
    "restoredFromSparse": (
        before_sha256 == EXPECTED_SPARSE_SHA256
    ),
    "applied": applied,
    "compileMessages": compile_messages,
    "saved": saved,
    "active": bool(component.is_active()),
    "advancedFrames": 180,
}
print(
    "PERF_RESTORE_DENSE_AFTER_VISUAL_FAIL="
    + json.dumps(result, sort_keys=True)
)
