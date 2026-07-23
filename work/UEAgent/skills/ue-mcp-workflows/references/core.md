# Core MCP SOP

## Authority and connection

Read the UEAgent project-root `SETUP.md` when installation or transport details matter. Use the project-root `scripts/mcp_gateway.ps1` for hosts without native MCP support.

Prefer native MCP when the host exposes `list_toolsets`, `describe_toolset`, and `call_tool`. Otherwise use the canonical gateway. For nested arguments, use `-ArgumentsFile`; do not fight PowerShell escaping.

## Identify objects precisely

Keep these path forms distinct:

```text
Asset path:     /Game/Folder/Asset
Object refPath: /Game/Folder/Asset.Asset
Subobject:      /Game/Folder/Asset.Asset:MaterialExpressionCustom_0
Level object:   /Game/Maps/L_Map.L_Map:PersistentLevel.Actor.Component
```

Use full `refPath` values returned by tools. Do not reconstruct short actor or component names.

## Discover before mutation

1. Use `describe_toolset` for unfamiliar tools.
2. Use `list_properties` before setting an unfamiliar UObject property.
3. Use material input/output-name queries before connecting pins.
4. Read existing array/struct values before modifying them.
5. Record a cheap precondition such as asset existence, class, node count, parent, or current level.

## Modify arrays and structs safely

`ObjectTools.set_properties` performs a structural diff. Changing existing elements while changing array size can fail with:

```text
ArrayAdd: elements changed alongside the size change; insertion points are ambiguous
```

Use full read-modify-write:

1. Change existing elements without changing array length.
2. Read the property back in its complete serialized form.
3. Preserve every existing nested field exactly.
4. Append or remove elements in a separate call.
5. Read back and verify order, names, and nested values.

Do not assume a schema showing only one required field means omitted nested fields are irrelevant to the diff engine.

## Batch without assuming transactions

- Call `ProgrammaticToolset.get_execution_environment` before unfamiliar batch scripts.
- Define `run()` and return a dictionary.
- Call registered tools through `execute_tool`; do not `import unreal`.
- Treat `_StrictDict` as direct-index only. Avoid `.get(key, default)`.
- Assume an exception may leave partial mutations. Re-read state before retrying.
- Keep one writer per UE object. Do not parallelize mutations against the same asset, actor, or component.
- Add exact preconditions and postconditions to every nontrivial mutation script.

## Verify independently

Do not accept `true`, `success`, or a clean tool response as proof. Verify with a different signal:

- asset mutation -> `exists`, class, parent, property readback, dependency, or node count
- material mutation -> input wiring, output root, compile/log result
- Blueprint mutation -> compile plus node/pin/connection readback
- actor mutation -> transform, tags, folder, components, or bounds readback
- batch generation -> batch tag and folder query
- cleanup -> `exists=false` or zero actors in the scoped tag/folder

Use floating-point tolerances for readback; do not compare serialized UE floats for exact equality.

## Control lifecycle and risk

- Treat delete, move, save, merge, and level commit as high-risk.
- Reassign dependents before deleting a parent asset.
- Check referencers and exact scope before destructive changes.
- Distinguish in-memory Dirty state, `Saved/Autosaves`, and formal `Content` assets.
- Do not call an Autosave a completed deliverable.
- Never save the current level merely because asset validation succeeded.

## Handle long results

- Prefer `-OutFile` for large JSON and images when using the gateway.
- A missing gateway output file does not prove UE did nothing; query editor state.
- Large base64 payloads may be truncated by the host. Follow UEAgent's screenshot-consent rule and prefer direct viewport review.
- Run gateway calls as separate shell invocations; do not assume commands after a gateway process will execute in the same shell.

## Improve the workflow after real use

Run a short postflight only when the task exposed material friction:

- the same low-level call or code pattern was repeated three or more times
- a guessed schema, property, pin, or return shape caused a retry
- an exception required manual state recovery
- latency, escaping, or payload size dominated the work
- a capability was unavailable through the registered tools

Use the first improvement that holds:

1. Reuse an existing tool or recipe.
2. Batch deterministic repetition with `ProgrammaticToolset`.
3. Add or tighten one project-local Probe/script when the logic is fragile or repeatedly rewritten.
4. Propose an MCP, gateway, or plugin extension only when registered tools cannot express the operation.

Record observed friction in `notes/mcp-pitfalls.md` with the date, evidence, workaround, and count. Promote it into the relevant Skill reference only after an isolated Probe verifies the behavior. Promote a batch into `scripts/` only after real repetition; do not scaffold speculative tools.

You may update this project-local Skill, its probes/scripts, gateway, and pitfalls ledger without another prompt when the change stays inside the current task, is reversible, and receives one representative check. Report the change to the user.

Ask before changing UE/VibeUE plugins, platform-installed Skill copies, production assets, or save/delete behavior. Preserve evidence and propose the smallest patch instead of silently expanding authority.
