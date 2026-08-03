# UEAgent decision log

The current progressive-disclosure implementation and rollback map are maintained in
`PROGRESSIVE-DISCLOSURE.md`; the dated implementation record is
`notes/optimization-20260802-progressive.md`.

The Gateway follow-up also pins UTF-8 BOM compatibility for Windows PowerShell 5.1 and keeps
`DescribeDetail`/`DescribeToolName` plus the active MCP session in the schema-cache key; see the
dated note for the checks.

The current follow-up adds the optional UE v3 call view: Gateway/daemon discovery defaults to
structured-only `detail=call`; explicit `detail=full` is still the exact-schema path. See
`patches/ue58-mcp-tool-search-v3-call-view.patch` and the dated progressive note.

This file keeps current-stack decisions only. Retired WorkBuddy /
UnrealGenAISupport history remains available in Git history and is not operating guidance.

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
may skip `intent.list` and `toolsets.list` in favor of one selected-tool description. A trusted
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
`Saved/UEAgent/route.json`. `doctor.ps1` separates configuration, listener, MCP discovery,
and live read health before any UE-dependent work.

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
change is reversible through `patches/ue58-mcp-tool-search.patch`; the broader Iris hot-path edits
still need a clean checkpoint before they can have a safe one-command rollback bundle.

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
