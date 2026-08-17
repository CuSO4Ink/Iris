# Core MCP SOP

## Start from the receipt

Run the UEAgent doctor before live work. Port listening alone is insufficient: the gate also
checks all nine reliable control tools and reads `ueagent_state`. The returned editor epoch is the
live identity; a listener or old `state.json` alone is not proof.

- `HEALTHY` proves the base live route, not every domain capability and not write authority.
- `DEGRADED` is read-only.
- `OFFLINE` forbids live-state claims and UE mutation.
- Timeout after acceptance means poll the same command job/receipt. If a previous editor epoch left
  only a journal, run `ueagent_recover`, accept `RESULT_UNKNOWN`, and independently read state
  before any retry.

If the server requires a console action, stop and ask the user to perform the exact step. Do not
drive Unreal UI with Computer Use.

## Choose the narrowest backend

1. Current Reflect Cache for saved-state reads.
2. `ueagent_snapshot` or `ueagent_batch_read` for authoritative bounded Editor state.
3. An explicitly reviewed read-only typed tool through Gateway.
4. `ueagent_submit` targeting a typed ToolsetRegistry or VibeUE operation.
5. An exact manual UE step when no registered typed operation exists.

The Gateway exposes no script or Python execution action, and the server authorization gate
rejects every unreviewed direct mutation, including nested `call_tool` dispatch. Add the missing
typed operation or stop.

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
5. capture canonical scope hashes with `ueagent_snapshot`; put them in `expected_snapshots`.

Submit a canonical hyphenated UUID as `command_id`, declare every package/object/editor scope, and
choose `changed_or_noop`, `changed`, `unchanged`, or `success`. Reusing that UUID with the same
canonical digest is an idempotent replay; another digest is rejected. Arguments at or above 64 KiB
must include `payload_sha256`; attachments must be UTF-8 files under `Saved/UEAgent/Inbox` with an
exact SHA-256.

## Modify arrays and structs safely

`ObjectTools.set_properties` may reject simultaneous element changes and array resizing as an
ambiguous structural diff. Use staged full read-modify-write:

1. change existing elements without changing length;
2. read the complete serialized value;
3. preserve every nested field;
4. append/remove in a separate call;
5. read back order, names, and nested values.

## Mutate once and verify independently

- The kernel keeps one global logical writer. Mutations may queue, but never bypass that queue.
- Assume an exception may leave a partial mutation.
- Poll `ueagent_get_job`, then require the immutable terminal receipt. Do not accept `true`,
  compile green, or a clean RPC response as proof.
- Use a different signal:
  - asset → existence, class, parent, dependency, property, or node count;
  - material → wiring/output roots plus compile/log result;
  - Blueprint → compile plus node/pin/connection or runtime readback;
  - actor → transform/tags/folder/components/bounds;
  - cleanup → `exists=false` or zero objects in the exact tag/folder scope.
- Compare UE floats with tolerance.

For GPU/runtime work, end the mutation request and allow real frames before the validation
request. A fast empty dispatch or stale runtime object is not success.

Read back the changed region with a new authoritative snapshot, not the entire graph/system, unless
the invariant crosses the whole asset. Include changed nodes/pins/properties and compile/dirty
state. The receipt reports outcome, effect, verification, and persistence separately.

## Keep save and destruction separate

- Delete, move, merge, Undo/Redo, transaction reset, and level commit remain high-risk mutations.
- Managed VibeUE service saves are deferred. A verified changed receipt may issue a short-lived,
  one-use save capability for exactly the dirty declared packages; no token means no save.
- Pre-existing dirty target packages do not enter a token unless
  `allow_preexisting_dirty_save=true` was explicit in the submitted command.
- Reassign dependents before deleting a parent.
- Query referencers and exact scope before deletion; zero registry referencers is not sole proof.
- Distinguish Dirty memory, Autosave, and formal Content saves.
- `ueagent_save` rechecks package generations/snapshots and saves only the token's exact set. A
  retry of a consumed token returns the same immutable save receipt; it never saves twice.
- Never save the current level merely because an asset passed validation. A byte-identical `.umap`
  is not sufficient for World Partition; include exact external Actor packages in scopes/readback.

## Control payload and lifecycle

- Prefer filtered results and gateway `-OutFile` for large text.
- Do not carry image/base64 payloads through MCP when the user can inspect the viewport.
- A missing output file or client timeout does not prove UE did nothing. Command identity and the
  Editor journal outlive the transport request.
- Keep one submit request per command identity; poll instead of launching a new mutation.
- Gateway is the only AI-facing client route, not a second source of tool semantics; native MCP is
  its server. A missing Gateway capability blocks the task until the typed surface is extended.

## Postflight only when useful

Record a pitfall when a task caused a schema retry, partial recovery, material latency/payload
cost, or a real capability gap. Use this order:

1. reuse an existing tool/rule;
2. tighten one domain rule;
3. add one isolated typed-tool probe for fragile behavior;
4. propose plugin/engine work only when registered tools cannot express the operation.

Use namespaced IDs and evidence states from `../../../notes/mcp-pitfalls.md`. Ask before
changing UE/VibeUE code, production assets, or save/delete behavior.
