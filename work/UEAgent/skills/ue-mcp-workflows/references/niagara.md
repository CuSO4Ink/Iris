# Niagara SOP

## Read saved structure from the sidecar

Try `<PackageFile>.uasset.ai.md` first. A current
`vibeue-niagara-system-cache-v1` may answer user variables, emitter/simulation type, stage and
module order, effective inputs, renderer configuration, dependencies, and embedded logic.

- Packaged module/function scripts point to their own future sidecars; never inline them.
- A script object owned by the Niagara System package has no independent source file, so its
  compact nodes/links and full Custom HLSL may be inlined.
- Stack topology decides active semantics; editable scratch inventory does not.
- Compile, dirty, component override, and runtime state are always live.
- Avoid `GetScriptGraphText` as a normal cache body; it is large and has produced invalid JSON
  around escaped HLSL comments.

Use targeted live reads when the cache is stale, manual-pilot, missing a field, or the package or
component is live-dirty.

If the route includes `engineNiagaraPatchSha256`, run doctor with
`-ProbeAdvancedCapabilities` before using the extension. A successful probe verifies live
`GetScriptGraphText`, `GetScriptCustomHlsl`, `GetScriptRapidIterationParameters`,
`GetScriptObject`, `SetScriptCustomHlsl`, and `GetRuntimeState`. The first four are read paths;
the setter remains task-gated. `GetScriptGraphText` is an exact, high-volume fallback rather than
a replacement for the compact sidecar.

## Discover before editing

1. Describe `NiagaraToolsets.NiagaraToolset_System` and any VibeUE scratch surface in the
   current session.
2. Read system summary, emitter/stage/module topology, effective inputs, renderers, dependencies,
   and compile state.
3. Record the exact system, embedded-script, module, node, and pin identities.
4. Keep packaged scripts outside the system mutation scope.

## Gate scratch pin authoring

Do not assume `AddPin` / `ConnectPins` is safe. In the SSPR incident, VibeUE used bare
`CreatePin` plus a manual signature rebuild; pin indices diverged from
`Signature.Inputs/Outputs` and Niagara asserted during compile/UI traversal.

The former crash sequence passed only after a UE 5.8 build exported the required Niagara editor
APIs and VibeUE used `RequestNewTypedPin`. The verified UEAgent route is the
`vibeUEProfile=niagara-authoring` bootstrap profile: it applies the revision-adapted engine patch
and the conflict-resolved VibeUE composite as one unit. Require that profile and a healthy doctor
receipt before dynamic pin mutation; otherwise allow scratch inspection but block mutation or
isolate it in a disposable system.

Do not call `NiagaraScratchPadService` from inside `ProgrammaticToolset`: two real runs timed
out with no mutation. Prefer its discovered top-level route. If only Python exposes the needed
operation, use one scoped top-level `execute_python_code -> unreal.NiagaraScratchPadService`
call, then independently read back the graph.

## Apply, diagnose, and save

1. Make one logical scratch/stack change.
2. Call `ApplyChanges` once.
3. If it returns false, query compile messages.
4. If messages are empty, inspect `LogsToolset` or the editor log for
   `LogTemp: Error: ApplyChanges`; stale scratch copies and duplicate anonymous MapGet pins have
   been reported only there.
5. On timeout, treat the outcome as unknown and read back before retrying.
6. Compile and verify exact stack/input/renderer/graph state.

Some VibeUE builds save during `ApplyChanges`. Until the active implementation proves
mutation/compile/save are separate, treat the call itself as an authorised save boundary.

## Validate runtime across requests

For GPU Niagara, do not mutate, compile, reinitialize, and make a final RT/output judgment in one
MCP request. Long Game Thread calls can prevent new render frames and return stale or empty data.

Use:

1. request A: mutation/apply/compile/authorised save;
2. request B: bind or reinitialize the exact component;
3. allow real editor/render frames;
4. request C: read current component identity and runtime output;
5. user viewport: aesthetic approval.

`UpToDate` and a successful duplicated Niagara System do not prove embedded Simulation Stages
run. When runtime behavior matters, validate a clean component and the actual current DI/output.

For screen-space systems, set and record a deterministic test camera, then prove sampled
ScreenUV values are finite/on-screen and depth is positive before interpreting an empty RT.
Absolute markers and numerical statistics must use non-normalized raw readback; record that mode
with the evidence.

PIE Niagara DI identities can change after `reinitialize_system()`, especially with World
Partition. Re-read the component's current User Variable DI refPaths after every reinitialize and
verify the dimensions of the actual render targets owned by the PIE World. Do not infer identity
from `_0`, `_1`, or another numeric UObject suffix, and do not retain a prior-generation wrapper.
