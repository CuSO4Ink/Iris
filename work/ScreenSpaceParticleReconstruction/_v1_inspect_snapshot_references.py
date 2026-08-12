import json
import unreal


ROOTS = {
    "v1": "/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729",
    "v2": "/Game/SSPR_Validation/M2/AnisotropicSplat_V2",
}


def function_references(material):
    result = []
    for expression in unreal.MaterialEditingLibrary.get_material_expressions(material):
        if not isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall):
            continue
        reference = None
        for property_name in ("material_function", "material_function_asset"):
            try:
                reference = expression.get_editor_property(property_name)
                break
            except Exception:
                pass
        result.append(reference.get_path_name() if reference is not None else None)
    return sorted(result, key=lambda value: value or "")


def main():
    result = {
        "functionCallMethods": [
            name
            for name in dir(unreal.MaterialExpressionMaterialFunctionCall)
            if "function" in name.lower()
        ]
    }
    configs = {
        "v1": {
            "material": "M_SSPR_ParticleTrails_FluidV2",
            "instance": "MI_SSPR_ParticleTrails_FluidV2_HQ",
            "system": "NS_SSPR_ParticleTrails_Main",
        },
        "v2": {
            "material": "M_SSPR_AnisotropicSplat_Display",
            "instance": "MI_SSPR_AnisotropicSplat_HQ",
            "system": "NS_SSPR_AnisotropicSplat_Main",
        },
    }
    for key, root in ROOTS.items():
        config = configs[key]
        material = unreal.load_asset(root + "/" + config["material"])
        instance = unreal.load_asset(root + "/" + config["instance"])
        system = unreal.load_asset(root + "/" + config["system"])
        if not isinstance(material, unreal.Material):
            raise RuntimeError(key + " material is missing")
        if not isinstance(instance, unreal.MaterialInstanceConstant):
            raise RuntimeError(key + " instance is missing")
        if not isinstance(system, unreal.NiagaraSystem):
            raise RuntimeError(key + " Niagara system is missing")
        diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
            material.get_path_name()
        )
        result[key] = {
            "root": root,
            "assetCount": len(
                unreal.EditorAssetLibrary.list_assets(
                    root, recursive=True, include_folder=False
                )
            ),
            "material": material.get_path_name(),
            "materialCompiled": bool(diagnostics.is_compiled_ok),
            "materialErrors": [str(value) for value in diagnostics.compile_errors],
            "instance": instance.get_path_name(),
            "instanceParent": instance.get_editor_property("parent").get_path_name(),
            "system": system.get_path_name(),
            "functionReferences": function_references(material),
        }
    print("SSPR_VERSION_REFERENCE_CHECK=" + json.dumps(result, sort_keys=True))


main()
