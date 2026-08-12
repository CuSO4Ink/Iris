import json
import unreal


SOURCE_ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
V3_ROOT = "/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730"

SOURCE_TO_V3 = {
    SOURCE_ROOT + "/L_SSPR_AnisotropicSplat_Validation": (
        V3_ROOT + "/L_SSPR_AnisotropicSplat_V3_Validation"
    ),
    SOURCE_ROOT + "/NS_SSPR_AnisotropicSplat_Main": (
        V3_ROOT + "/NS_SSPR_AnisotropicSplat_V3"
    ),
    SOURCE_ROOT + "/M_SSPR_AnisotropicSplat_G5_V2": (
        V3_ROOT + "/M_SSPR_AnisotropicSplat_V3"
    ),
    SOURCE_ROOT + "/MI_SSPR_AnisotropicSplat_G5_V2_HQ": (
        V3_ROOT + "/MI_SSPR_AnisotropicSplat_V3_HQ"
    ),
    (
        SOURCE_ROOT
        + "/Functions/AnisotropicSplat/MF_SSPR_RawAnisotropicDensity"
    ): (
        V3_ROOT
        + "/Functions/RasterInput/MF_SSPR_V3_RawAnisotropicDensity"
    ),
    (
        SOURCE_ROOT
        + "/Functions/G5/MF_SSPR_G5_StreamlineDensityV2"
    ): (
        V3_ROOT
        + "/Functions/Reconstruction/MF_SSPR_V3_StreamlineDensity"
    ),
    (
        SOURCE_ROOT
        + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity"
    ): (
        V3_ROOT
        + "/Functions/Reconstruction/MF_SSPR_V3_MipPyramidDensity"
    ),
    (
        SOURCE_ROOT
        + "/Functions/M3_HQBaseline/MF_SSPR_DensityShape"
    ): (
        V3_ROOT
        + "/Functions/Reconstruction/MF_SSPR_V3_DensityShape"
    ),
    (
        SOURCE_ROOT
        + "/Functions/G5/MF_SSPR_G5_DepthLightingV2"
    ): (
        V3_ROOT
        + "/Functions/Shading/MF_SSPR_V3_DepthLighting"
    ),
    (
        SOURCE_ROOT
        + "/Functions/M3_HQBaseline/MF_SSPR_SmokeResolve"
    ): (
        V3_ROOT
        + "/Functions/Shading/MF_SSPR_V3_SmokeResolve"
    ),
    (
        SOURCE_ROOT
        + "/Functions/M3_HQFluidV2/MF_SSPR_ScreenEdgeMask"
    ): (
        V3_ROOT
        + "/Functions/Utility/MF_SSPR_V3_ScreenEdgeMask"
    ),
}


def package_path(value):
    return value.get_path_name().split(".", 1)[0]


if unreal.EditorAssetLibrary.does_directory_exist(V3_ROOT):
    existing = unreal.EditorAssetLibrary.list_assets(
        V3_ROOT, recursive=True, include_folder=False
    )
    if existing:
        raise RuntimeError(
            "Refusing to overwrite existing V3 snapshot: " + repr(existing)
        )

for directory in (
    V3_ROOT,
    V3_ROOT + "/Functions/RasterInput",
    V3_ROOT + "/Functions/Reconstruction",
    V3_ROOT + "/Functions/Shading",
    V3_ROOT + "/Functions/Utility",
):
    unreal.EditorAssetLibrary.make_directory(directory)

duplicate_order = [
    source
    for source in SOURCE_TO_V3
    if "/Functions/" in source
]
duplicate_order.extend(
    source
    for source in SOURCE_TO_V3
    if "/Functions/" not in source
)

duplicated = []
for source in duplicate_order:
    destination = SOURCE_TO_V3[source]
    if not unreal.EditorAssetLibrary.does_asset_exist(source):
        raise RuntimeError("Missing V3 source asset: " + source)
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        raise RuntimeError("V3 destination already exists: " + destination)
    result = unreal.EditorAssetLibrary.duplicate_asset(
        source, destination
    )
    if result is None:
        raise RuntimeError(
            "Failed to duplicate {} -> {}".format(source, destination)
        )
    duplicated.append(
        {
            "source": source,
            "destination": destination,
            "class": result.get_class().get_name(),
        }
    )

v3_material_path = SOURCE_TO_V3[
    SOURCE_ROOT + "/M_SSPR_AnisotropicSplat_G5_V2"
]
v3_instance_path = SOURCE_TO_V3[
    SOURCE_ROOT + "/MI_SSPR_AnisotropicSplat_G5_V2_HQ"
]
v3_material = unreal.load_asset(v3_material_path)
v3_instance = unreal.load_asset(v3_instance_path)
if not isinstance(v3_material, unreal.Material):
    raise RuntimeError("Duplicated V3 material is invalid")
if not isinstance(v3_instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Duplicated V3 material instance is invalid")

function_remaps = []
for expression in unreal.MaterialEditingLibrary.get_material_expressions(
    v3_material
):
    if not isinstance(
        expression, unreal.MaterialExpressionMaterialFunctionCall
    ):
        continue
    old_function = expression.get_editor_property("material_function")
    if not isinstance(old_function, unreal.MaterialFunction):
        continue
    old_path = package_path(old_function)
    if old_path not in SOURCE_TO_V3:
        raise RuntimeError(
            "V3 material contains an unplanned function dependency: "
            + old_path
        )
    new_path = SOURCE_TO_V3[old_path]
    new_function = unreal.load_asset(new_path)
    if not isinstance(new_function, unreal.MaterialFunction):
        raise RuntimeError("Missing duplicated V3 function: " + new_path)
    expression.set_material_function(new_function)
    function_remaps.append(
        {
            "expression": expression.get_name(),
            "from": old_path,
            "to": new_path,
        }
    )

if len(function_remaps) != 7:
    raise RuntimeError(
        "Expected seven V3 material function remaps, got "
        + str(len(function_remaps))
    )
unreal.MaterialEditingLibrary.recompile_material(v3_material)
if not unreal.EditorAssetLibrary.save_asset(v3_material_path, False):
    raise RuntimeError("Failed to save remapped V3 material")

old_parent = v3_instance.get_editor_property("parent")
v3_instance.set_editor_property("parent", v3_material)
if not unreal.EditorAssetLibrary.save_asset(v3_instance_path, False):
    raise RuntimeError("Failed to save remapped V3 material instance")

saved_assets = []
for destination in SOURCE_TO_V3.values():
    if not unreal.EditorAssetLibrary.save_asset(destination, False):
        raise RuntimeError("Failed to save V3 asset: " + destination)
    saved_assets.append(destination)

diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    v3_material_path
)
result = {
    "root": V3_ROOT,
    "assetCount": len(saved_assets),
    "assets": sorted(saved_assets),
    "duplicates": duplicated,
    "functionRemaps": function_remaps,
    "instanceParentBefore": (
        package_path(old_parent) if old_parent is not None else None
    ),
    "instanceParentAfter": package_path(
        v3_instance.get_editor_property("parent")
    ),
    "materialCompiled": bool(diagnostics.is_compiled_ok),
    "materialErrors": [
        str(value) for value in diagnostics.compile_errors
    ],
}
print("V3_SNAPSHOT_CREATED=" + json.dumps(result, sort_keys=True))
if (
    result["assetCount"] != 11
    or result["instanceParentAfter"] != v3_material_path
    or not result["materialCompiled"]
    or result["materialErrors"]
):
    raise RuntimeError("V3 snapshot creation gate failed: " + repr(result))
