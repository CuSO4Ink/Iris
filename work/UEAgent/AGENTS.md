# UEAgent agent entry

UEAgent is the mandatory gate for any AI work that depends on live Unreal Editor state.

## Standard UE project brief block

Every UE-related project's `AI-BRIEF.md` must begin with the marker
`<!-- iris-project-kind: ue -->` and this navigation contract (adapt only the relative links):

> **UEAgent first (mandatory for live UE/MCP work).** Navigate to the [UEAgent entry](AGENTS.md)
> and [hot path](skills/ue-mcp-workflows/HOTPATH.md) before using live Unreal state. Read the
> target project's `Saved/UEAgent/route.json`, run `compact_context.ps1`, and stop on
> `CACHE_READ`; on `NEEDS_DOCTOR` run `doctor.ps1` before the first live call. A `BLOCKED` route
> requires repair. After the route state is known, continue with this project's brief and task documents. Offline source, cache, config,
> log, and documentation analysis may skip MCP, but must not claim live editor state.

1. Read `skills/ue-mcp-workflows/HOTPATH.md` and the target project's `Saved/UEAgent/route.json`.
2. Run `scripts/compact_context.ps1` for the requested asset and operation.
3. If it returns `CACHE_READ`, read the sidecar and stop before MCP. If it returns `NEEDS_DOCTOR`,
   run `scripts/doctor.ps1` once and use that receipt directly; do not rerun compact_context for
   the same task. A `BLOCKED` result requires route repair. For `LIVE_READ`, load only the
   relevant domain reference; add `AI-BRIEF.md`, the Skill, and Core for mutation/save work.
4. Read the target project's own brief and task documents after the connection state is known.

## Transport priority

After the cache/route gate, use the local Gateway as the default live transport:

1. `CACHE_READ`: read the sidecar and use no live transport.
2. `LIVE_READ` or an authorized mutation: call `scripts/mcp_gateway.ps1`; use
   `-AutoDaemon` (or the warm daemon) for repeated calls.
3. If the Gateway client/daemon is unavailable, times out before an operation starts, or lacks a
   required client feature **while the receipt is still healthy**, use the platform/native MCP
   client against the same routed endpoint. If the endpoint/Editor is unhealthy, repair or remain
   offline; do not blindly switch transports.
4. If both transports are unavailable, remain in offline source/cache/config/log analysis.

Gateway is a thin local client/daemon route to the same UE MCP endpoint, not a second MCP server
or a second source of tool semantics. The platform/native client is a transport fallback, not a
permission or safety bypass. After a possible mutation timeout, read back first (`RESULT_UNKNOWN`)
before changing transport or retrying.

Performance override: a host that already exposes a trusted native MCP client may use it directly
for an ordinary live call after the same gate, when no Gateway projection/session/debug feature is
needed. This is a transport optimization, not a new authority path; Gateway remains the portable
default and the native client remains available as its fallback.

Local source, cache, config, log, and documentation analysis may proceed while MCP is offline.
Never claim live state or mutate UE unless the current receipt permits that route. A
`HEALTHY` receipt does not authorize save, delete, move, merge, or level commit.

Do not control Unreal UI with Computer Use or mouse automation. When UI interaction or visual
approval is required, stop and give the user exact manual steps.

For sidecar cache implementation work, read `projects/ReflectCache/AI-BRIEF.md`. For ordinary
asset reads, use the cache-first rules selected by the domain reference; do not load the whole
ReflectCache protocol.

Read `BACKLOG.md` only when changing UEAgent itself. Historical incidents belong in
`notes/mcp-pitfalls.md`, not in the mandatory route.
