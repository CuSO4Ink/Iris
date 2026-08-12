# UEAgent

UEAgent is the policy and routing layer for AI access to Unreal Engine 5.8. It is not an
engine fork or a second MCP server. The full token/rollback record is
[PROGRESSIVE-DISCLOSURE.md](PROGRESSIVE-DISCLOSURE.md); this brief is the compact authority map.

## Authority

| Source | Authority |
|---|---|
| Target project | intent, conventions, visual goals |
| Live Editor | dirty/in-memory state, compile/runtime/current level |
| `.uasset` | saved asset truth |
| Reflect Cache | disposable saved-state read model; never writes UE |
| UEAgent | route, capability discovery, safety, reusable MCP practice |
| Gateway/native MCP/VibeUE | replaceable execution transports |

## Required route

```text
project gate -> HOTPATH + route -> CACHE_READ or doctor receipt
-> cache/live read -> target brief -> one scoped operation
-> independent readback -> explicit save -> recorded result
```

`compact_context.ps1` is a router, not live evidence. `CACHE_READ` stops before MCP. On
`NEEDS_DOCTOR`, run `doctor.ps1` once and use its receipt; do not rerun compact context for the
same task. Reuse a receipt while Editor listener PID, MCP session, and plugin fingerprint match;
restart/reconnect/timeout/transport failure/plugin reload invalidates it. TTL is only a fallback.

| Receipt | Allowed |
|---|---|
| `HEALTHY` | cache, proven live reads, task-gated mutation |
| `DEGRADED` | cache and only proven live reads |
| `OFFLINE` | source/cache/config/log analysis |
| `BLOCKED` | route repair only |

`RESULT_UNKNOWN` means a possible mutation timed out; read back before retrying or switching
transport.

## Default live transport

Gateway (`scripts/mcp_gateway.ps1`) is the portable default; use `-AutoDaemon` only for repeated
calls. Native/platform MCP is a fallback when the receipt is healthy and Gateway fails before an
operation or lacks a required client feature. Both routes use the same endpoint, schema, authority,
one-writer rule, and readback. A trusted native client may be a performance override for ordinary
calls when Gateway projection/session/debug shaping is unnecessary.

The optional `project-unrealmcp-stdio` transport is a platform fallback for projects that already
ship a compatible UnrealMCP binary. UEAgent verifies an exact STDIO read-tool allow-list and one
loopback TCP live read, then deliberately issues a read-only `DEGRADED` receipt; it never grants
mutation or save.

## Safety and capability order

- One writer per UE object; never guess a tool, UObject property, or graph pin.
- Make one logical mutation, verify independently, and treat save/delete/move/merge/Undo/Redo/
  level commit as explicit high-risk boundaries.
- Stop at the first sufficient source: current sidecar -> official typed MCP -> verified VibeUE
  gap -> narrow discovered Python fallback -> user UI step.
- Structural evidence belongs to AI; visual/aesthetic approval belongs to the user. UEAgent never
  drives Unreal UI with Computer Use.

## Context policy

Always load only `work/UEAgent/AGENTS.md` and `skills/ue-mcp-workflows/HOTPATH.md` for routing.
Load one domain card after a live receipt. Add the workflow Skill, Core, and target brief only for
mutation/save or an unfamiliar capability. Do not preload `SETUP.md`, `LOG.md`, `BACKLOG.md`, the
full pitfall ledger, or the full ReflectCache protocol.

For exact profiles, patch hashes, daemon limits, and reproduction commands use
[STACK-MANIFEST.json](STACK-MANIFEST.json). For cache lifecycle use
`scripts/reflect_cache.ps1 -Action reconcile`; it is offline-only, preserves orphaned sidecars,
and never represents dirty Editor state.

## On-demand map

- `skills/ue-mcp-workflows/`: hot path, Skill, Core, and domain cards.
- `scripts/`: route, doctor, Gateway, daemon, cache reader/reconciler.
- `patches/`: portable UE/VibeUE extensions recorded in the manifest.
- `projects/ReflectCache/`: cache implementation and evidence.
- `notes/`: verified/observed version-specific friction.
- `PROGRESSIVE-DISCLOSURE.md`: full views, measurements, and rollback history.
