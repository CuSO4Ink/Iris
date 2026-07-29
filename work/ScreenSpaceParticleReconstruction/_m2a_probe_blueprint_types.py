import json
import unreal

queries = (
    "Render",
    "Texture",
    "Dynamic",
    "TextureRenderTarget2D",
    "MaterialInterface",
    "MaterialInstanceDynamic",
    "NiagaraComponent",
)
result = {}
for query in queries:
    try:
        values = unreal.BlueprintService.search_variable_types(query)
        result[query] = [str(value) for value in values]
    except Exception as exc:
        result[query] = {"error": str(exc)}
print("M2A_BP_TYPES=" + json.dumps(result, sort_keys=True))
