import json
import unreal


registry = unreal.AssetRegistryHelpers.get_asset_registry()
rows = []
for root in ("/NiagaraFluids", "/Niagara", "/Engine"):
    for asset_data in registry.get_assets_by_path(unreal.Name(root), recursive=True):
        asset_name = str(asset_data.asset_name)
        asset_path = str(asset_data.package_name)
        class_path = str(asset_data.asset_class_path)
        searchable = (asset_name + " " + asset_path).lower()
        if "niagaraemitter" not in class_path.lower():
            continue
        if not any(token in searchable for token in ("grid2d", "grid_2d", "simulationstage", "simulation_stage")):
            continue
        rows.append(
            {
                "name": asset_name,
                "package": asset_path,
                "class": class_path,
            }
        )

print("GRID_EMITTER_TEMPLATES=" + json.dumps(rows, sort_keys=True))
