import json
import unreal


SYSTEM = "/Game/SSPR_Validation/NS_SSPR_ProjTest.NS_SSPR_ProjTest"
EMITTER = "ProjParticles"
MODULE = "SSPR_WriteOccupancy"
HLSL_NODE = "1877D2CA4F034875E12FFB8B17F65DEE"
GRID_PATH = SYSTEM + ":NiagaraDataInterfaceGrid2DCollection_0"
SERVICE = unreal.NiagaraScratchPadService


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


grid = find_by_path(unreal.NiagaraDataInterfaceGrid2DCollection, GRID_PATH)
if grid is None:
    raise RuntimeError("Grid DI not found: " + GRID_PATH)

old_code = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))
if "OccupancyGrid.SetFloatValue<Attribute=Occupancy>" not in old_code:
    raise RuntimeError("Expected named Occupancy writer was not found")
if grid.get_editor_property("num_attributes") != 0:
    raise RuntimeError("Expected NumAttributes=0 before anonymous-channel patch")

new_code = old_code.replace(
    "OccupancyGrid.SetFloatValue<Attribute=Occupancy>(\n"
    "                    writePx.x, writePx.y, 1.0f);",
    "OccupancyGrid.SetValueAtIndex(\n"
    "                    writePx.x, writePx.y, 0, 1.0f);",
)
if new_code == old_code:
    raise RuntimeError("Exact writer replacement did not match")

grid.set_editor_property("num_attributes", 1)
if not SERVICE.set_custom_hlsl_code(
        SYSTEM, EMITTER, MODULE, HLSL_NODE, new_code):
    raise RuntimeError("SetCustomHlslCode failed")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [
    str(item)
    for item in SERVICE.get_compile_messages(SYSTEM, False)
]
stored_code = str(SERVICE.get_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, HLSL_NODE
))

result = {
    "applied": applied,
    "compileMessages": messages,
    "numAttributes": grid.get_editor_property("num_attributes"),
    "usesAnonymousChannel": "SetValueAtIndex" in stored_code,
    "usesNamedAttribute": "Attribute=Occupancy" in stored_code,
    "usesOldRTWrite": "SetRenderTargetValue" in stored_code,
}
print("ANONYMOUS_GRID_PATCH=" + json.dumps(result, sort_keys=True))

if (
    not applied
    or messages
    or result["numAttributes"] != 1
    or not result["usesAnonymousChannel"]
    or result["usesNamedAttribute"]
    or result["usesOldRTWrite"]
):
    raise RuntimeError("Anonymous Grid patch verification failed")
