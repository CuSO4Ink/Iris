# Blueprint SOP

## Evidence boundary

The current official MCP stack exposes `editor_toolset.toolsets.blueprint.BlueprintTools`, but UEAgent has not yet verified every general graph-authoring operation. Describe the live toolset before use and label newly observed behavior accurately.

Do not reuse operational instructions from the retired UnrealGenAISupport/TCP 9877 stack. Keep those entries in `LOG.md` as history only.

## Inspect user-exported graphs

Use the project-root tool when the user copies Blueprint nodes as text:

```powershell
From the UEAgent project root:

```bash
python ./bp_clipboard_to_ai.py blueprint_clipboard.txt --json-out simplified.json --summary-out summary.txt
```
```

The parser intentionally preserves node semantics, pin types/defaults, and link relationships while dropping editor serialization noise. Treat its output as a compact representation of the exported selection, not proof of the entire Blueprint asset.

## Modify a Blueprint cautiously

1. Record Blueprint path, class, parent, graph name, component tree, and compile state.
2. Describe `BlueprintTools` and use only schema-confirmed operations.
3. Isolate uncertain node or pin creation in a disposable Blueprint.
4. Create one node chain or component change at a time.
5. Compile the Blueprint.
6. Read back nodes, pins, connections, defaults, variables, or components.
7. Verify an instance or PIE behavior when the user requested functional behavior.
8. Save only after compile and behavior checks pass.

Do not treat `compile succeeded` as sufficient proof of logic. Verify the intended pin connections and runtime effect independently.

## Keep editor layers distinct

- Blueprint asset defaults, the Class Default Object, placed instances, and runtime instances are different mutation targets.
- Construction Script changes may overwrite placed-instance state.
- Widget, Niagara, and other specialized editor actions may live outside generic UObject/Blueprint APIs.
- If the official toolset cannot expose a required operation, report the boundary before proposing plugin C++, Editor Utility, or manual work.

Add a recipe here only after an isolated official-stack Probe passes and cleans up.
