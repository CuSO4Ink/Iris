import json
import unreal


SOURCE_ROOT = "/Game/SSPR_Validation/M2/ParticleTrails"
VERSION_ROOTS = {
    "v1": "/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729",
    "v2": "/Game/SSPR_Validation/M2/AnisotropicSplat_V2",
}
RENAMED_PACKAGES = {
    "v2": {
        "M_SSPR_ParticleTrails_FluidV2": "M_SSPR_AnisotropicSplat_Display",
        "MI_SSPR_ParticleTrails_FluidV2_HQ": "MI_SSPR_AnisotropicSplat_HQ",
        "NS_SSPR_ParticleTrails_Main": "NS_SSPR_AnisotropicSplat_Main",
        "L_SSPR_ParticleTrails_Validation": "L_SSPR_AnisotropicSplat_Validation",
    }
}


def package_path(obj):
    return obj.get_path_name().split(".", 1)[0]


def remap_source_path(source_path, version_key, version_root):
    if not source_path.startswith(SOURCE_ROOT + "/"):
        return None
    relative = source_path[len(SOURCE_ROOT) + 1 :]
    directory, slash, name = relative.rpartition("/")
    mapped_name = RENAMED_PACKAGES.get(version_key, {}).get(name, name)
    relative_mapped = directory + slash + mapped_name if slash else mapped_name
    return version_root + "/" + relative_mapped


def main():
    result = {}
    for version_key, version_root in VERSION_ROOTS.items():
        assets = [
            unreal.load_asset(path)
            for path in unreal.EditorAssetLibrary.list_assets(
                version_root, recursive=True, include_folder=False
            )
        ]
        materials = [value for value in assets if isinstance(value, unreal.Material)]
        instances = [
            value
            for value in assets
            if isinstance(value, unreal.MaterialInstanceConstant)
        ]
        function_remaps = []
        parent_remaps = []

        for material in materials:
            changed = False
            for expression in unreal.MaterialEditingLibrary.get_material_expressions(
                material
            ):
                if not isinstance(
                    expression, unreal.MaterialExpressionMaterialFunctionCall
                ):
                    continue
                function = expression.get_editor_property("material_function")
                if function is None:
                    continue
                old_path = package_path(function)
                new_path = remap_source_path(
                    old_path, version_key, version_root
                )
                if new_path is None:
                    continue
                local_function = unreal.load_asset(new_path)
                if not isinstance(local_function, unreal.MaterialFunction):
                    raise RuntimeError(
                        "Missing local material function: " + new_path
                    )
                expression.set_material_function(local_function)
                changed = True
                function_remaps.append(
                    {
                        "material": material.get_path_name(),
                        "from": old_path,
                        "to": package_path(local_function),
                    }
                )
            if changed:
                unreal.MaterialEditingLibrary.recompile_material(material)
                if not unreal.EditorAssetLibrary.save_asset(
                    package_path(material), False
                ):
                    raise RuntimeError(
                        "Failed to save remapped material: "
                        + material.get_path_name()
                    )

        for instance in instances:
            parent = instance.get_editor_property("parent")
            if parent is None:
                continue
            old_path = package_path(parent)
            new_path = remap_source_path(old_path, version_key, version_root)
            if new_path is None:
                continue
            local_parent = unreal.load_asset(new_path)
            if not isinstance(local_parent, unreal.MaterialInterface):
                raise RuntimeError("Missing local material parent: " + new_path)
            instance.set_editor_property("parent", local_parent)
            if not unreal.EditorAssetLibrary.save_asset(
                package_path(instance), False
            ):
                raise RuntimeError(
                    "Failed to save remapped instance: "
                    + instance.get_path_name()
                )
            parent_remaps.append(
                {
                    "instance": instance.get_path_name(),
                    "from": old_path,
                    "to": package_path(local_parent),
                }
            )

        current_material_name = (
            "M_SSPR_AnisotropicSplat_Display"
            if version_key == "v2"
            else "M_SSPR_ParticleTrails_FluidV2"
        )
        current_material_path = version_root + "/" + current_material_name
        diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
            current_material_path
        )
        result[version_key] = {
            "root": version_root,
            "functionRemaps": function_remaps,
            "parentRemaps": parent_remaps,
            "currentMaterial": current_material_path,
            "compiled": bool(diagnostics.is_compiled_ok),
            "compileErrors": [str(value) for value in diagnostics.compile_errors],
        }
        if not diagnostics.is_compiled_ok or diagnostics.compile_errors:
            raise RuntimeError(
                version_key + " current material failed after reference remap"
            )

    print("SSPR_VERSION_SELF_CONTAINED=" + json.dumps(result, sort_keys=True))


main()
