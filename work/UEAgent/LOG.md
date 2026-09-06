# UEAgent decision log

The current progressive-disclosure implementation and rollback map are maintained in
`PROGRESSIVE-DISCLOSURE.md`; the dated implementation record is
`notes/optimization-20260802-progressive.md`.

The Gateway follow-up also pins UTF-8 BOM compatibility for Windows PowerShell 5.1 and keeps
`DescribeDetail`/`DescribeToolName` plus the active MCP session in the schema-cache key; see the
dated note for the checks.

The current UE MCP tool-search patch contains both compact toolset discovery and the structured
call view. Gateway/daemon discovery defaults to `detail=call`; explicit `detail=full` remains the
exact-schema path. See `patches/ue58-mcp-tool-search.patch` and the dated progressive note.

This file keeps current-stack decisions only. Retired WorkBuddy /
UnrealGenAISupport history remains available in Git history and is not operating guidance.

### 2026-09-02 - User-parameter hierarchy authoring APIs

`NiagaraExternalSystemEditorUtilities` gained the `FNiagaraExt_UserParameterCategory` /
`FNiagaraExt_UserParameterHierarchy` DTOs plus `GetUserParameterHierarchy` (pure read: no `Modify`,
transaction, or package dirtying) and `SetUserParameterCategory` (creates the category when missing,
re-parents existing elements, empty category moves parameters back to the ungrouped root).
`NiagaraToolset_System` exposes both as `AICallable`; `NiagaraToolsets.Build.cs` gained the
`DataHierarchyEditor` dependency that `NiagaraEditor.Build.cs` already carried. There is no
remove-category API, so renaming a category the user created by hand leaves an empty shell in the
Parameters panel - fill the existing category instead of inventing a parallel name.

Back-flow regenerated the two existing engine patches rather than adding a third file. Each patch
keeps its own `index` abbreviation width (toolsets 9 chars, authoring 7), so every file block the
change did not touch stays byte-identical and the reviewable delta is exactly the new work; verify
that way before overwriting a shared patch. Live Coding is not a substitute for the build: it never
runs UHT, so new `UFUNCTION`/`USTRUCT` reflection does not land.

### 2026-09-02 - Read/write classification is two independent layers

The `effect` field from `toolset.describe` is ToolsetRegistry inference and is not the gate. The gate
is the reliable kernel's explicit `ReadOnlyTools` allow-list, whose built-in entries are all
`VibeUE.*`; no `NiagaraToolsets.*` tool is listed, so every call on that toolset - including pure
reads - must go through `ueagent_submit`. The list is extensible from `[UEAgent.Reliable]
ReadOnlyTools` in the project's `Config/DefaultEditor.ini` with no rebuild, but the kernel reads it
once at construction, so it takes an editor restart. A getter reporting `effect: write` is
pre-existing (`GetEmitterTopology` does too), not a regression to chase.

### 2026-09-02 - Patch hashes flow manifest to route, and bootstrap refresh needs the right switches

bootstrap reads patch hashes from `STACK-MANIFEST.json`, writes them into `route.json`, then verifies
route against manifest - so any patch regeneration must be followed by a bootstrap run or the next
run throws "does not match the installed engine". `-CheckOnly` exits before the VibeUE git section,
which makes it a safe full-consistency validator. A dirty VibeUE checkout (Lightning carries 32
modified files) makes plain bootstrap throw; `-PreserveExistingVibeUE` takes the validate-and-warn
branch with no fetch, detach, or merge, and `-SkipBuild` avoids the editor-target build.
`-Endpoint` is equally mandatory for any project whose port differs from the manifest default:
`runtime.endpoint` is 8000, so a bootstrap run without `-Endpoint` silently rewrote Lightning's
`route.json` from 8001 to 8000, after which every Gateway call failed with a connection error while
the editor and its 8001 listener were healthy and responding. `-CheckOnly` does not catch this
because it validates files and hashes, not connectivity. The authoritative port is in the editor log
(`LogModelContextProtocol: Starting MCP server on port N` plus the `LogHttpListener` line), not in
the manifest. bootstrap does not iterate the manifest profile `apply` lists - they are declarative.
Each engine patch is
threaded individually through six sites (path, hash, batch-applied, route verify, apply, route
write), so adding a new patch file costs six bootstrap edits; prefer extending an existing patch.

### 2026-08-31 - AddParticleReadNode flowed into the Niagara authoring composite

The Lightning V5 ECS spike needed a particle-read DI authoring path, so the VibeUE scratchpad
service gained `AddParticleReadNode` (DI-typed input pin on a Custom HLSL node plus a
`UNiagaraNodeInput` carrying a `UNiagaraDataInterfaceParticleRead` bound by `EmitterBinding`,
auto-linked). Flowed into `patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch`;
manifest hash is now `BF3A47D3ACD878576817E2226BCA11598F76430294C28154C2ADACD556D2BCF1` and the
Lightning route hash was synced; the Satris checkout still carries the previous composite
(`E2AE5C63…`) until re-bootstrap. Build constraints hit: NiagaraEditor `MinimalAPI` classes do not
export member functions (worked around with public member writes + UPROPERTY reflection) and
`UNiagaraDataInterface::BuildObjectFlagsForOwner` is private (flag logic inlined).

### 2026-08-12 - Remove secondary compatibility paths

Automatic GPU profiling remains part of the reliable command queue. Reflect Cache now exposes
only `read` and `reconcile`; ordinary text/source-control diff plus the reliable receipt and live
readback replace its unused index/diff/receipt views. Doctor now has one mandatory `RouteFile`
live contract and reports only capabilities proven by the running Editor; offline project, source,
Git, and patch verification belongs to `bootstrap.ps1 -CheckOnly`.
The implementation dropped from 692 to 374 lines. Abyss passed the static check and live Doctor;
one standard probe took 2.63 s and the opt-in Niagara probe took 5.27 s.

The split MCP tool-search patches are squashed into `patches/ue58-mcp-tool-search.patch`, with one
`mcpToolSearchPatchSha256` route field and singular `-ApplyMcpToolSearchPatch` bootstrap switch.
Gateway and daemon accept only `projectionProfile`, `describeDetail`, and `describeToolName`; old
`view`, `intent`, `detail`, and `toolName` request fields fail explicitly. Abyss static/bootstrap,
clean-apply/current-reverse patch checks, Reflect Cache read, and Gateway transport checks passed.

### 2026-08-04 - Make the MCP shutdown guard part of every environment

The VibeUE GameThread shutdown guard is now a required tail patch for both the base and Niagara
authoring profiles. Bootstrap applies it idempotently, records
`vibeUEMcpShutdownGuardPatchSha256` in the route, and `-CheckOnly` rejects a missing, changed, or
unapplied guard. ReflectCache includes that fingerprint in generator identity so a
lifecycle-patched adapter cannot silently share cache provenance with an older environment.
An isolated Niagara-profile bootstrap wrote hash
`8638899C684BFB47AB18F29718099D322FE824484889A13ECED56A0D33758250`; `-CheckOnly` passed and
the static check reported the guard applied and live Doctor returned zero issues. The temporary
fixture was removed.

### 2026-08-03 - Compress the default AI context

The default entry now keeps only navigation, route state, safety boundaries, and the next
required action. `AGENTS.md`, `AI-BRIEF.md`, `HOTPATH.md`, and `SKILL.md` no longer repeat the
full transport/projection/history explanation; `SETUP.md`, `LOG.md`, `BACKLOG.md`, the full
protocol, and pitfall history are on-demand references. The measured entry is about 3.4k
estimated tokens when all four files are needed, while ordinary cache routing reads only
`AGENTS.md` + `HOTPATH.md` (about 1.3k); exact rules and rollback remain in the full contract.

The safety gate is unchanged: cache-first, doctor receipt before live work, one writer,
independent readback, explicit save, and no UI automation. This is a context-loading change,
not a permission change.

### 2026-08-03 - Trace one complete live MCP read

With the Abyss Editor live and the receipt `HEALTHY`, a known Material read was traced without
mutation: `initialize` request 160 chars, `notifications/initialized` 54, internal `tools/list`
request 58 and response 11,207, one-tool `describe_toolset(detail=call)` request 207 and
normalized result 183, then `call_tool` with the exact UObject ref and a server projection.
The projection request was 364 chars. `get_expressions` with `max_items=3` returned 386 raw /
330 normalized chars; the full 171-ref response was 16,757 raw / 16,701 normalized chars.
The raw result contained `structuredContent` only (no duplicate text content), and Gateway's
model-facing output was data-only. A current sidecar would have stopped before all of these live
round trips with `CACHE_READ`.

### 2026-08-02 — Make Gateway the default transport

After the cache/route/doctor gate, UEAgent now routes live reads and authorized mutations through
`mcp_gateway.ps1` by default; `-AutoDaemon` remains the optional warm path for repeated calls.
The generated platform/native MCP client stays available as a transport fallback for a Gateway
startup/pre-operation failure or a client-only feature. Both routes use the same UE endpoint and
must obey the same schema, authority, one-writer, and readback rules. A possible mutation timeout
is still `RESULT_UNKNOWN`, so transport switching cannot be used as an automatic retry.

### 2026-08-02 — Reuse live receipt and discovery evidence

`compact_context.ps1` now returns `NEEDS_DOCTOR` instead of `BLOCKED` for a missing/stale live
receipt; the caller runs doctor once and uses its `allowed`/`blocked` result without a second
compact pass. A healthy receipt remains valid while the stored listener PID, MCP session ID, and
plugin binary fingerprint remain unchanged; TTL is only the identity-unavailable fallback.
Gateway/daemon failures write a project-local invalidation marker, and explicit close/session
replacement forces a new doctor.

Reused-session `tools/list` results now feed `preflight`, `ping`, and `tools.list` directly, and
schema-cache entries are keyed by MCP session ID. Normal successful Gateway replies prefer
`structuredContent` and omit transport/session diagnostics unless requested. Known domain cards
may skip `toolsets.list` in favor of one selected-tool description. A trusted
native MCP host may use direct transport as a performance override; the portable Gateway policy
and all safety/readback rules remain unchanged.

### 2026-07-09 — Use UE 5.8 native MCP

Retired the TCP 9877 stack. The operating endpoint is loopback streamable HTTP on
`http://127.0.0.1:8000/mcp`, with live tool discovery instead of fixed tool counts.

### 2026-07-15 — Keep the workflow Skill inside UEAgent

`skills/ue-mcp-workflows/` is the policy source. Platform/client files are thin adapters, not
independent copies. Experience promotion is evidence → pitfall → isolated Probe → domain SOP.

### 2026-07-22 — Official tools first, VibeUE for gaps

Official typed toolsets own ordinary CRUD. VibeUE supplies confirmed gaps such as domain
services and scoped Python. Every backend follows the same one-writer, readback, cleanup, and
save-boundary rules.

### 2026-07-23 — Make setup path-independent

UEAgent owns bootstrap, endpoint configuration, gateway fallback, and validation. UE/engine
paths are machine inputs. Local engine branches and uncommitted plugin patches are not baseline
dependencies.

### 2026-07-29 — Make Reflect Cache a source sidecar

Saved-state caches live beside `.uasset` as `.uasset.ai.md`. UE is the only writer of truth;
cache is one-way and disposable. Material v2 uses deterministic graph IR instead of semantic
guessing, and external functions remain independent cache units.

### 2026-07-29 — Define Blueprint and Niagara cache boundaries

Blueprint reuses official graph DSL. Niagara stores stack, effective inputs, renderers, and
dependencies; packaged scripts are paths, while system-embedded scripts may inline compact IR
and Custom HLSL. Compile/dirty/runtime state remains live-only.

### 2026-07-29 — Add direct gateway calls

Nested `ProgrammaticToolset` scene creation stalled while the equivalent direct typed call
succeeded. The gateway gained the smallest `direct.call` route; no second protocol layer was
introduced.

### 2026-08-01 — Establish UEAgent as the mandatory project gate

Every target project receives a thin `AGENTS.md` route and machine-local
`Saved/UEAgent/route.json`. `doctor.ps1` checks the route contract, listener, MCP discovery, and
live read health before any UE-dependent work; bootstrap owns offline configuration checks.

### 2026-08-01 — Integrate upstream Niagara evidence conditionally

Imported SSPR K11/K17/K18 with source namespaces to avoid global ID collisions. The
`RequestNewTypedPin` fix is verified only on its patched UE/VibeUE build; nested scratch calls
remain Observed, and `ApplyChanges=false` now requires a `LogTemp` fallback when compile
messages are empty.

### 2026-08-01 — Stream gateway responses by JSON-RPC id

The buffered preflight took 16.3 seconds even after removing full toolset enumeration. Reading
HTTP/SSE only until the matching response id reduced the same top-tools + current-level preflight
to 1.1 seconds; complete doctor time was about 5.0 seconds. Sessions now receive best-effort
`DELETE`, and timeout is reported as `result_unknown`.

### 2026-08-01 — Make local source extensions reproducible

Captured the exact VibeUE and UE 5.8 Niagara Toolsets diffs under `patches/`. Bootstrap applies
the VibeUE extension by default, can preserve only a matching dirty checkout, and treats the
engine extension as explicit and conflict-checked. Abyss static bootstrap, repeated-run hashes,
VibeUE patch identity, MCP discovery, and `/Game/Bifrost/Maps/L_Bifrost` readback all passed; its
doctor state is `HEALTHY` with advanced mutation capabilities still unverified.

The optional deep doctor probe confirmed all six patched Niagara methods in the running editor.
A real read resolved `NS_InfiniteMesh:SingleLoopingParticle.UpdateScript` and returned its native
550-line, 156,356-character graph export without mutating or saving the asset.

### 2026-08-01 — Compress the MCP hot path

Added `HOTPATH.md` plus `compact_context.ps1`: cache-current reads now route to `CACHE_READ`
before MCP, while live work receives one compact route/receipt/asset envelope. The gateway can
optionally TTL-cache only discovery/schema responses; tool calls and mutations are never cached.
The measured material live-read control context fell from about 3.8k to 1.83k estimated tokens;
a current sidecar routes to `CACHE_READ` at about 0.72k control tokens.

### 2026-08-01 — Resolve remote Niagara authoring overlap

The upstream generic Niagara authoring patch overlaps the local VibeUE embedded-script/cache
changes in `UNiagaraScratchPadService`. Kept the small core patch as the default, and generated
one conflict-resolved advanced composite for the pinned `271f487` baseline. It combines System
scratch registration, SimulationStage/Grid2D/RenderTarget2D/RasterizationGrid3D authoring, and
the local embedded-script/cache behavior. The composite is opt-in and requires the matching
engine API-export patch; neither source presence nor patch application proves runtime safety.

### 2026-08-02 鈥?Compress server tool discovery

The UE 5.8 MCP tool-search adapter now returns only one trimmed summary line per toolset from
`list_toolsets`; `describe_toolset` remains the full schema path. The rebuilt Abyss editor returned
5,605 characters instead of 50,951 (about 89% less by the bytes/4 estimate). The exact engine
change is contained in `patches/ue58-mcp-tool-search-v2.patch`; reverse v3 and then v2 using the
manifested order.

### 2026-08-02 鈳?Add opt-in result shaping

`patches/ue58-mcp-tool-search-v2.patch` keeps the catalog reduction and adds summary/single-tool
`describe_toolset`, plus server-side `call_tool.projection` for dotted fields, exclusions, array
caps, and opt-in structured-only MCP results. Defaults remain text-compatible; HLSL strings are not
silently truncated. Final Development link passed after the editor was closed, and live MCP probes
passed: summary/single-tool discovery, default text compatibility, field projection, array cap,
and structured-only output.

### 2026-08-02 鈳?Sync VibeUE 5.8 branch

Fetched VibeUE. `origin/master` stayed at the pinned `271f487`; `origin/5-8` advanced to `6a0617c`
with the Fab engine-version filter only. The checkout was unshallowed, then merged without conflict
as local commit `bf96d6b`; the dirty UEAgent cache/Niagara edits were preserved. Bootstrap pin stays
unchanged for reproducibility.

### 2026-08-02 - Make Gateway fallback session-aware

`mcp_gateway.ps1` now accepts a project-scoped session file, probes reused sessions before an
action, rebuilds stale sessions, and rejects non-loopback endpoints. It also forwards result
projection and targeted toolset-description controls. Live Abyss checks passed: first ping created
and persisted a session, the second reused it, projected Material output stayed structured-only,
and a remote endpoint was rejected before network access. Native MCP remains available as a
fallback; the Gateway path is now independently usable for repeated local calls.

### 2026-08-02 - Add optional warm Gateway daemon

Measured the remaining latency gap and added `scripts/mcp_gateway_daemon.ps1`. It binds only to
127.0.0.1, reuses one MCP session and `HttpClient`, serializes requests, supports the same tool
call/projection envelope, and exits through `shutdown`. Abyss measurements: native MCP 270–333 ms,
one-shot Gateway 1,859–2,002 ms, session-file Gateway 1,334–1,347 ms, warm daemon 149–332 ms.
The daemon is opt-in; the normal one-shot fallback remains unchanged.

`-AutoDaemon` now warms the daemon in the background on the first call and uses the one-shot path
for that call. The cold measured call was 2,338 ms; subsequent gateway-wrapper calls were about
0.9–1.0 s, while direct daemon calls remained 0.15–0.33 s. This keeps startup transparent without
making the first action wait for daemon readiness.

### 2026-08-02 - Add compact token shaping presets

Added Gateway `-ProjectionProfile refs|compact` and `-DataOnly`. Profiles are generic, bounded,
structured projections; explicit projection remains authoritative and logic/HLSL is never guessed
away. Static PowerShell checks passed. Live Abyss verification passed after startup (`doctor=HEALTHY`):
data-only ping returned the two health fields, `compact` returned 64 refs/6,325 characters, and an
explicit three-ref projection returned 330 characters. The refs preset returned all 164 refs because
this source shape was already ref-only. No asset mutation or save was performed.

### 2026-08-02 - Isolate Gateway daemon port

Changed the daemon default from `8765` to `18765` because the former is occupied by an unrelated
local service. AutoDaemon now requires the daemon-specific identity probe before forwarding; a
foreign listener cannot receive gateway actions. Existing direct MCP and one-shot Gateway paths
are unchanged.

### 2026-08-02 - Live long-task benchmark

With AbyssEditor PID 53448 and a stable MCP session, live `doctor -Profile live` took 4.6-4.7 s
after the initial session establishment (the first cold run took 25.6 s). Ten read-only cycles of
`compact_context` plus a warm Gateway daemon `level.current` call took 10.906 s total: compact
was 0.41-0.55 s and Gateway was 0.55-0.78 s per cycle. One-shot `ping` was 0.92-0.96 s; a new
PowerShell process with session reuse was 1.02-1.08 s because it still probes `tools/list`.
The session-bound receipt remained `FRESH` even when its timestamp was artificially aged by two
hours. The running editor rejected `detail=call`, so Gateway correctly fell back to `full`; the
call-view token reduction is therefore not active until the v3 server patch is loaded.

### 2026-08-02 - Reduce model-facing MCP payloads

Non-`preflight` Gateway/daemon actions now default to data-only success responses; `-Envelope`
restores the legacy wrapper and `-Diagnostics` is the only transport/raw-payload path. Default
`ping` and `level.current` responses are now only 41 and 46 characters respectively in the live
check. Gateway-to-daemon requests keep action/tool/arguments/projection/schema-cache fields and
drop local endpoint, session-file, daemon, and timeout plumbing. The daemon now reads/writes the
existing session-scoped schema cache. When the running v2 editor rejects `detail=call`, both
clients fetch `full` once and locally project the compact call view; live Material discovery was
291 bytes in the compact envelope versus 1,261 bytes for selected-tool full (about 77% smaller).
Default tool errors now omit verbose `Available toolsets:` tails and cap residual text at 768
characters; `-Diagnostics` still carries the raw MCP response. The daemon also retains the
session probe's `tools/list` for the lifetime of that session, clearing it on session rebuild or
error instead of issuing the same discovery request for every `ping`/`tools.list` action.

### 2026-08-02 - Final progressive-disclosure regression

After the payload changes, the running Abyss editor (PID 53448) passed the routed compact check
(`LIVE_READ`, receipt `FRESH`) and live doctor (`HEALTHY`, 5.3 s). Direct Gateway checks passed:
default `ping` 41 chars, default `level.current` 46 chars, legacy `-Envelope` and diagnostic
`-Diagnostics` compatibility, and compact invalid-toolset errors (148 chars). The v2 editor's
selected Material call view remained 291 chars versus 1,261 chars for `full`; the call/full/call
sequence returned 291/1,261/290 chars, proving the detail/tool cache key separation. A temporary
AutoDaemon test showed first ping 2.88 s, warm diagnostic ping 1.27 s, raw data-only ping 0.55 s;
the temporary daemon was shut down and its port was closed. A temporary daemon schema test wrote
the existing session-scoped cache (1,489 bytes) and returned the second selected-tool request as
`cached=true` in 402 ms. No UE asset was mutated or saved.

### 2026-08-03 - Load and verify UE v3 call view

After a clean `AbyssEditor` rebuild, the engine's `ModelContextProtocolEditor` DLL loaded with
the v3 call-view implementation. The first live startup was blocked by Unreal's `Restore Packages`
modal; selecting `Skip Restore` allowed the normal editor loop to run. Doctor then returned
`HEALTHY` with official tool search, VibeUE, and Niagara enabled. A raw MCP probe returned
`text/event-stream` containing only `structuredContent` for `detail=call`; no legacy text payload
was present. The selected Material `get_expressions` view was 285 Gateway characters, and the
effect classifier correctly returned `read` after stripping the full toolset prefix. No asset was
mutated or saved.
The HEALTHY receipt was persisted to `Saved/UEAgent/doctor.json`; the routed compact context then
returned `LIVE_READ` with `FRESH` age 0.

### 2026-08-03 - Gateway daemon memory incident

The overnight daemon PID 57704 was reported at roughly 134.5 GiB Private Commit, including about
102.5 GiB LOH, exhausting system commit and cascading into desktop/D3D12 device removal. The PID
was already gone when containment ran; port 18765 was closed. A separate UE-owned
`LiveCodingConsole.exe` (PID 101896, parent AbyssEditor) held about 12.3 GiB and was terminated
explicitly; UE itself was left running.

Code review identifies an unbounded-risk chain rather than a proven single heap root: the daemon
keeps an infinite-timeout shared `HttpClient`, manually waits on `SendAsync`/`ReadAsStringAsync`/
`ReadLineAsync` without cancellation, leaves the per-request `StreamReader` and
`HttpListenerContext` undisposed, and materializes each large MCP result repeatedly (JSON object,
serialized string, UTF-8 byte array, and Gateway parse). Full Material/Blueprint/Niagara/HLSL
responses can therefore create repeated LOH allocations; transport timeouts can leave pending
tasks holding response buffers. The daemon has no request/response byte cap, memory watchdog, or
automatic recycle budget. The 102.5 GiB LOH figure is consistent with this hazard, but needs a
heap dump to attribute exact retained objects. Closing PID 57704 was incident containment, not a
policy decision to abandon the daemon: daemon-first remains the target, with one-shot/native MCP
as failure fallback after the guardrails are added.

### 2026-08-03 - Daemon guardrails implemented and verified

`mcp_gateway_daemon.ps1` now has process-level limits: optional UE `ParentPid` binding, 2 GiB
private-memory budget, 1,000-request budget, 2-hour uptime budget, 15-minute idle budget, 8 MiB
request cap, and 64 MiB response cap. Request bodies are read in bounded chunks and disposed;
the Gateway MCP path cancels timed-out `SendAsync`/stream waits and disposes the request,
response, reader, and cancellation source. A single pending `GetContextAsync` is reused while
polling budgets, avoiding the previous accumulation of unobserved accept tasks.

`-AutoDaemon` discovers the UE listener PID and passes it to the daemon. If UE exits, the daemon
stops; if a budget is reached it finishes the current response and exits without retrying the
operation. The next auto-daemon Gateway call can start a fresh bounded process; explicit
`-DaemonUrl` callers receive the normal unavailable error and may use one-shot/native MCP as the
fallback.

Verification: PowerShell AST and `git diff --check` passed; a `MaxRequests=1` daemon served one
`daemon.ping` and closed its port; an auto-daemon on port 18772 connected to UE PID 49816, showed
all guard arguments including `-ParentPid 49816`, answered ping, and closed via `shutdown`; 32-byte
request and response caps returned HTTP 500 and closed; a 1-second idle budget exited without a
request.
Ports 18772-18775 are closed, no daemon process remains, UE stayed PID 49816, and no UE asset was
mutated or saved. Exact historical LOH retention still requires a dump; these guards limit blast
radius without claiming a single proven retained object.

### 2026-08-03 - Portable stack release and remote reproduction check

The reproducible stack is now described by `STACK-MANIFEST.json`. Bootstrap accepts
`-ApplyMcpToolSearchPatches`, applies the v2 then v3 engine patches, records both fingerprints in
the route, and `-CheckOnly` verifies the same profile. Patch fingerprints normalize line endings,
so Windows CRLF checkouts and Git LF archives resolve to the same SHA-256. The canonical VibeUE
baseline remains public `271f48771d077179fb597dc285ab5b898c5e8038`; the local Abyss checkout's
`bf96d6b` merge of the public `5-8` branch is intentionally treated as a local update, not the
portable baseline.

UEAgent changes were split into four functional commits and pushed to
`origin/codex/ueagent-portable-setup` at `274be1f`. A clean archive of that remote branch was
extracted independently: all seven PowerShell scripts parsed with zero errors, all manifest patch
hashes matched after newline normalization, and the manifest, daemon, ReflectCache protocol, and
patch profiles were present. No unrelated Iris project changes were staged or pushed.

### 2026-08-03 - Promote verified Niagara authoring to bootstrap

The validated UE 5.8 Niagara authoring build is now a first-class bootstrap profile. Pass
`-ApplyNiagaraAuthoringProfile` to apply the revision-adapted engine export patch and the
conflict-resolved VibeUE composite as one unit. The composite replaces the core VibeUE patch; it
is never layered on top of it. Bootstrap records `vibeUEProfile` and
`engineNiagaraAuthoringPatchSha256` in `Saved/UEAgent/route.json`, and `-CheckOnly` validates the
selected VibeUE/engine pair. Doctor's opt-in advanced probe reports only the patched methods
actually exported by the running Editor before the Niagara SOP uses them.

### 2026-08-03 - Add intent projections and cache lifecycle reconciliation

Gateway/daemon `tool.call` now accepts bounded `identity`, `topology`, `logic`, `runtime`, `hlsl`,
and `changed` projection profiles, including `material.*`, `blueprint.*`, and `niagara.*` aliases.
Profiles use server-side dotted field projection and structured-only results; functions and
referenced graphs remain separate assets. Logic excludes layout/properties/HLSL, while HLSL is an
explicit view and is not silently truncated.

`reflect_cache.ps1 -Action reconcile -ProjectRoot <PROJECT> -Repair` now maintains a project-local
`Saved/UEAgent/cache-manifest.json`, rejects unsupported cache formats, rehomes a sidecar only on a
unique source SHA-256 match, and quarantines unresolved orphan sidecars under
`Saved/UEAgent/cache-orphans` instead of deleting them. `compact_context.ps1` exposes `FRESH`,
`STALE`, `ORPHAN`, and `UNSUPPORTED_FORMAT` states and invalidates cache-first routing when the
recorded plugin fingerprint changes. Dirty Editor memory remains a required live check.

Verification: all seven PowerShell scripts parsed with zero errors; profile probes resolved the
Material/Blueprint/Niagara aliases; an isolated fixture passed source-hash rename repair and
orphan quarantine. A read-only Abyss audit reported 27 sidecars (21 fresh, 3 stale, 3 orphaned);
no repair was applied to the user project.

### 2026-08-08 - Bound one-shot Gateway and in-flight daemon requests

Incident review found a Windows PowerShell 5.1 `mcp_gateway.ps1 script.execute` process that
outlived its parent and reached 100.624 GiB working set, while Windows Event 2004 recorded several
other large PowerShell processes. The exact retained allocation from that historical process is
not recoverable, but the one-shot Gateway still parsed SSE one character at a time through the
PowerShell pipeline and had no process-level memory or deadline guard. The daemon's existing
budgets were checked only between requests, so one stuck request could also bypass them.

`mcp_gateway.ps1` now parses SSE with `StreamReader.ReadLineAsync`, retains the 64 MiB network
response cap, and arms an independent process guard with a 2 GiB private-memory ceiling and a hard
deadline of `TimeoutSec + 15 s`. The guard runs on a .NET timer and terminates the process even when
the PowerShell thread is blocked in `Invoke-WebRequest`, stream cleanup, or JSON handling.
`mcp_gateway_daemon.ps1` arms the same guard around every accepted request and disarms it only
after the response context closes. A hard-killed mutation remains `RESULT_UNKNOWN`; callers must
read back before retrying.

Offline loopback fixtures verified an exact 8 MiB single-line SSE round trip in 1.45 s at 396 MiB
peak private memory, normal `tools/call` timeout at 98 MiB, an indefinitely open initialize body
hard-killed at 88 MiB, a forced 64 MiB memory ceiling, and daemon hard timeout. Every run ended
with zero Gateway or daemon PowerShell processes. PowerShell AST, Python AST, UTF-8 BOM, and
`git diff --check` validation passed. Unreal Editor was not running and no UE asset was touched.

### 2026-08-08 - Separate Programmatic scripts from isolated Unreal Python

Follow-up diagnosis established that Gateway `script.execute` routes to
`ProgrammaticToolset.execute_tool_script`, not `execute_python_code`. It now rejects explicit
Unreal-Python imports with `wrong_script_backend` and points callers to the new `python.execute`
action. `python.execute` routes to the top-level Python tool, evaluates the payload in a private
globals dictionary, clears it in `finally`, and runs Python GC before returning.

The isolation is required for PIE lifecycle safety, not only naming clarity. SSPR runtime probes
previously loaded files with plain `exec` in the persistent interpreter namespace. Their global
Niagara render-target wrappers rooted the PIE world; `StopPIE` reached teardown but UE 5.8 then
asserted in `PlayLevel.cpp:553` because `FPyReferenceCollector` prevented the old package from
being collected. Offline fixtures now verify the exact `execute_python_code` route, isolation
bootstrap, explicit wrong-backend rejection before `tools/call`, transport timeouts/memory
ceilings, and zero residual Gateway processes.

After the helper/daemon refactor, the full formal 8 MiB suite was rerun on 2026-08-08. The exact
single-line payload completed in 1.782 s at 397.46 MiB peak private memory; call/initialize hard
timeouts, the forced memory guard, and the daemon hard-timeout case all passed, with zero leftover
Gateway processes.

### 2026-08-12 - Retire alternate execution routes

Removed the experimental project-owned Python/TCP MCP profile and the Gateway script/Python
actions. UEAgent now has one writable architecture: UE 5.8 native MCP, the process-wide
authorization gate, and the Editor-local reliable command queue. Historical incidents remain in
the pitfall ledger, but none of those execution routes are callable.

### 2026-08-12 - Move execution artifacts behind the workspace boundary

Cleared the generated `out/` tree, stale install-smoke/reproduction copies, an obsolete Python
cache, and completed UEAgent test directories under `tmp/`. Future temporary clones, captures,
test output, and reproduction bundles use `tmp/UEAgent/<task>/`; `work/UEAgent/` retains only the
durable routing layer, source, tests, patches, and verified documentation.

### 2026-08-12 - Collapse Gateway to a machine-only call contract

Gateway now binds endpoint/session/schema cache from the target route and infers direct call,
registry call, toolset describe, structured-only transport, and data-only output. A known call
therefore exposes only `tool`, non-empty `arguments`, and optional `toolset`/projection profile;
raw JSON command-line parameters were removed. The shared result codec removes transport/MCP
wrappers, duplicate text, positive success flags, lone `returnValue`, empty/derived reliable
fields, timestamps, fixed-state diagnostics, and nested JSON escaping while preserving every
reliable identity/outcome/hash/save/error field and semantic payload value.

Daemon and one-shot paths now distinguish local validation, pre-operation transport failure,
in-flight unknown result, and post-operation response formatting. A malformed daemon request no
longer clears the MCP session or Doctor receipt, and a normal tool error retains the valid session.
The constant `liveDirtyCheck`, duplicate `inspect` operation, Doctor's task-agnostic `next`, and
compact-view expansion prose were removed.

Verification passed the PowerShell contract suite and full 8 MiB JSON/SSE timeout/memory suite
with no leftover Gateway process. Live Abyss 5.8.1 read-only checks were `HEALTHY`; the minimal
`-Tool ueagent_state` call returned 183 bytes versus 441 bytes before result shaping (58.5% less),
and a live validation error compressed to 216 bytes without changing Editor state.

### 2026-08-13 - Record enabled external plugins at bootstrap

Bootstrap now records each explicitly enabled project-local external plugin's relative descriptor,
version, and normalized descriptor hash in `route.json`; `-CheckOnly` rejects drift. VibeUE remains
covered by its existing Git revision and patch hashes instead of a duplicate inventory entry.

### 2026-08-25 - Generic interface with declarative target overrides

UEAgent is a generic system interface; per-project specialization exists only as declared data.
STACK-MANIFEST gained a top-level `targets` section beside the capability `profiles` (now marked
`kind: capability`). The former `profiles.abyss` became the `targets.Abyss` data instance:
`capabilities`, `extra_patches` (engine/vibeue), `external_plugins`, and sectioned
`project_settings`. Bootstrap replaced `-ApplyAbyssProfile` and every `*-Abyss*` function with
generic `Get-TargetProfile`, `Assert/Set-ProjectSettings`, `Assert/Ensure-ExternalPlugins`, and
`-TargetProfile <name>`; explicit capability switches that a target does not declare are rejected
as drift. Routes now record `targetProfile` plus a `targetPatchSha256` fingerprint table. The old
`environmentProfile: abyss-full` route keeps a one-time compatibility read with a warning until
Abyss reruns bootstrap; the legacy branch is then deleted (BACKLOG P0). Verified pitfall rules
(CDO snapshot gap, native component CDO dirty loop, landscape enumeration timeout, VibeUE animation
GC scope) were promoted into the Blueprint, scene-editing, and new animation domain cards; the
pitfall ledger keeps the full incident records. No patch file changed; all manifest hashes are
unchanged.

### 2026-08-25 - Remove the manual plugin enable / MCP auto-start gap

Two bootstrap gaps forced a manual Plugins-window enable plus editor restart before the MCP port
listened. First, `NiagaraToolsets` was never written into the `.uproject`; bootstrap now enables it
whenever a Niagara capability is selected (apply path uses the capability switches, `-CheckOnly`
uses the routed patch fingerprint or `vibeUEProfile`). Second, `bAutoStartServer=True` was written
only to the Default ini layer while the per-user layer `Saved/Config/WindowsEditor/
EditorPerProjectUserSettings.ini` outranks it and the plugin native default is False, so a stale
serialized False silently disabled auto-start on every launch. Bootstrap now writes the MCP
settings block into both layers via the shared `Set-McpSettingsFile`, and `-CheckOnly` rejects a
user-layer `bAutoStartServer=False` with a repair hint. VibeUE remains a bootstrap-managed
dependency (clone plus pinned `5-8` ref plus patches); target external plugins still come from the
local bundle root.

### 2026-08-25 - Satris bootstrap: hardened the generic path end to end

First full generic-path bootstrap of a new project (F:\Omni\Project\Satris\Satris against the
F:\Omni\Enigine UE 5.8.1 source engine) exposed and fixed five real defects. Machine unblock:
Smart App Control evaluation (WDAC UMCI audit) forced every PowerShell session into
ConstrainedLanguage; the user turned SAC off and bootstrap removed the machine-level
`__PSLockdownPolicy=4` value, restoring FullLanguage. Git hardening: every native git call now
runs through `Invoke-GitQuiet` (child-scope EAP Continue, stderr suppressed, exit-code verdict)
because EAP Stop turns git stderr into terminating errors; `Ensure-GitPatchApplied` and
`Test-GitPatchesApplied` gained a `-C1 --ignore-space-change --ignore-whitespace` fallback tier.
VibeUE baseline: the packaged patches were generated on the local merge of master `271f487` plus
5-8 `6a0617c`, so bootstrap now replays that exact merge from two pinned public SHAs and verifies
the merged TREE `4612cc04` (commit SHAs vary with committer identity; upstream master also moved,
so branch refs were replaced with pinned SHAs in the manifest). Empty-file null bug:
`Get-Content -Raw` on a present-but-empty ini returns `$null` in PS 5.1 and `[string]` casts do
not survive empty pipeline output, so all ini/AGENTS readers coerce with `+ ''`; Satris shipped an
empty `DefaultEditor.ini`, which crashed `Set-UeAgentReliableConfig`. Live results without any
manual plugin step: plugins (including NiagaraToolsets) enabled via `.uproject`, dual-layer MCP
inis written, editor built in 123 s, port 8000 auto-listening, doctor `HEALTHY` receipt persisted,
compact router returned `LIVE_READ`, and a Gateway `ueagent_state` live read returned protocol
2.0.0 with the matching editor epoch and zero dirty packages.

### 2026-08-25 - Lightning onboarded as the second generic-path project

G:\Work\Project\Lightning was a content-only project (no Source, hence no .sln could exist and
VibeUE source plugin could never load), so a minimal Runtime module was scaffolded first
(Lightning.Target.cs, LightningEditor.Target.cs, Lightning.Build.cs, empty module pair, plus the
Modules entry in the .uproject). Two build fixes surfaced: UE 5.8.1 requires
`BuildSettingsVersion.V7` targets because LightningEditor shares the UnrealEditor build
environment (V5 defaults were rejected), and the MCP endpoint had to move to port 8001 because
the Satris editor already owns 8000 (`-Endpoint http://127.0.0.1:8001/mcp`; both inis, .mcp.json,
and the route record 8001). The rerun reused the patched VibeUE checkout via
`-PreserveExistingVibeUE` (merged-baseline tree plus profile markers accepted), skipped the
already-applied engine patches, built LightningEditor, and launched. Results: port 8001
auto-listening within 30 s, doctor `HEALTHY` (PID 36412), `ueagent_state` live read protocol 2.0.0
with matching epoch, and `GenerateProjectFiles.bat` produced Lightning.sln.
### 2026-08-26 - Abyss route reactivated after F:\Omni migration

The Abyss project and the 5.8.1 source engine moved from D:\Work to F:\Omni (project `F:\Omni\Project\Abyss`, engine root `F:\Omni\Enigine`). The copied `Plugins/VibeUE` had lost `.git` in transit, so bootstrap re-cloned the pinned merge and re-applied the packaged patches (verified merged tree `4612cc04`); the old copy is parked under Iris `tmp/abyss-restore-20260825/`. The route was regenerated in `targetProfile` format via `bootstrap -TargetProfile Abyss -SkipBuild`, and a full `AbyssEditor Win64 Development` rebuild succeeded (4198 actions, ~2.7 h). After cold start, doctor reports HEALTHY (PID 14912, epoch A4F54B9C-4657-0C57-E467-7DA76CB652F8, fingerprint 18422b7b) and `-ProbeAdvancedCapabilities` returns `niagaraToolsetsExtension: true`, satisfying the Abyss smoke gate on port 8000 while the Lightning editor stays on 8001.

### 2026-08-27 - Delete the legacy environmentProfile compatibility branch

With the Abyss route regenerated in `targetProfile` format (2026-08-25) and smoke-verified (2026-08-26), the one-time legacy read in `bootstrap.ps1` was removed: the `environmentProfile: abyss-full` elseif in route parsing and the `$routedLegacyTarget`/`$legacyRouteShaFieldByPatch` verification branch. Only `targetProfile` routes with the `targetPatchSha256` fingerprint table are accepted now. PowerShell AST, `test_reliable_profile.ps1`, and a live Abyss `-CheckOnly` (targetProfile path with two target extra patches) all passed.

### 2026-08-27 - Satris write path verified end to end

Closed the portable-baseline mutation gap on the Satris route. Route repair first: port 8000 was owned by the Abyss editor, so Satris was re-bootstrapped onto `http://127.0.0.1:8002/mcp` (both ini layers, `.mcp.json`, route record). Two build blocks surfaced: UBT's Live Coding guard keys on a per-running-process named mutex (`Global\\LiveCoding_<exe-path>` held by the editor process itself, not by LiveCodingConsole — consoles were terminated with user consent but the guard persists while an editor runs), bypassed for this build with `-NoHotReloadFromIDE` (engine binaries were already current; only project modules compiled); and an `UnrealEditor-NetCore.dll` relink locked by the running Abyss/Lightning editors, unblocked by renaming the in-use DLL (running editors keep their mapped copy; leftover `UnrealEditor-NetCore.dll.locked-20260827` deletes after those editors restart). The verified chain on a disposable material: OCC `exists=false` snapshot -> `ueagent_submit` `MaterialTools.create_material` -> terminal receipt (succeeded/changed/verified/dirty_not_saved) -> independent `ueagent_snapshot` (exists, `/Script/Engine.Material`, dirty) -> save capability -> immutable save receipt -> `.uasset` plus ReflectCache sidecar on disk (packaged save hook fired) -> referencer-free `AssetTools.delete` -> `exists=false`, file gone. Receipts persist under Satris `Saved/UEAgent/Operations` (`1bd5432a` create, `373e7423`/`a4ef0c70` property flips, the latter with the save receipt, `74eea195` delete). One incident became new evidence: the editor Autosave fired ~82 s after the create receipt, latching OUT_OF_BAND_SAVE and killing the 5-minute token; recovery required a fresh mutation with explicit `allow_preexisting_dirty_save=true` (same-task-owned dirty state) followed by an immediate `ueagent_save`. Recorded as `CORE-20260827-AUTOSAVE-SAVE-TOKEN-RACE`.

### 2026-08-27 - Hidden-save audit closes P0; K02 fix flowed into the composite patch

Exhaustive save-site audit across the reachable surface: all 16 VibeUE service saves — including the two P0-named paths, `UNiagaraScratchPadService::ApplyChanges` and `UBlueprintService::SetProperty` — are guarded by `FUEAgentReliableKernel::ShouldDeferDirectSave()` inside the packaged `vibeue-reliable-kernel.patch`; the engine NiagaraToolsets/MCP plugins contain zero save calls; official EditorToolset exposes only explicit `Save*` tools, which the kernel rejects by name (`SAVE_REQUIRES_TOKEN`); the only unguarded site is the `execute_python_code` pre-save, unreachable on this stack (no registered toolset, no Gateway action, gate blocks direct calls). Live behavior matched the audit: official `create_material`/`set_properties` on Satris ended `persistence=dirty_not_saved`. The one real baseline gap found by the audit — LIGHTNING-K02's ApplyChanges validator fix (skip `Input`+`None`+`bNotConnectable` shadow pins) living only in Lightning's project copy — was flowed back: the composite was regenerated from a pristine pinned-merge replay (`git diff --output` to avoid PowerShell codepage mojibake in patch context), applied-tree A/B against the old composite differs only in the 5-line skip, and the packaged `vibeue-ueagent-authoring.patch` is now sha256 `E2AE5C6353CE4850A9E0ADC73A25629D020A603820871BF0912BCDDE9C3EA17F` (manifest updated; `test_reliable_profile.ps1` passed). Satris adopted it (route rewritten, VibeUE recompiled — the fix compiles — doctor HEALTHY, `-CheckOnly` passed). Abyss and Lightning routes still record the previous composite hash and will fail `-CheckOnly` until re-bootstrap; their running editors are unaffected since the false positive only triggers on `ApplyChanges` with a Map Get carrying two or more typed reads.

### 2026-09-05 - Niagara authoring composite rebuilt; CRLF patches were the silent-misapply mechanism

The 2026-08-27 entry above records the authoring composite as sha256 `E2AE5C63...` carrying the
LIGHTNING-K02 shadow-pin skip. That state never reached any committed artifact: no revision of
`vibeue-ueagent-authoring.patch` in Iris history contains `bNotConnectable`, and neither did the
working-tree version found at the start of this session. K02 survived only in the
`G:/Work/Project/Lightning/Plugins/VibeUE` working copy, which is the fullest state on the box
(DI ops + the four new ops + `RefreshModuleCallNodes`/`RemoveScratchPin` + K02, all uncommitted).

The working-tree authoring patch was a **chained regeneration**: it had been diffed against a tree
that already carried the four DI ops *and* `vibeue-reliable-kernel.patch`, so those ops degraded
from carried content into baseline, the `Public/Module.h` and `VibeUE.Build.cs` blocks vanished
(6 file blocks -> 4), and its declared baselines (`NSP.cpp 2b6a57d`, `NSP.h 6208f8e`) exist nowhere
in the pinned stack. `NSP.h 6208f8e` is the *result* blob of the previous good patch, which is the
fingerprint of chaining. It could not apply to `merged_tree 4612cc0` even under bootstrap's full
`-C1 --ignore-space-change --ignore-whitespace` tolerance, so `-ApplyNiagaraAuthoringProfile` was
hard-broken. STACK-MANIFEST's sha had been re-pinned to match it (`C8318013...`), so
`test_reliable_profile.ps1` passed throughout.

Root cause of the whole class: `.gitattributes` held `*.patch -whitespace` with no `eol=lf`, and the
repo runs `core.autocrlf=true`, so all 23 tracked patch files were `i/lf w/crlf`. A CRLF patch
against an LF source tree fails strict `git apply --check`, so `Invoke-GitPatch` took its relaxed
branch on *every* patch, every time - context reduced to one line, hunks free to land in the wrong
place. `bootstrap.ps1:584` already claimed "Packaged patches are LF"; the attribute gap made that
false. Now `*.patch text eol=lf -whitespace`.

Rebuilt by union rather than by choosing a lineage: pristine `4612cc0` -> previous good authoring
content (DI ops, `Module.h`, `Build.cs`) -> the four new ops from the broken patch's `NSP` blocks
-> K02 from the Lightning copy -> `RefreshModuleCallNodes`/`RemoveScratchPin`. Two mechanical
context repairs were needed, both because the new content was authored against a later chain
position: the broken patch's first hunk carried `#include "Core/UEAgentReliableKernel.h"` as
context (reliable-kernel is applied *after* authoring), and its new
`#include "AssetRegistry/AssetRegistryModule.h"` landed between `EditorAssetLibrary.h` and
`EdGraph/EdGraph.h`, which is exactly reliable-kernel's own include-hunk context - so it moved below
`Misc/Guid.h`. All six VibeUE patches now **strict**-apply in manifest order from `4612cc0`, and the
terminal tree carries all ten ops plus K02. Authoring is `DCAA0754...`, refresh `3DA0BDF9...`.

Consequence to clear: Abyss's `route.json` is stale four ways and `-CheckOnly` now fails on the
first of them - `engineNiagaraPatchSha256` (`C3EB3E4F...` routed vs `7870BC1A...` pinned) and
`engineNiagaraAuthoringPatchSha256` (`E568B91D...` vs `67D5F951...`) were already drifted by other
sessions' uncommitted patch edits before this one; `vibeUEPatchSha256` moved with this rebuild; and
`vibeUERefreshModuleCallNodesPatchSha256` is new because refresh is now actually applied. Its VibeUE
checkout is 32 files dirty, so a re-bootstrap needs `-PreserveExistingVibeUE` and an explicit
`-Endpoint`.

### 2026-09-05 - STACK-MANIFEST apply lists became the authority bootstrap consumes

`profiles.*.apply` had zero consumers in `scripts/`: eleven positions in `bootstrap.ps1` hardcoded
patch paths, sha lookups, CheckOnly assertions, apply order and route fields, and the switch
`if ($ApplyNiagaraAuthoringProfile)` chose the composite. `apply` was read only by four test
membership assertions. The concrete cost was that
`patches/niagara-mcp-authoring/vibeue/vibeue-refresh-module-call-nodes.patch` sat in the
niagara-authoring apply list while bootstrap never applied it at all - adding an entry to `apply`
did nothing, and the manifest looked authoritative while the script was.

Chosen fix (over deleting the list or over a route-schema break): the manifest now carries the axes
bootstrap needs. `patches.<path>` is a record of `sha256`, `repo` (`engine`/`vibeue`) and
`route_field`; profiles carry `kind` (`core` for the mutually exclusive `base`/`niagara-authoring`
pair, `capability` for additive ones), an explicit `capability` name, optional `requires` and
optional `required_plugins`. `ueagent_common.ps1` gained `Get-UeAgentPatchPlan` and friends;
bootstrap resolves one plan and iterates it for resolution, application, CheckOnly and route
emission. The capability-to-switch table and `Get-TargetExtraPatches` are gone, and bootstrap
contains zero patch-path literals. Route field *names* are unchanged, so `reflect_cache.ps1` and
existing routes keep their schema - deliberately, since the alternative invalidates live targets.

Two behaviours changed on purpose. `-ApplyEngineNiagaraPatch` alone now throws, because
`niagara-toolsets` declares `requires: ["niagara-authoring"]`; the profile's warning string about
not compiling alone had no consumer and was fail-open. And the old single-patch guard ("the engine
has the Niagara authoring patch") generalised to: the engine must carry no pinned engine patch
outside the selected plan.

Defence added so a re-pinned hash cannot again hide semantic loss: the test asserts the authoring
patch's carried ops (all eight plus `bNotConnectable`) and its `Module.h`/`Build.cs` file blocks,
asserts each plan resolves, applies no patch twice and overwrites no route field, pins the verified
niagara-authoring VibeUE order, and - given `-VibeUEPath` - asserts every declared `index` baseline
blob equals that path's blob in `merged_tree 4612cc0`. That last one is the direct detector: it
reports 2 mismatches and 4 file blocks on the broken patch, 0 and 6 on the rebuild. CheckOnly also
compares fingerprints before touching the working tree, so a stale checkout no longer masks which
patch actually drifted.

### 2026-09-05 - Two fail-open corners closed: profile requirements and project_settings section names

`niagara-toolsets` carried a manifest `warning` explaining it does not compile alone, and nothing in
`scripts/` or `tests/` read it - a comment, not a gate. Taken the second of the two backlog options:
the profile now declares `requires: ["niagara-authoring"]` and `Assert-UeAgentProfileRequirements`
refuses it otherwise, so `-ApplyEngineNiagaraPatch` alone throws. What is left is narrower and stays
in the backlog: the profile is now a no-op alias whose one patch already ships in niagara-authoring's
apply list, so it could be deleted together with the switch and the only consumer of `requires`.

`project_settings` was the one place the design did not fail closed. `Set-IniSectionSettings`
appends a section that does not exist rather than erroring, and `Assert-ProjectSettings` read the
same manifest-supplied name back, so a misspelled section passed `-CheckOnly` while the setting never
reached the engine - consistently wrong on both sides of the same source. The fix is to consult an
authority that is neither the manifest nor bootstrap's own write: `Get-EngineIniSectionNames` reads
every `Engine/Config/**.ini` section header, and both the write and the read-back path refuse a
declared section the hierarchy does not define. Against UE 5.8.1 that yields 1044 known sections;
`SystemSettings` and `/Script/Engine.RendererSettings` are recognised, `SystemSettingz` and
`System_Settings` are not, so class-config sections are covered without a hardcoded allowlist.

### 2026-09-05 — Local sync keeps engine installation separate from project routing

The imported installer/profile/hash-routing entries above describe the source machine. This
workspace retains engine-scoped VibeUE and route-only Bootstrap; the new Niagara packages,
source revisions, diagnostics and package tests are merged into that path without restoring
the retired project installer. `SETUP.md` and the manifest describe the current installation.

### 2026-09-06 — Daemon binding, engine installer and incident dispositions aligned

A two-endpoint mock reproduced daemon misrouting: requesting B reached A because forwarding
removed endpoint identity. Gateway and daemon now enforce endpoint/project-session binding;
explicit mismatch rejects before dispatch and AutoDaemon keeps the requested one-shot target.
The transport suite passes all 14 cases, including both binding boundaries and no stray calls.

`install_engine.ps1` owns manifest-ordered engine/VibeUE installation, scoped defaults and build
invocation; Bootstrap retains project routing. Shared validation stays in `ueagent_common.ps1`.
Ten isolated install checks cover dependency order, conflict preservation, repeat/additive
installation, build dispatch, consumer bootstrap, and unchanged user indexes/dirty work. The base
and Niagara authoring VibeUE packages strictly apply to separate public-source checkouts (5 and
6 patches respectively). No production engine was rebuilt or live-verified in this session.

The redundant standalone Niagara Toolsets profile was removed; its wrappers and required exports
remain in the complete authoring profile. Sixteen pitfalls now state historical/current
applicability and preserve actual receipt semantics. Current SOPs no longer recommend unrelated
writes or reparenting to manufacture save tokens, or hiding out-of-scope dirty effects. CDO scope
coverage and asynchronous Niagara/save lifecycle failures remain explicit target probes.

### 2026-09-06 — real-engine reliability and save verification

The selected engine installation at `E:/work/engine_work/Enigne/UE` was upgraded without resetting
its pre-existing dirty source or Git index, then rebuilt and cold-started against UEAgentProbe.
The public-source base and authoring composites were regenerated and strictly replayed.

Protocol 2.0.1 fixes exact-object fallback. Scratch operations enforce same-package private
ownership; apply invalidates the script source before compiling. Niagara data-processing views
no longer compile on initialization, and SetStackInputData completes compilation before receipt
snapshots. Eight specifically reviewed Python/Niagara readers now avoid the mutation queue.
Gateway preserves empty/singleton arrays and null, and Doctor separately reports reflected
scratch authoring and parameter-hierarchy capability. Blueprint sidecars include inherited CDO
overrides. These replace the older operational claims about all getters requiring submission.

Five cache types, CDO mutation/reload, shared-package isolation, four added authoring operations,
refresh/pin removal, compile completion, exact save and save replay/rejection were exercised.
The detailed result and limitations are in `notes/runtime-verification-20260906.md`.

Abyss's project-local VibeUE descriptor was moved to `Saved/UEAgent/RetiredVibeUE` with its bytes
preserved; project source remains in place, and bootstrap checks the engine installation route.
VRM4U is its sole missing enabled plugin, so Abyss-specific activation still requires that dependency.
No commits were made and unrelated dirty work was retained.

### 2026-09-06 — user-approved five-boundary simplification

Implemented K1–K5 and R01–R25 as protocol 3.0. Generic snapshots/OCC, hashes, signed save tokens,
per-transition journals, the read whitelist/engine authorization delegate, profiling freeze,
session/schema TTL and per-call daemon probes were removed or replaced on one current path.
Gateway now handles local waiting, one typed readback and optional task-owned saving. Acceptance
and evidence write failures are checked. Exact values, including false/null/arrays and Niagara
instanced cache inputs, are preserved. Mandatory navigation was reduced to one short card plus
its pointer. Existing domain crash fixes and ordinary implementation bounds remain.

Actual build, native/transport/installer tests, cold Blueprint/Niagara reload, replay, readback
failure, exact save scope and acceptance-write failure were verified. No dirty test packages
remained. See `notes/minimal-execution-20260906.md` for measured scope and accepted limitations.
