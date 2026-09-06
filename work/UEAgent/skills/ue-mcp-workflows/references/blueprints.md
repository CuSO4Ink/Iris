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

## CDO mutation pitfalls

- Protocol 2.0.1 preserves exact object identity: a missing CDO/subobject stays `exists=false`
  instead of falling back to the main asset. CDO writes with the returned CDO scope plus package
  scope passed mutation, independent property readback, save, and reload on UE 5.8.1.
- A package root is not the CDO. Resolve the actual default object and read back the changed
  property there. Use that typed read as the task's verification before exact-package saving.
  Do not reparent or make unrelated changes to acquire save permission.

The reliable-kernel patch guards the direct `SaveAsset(BlueprintPath, false)` in the VibeUE
Blueprint property path with `ShouldDeferDirectSave()` while a managed mutation is active. The
guard passed a controlled UE 5.8.1 live smoke: the CDO changed while Content bytes stayed equal,
then the verified task saved the Blueprint and refreshed its sidecar. Prefer official typed
operations with explicit lifecycle behavior. Blueprint cache `## Defaults` records editable
inherited CDO overrides against the parent CDO; older sidecars without that section require a
targeted live read for inherited defaults.

Widget, Niagara, and other specialized editor actions may live outside generic
Blueprint/UObject APIs. If the official surface lacks the operation, report the boundary before
proposing a typed plugin operation or a manual editor step.
