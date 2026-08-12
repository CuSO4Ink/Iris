# Blueprint SOP

## Read the sidecar before MCP

Try `<PackageFile>.uasset.ai.md` first. A current `vibeue-blueprint-cache-v1` may answer saved
parent, variables/CDO defaults, component decisions, dependencies, and graph topology. Graph
sections are the official `BlueprintTools.read_graph_dsl` representation; do not invent a
second IR.

`generator: manual-pilot` means there is no save hook. Use targeted live reads when the source
is newer, the package is dirty, placed-instance state matters, or the requested field is absent.

## Keep targets distinct

Blueprint asset defaults, Class Default Object, component template, placed instance, and runtime
instance are different targets. Construction Script may overwrite placed-instance state.

Describe the live `BlueprintTools` schema before authoring. Do not reuse instructions from the
retired TCP 9877 stack.

## Inspect user-exported selections

When the user copies Blueprint nodes as text:

```powershell
python .\bp_clipboard_to_ai.py blueprint_clipboard.txt --json-out simplified.json --summary-out summary.txt
```

The parser preserves node semantics, pin types/defaults, and links while dropping editor
serialization noise. It proves only the copied selection, not the full asset.

## Modify cautiously

1. Record path, class, parent, graph, component tree, and compile/dirty state.
2. Use only schema-confirmed operations.
3. Probe uncertain node/pin creation in a disposable Blueprint.
4. Apply one node chain or component change.
5. Compile.
6. Read back nodes, pins, connections, defaults, variables, or components.
7. Verify an instance/PIE result when behavior matters.
8. Save only after compile and behavioral checks.

Compile success is not proof of intended wiring or runtime behavior.

Some VibeUE Blueprint property operations have saved implicitly. Until the active implementation
proves otherwise, treat those calls as save operations and do not use them outside an authorised
save boundary. Prefer official typed operations with explicit lifecycle behavior.

Widget, Niagara, and other specialized editor actions may live outside generic
Blueprint/UObject APIs. If the official surface lacks the operation, report the boundary before
proposing VibeUE Python, plugin C++, or a manual editor step.
