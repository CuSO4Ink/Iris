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
| Unreal Engine | UE 5.8 with native `ModelContextProtocol` and `EditorToolset` plugins |
| VibeUE | `271f48771d077179fb597dc285ab5b898c5e8038` |
| UEAgent VibeUE extension | selected profile patch plus `patches/vibeue-mcp-shutdown-guard.patch`, applied by bootstrap |
| Default engine profile | MCP tool-search v2 + v3 call view |
| Windows | Git and Windows PowerShell |

This baseline supports official typed tools plus the portable ReflectCache implementation. The
optional `patches/ue58-niagara-toolsets.patch` adds script graph/HLSL/rapid-iteration and live
component-state calls to a UE source checkout.

The verified advanced Niagara authoring profile covers dynamic `RequestNewTypedPin`, Simulation
Stage, Grid2D, RenderTarget2D, RasterizationGrid3D, and Custom HLSL authoring. Bootstrap applies
the revision-adapted engine patch and the conflict-resolved
`patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch` together.
<!-- BEGIN SUPERSEDED MANUAL PROFILE NOTE: DO NOT FOLLOW -->
That composite already contains the core cache/embedded-script changes, so it replaces—not
layers on top of—`patches/vibeue-ueagent.patch`. It is not applied by bootstrap or accepted as
verified by source presence alone.
<!-- SUPERSEDED: current bootstrap applies and validates this profile with -ApplyNiagaraAuthoringProfile. -->

<!-- END SUPERSEDED MANUAL PROFILE NOTE -->

The verified authoring profile is applied automatically with `-ApplyNiagaraAuthoringProfile`.
It applies the matching engine export patch, selects the composite VibeUE patch instead of the
core patch, and records `vibeUEProfile` plus `engineNiagaraAuthoringPatchSha256` in the route.
Every VibeUE profile then applies the shared MCP shutdown guard and records
`vibeUEMcpShutdownGuardPatchSha256`; `-CheckOnly` and doctor reject a missing, changed, or
unapplied guard.

## Configure a target project

From the UEAgent root:

### Prebuilt project UnrealMCP, read-only

When a target already enables a binary-compatible `UnrealMCP` plugin and its Python FastMCP
server exposes the approved read tools, bootstrap the project-owned TCP bridge without VibeUE:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -UseProjectUnrealMcp `
  -ProjectUnrealMcpServerName unreal-project `
  -SkipBuild
```

This profile verifies the engine/plugin BuildId, the existing `UnrealMCP` enablement, the Python
server checksum, and the exact six-tool read-only allow-list. It writes only the machine-local
`Saved/UEAgent/route.json`; it does not clone VibeUE, patch engine/project C++, change startup
maps, build, or launch Unreal. Doctor reports a healthy live connection as `DEGRADED` by design,
which permits proven reads while keeping mutation and save blocked.

Configure the same Python server as a Codex STDIO MCP using the
`-ProjectUnrealMcpServerName` value (`unreal-project` by default), restrict `enabled_tools` to the
route's `requiredTools`, and restart the local Codex client after changing its MCP configuration.
The Unreal TCP bridge defaults to loopback port 55557; pass `-ProjectUnrealMcpPort` only when the
compatible project plugin is configured for another loopback port.

### Full native MCP and VibeUE profile

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -UProject "X:\Projects\MyGame\MyGame.uproject" -EngineRoot "X:\UnrealEngine" -Launch
```

If the target already contains verified local VibeUE patches on the pinned baseline, preserve
them explicitly instead of letting bootstrap replace the checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -UProject "X:\Projects\MyGame\MyGame.uproject" -EngineRoot "X:\UnrealEngine" -PreserveExistingVibeUE -SkipBuild
```

The switch still rejects a dirty checkout whose `HEAD` differs from the pinned baseline or does
not contain the selected UEAgent VibeUE profile patch.

For a UE source checkout, add `-ApplyEngineNiagaraPatch` when the optional Niagara Toolsets
extension is required. Bootstrap first checks whether the exact patch is already present and
refuses conflicts; it never resets engine changes.

For the verified advanced Niagara authoring profile, pass `-ApplyNiagaraAuthoringProfile`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -ApplyNiagaraAuthoringProfile -ApplyMcpToolSearchPatches -Launch
```

The profile requires the pinned VibeUE baseline and a source-engine Git checkout. `-CheckOnly`
reads the route profile and validates the selected composite and engine patch automatically; the
profile switch is only needed when bootstrapping or when asserting the requested profile.

The default reproducible engine profile is the compact MCP tool-search response. Pass
`-ApplyMcpToolSearchPatches` to bootstrap; it applies v2 and then v3, records both SHA-256
fingerprints in `Saved/UEAgent/route.json`, and refuses a conflicting dirty engine checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -ApplyMcpToolSearchPatches -Launch
```

The v2 patch adds catalog search, per-tool discovery, server-side JSON projection, and
structured-only results. The v3 follow-up
`patches/ue58-mcp-tool-search-v3-call-view.patch` adds the compact `detail=call` view and makes
the Gateway/daemon request it when discovery has no explicit detail. Use `detail=full` only when
the complete JSON schema is required; `detail=summary` remains useful for names/descriptions.
For large Material/Blueprint/Niagara JSON results,
pass `projection` to `call_tool`; `fields`, `exclude`, and `max_items` are server-side and never
reach the underlying tool. Add `structured=true` for `structuredContent`; it omits the duplicate
legacy text part unless `include_text=true` is also supplied. HLSL is never silently truncated.

For a manual source checkout, the equivalent ordered application is:

```powershell
git -C <UE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search-v2.patch
git -C <UE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search-v2.patch
git -C <UE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search-v3-call-view.patch
git -C <UE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search-v3-call-view.patch
```

`detail=call` returns structured-only compact shapes (`tool`, `effect`, `args`, `returns`). The
effect label is a conservative name/description heuristic; `unknown` is intentional when the
source schema does not declare side effects. Explicit `full` is the validation fallback.

The bootstrap:

1. validates UE 5.8 and the native MCP plugins;
2. installs the pinned VibeUE checkout and applies the packaged UEAgent extension, or explicitly
   preserves the matching extension already present;
3. optionally applies the default engine MCP tool-search profile and records its hashes;
4. optionally applies the Niagara Toolsets profile and records its hash;
5. optionally applies the verified Niagara authoring profile and records both selected patch
   fingerprints;
6. enables the three plugins and writes the loopback MCP configuration;
7. merges `ue-editor` into the target `.mcp.json`;
8. writes machine-local `Saved/UEAgent/route.json`;
9. creates or updates a small managed UEAgent gate in the target `AGENTS.md`;
10. builds and optionally launches the editor.

Use `-SkipBuild` only when matching binaries already exist. Use `-CheckOnly` to verify the
installed state without changing it; add `-ApplyMcpToolSearchPatches` when that profile is
required. The check compares the route-selected VibeUE profile, patch fingerprints, patch
application state, plugins, endpoint, and the target-project gate.

## Run the mandatory preflight

From the target project root:

```powershell
$route = Get-Content -Raw .\Saved\UEAgent\route.json | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') -RouteFile .\Saved\UEAgent\route.json -Pretty
```

Use `-Profile quick -View compact` only for an offline route/listener check. Before a live call,
run `-Profile live -View compact`; use `-View detail` only to diagnose a failed receipt.

For the hot path, save the receipt once and let the compact context router decide whether MCP is
needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -Pretty | Set-Content .\Saved\UEAgent\doctor.json -Encoding utf8
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\compact_context.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -AssetPath /Game/... -Operation read -Pretty
```

When the envelope says `CACHE_READ`, use the adjacent `.uasset.ai.md` through
`scripts\reflect_cache.ps1` in the order `summary -> refs -> detail -> full`; do not start with
MCP. `scripts\progressive_audit.ps1 -Sidecar <sidecar>` records the byte/token reduction for a
cache. Use `mcp_gateway.ps1 -Action intent.list -Intent <domain> -DataOnly` only as a local hint;
the running `describe_toolset` response remains authoritative.

The receipt checks project configuration, endpoint safety, listener state, MCP top-level
discovery, toolset-router availability, and a cheap current-level read. Domain toolsets are
described later only when the task needs them. Follow `status`, `allowed`, and `blocked`;
a healthy connection still does not grant save or destructive authority. `allowed` and `blocked`
are present in `-View detail`; the compact view exposes only the next route and capability flags.

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
route, use `scripts/mcp_gateway.ps1` by default. The generated target-project `.mcp.json` remains
the platform/native MCP fallback. Both clients call
the same unauthenticated loopback endpoint, so the AI client and Unreal Editor must run on the
same machine.

A host with a trusted native MCP client may use direct native transport for ordinary calls as a
latency override when Gateway shaping/session diagnostics are not needed; keep Gateway as the
portable default and use the same receipt and readback rules.

Gateway clients may pass `-SchemaCacheFile .\Saved\UEAgent\schema-cache.json` to
`tools.list`, `toolsets.list`, and `toolset.describe`. This cache is disposable, session-scoped
when a project session file is present, TTL-bounded as a fallback, and read-only; never use it for
asset/tool results or mutations.

For platform-independent repeated calls, add a project-scoped session record:

```powershell
$gw = '<IRIS_ROOT>\work\UEAgent\scripts\mcp_gateway.ps1'
$session = '<PROJECT>\Saved\UEAgent\mcp-session.json'
powershell -NoProfile -ExecutionPolicy Bypass -File $gw -Action ping `
  -Endpoint http://127.0.0.1:8000/mcp -SessionFile $session -ReuseSession
```

The first call initializes and stores only the MCP session ID; later calls probe `tools/list`, reuse
the session when valid, and create a new one after an editor restart or expiry. The record belongs
under `Saved\UEAgent` and must not be committed or copied between projects. Use `-CloseSession` for
an explicit shutdown. The gateway rejects non-loopback HTTP endpoints.

Gateway also exposes the v2 shaping controls: `-ProjectionJson` or `-ProjectionFile` on
`tool.call`, plus `-DescribeDetail summary` and `-DescribeToolName <suffix>` on
`toolset.describe`. Use `-RequestBase64`/`-RequestFile` when PowerShell command-line quoting would
alter JSON paths or dotted projection fields.

For common ref-list reads, `-ProjectionProfile refs` keeps only `returnValue.refPath` (maximum 256)
and uses structured output; `-ProjectionProfile compact` keeps `returnValue` (maximum 64). Intent
profiles are `identity`, `topology`, `logic`, `runtime`, `hlsl`, and `changed`; domain aliases such
as `material.topology`, `blueprint.logic`, and `niagara.runtime` are accepted. An explicit
`-ProjectionJson` overrides a profile. Add `-DataOnly` when the caller wants only `data` and
Model-facing successful Gateway actions are data-only by default; use `-Envelope` for the legacy
diagnostic wrapper and `-Diagnostics` for transport/session details. Errors still retain a compact
error envelope, while raw server payloads require diagnostics.
Passing the dotted name through `-Intent` also selects the matching profile; a plain domain such as
`material` remains only a routing hint.

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
UE plugin or a replacement MCP server. For repeated work it is the preferred low-latency path,
and it runs under process-level health guardrails. Auto-start passes the current UE listener PID
and these defaults: 2 GiB private memory, 1,000 requests, 2 hours uptime, 15 minutes idle,
8 MiB request, and 64 MiB response. The daemon cancels timed-out MCP requests, disposes request
and response streams, and exits cleanly when a budget is reached; it never retries a mutation after
an uncertain result. One-shot Gateway/native MCP are failure fallbacks, not the normal performance
path. A manually started daemon should also pass `-ParentPid <AbyssEditor PID>`; all budgets are
overrideable on `mcp_gateway_daemon.ps1` when a project needs a different envelope.

For transparent warm-up, add `-AutoDaemon` to a normal gateway action. If 18765 is free, that
first action stays on the one-shot path while the daemon starts in the background; later actions
automatically forward to the warm daemon. The gateway verifies a daemon identity probe before
forwarding, so an unrelated listener is never treated as UEAgent. Use `-DaemonUrl` directly for
an already-running daemon.

`AGENTS.md` is the current Codex adapter. Add another client's thin rule adapter only when that
client is actually used; UEAgent remains the single policy source.
