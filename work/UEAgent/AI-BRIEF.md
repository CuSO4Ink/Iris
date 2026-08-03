# UEAgent

UEAgent is the canonical onboarding and operating layer for AI access to Unreal Engine 5.8.
It is not an engine fork or another MCP server. It routes an AI to the available execution
backend, defines what is safe, and keeps verified cross-project experience in one place.

The complete progressive-disclosure and rollback record is
[PROGRESSIVE-DISCLOSURE.md](PROGRESSIVE-DISCLOSURE.md). It defines the only compact-to-full
expansion order; this brief remains the authority boundary summary.

## Authority boundaries

| Authority | Owns |
|---|---|
| Target UE project | Product intent, asset meaning, project conventions, visual goals |
| Live Unreal Editor | Dirty/in-memory state, current level, compile and runtime state |
| `.uasset` | Saved asset truth |
| Reflect Cache | Disposable saved-state read model; never writes back to UE |
| UEAgent | Connection gate, capability routing, safety rules, reusable MCP experience |
| Native MCP / VibeUE | Replaceable execution adapters, not policy sources |

## Mandatory route

```text
target project AGENTS.md
-> HOTPATH.md + compact_context.ps1
-> CACHE_READ or UEAgent doctor receipt
-> cache or live capability route
-> target project brief/task
-> one scoped operation
-> independent verification
-> explicit save boundary
-> verified experience back to UEAgent
```

Run the doctor once per new AI/editor session and again after an editor restart, reconnect,
timeout, or transport failure. Do not run it before every tool call.

If `compact_context.ps1` returns `NEEDS_DOCTOR`, run doctor once and use its receipt directly;
do not rerun compact context for the same task. A healthy receipt follows the listener PID and MCP
session ID; the age limit is only a fallback when identity cannot be checked.

`doctor -Profile quick` is only a route/listener check. A live call requires
`doctor -Profile live` and its receipt. `compact_context.ps1` defaults to a compact envelope;
use `-View detail` only for diagnosis.

## Receipt states

| State | Allowed | Blocked |
|---|---|---|
| `HEALTHY` | Cache, live reads, and task-gated mutation | Unauthorised save/delete/move/merge; unverified capabilities |
| `DEGRADED` | Cache and only the live reads that the receipt proved | Mutation and save |
| `OFFLINE` | Source, cache, config, and log analysis | Live-state claims and UE mutation |
| `BLOCKED` | Fix route/configuration inputs | MCP work |

`RESULT_UNKNOWN` is an operation outcome, not a connection state. A timeout after a possible
mutation means read back the target before retrying.

## Transport priority

After the gate, Gateway is the default live client route (`scripts/mcp_gateway.ps1`; use
`-AutoDaemon` for repeated calls). The platform/native MCP client remains the fallback for a
Gateway client/daemon failure, a pre-operation timeout, or a client-only capability while the
receipt is still healthy. If the endpoint/Editor is unhealthy, repair or remain offline. Both
routes hit the same loopback UE MCP endpoint and follow the same schema, authority, one-writer,
and readback rules. A post-mutation timeout must be read back before any transport switch or retry.
Hosts with a trusted native MCP client may bypass Gateway for ordinary calls as a performance
override when no Gateway shaping/session/debug feature is needed; this does not change the gate or
authority rules. Doctor receipts follow the listener PID, MCP session ID, and plugin binary
fingerprint; their age limit is only a fallback when identity cannot be checked.

## Capability ladder

Stop at the first rung that answers the task:

1. Current `.uasset.ai.md` sidecar for saved-state read questions.
2. Official typed MCP tool discovered from the live schema.
3. VibeUE service for a confirmed official-tool gap.
4. Narrow, discovered `execute_python_code` fallback with exact pre/postconditions.
5. User-performed editor UI step.

Do not use fixed tool counts as a health check. Tool and toolset registration is dynamic.
Do not nest a service inside `ProgrammaticToolset` merely to reduce calls; Scene actor creation
and Niagara scratch operations have both produced long stalls in that shape.

## Operating invariants

- One writer per UE object; never parallelize mutations against the same asset or level.
- Discover tool schema, UObject properties, and graph pin names before writing.
- Make one logical mutation, then verify through an independent signal.
- Treat save, delete, move, merge, Undo/Redo, and level commit as separate high-risk boundaries.
- Compile success and tool `success=true` are not behavioral proof.
- Structural evidence belongs to AI; visual/aesthetic approval belongs to the user.
- UI interaction is manual: UEAgent does not use Computer Use to drive Unreal.

## Knowledge lifecycle

```text
Observed friction -> namespaced pitfall -> isolated Probe -> Verified domain rule
                  -> small script/plugin fix only after real repetition
```

Mandatory instructions contain only stable rules. Project-specific or version-specific evidence
stays in `notes/mcp-pitfalls.md` with provenance.

## Repository map

- `skills/ue-mcp-workflows/HOTPATH.md`, `scripts/compact_context.ps1` — hot-path routing and
  compact session/asset context.

- `SETUP.md`, `scripts/bootstrap.ps1` — install and target-project routing.
- `STACK-MANIFEST.json` — machine-independent profile, patch hashes, daemon defaults, and
  verification commands for reproducing this stack on another checkout.
- `scripts/doctor.ps1` — machine-readable preflight receipt.
- `scripts/mcp_gateway.ps1` — default live client route; it can reuse a project-scoped MCP session
  and apply server-side response projection.
- `scripts/mcp_gateway_daemon.ps1` — optional loopback daemon for warm-call latency and HTTP-client
  reuse; it is not required for the normal cache-first route.
- `patches/` — exact portable source extensions consumed by bootstrap.
- `skills/ue-mcp-workflows/` — mandatory router, Core rules, and domain SOPs.
- `projects/ReflectCache/` — sidecar protocol and implementation evidence.
- `notes/mcp-pitfalls.md` — observed/conditional/version-specific evidence.
- `BACKLOG.md` — only unresolved UEAgent work.
- `LOG.md` — concise current-stack decisions.

## Portability boundary

The reproducible base is UE 5.8 native MCP plus pinned VibeUE
`271f48771d077179fb597dc285ab5b898c5e8038` and `patches/vibeue-ueagent.patch`. Bootstrap applies
that extension and records its checksum in the target route. The optional
`patches/ue58-niagara-toolsets.patch` is recorded only when present. Source presence is not runtime
proof: doctor reports advanced hooks as `PRESENT_UNVERIFIED` until a task-specific live probe
succeeds, and Niagara scratch-pin mutation remains blocked by default.

The remote Niagara authoring overlap is resolved under
`patches/niagara-mcp-authoring/`: use the revision-adapted engine patch plus
`vibeue/vibeue-ueagent-authoring.patch` as one advanced profile. That composite replaces the
core VibeUE patch; never apply both. It is packaged for explicit opt-in only and remains
`PRESENT_UNVERIFIED` until a clean rebuild and disposable-asset probe pass.

`patches/ue58-mcp-tool-search-v2.patch` is the optional UE 5.8 catalog/projection optimization;
`patches/ue58-mcp-tool-search-v3-call-view.patch` adds compact authoritative discovery. With v3,
Gateway and daemon discovery defaults to `detail=call`; direct native callers can request
`detail=full` for exact JSON Schema. The call result is structured-only and omits repeated toolset
metadata, long descriptions, and the single-tool `tools` wrapper. `structured=true` on
`call_tool` remains available for large result data. Abyss runtime proof was completed on
2026-08-03: the rebuilt editor returned v3 `detail=call` as structured-only data, with
`get_expressions.effect=read`.

The default remote-reproduction command is `scripts/bootstrap.ps1` with
`-ApplyMcpToolSearchPatches`; it applies v2 then v3 and records both patch hashes in the target
route. `scripts/bootstrap.ps1 -CheckOnly -ApplyMcpToolSearchPatches` verifies the same profile
without changing the target. The daemon is a UEAgent-owned runtime script with bounded defaults;
it is not an engine patch and does not require an editor rebuild when only the daemon changes.
