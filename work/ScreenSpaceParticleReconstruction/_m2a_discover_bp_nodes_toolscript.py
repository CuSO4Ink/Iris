import json

GRAPH = {
    "refPath": (
        "/Game/SSPR_Validation/M2/"
        "BP_SSPR_TemporalOrchestrator."
        "BP_SSPR_TemporalOrchestrator:EventGraph"
    )
}


def find_nodes(term):
    result = execute_tool(
        "editor_toolset.toolsets.blueprint.BlueprintTools.find_node_types",
        json.dumps(
            {
                "graph": GRAPH,
                "type_id_filter": term,
                "context_pins": [],
            }
        ),
    )
    return result["returnValue"]
def run():
    terms = [
        "DynamicMaterial",
        "DrawMaterialToRenderTarget",
        "ClearRenderTarget2D",
        "SetTextureParameterValue",
        "SetScalarParameterValue",
        "SetVariableTextureRenderTarget",
        "TickPrerequisite",
        "Activate",
    ]
    found = {term: find_nodes(term) for term in terms}
    return {"found": found}
