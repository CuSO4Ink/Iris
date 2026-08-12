# UEAgent hot path

This is the default machine-facing card. For `CACHE_READ`, load only this card, the route,
`compact_context.ps1`, and the sidecar view needed for the answer. Do not preload AI-BRIEF,
SETUP, LOG, BACKLOG, Core, or every domain card. Full measurements and rollback are in
[PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

Budget before the MCP result: navigation <=1.5k estimated tokens, live read rules <=4k, mutation
rules <=8k. If a task exceeds the budget, unload on-demand prose before weakening a safety gate.

## Gate

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <ueAgentRoot>\scripts\compact_context.ps1 `
  -RouteFile <project>\Saved\UEAgent\route.json -AssetPath /Game/... `
  -Domain material -Operation read -ReceiptFile <project>\Saved\UEAgent\doctor.json
```

Default output is compact routing state, not live evidence. Use `-View detail` only for diagnosis.

| Result | Next step |
|---|---|
| `CACHE_READ` | `reflect_cache.ps1 -Action read -View summary`; expand `refs -> detail -> full` only as needed; no MCP if answered |
| `NEEDS_DOCTOR` | run `doctor.ps1` once; use its receipt directly; no second compact pass |
| `LIVE_READ` | one targeted live read using cached schema when valid |
| `LIVE_MUTATE_TASK_GATED` | load Skill + Core + one domain card; one writer, then independent readback |
| `LIVE_SAVE_EXPLICIT` | save only inside the user boundary; verify asset and sidecar |
| `BLOCKED` | repair route or request the exact manual UE console step |

The `project-unrealmcp-stdio` profile is intentionally read-only. Its successful live doctor
receipt is `DEGRADED` with `blueprintRead=true` only after the exact tool allow-list and a cheap
live read both pass; reads may continue, while mutation and save stay `BLOCKED`.

## Live call bounds

- Gateway is the default live client; add `-AutoDaemon` for repeated calls. Use native/platform
  MCP only for a healthy receipt when Gateway fails before the operation or lacks a needed feature.
  A mutation timeout is `RESULT_UNKNOWN`: read back before retrying or switching transport.
- If the domain/tool is known, skip `intent.list` and `toolsets.list`; describe one tool with
  `detail=call`. Use `summary` for routing and `full` only for exact schema validation/recovery.
- Request one projection: `identity`, `topology`, `logic`, `runtime`, `hlsl`, or `changed`.
  Domain aliases (`material.*`, `blueprint.*`, `niagara.*`) are accepted. HLSL/script is explicit.
- Prefer structured/data-only success. Use `-Envelope` only for legacy consumers and
  `-Diagnostics` only for transport/session debugging. Never default to full graphs, images/base64,
  recursive dependencies, or duplicated text+structured payloads.
- Never cache calls or mutations. Discovery/schema cache is session-scoped with TTL fallback.
  Combine only a known-safe logical mutation; compile once and read back changed nodes/pins/
  properties plus compile/dirty state.

## Invalidation

Discard receipt/schema cache after Editor restart, reconnect, timeout, transport failure, plugin
reload, or toolset change. A sidecar describes saved state; dirty Editor state always requires live
read. After rename/delete/cache-generator change:

```powershell
powershell -File <ueAgentRoot>\scripts\reflect_cache.ps1 -Action reconcile `
  -RouteFile <project>\Saved\UEAgent\route.json -Repair
```

The reconciler rehomes only a unique source-hash match and quarantines unresolved sidecars under
`Saved\UEAgent\cache-orphans`; it never deletes them.
