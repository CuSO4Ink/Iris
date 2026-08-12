import json
import unreal

MATERIAL_PATH = "/Game/SSPR_Validation/M2/M_SSPR_TemporalCombine"
material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
if material is None or not isinstance(material, unreal.Material):
    raise RuntimeError("Temporal material is missing")

library = unreal.MaterialEditingLibrary
expressions = list(library.get_material_expressions(material))

custom_nodes = [
    item for item in expressions if isinstance(item, unreal.MaterialExpressionCustom)
]
if len(custom_nodes) != 1:
    raise RuntimeError("Expected exactly one Custom expression")
custom = custom_nodes[0]

texture_parameters = {
    str(item.get_editor_property("parameter_name")): item
    for item in expressions
    if isinstance(item, unreal.MaterialExpressionTextureObjectParameter)
}
scalar_parameters = {
    str(item.get_editor_property("parameter_name")): item
    for item in expressions
    if isinstance(item, unreal.MaterialExpressionScalarParameter)
}
vector_parameters = {
    str(item.get_editor_property("parameter_name")): item
    for item in expressions
    if isinstance(item, unreal.MaterialExpressionVectorParameter)
}
uv_nodes = [
    item for item in expressions if isinstance(item, unreal.MaterialExpressionTextureCoordinate)
]
if len(uv_nodes) != 1:
    raise RuntimeError("Expected exactly one TextureCoordinate expression")
uv = uv_nodes[0]

new_scalars = (
    ("CameraDataValid", 0.0),
    ("TanHalfHorizontalFOV", 1.0),
    ("ViewAspect", 1.7777778),
    ("CameraCutDistance", 2000.0),
    ("CameraCutCosine", 0.5),
)
for index, (name, value) in enumerate(new_scalars):
    if name not in scalar_parameters:
        expression = library.create_material_expression(
            material,
            unreal.MaterialExpressionScalarParameter,
            -1300,
            750 + index * 120,
        )
        expression.set_editor_property("parameter_name", name)
        expression.set_editor_property("default_value", value)
        scalar_parameters[name] = expression

vector_specs = (
    ("CurrentCameraPosition", unreal.LinearColor(0.0, 0.0, 0.0, 0.0)),
    ("CurrentCameraForward", unreal.LinearColor(1.0, 0.0, 0.0, 0.0)),
    ("CurrentCameraRight", unreal.LinearColor(0.0, 1.0, 0.0, 0.0)),
    ("CurrentCameraUp", unreal.LinearColor(0.0, 0.0, 1.0, 0.0)),
    ("PreviousCameraPosition", unreal.LinearColor(0.0, 0.0, 0.0, 0.0)),
    ("PreviousCameraForward", unreal.LinearColor(1.0, 0.0, 0.0, 0.0)),
    ("PreviousCameraRight", unreal.LinearColor(0.0, 1.0, 0.0, 0.0)),
    ("PreviousCameraUp", unreal.LinearColor(0.0, 0.0, 1.0, 0.0)),
)
for index, (name, value) in enumerate(vector_specs):
    if name not in vector_parameters:
        expression = library.create_material_expression(
            material,
            unreal.MaterialExpressionVectorParameter,
            -1650 if index < 4 else -1350,
            -550 + (index % 4) * 140,
        )
        expression.set_editor_property("parameter_name", name)
        expression.set_editor_property("default_value", value)
        vector_parameters[name] = expression

input_names = (
    "CurrentTexture",
    "HistoryTexture",
    "UV",
    "DeltaSeconds",
    "DecayRate",
    "RepresentativeDepth",
    "HistoryValid",
    "ReprojectionEnabled",
    "CameraDataValid",
    "TanHalfHorizontalFOV",
    "ViewAspect",
    "CameraCutDistance",
    "CameraCutCosine",
    "CurrentCameraPosition",
    "CurrentCameraForward",
    "CurrentCameraRight",
    "CurrentCameraUp",
    "PreviousCameraPosition",
    "PreviousCameraForward",
    "PreviousCameraRight",
    "PreviousCameraUp",
)
custom_inputs = []
for input_name in input_names:
    entry = unreal.CustomInput()
    entry.set_editor_property("input_name", input_name)
    custom_inputs.append(entry)
custom.set_editor_property("inputs", custom_inputs)
custom.set_editor_property(
    "description",
    "SSPR temporal explicit-camera reprojection and decay",
)
custom.set_editor_property(
    "code",
    r"""
float currentDensity = Texture2DSampleLevel(
    CurrentTexture, CurrentTextureSampler, UV, 0).r;

float2 currentNDC = float2(
    UV.x * 2.0f - 1.0f,
    1.0f - UV.y * 2.0f);
float tanHalfHorizontal = max(abs(TanHalfHorizontalFOV), 1.0e-3f);
float tanHalfVertical = tanHalfHorizontal / max(abs(ViewAspect), 1.0e-3f);
float representativeDepth = max(RepresentativeDepth, 1.0f);

float3 currentRayAtDepth =
    CurrentCameraForward.rgb +
    currentNDC.x * tanHalfHorizontal * CurrentCameraRight.rgb +
    currentNDC.y * tanHalfVertical * CurrentCameraUp.rgb;
float3 representativeWorldPosition =
    CurrentCameraPosition.rgb +
    representativeDepth * currentRayAtDepth;
float3 previousCameraRelative =
    representativeWorldPosition - PreviousCameraPosition.rgb;
float previousDepth =
    dot(previousCameraRelative, PreviousCameraForward.rgb);
float safePreviousDepth =
    max(abs(previousDepth), 1.0e-4f);
float2 previousNDC = float2(
    dot(previousCameraRelative, PreviousCameraRight.rgb) /
        (safePreviousDepth * tanHalfHorizontal),
    dot(previousCameraRelative, PreviousCameraUp.rgb) /
        (safePreviousDepth * tanHalfVertical));
float2 reprojectedUV = float2(
    previousNDC.x * 0.5f + 0.5f,
    0.5f - previousNDC.y * 0.5f);

float cameraBasisValid =
    dot(CurrentCameraForward.rgb, CurrentCameraForward.rgb) > 0.5f &&
    dot(PreviousCameraForward.rgb, PreviousCameraForward.rgb) > 0.5f &&
    previousDepth > 1.0e-4f;
float3 normalizedCurrentForward = normalize(CurrentCameraForward.rgb);
float3 normalizedPreviousForward = normalize(PreviousCameraForward.rgb);
float cameraTranslation =
    distance(CurrentCameraPosition.rgb, PreviousCameraPosition.rgb);
float cameraRotationCosine =
    dot(normalizedCurrentForward, normalizedPreviousForward);
float cameraContinuity =
    saturate(CameraDataValid) *
    (cameraTranslation <= max(CameraCutDistance, 0.0f) ? 1.0f : 0.0f) *
    (cameraRotationCosine >= CameraCutCosine ? 1.0f : 0.0f);
float useReprojection =
    saturate(ReprojectionEnabled) *
    cameraContinuity *
    (cameraBasisValid ? 1.0f : 0.0f);
float2 historyUV = lerp(UV, reprojectedUV, useReprojection);

bool historyInBounds =
    historyUV.x >= 0.0f && historyUV.x <= 1.0f &&
    historyUV.y >= 0.0f && historyUV.y <= 1.0f;
float historyDensity = historyInBounds
    ? Texture2DSampleLevel(
        HistoryTexture, HistoryTextureSampler, historyUV, 0).r
    : 0.0f;

float decay = exp(
    -max(DecayRate, 0.0f) *
    clamp(DeltaSeconds, 0.0f, 0.25f));
float validHistory =
    historyDensity * decay * saturate(HistoryValid) * cameraContinuity;
float combinedDensity = max(currentDensity, validHistory);
return float3(combinedDensity, 0.0f, 0.0f);
""".strip(),
)

sources = {
    "CurrentTexture": texture_parameters["CurrentTexture"],
    "HistoryTexture": texture_parameters["HistoryTexture"],
    "UV": uv,
    "DeltaSeconds": scalar_parameters["DeltaSeconds"],
    "DecayRate": scalar_parameters["DecayRate"],
    "RepresentativeDepth": scalar_parameters["RepresentativeDepth"],
    "HistoryValid": scalar_parameters["HistoryValid"],
    "ReprojectionEnabled": scalar_parameters["ReprojectionEnabled"],
    "CameraDataValid": scalar_parameters["CameraDataValid"],
    "TanHalfHorizontalFOV": scalar_parameters["TanHalfHorizontalFOV"],
    "ViewAspect": scalar_parameters["ViewAspect"],
    "CameraCutDistance": scalar_parameters["CameraCutDistance"],
    "CameraCutCosine": scalar_parameters["CameraCutCosine"],
}
sources.update(vector_parameters)

connection_results = {}
for input_name in input_names:
    connection_results[input_name] = bool(
        library.connect_material_expressions(
            sources[input_name],
            "",
            custom,
            input_name,
        )
    )
    if not connection_results[input_name]:
        raise RuntimeError("Failed to connect material input " + input_name)

library.layout_material_expressions(material)
library.recompile_material(material)
saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False))
if not saved:
    raise RuntimeError("Failed to save upgraded temporal material")

print(
    "M2A_CAMERA_MATERIAL "
    + json.dumps(
        {
            "material": material.get_path_name(),
            "expressionCount": len(library.get_material_expressions(material)),
            "connections": connection_results,
            "saved": saved,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
