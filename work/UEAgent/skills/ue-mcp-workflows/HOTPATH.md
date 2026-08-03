# UEAgent hot path

Use this card for ordinary AI work. Load `SKILL.md` and a domain reference only when the task
needs live UE or mutation details. Do not load `SETUP.md`, `LOG.md`, `BACKLOG.md`, or the full
pitfall ledger for a normal asset read.

The complete progressive-disclosure contract, view bounds, receipts, measurements, and rollback
map is [UEAgent/PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

For an ordinary `CACHE_READ`, load only this card, `compact_context`, and the sidecar view needed
for the answer. Do not pre-load `AI-BRIEF.md`, `SETUP.md`, `LOG.md`, `BACKLOG.md`, Core, or every
domain card. Load Core plus one domain card only when the route reaches mutation/save or an
unfamiliar live capability.

## 1. Build one context envelope

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  <ueAgentRoot>\scripts\compact_context.ps1 `
  -RouteFile <project>\Saved\UEAgent\route.json `
  -AssetPath /Game/... -Domain material -Operation read `
  -ReceiptFile <project>\Saved\UEAgent\doctor.json
```

The default output is the compact view. Add `-View detail` only when the full route/asset block
is needed. The envelope is a router, not authority. It reports `CACHE_READ`, `LIVE_READ`,
`LIVE_MUTATE_TASK_GATED`, `LIVE_SAVE_EXPLICIT`, or `BLOCKED`.

## 2. Route by result

- `CACHE_READ`: read `reflect_cache.ps1 -View summary`, then `refs` or a named `detail` block;
  do not call MCP while the cache answers the task.
- `NEEDS_DOCTOR`: run `doctor.ps1` once, then use its `allowed`/`blocked` receipt directly; do
  not rerun `compact_context.ps1` for the same task.
- `LIVE_READ`: use the cached schema if present, then one targeted live read.
- `LIVE_MUTATE_TASK_GATED`: load `SKILL.md`, Core, and the one relevant domain reference;
  discover the exact tool once, then use one writer and independent readback.
- `LIVE_SAVE_EXPLICIT`: save only inside the user boundary and verify the sidecar/asset state.
- `BLOCKED`: repair the route or ask the user for the exact Unreal console action.

## 2a. Select the live transport

For `LIVE_READ` and task-gated mutation, Gateway is the default (`mcp_gateway.ps1`; add
`-AutoDaemon` for repeated calls). Use the platform/native MCP client only when the Gateway
client/daemon fails before the operation starts and the receipt is still healthy, or when it
cannot expose a required client feature. If the endpoint/Editor is unhealthy, repair or remain
offline. A possible mutation timeout is `RESULT_UNKNOWN`: read back before switching transport or retrying.
`CACHE_READ` never needs either transport.

## 3. Payload rules

- Request only the needed field projection: summary, topology, logic, or runtime.
- Keep exact asset/refPath identities and mutation preconditions.
- For unknown tools, use the compact structured `describe_toolset detail=call` view first; use
  `summary` for routing and `full` only for argument validation or recovery.
- When the domain card already names the toolset and tool, skip `intent.list` and `toolsets.list`;
  describe only that tool.
- Expand cache views in order: `summary -> refs -> detail -> full`; `full` is explicit only.
- Never default to full graph text, image/base64 payloads, or recursive node inventories.
- Never cache tool calls or mutations. Only discovery/schema results may use the gateway schema
  cache, and only with an explicit TTL.
- Combine a known-safe logical mutation into one request, compile once, and read back only the
  changed nodes/pins/properties plus compile/dirty state. Do not batch unverified high-risk calls.

## 4. Invalidation

Re-run doctor and discard the receipt/schema cache after editor restart, reconnect, timeout,
tool transport failure, plugin rebuild, or toolset version change. A sidecar is saved-state
context; live dirty state still wins.
