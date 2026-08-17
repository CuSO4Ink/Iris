# UEAgent setup

The bootstrap installs the full verified adapter baseline and writes a thin route into the target
UE project. Machine paths live under `Saved/UEAgent`; committed project instructions remain
portable.

Ordinary reads use the short [HOTPATH](skills/ue-mcp-workflows/HOTPATH.md). The complete
compact-to-full contract, measurements, and rollback map is
[PROGRESSIVE-DISCLOSURE.md](PROGRESSIVE-DISCLOSURE.md).
The machine-independent stack contract and patch hashes are in
[STACK-MANIFEST.json](STACK-MANIFEST.json); use it as the release checklist when reproducing
UEAgent on another checkout.

## Stable baseline

| Dependency | Requirement |
|---|---|
| Unreal Engine | UE 5.8 (verified on 5.8.1) with native `ModelContextProtocol` and `EditorToolset` plugins |
| VibeUE | public `5-8` commit `6a0617cfb05aaced82d6613e88b1572fe7452eaa` |
| UEAgent VibeUE extension | selected profile + performance + shutdown guard + reliable kernel |
| UE native MCP extension | process-wide `tools/call` authorization gate |
| Default engine profile | current MCP tool-search + call-view patch |
| Abyss full profile | Niagara authoring + Niagara Toolsets + engine extensions + pinned project plugins |
| Windows | Git and Windows PowerShell |

This baseline supports official typed tools plus the portable ReflectCache implementation. The
`-ApplyAbyssProfile` switch applies the complete current Abyss stack, including script
graph/HLSL/rapid-iteration and live component-state calls.

The verified advanced Niagara authoring profile covers dynamic `RequestNewTypedPin`, Simulation
Stage, Grid2D, RenderTarget2D, RasterizationGrid3D, and Custom HLSL authoring. Bootstrap applies
the revision-adapted engine patch and the conflict-resolved
`patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch` together.
The verified authoring profile is applied automatically with `-ApplyNiagaraAuthoringProfile`.
It applies the matching engine export patch, selects the composite VibeUE patch instead of the
core patch, and records `vibeUEProfile` plus `engineNiagaraAuthoringPatchSha256` in the route.
Every VibeUE profile then applies the shared performance monitor, shutdown guard, and
`patches/vibeue-reliable-kernel.patch`; every writable profile also applies
`patches/ue58-mcp-authorization-gate.patch` to the source engine. Bootstrap writes
`[UEAgent.Reliable]`, and the route records protocol `2.0.0` plus both fingerprints. `-CheckOnly`
rejects a missing, changed, disabled, or unapplied component; Doctor verifies the loaded runtime.
See
[RELIABLE-EXECUTION.md](RELIABLE-EXECUTION.md) for the command/receipt/save contract.

## Configure a target project

From the UEAgent root:

### Native MCP and VibeUE profile

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -UProject "X:\Projects\MyGame\MyGame.uproject" -EngineRoot "X:\UnrealEngine" -Launch
```

When a built project editor target exists, `-Launch` uses it before falling back to the generic
engine editor binary. This keeps the executable and freshly rebuilt project/plugin DLLs aligned.

If the target already contains verified local VibeUE patches on the pinned baseline, preserve
them explicitly instead of letting bootstrap replace the checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -UProject "X:\Projects\MyGame\MyGame.uproject" -EngineRoot "X:\UnrealEngine" -PreserveExistingVibeUE -SkipBuild
```

The switch still rejects a dirty checkout whose `HEAD` differs from the pinned baseline or does
not contain the selected UEAgent VibeUE profile patch.

For a UE source checkout, `-ApplyNiagaraAuthoringProfile` includes the Niagara Toolsets
extension. Bootstrap first checks whether the exact patch is already present and refuses
conflicts; it never resets engine changes.

For the verified advanced Niagara authoring profile, pass `-ApplyNiagaraAuthoringProfile`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -ApplyNiagaraAuthoringProfile -ApplyMcpToolSearchPatch -Launch
```

For the exact current Abyss environment, use the canonical full profile. The source root must
contain `Plugins\<PluginName>` for the seven pinned project plugins; bootstrap copies only missing
plugin directories and refuses to merge or overwrite an existing mismatched directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\Abyss\Abyss.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -ApplyAbyssProfile `
  -ExternalPluginSourceRoot "X:\Bundles\Abyss" `
  -SkipBuild
```

The full profile requires UE 5.8.1 compatible changelist `55116800`, applies the current engine
and VibeUE patches (including the read-only material diagnostics and UE 5.8 Niagara compatibility
fixes), writes the volumetric-cloud setting, and pins the seven enabled external plugin
descriptors. It fails closed when the external plugin bundle is absent or differs; it does not
guess public/private plugin origins or silently substitute another version.

Every writable profile requires the pinned VibeUE baseline and a source-engine Git checkout.
`-CheckOnly`
reads the route profile and validates the selected composite and engine patch automatically; the
profile switch is only needed when bootstrapping or when asserting the requested profile.

The default reproducible engine profile is the compact MCP tool-search response. Pass
`-ApplyMcpToolSearchPatch` to bootstrap; it applies the current patch, records its SHA-256
fingerprint in `Saved/UEAgent/route.json`, and refuses a conflicting dirty engine checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -ApplyMcpToolSearchPatch -Launch
```

`patches/ue58-mcp-tool-search.patch` adds catalog search, per-tool discovery, server-side JSON
projection, structured-only results, and the compact `detail=call` view. Gateway and daemon
request it when discovery has no explicit detail. Use `detail=full` only when
the complete JSON schema is required; `detail=summary` remains useful for names/descriptions.
For large Material/Blueprint/Niagara JSON results,
pass `projection` to `call_tool`; `fields`, `exclude`, and `max_items` are server-side and never
reach the underlying tool. Add `structured=true` for `structuredContent`; it omits the duplicate
text part. HLSL is never silently truncated.

For a manual source checkout, apply the same current patch once:

```powershell
git -C <UE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search.patch
git -C <UE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search.patch
```

`detail=call` returns structured-only compact shapes (`tool`, `effect`, `args`, `returns`). The
effect label is a conservative name/description heuristic; `unknown` is intentional when the
source schema does not declare side effects. Use explicit `full` only for exact schema validation.

The bootstrap:

1. validates the pinned UE 5.8.1 baseline and the native MCP plugins;
2. installs the pinned VibeUE checkout and applies the selected profile plus performance monitor,
   shutdown guard, and reliable execution kernel;
3. applies the native MCP authorization gate and writes the reliable Editor config;
4. optionally applies the default engine MCP tool-search profile and records its hash;
5. optionally applies the verified Niagara authoring profile, including its Niagara Toolsets
   extension;
6. optionally applies the Abyss engine/VibeUE compatibility extensions, project setting, and
   external-plugin inventory;
7. enables the three plugins and writes the loopback MCP configuration;
8. merges `ue-editor` into the target `.mcp.json`;
9. records explicitly enabled project-local external plugin versions and descriptor hashes in the
   machine-local `Saved/UEAgent/route.json`;
10. creates or updates a small managed UEAgent gate in the target `AGENTS.md`;
11. builds and optionally launches the editor.

Use `-SkipBuild` only when matching binaries already exist. Use `-CheckOnly` to verify the
installed state without changing it; add `-ApplyMcpToolSearchPatch` when that profile is
required. The check compares the route-selected VibeUE profile, patch fingerprints, patch
application state, plugins, endpoint, and the target-project gate.

## Run the mandatory preflight

From the target project root:

```powershell
$route = Get-Content -Raw .\Saved\UEAgent\route.json | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') -RouteFile .\Saved\UEAgent\route.json -Pretty
```

Doctor always performs the live route check; use `-View detail` only to diagnose a failed receipt.
For offline configuration validation use `bootstrap.ps1 -CheckOnly`.

For the hot path, save the receipt once and let the compact context router decide whether MCP is
needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -OutFile .\Saved\UEAgent\doctor.json -Pretty
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\compact_context.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -AssetPath /Game/... -Operation read -Pretty
```

When the envelope says `CACHE_READ`, use the adjacent `.uasset.ai.md` through
`scripts\reflect_cache.ps1` in the order `summary -> refs -> detail -> full`; do not start with
MCP. For a known domain, describe the selected tool directly. For an unknown domain, use the
cacheable `toolsets.list` result once, then treat the running `describe_toolset` response as
authoritative.

The receipt checks the route contract, endpoint safety, listener state, the native compact-call
schema, all reliable control tools, and the live `ueagent_state` protocol/editor epoch/PID. Static
project, source, Git, and patch validation belongs to `bootstrap.ps1 -CheckOnly`. Domain toolsets are
described later only when the task needs them. Follow `status`, `allowed`, and `blocked`;
a healthy connection still does not grant save or destructive authority. `allowed` and `blocked`
are present in `-View detail`; compact Doctor exposes status/capabilities and `compact_context`
alone selects the task-specific next route.

Gateway infers the mechanical action from the tool. A normal call exposes only the tool and its
non-empty arguments; from the target project root it auto-loads `Saved/UEAgent/route.json`, while
other working directories pass `-RouteFile`. Keep complex arguments in a file instead of
PowerShell-escaped inline text:

```powershell
$gw = Join-Path $route.ueAgentRoot 'scripts\mcp_gateway.ps1'
powershell -File $gw -RouteFile .\Saved\UEAgent\route.json -Tool ueagent_state
powershell -File $gw -RouteFile .\Saved\UEAgent\route.json `
  -Tool ueagent_submit -ArgumentsFile .\Saved\UEAgent\submit.json
```

When work needs the packaged Niagara Toolsets extension, add
`-ProbeAdvancedCapabilities`. This describes only the two relevant toolsets and verifies that the
running editor binary—not merely its source tree—exports the patched methods.

## Offline recovery

If the receipt is `OFFLINE` and port 8000 has no listener, do not use UI automation. Ask the
user to run this once in the Unreal console:

```text
ModelContextProtocol.StartServer 8000
```

Then rerun the doctor. If Unreal reports `unable to bind`, inspect the exact listener PID first;
do not start more gateways or broadly terminate processes.

## Transport routing

After `compact_context.ps1` returns `NEEDS_DOCTOR`, run `doctor.ps1` once and use its receipt
directly; do not run `compact_context.ps1` again for that task. Once the receipt permits a live
route, use `scripts/mcp_gateway.ps1`; it is the sole AI-facing client. Native MCP is the server
behind Gateway, and all writes still enter through the fixed `ueagent_*` control surface. If that
surface cannot express the operation, extend it or stop at `BLOCKED`; do not use another client.
The unauthenticated endpoint stays loopback-only, so Gateway and Unreal Editor must run on the same
machine.

Gateway clients may pass `-SchemaCacheFile .\Saved\UEAgent\schema-cache.json` to
`tools.list`, `toolsets.list`, and `toolset.describe`. This cache is disposable, session-scoped
when a project session file is present, expiry-bounded, and read-only; discard it when its session
cannot be verified. Never use it for asset/tool results or mutations.

For platform-independent repeated calls, add a project-scoped session record:

```powershell
$gw = '<IRIS_ROOT>\work\UEAgent\scripts\mcp_gateway.ps1'
$session = '<PROJECT>\Saved\UEAgent\mcp-session.json'
powershell -NoProfile -ExecutionPolicy Bypass -File $gw -Action ping `
  -Endpoint http://127.0.0.1:8000/mcp -SessionFile $session
```

The first call initializes and stores only the MCP session ID; later calls use it directly and
reinitialize once only when the server explicitly rejects that session before dispatch. The record belongs
under `Saved\UEAgent` and must not be committed or copied between projects. Use `-CloseSession` for
an explicit shutdown. The gateway rejects non-loopback HTTP endpoints.

Gateway exposes `-ProjectionFile` on inferred registry calls, plus `-DescribeDetail summary` and
`-DescribeToolName <suffix>` when `-Toolset` infers describe. Every AI-generated request crossing a
child `powershell.exe` boundary must be built as an object, serialized with `ConvertTo-Json`, and
passed as UTF-8 `-RequestBase64`; use `-RequestFile` for large/multiline requests and `-ScriptFile`
only for actions that support it. Otherwise keep code such as Custom HLSL inside the encoded
request. Never hand-escape raw JSON into `-RequestJson`, `-ArgumentsJson`, or `-ProjectionJson`
across that boundary, even for read-only calls. The model-facing object itself needs only `tool`,
`arguments`, optional `toolset`, and optional `projectionProfile`.

For common ref-list reads, `-ProjectionProfile refs` keeps only `returnValue.refPath` (maximum 256)
and uses structured output; `-ProjectionProfile compact` keeps `returnValue` (maximum 64).
Projection profiles are `identity`, `topology`, `logic`, `runtime`, `hlsl`, and `changed`; domain
aliases such as `material.topology`, `blueprint.logic`, and `niagara.runtime` are accepted. An
explicit request/file projection overrides a profile. Unprojected registry calls request structured-only
transport without truncation. Model-facing results are data-only and remove standard transport
envelopes, duplicate text, positive success flags, lone `returnValue`, and empty/derived reliable
fields, timings, and fixed-state diagnostics. Receipt identity,
outcome/effect/verification/persistence, hashes, save tokens, errors,
and semantic payload values remain exact. Use `-Diagnostics` only for a scoped transport incident;
ordinary model-facing calls never request raw envelopes.

The profiles are progressive, not semantic authority: `identity`/`topology` omit node properties,
`logic` omits layout and HLSL, `runtime` keeps state/overrides, `hlsl` is explicit for code, and
`changed` is for mutation readback. Tool-specific fields remain authoritative; if a profile does
not contain a required field, request an explicit projection or `compact`/`full`.

Cache lifecycle maintenance is offline and cache-only. After an asset rename/delete or a cache
format/plugin upgrade, run `reflect_cache.ps1 -Action reconcile -RouteFile <PROJECT>\Saved\UEAgent\route.json -Repair`.
It writes `Saved\UEAgent\cache-manifest.json`, repairs only a unique source-hash rename match,
and moves unresolved sidecars to `Saved\UEAgent\cache-orphans`; it never deletes them. The
sidecar still describes saved state only; dirty Editor memory requires live MCP.

If repeated Gateway latency matters, run the optional local daemon once and send the same request
JSON over loopback HTTP. It keeps one MCP session and one HTTP client in memory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <IRIS_ROOT>\work\UEAgent\scripts\mcp_gateway_daemon.ps1 `
  -ListenPort 18765 -Endpoint http://127.0.0.1:8000/mcp `
  -SessionFile <PROJECT>\Saved\UEAgent\mcp-session.json

Invoke-RestMethod -Uri http://127.0.0.1:18765/ -Method Post -ContentType application/json `
  -Body (@{ action = 'ping' } | ConvertTo-Json -Compress)
```

The daemon is serialized, loopback-only, and supports `close`/`shutdown`; it is not an additional
UE plugin or a replacement MCP server. Enable it only when repeated-call latency is measured and
the warm session is worth another local process. It runs under process-level health guardrails;
auto-start passes the current UE listener PID
and these defaults: 2 GiB private memory, 1,000 requests, 2 hours uptime, 15 minutes idle,
8 MiB request, and 64 MiB response. The daemon cancels timed-out MCP requests, disposes request
and response streams, and exits cleanly when a budget is reached; it never retries a mutation after
an uncertain result. The one-shot Gateway remains the default. A manually started daemon should
also pass `-ParentPid <AbyssEditor PID>`; all budgets are
overrideable on `mcp_gateway_daemon.ps1` when a project needs a different envelope.

For transparent warm-up, add `-AutoDaemon` to a normal gateway action. If 18765 is free, that
first action stays on the one-shot path while the daemon starts in the background; later actions
automatically forward to the warm daemon. The gateway verifies a daemon identity probe before
forwarding, so an unrelated listener is never treated as UEAgent. Use `-DaemonUrl` directly for
an already-running daemon.

`AGENTS.md` is the current Codex adapter. Do not create another client adapter unless the current
task activates that client; then add only thin routing to UEAgent's single policy source.
