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
| UEAgent reliable kernel | editor epoch, command queue, leases/OCC, immutable receipts, scoped save capabilities |
| UEAgent | route, capability discovery, safety, reusable MCP practice |
| Gateway | sole AI-facing live client; route binding, bounded requests, and result shaping |
| Native MCP server | canonical server transport reached through Gateway |
| ToolsetRegistry / VibeUE | typed Editor operations executed under the reliable kernel |

## Required route

```text
project gate -> HOTPATH + route -> CACHE_READ or doctor receipt
-> cache or authoritative snapshot -> target brief -> ueagent_submit
-> job/receipt -> independent snapshot -> optional save capability -> save receipt
```

`compact_context.ps1` is a router, not live evidence. `CACHE_READ` stops before MCP. On
`NEEDS_DOCTOR`, run `doctor.ps1` once and use its receipt; do not rerun compact context for the
same task. Reuse a receipt while Editor listener PID/epoch and plugin fingerprint match; an MCP
session is only a disposable client lease. Restart, ambiguous transport failure, explicit close,
or plugin reload invalidates the receipt. If identity cannot be revalidated, discard the receipt.

| Receipt | Allowed |
|---|---|
| `HEALTHY` | cache, proven live reads, task-gated mutation |
| `DEGRADED` | cache and only proven live reads |
| `OFFLINE` | source/cache/config/log analysis |
| `BLOCKED` | route repair only |

`RESULT_UNKNOWN` means the journal proves acceptance but not a terminal outcome. Query the receipt,
then use `ueagent_recover` and authoritative readback before any retry; the same `command_id` is the
only legal replay identity.

## Default live transport

Gateway (`scripts/mcp_gateway.ps1`) is the only AI-facing client; native MCP remains the only
server. Gateway calls the fixed `ueagent_*` control surface. If that surface lacks a required
operation, add one typed operation or stop—do not bypass Gateway with another client. Mutations
never execute through a Python/CLI side-channel: `ueagent_submit` journals and queues a typed
ToolsetRegistry or VibeUE call inside the Editor, while state, snapshots, jobs, and receipts provide
bounded readback.

## Safety and capability order

- One global logical writer is the deliberate reliability ceiling; declared scopes and OCC hashes
  prevent stale or undeclared writes.
- Make one logical queued mutation, require a terminal receipt, verify independently, and use the
  receipt-issued one-use capability to save exactly its package set.
- Stop at the first sufficient source: current sidecar -> `ueagent_snapshot`/bounded typed read ->
  queued typed ToolsetRegistry or VibeUE operation -> exact user UI step.
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

## File boundary

`work/UEAgent/` contains only durable policy, source, tests, patches, and verified documentation.
Temporary engine/plugin clones, install smokes, reproduction bundles, captures, and test output go
under `tmp/UEAgent/<task>/` and are removed after verification; do not recreate project-local
`out/` or `_tmp/` directories.

## On-demand map

- `skills/ue-mcp-workflows/`: hot path, Skill, Core, and domain cards.
- `scripts/`: route, doctor, Gateway, daemon, cache reader/reconciler.
- `patches/`: portable UE/VibeUE extensions recorded in the manifest.
- `RELIABLE-EXECUTION.md`: command queue, OCC, receipts, recovery, and save capability contract.
- `projects/ReflectCache/`: cache implementation and evidence.
- `notes/`: verified/observed version-specific friction.
- `PROGRESSIVE-DISCLOSURE.md`: full views, measurements, and rollback history.
