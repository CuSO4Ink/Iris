"""ProgrammaticToolset Probe for MaterialExpressionCustom input-array editing.

Run through ProgrammaticToolset.execute_tool_script, not as standalone Python.
Creates and deletes /Game/MCPTests/M_CustomInputProbe without saving it.
"""

import json


FOLDER = "/Game/MCPTests"
NAME = "M_CustomInputProbe"
PATH = FOLDER + "/" + NAME
MATERIAL = {"refPath": PATH + "." + NAME}


def call(tool, arguments=None):
    return execute_tool(tool, json.dumps(arguments or {}))["returnValue"]


def set_properties(instance, values):
    return call("editor_toolset.toolsets.object.ObjectTools.set_properties", {
        "instance": instance,
        "values": json.dumps(values),
    })


def add(class_path, x, y):
    return call("editor_toolset.toolsets.material.MaterialTools.add_expression", {
        "material_or_function": MATERIAL,
        "expression_class": {"refPath": class_path},
        "x": x,
        "y": y,
    })


def connect(source, target, input_name):
    return call("editor_toolset.toolsets.material.MaterialTools.connect_expressions", {
        "from_expression": source,
        "from_output_name": "",
        "to_expression": target,
        "to_input_name": input_name,
    })


def run():
    asset = "editor_toolset.toolsets.asset.AssetTools."
    material = "editor_toolset.toolsets.material.MaterialTools."
    obj = "editor_toolset.toolsets.object.ObjectTools."
    if call(asset + "exists", {"path": PATH}):
        raise RuntimeError("Probe asset already exists; inspect it instead of deleting unknown work")

    folder_existed = call(asset + "exists", {"path": FOLDER})
    created = False
    result = None
    try:
        call(asset + "create_folder", {"path": FOLDER})
        call(material + "create_material", {"folder_path": FOLDER, "asset_name": NAME})
        created = True
        custom = add("/Script/Engine.MaterialExpressionCustom", 0, 0)

        set_properties(custom, {"inputs": [{"inputName": "A"}]})
        current = json.loads(call(obj + "get_properties", {
            "instance": custom,
            "properties": ["inputs"],
        }))
        inputs = current["inputs"]
        inputs.append({
            "inputName": "B",
            "input": {
                "expression": "None",
                "outputIndex": 0,
                "inputName": "None",
                "mask": 0,
                "maskR": 0,
                "maskG": 0,
                "maskB": 0,
                "maskA": 0,
            },
        })
        set_properties(custom, {"inputs": inputs})
        set_properties(custom, {
            "code": "return A + B;",
            "outputType": "CMOT_Float1",
            "description": "UEAgent MCP Custom input Probe",
        })

        a = add("/Script/Engine.MaterialExpressionConstant", -500, -100)
        b = add("/Script/Engine.MaterialExpressionConstant", -500, 100)
        set_properties(a, {"r": 0.25})
        set_properties(b, {"r": 0.5})
        connect(a, custom, "A")
        connect(b, custom, "B")
        call(material + "connect_to_output", {
            "expression": custom,
            "output_name": "",
            "material_property": "MP_EmissiveColor",
        })
        call(material + "recompile", {"material_or_function": MATERIAL})

        names = call(material + "get_expression_input_names", {"expression": custom})
        wiring = call(material + "get_expression_inputs", {
            "material_or_function": MATERIAL,
            "expression": custom,
        })
        root = call(material + "get_property_input", {
            "material": MATERIAL,
            "material_property": "MP_EmissiveColor",
        })
        if names != ["A", "B"]:
            raise RuntimeError("Unexpected Custom input names: " + repr(names))
        if any(item["expression"] == "None" for item in wiring):
            raise RuntimeError("One or more Custom inputs are not wired")
        if root["expression"]["refPath"] != custom["refPath"]:
            raise RuntimeError("Custom output is not the Emissive root")
        result = {"verified": True, "inputNames": names, "wiring": wiring}
    finally:
        if created and call(asset + "exists", {"path": PATH}):
            call(asset + "delete", {"path": PATH})
        if not folder_existed and call(asset + "exists", {"path": FOLDER}):
            remaining = call(asset + "find_assets", {
                "folder_path": FOLDER,
                "name": "",
                "recursive": True,
            })
            if not remaining:
                call(asset + "delete", {"path": FOLDER})

    if call(asset + "exists", {"path": PATH}):
        raise RuntimeError("Probe cleanup failed: " + PATH)
    return result
