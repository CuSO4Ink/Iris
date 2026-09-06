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

- A CDO write can show the new value in an independent object snapshot while the package-scope
  before/after snapshot stays equal and the job ends `VERIFY_EXPECTED_CHANGE`. Treat that mismatch
  as `RESULT_UNKNOWN`; independently read the exact object and package dirty state before retry or
  save (BLUEPRINT-20260814-CDO-PACKAGE-SNAPSHOT-GAP).
- Direct writes to a generated CDO's native inherited component (for example
  `SkeletalMeshComponent`) can persist yet leave generated/transient component state dirty,
  producing a compile/save loop. Restore the source component defaults, express the runtime
  override in an authoritative Blueprint graph, save once, then fully reload the Editor/package
  before trusting any state cache (BLUEPRINT-20260814-NATIVE-COMPONENT-CDO-DIRTY-LOOP).

Some VibeUE Blueprint property operations have saved implicitly. Until the active implementation
proves otherwise, treat those calls as save operations and do not use them outside an authorised
save boundary. Prefer official typed operations with explicit lifecycle behavior.

Widget, Niagara, and other specialized editor actions may live outside generic
Blueprint/UObject APIs. If the official surface lacks the operation, report the boundary before
proposing a typed plugin operation or a manual editor step.
