# Core MCP SOP

## Start from the receipt

Run the UEAgent doctor before live work. Port listening alone is insufficient: the gate also
checks MCP discovery and a cheap Game Thread read.

- `HEALTHY` proves the base live route, not every domain capability and not write authority.
- `DEGRADED` is read-only.
- `OFFLINE` forbids live-state claims and UE mutation.
- Timeout after a possible mutation means `RESULT_UNKNOWN`; independently read state before
  any retry.

If the server requires a console action, stop and ask the user to perform the exact step. Do not
drive Unreal UI with Computer Use.

## Choose the narrowest backend

1. Current cache for saved-state reads.
2. Gateway as the default client route to an official typed tool confirmed by live schema.
3. Platform/native MCP as a transport fallback when Gateway cannot start or complete a
   pre-operation request while the receipt is still healthy; an unhealthy endpoint stays offline.
4. VibeUE service for a confirmed official gap.
5. Scoped `execute_python_code` fallback with exact pre/postconditions.

Use `ProgrammaticToolset` only for deterministic repetition after the nested calls are known to
work. Its sandbox cannot `import unreal`. Do not assume a tool that works directly is safe when
nested; Scene creation and Niagara scratch calls have stalled in that shape.

Gateway backend names are intentional: `script.execute` calls `ProgrammaticToolset`, while
`python.execute` calls top-level `execute_python_code` and evaluates the payload in an isolated
dictionary. Never send `import unreal` code through `script.execute`, and never use a plain
`exec(payload)` in the persistent `execute_python_code` namespace. A PIE probe must not leave
UObject wrappers in interpreter globals: execute it in a private scope, clear that scope in
`finally`, and run Python garbage collection before stopping PIE.

## Identify objects precisely

```text
Asset path:     /Game/Folder/Asset
Object refPath: /Game/Folder/Asset.Asset
Subobject:      /Game/Folder/Asset.Asset:MaterialExpressionCustom_0
Level object:   /Game/Maps/L_Map.L_Map:PersistentLevel.Actor.Component
```

Use returned full `refPath` values. Do not reconstruct short actor/component names.

Before mutation:

1. describe unfamiliar tools;
2. list unfamiliar UObject properties;
3. query material/graph pin names;
4. read existing arrays/structs;
5. record a cheap precondition such as class, parent, current level, node count, or existence.

## Modify arrays and structs safely

`ObjectTools.set_properties` may reject simultaneous element changes and array resizing as an
ambiguous structural diff. Use staged full read-modify-write:

1. change existing elements without changing length;
2. read the complete serialized value;
3. preserve every nested field;
4. append/remove in a separate call;
5. read back order, names, and nested values.

## Mutate once and verify independently

- Keep one writer per UE object; never parallelize mutations against the same asset or level.
- Assume an exception may leave a partial mutation.
- Do not accept `true`, `success`, compile green, or a clean RPC response as proof.
- Use a different signal:
  - asset → existence, class, parent, dependency, property, or node count;
  - material → wiring/output roots plus compile/log result;
  - Blueprint → compile plus node/pin/connection or runtime readback;
  - actor → transform/tags/folder/components/bounds;
  - cleanup → `exists=false` or zero objects in the exact tag/folder scope.
- Compare UE floats with tolerance.

For GPU/runtime work, end the mutation request and allow real frames before the validation
request. A fast empty dispatch or stale runtime object is not success.

Read back the changed region, not the entire graph/system, unless the invariant crosses the whole
asset. Include changed nodes/pins/properties and compile/dirty state.

## Keep save and destruction separate

- Save, delete, move, merge, Undo/Redo, transaction reset, and level commit are high-risk.
- Some VibeUE Niagara/Blueprint calls have hidden save behavior; the domain SOP must treat those
  calls as save boundaries until the implementation is decoupled.
- Reassign dependents before deleting a parent.
- Query referencers and exact scope before deletion; zero registry referencers is not sole proof.
- Distinguish Dirty memory, Autosave, and formal Content saves.
- Never save the current level merely because an asset passed validation.
- Top-level `execute_python_code` may save dirty content/world packages before user code runs.
  After a call dirties a World Partition external Actor, do not issue another Python request to
  inspect or clean it: that request can persist the package first. Use a verified typed route or,
  after confirming there are no unrelated dirty packages, exit UE and restore the exact external
  Actor file. A byte-identical `.umap` is not sufficient; check `Content/__ExternalActors__` too.

## Control payload and lifecycle

- Prefer filtered results and gateway `-OutFile` for large text.
- Do not carry image/base64 payloads through MCP when the user can inspect the viewport.
- A missing output file or client timeout does not prove UE did nothing.
- Keep one gateway request in flight; wait for it instead of launching a duplicate.
- Gateway is the default client route, not a second source of tool semantics; platform/native MCP
  is the transport fallback. A possible mutation timeout requires independent readback first.

## Postflight only when useful

Record a pitfall when a task caused a schema retry, partial recovery, material latency/payload
cost, or a real capability gap. Use this order:

1. reuse an existing tool/rule;
2. tighten one domain rule;
3. add one isolated Probe for fragile behavior;
4. add a script only after repetition;
5. propose plugin/engine work only when registered tools cannot express the operation.

Use namespaced IDs and evidence states from `../../../notes/mcp-pitfalls.md`. Ask before
changing UE/VibeUE code, production assets, or save/delete behavior.
