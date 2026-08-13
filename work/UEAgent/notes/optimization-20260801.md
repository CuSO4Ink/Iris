# UEAgent MCP hot-path optimization

## Baseline (before)

Measured from the current UEAgent working tree on 2026-08-01. Token values are a stable
`bytes / 4` estimate, not a model tokenizer count.

| Scope | Bytes | Est. tokens |
|---|---:|---:|
| All UEAgent operating docs in the audit set | 43,798 | 10,950 |
| Material hot path: Skill + Core + Materials + ReflectCache brief | 15,228 | 3,807 |
| Cold docs not needed for an ordinary read: Setup + Log + Backlog + full pitfalls | 15,206 | 3,802 |

The mandatory text repeated the same route/doctor/receipt, cache-first, save-boundary, timeout,
and independent-readback rules across `AGENTS.md`, `AI-BRIEF.md`, Skill, Core, and domain SOPs.
The gateway opened a new MCP session for every action. A cold live material read therefore
typically repeated:

```text
preflight: initialize + initialized + tools/list + current-level call + DELETE
schema:    initialize + initialized + describe_toolset + DELETE
read:      initialize + initialized + tool call + DELETE
```

That is up to 13 HTTP operations before the actual asset result. The full `GetScriptGraphText`
or unfiltered graph result was also allowed to enter the AI context when a compact sidecar would
have answered the question.

## Changes

- Added `skills/ue-mcp-workflows/HOTPATH.md`, a short default router. Installation, history,
  and the complete evidence ledger are now cold paths.
- Added `scripts/compact_context.ps1`. It emits one compact JSON envelope containing route,
  receipt age/state, asset sidecar freshness, and the next permitted route.
- Added opt-in read-only schema caching to `scripts/mcp_gateway.ps1` for `tools.list`,
  `toolsets.list`, and `toolset.describe`. Tool calls and mutations are never cached.
- Updated the root gate and workflow Skill to use the hot-path card and context envelope first.

## After (measured)

The same Material task now loads the hot-path card plus the relevant domain card, not the full
setup/history/evidence set. The compact context script was run against the real Abyss route and
`/Game/Bifrost/Ocean/Wave/M_Wave_Base`; it reported the sidecar as current and selected
`CACHE_READ` without contacting MCP.

| Flow | Before | After |
|---|---:|---:|
| Cache-hit live MCP calls | 1 preflight path by habit | 0; `CACHE_READ` is sufficient |
| Material live-read control context | ~3,807 est. tokens | ~1,832 est. tokens |
| Material cache-hit control context | ~3,807 est. tokens | ~723 est. tokens |
| Cold setup/history/evidence added to read | ~3,802 est. tokens if loaded | 0 |
| Repeated schema calls in the same cache window | every gateway action | first call only; later read-only schema hits use the cache file |

The reductions are not additive: the context numbers measure documentation only, while schema
cache numbers measure transport calls. Live dirty-state checks, mutation preconditions,
independent verification, and explicit save boundaries remain mandatory and were not compressed.

Verification receipts:

```text
compact_context.ps1 /Game/Bifrost/Ocean/Wave/M_Wave_Base -Operation read -> CACHE_READ
compact_context.ps1 /Game/Bifrost/Ocean/Wave/M_Wave_Base -Operation mutate -> BLOCKED (no receipt)
mcp_gateway.ps1 tools.list with a seeded TTL entry -> cached=true, exit 0, no listener required
PowerShell parse: compact_context.ps1, mcp_gateway.ps1, bootstrap.ps1 -> 0 errors
Conflict markers under work/UEAgent -> none
```

## Limits

- The schema cache is opt-in and TTL-based; editor restart, reconnect, or a toolset version change
  must invalidate it.
- The compact envelope does not claim that a sidecar describes unsaved editor memory. A live
  mutation still requires the normal doctor receipt and domain SOP.
- Full graph/HLSL reads remain available as targeted fallbacks; they are no longer the default
  context route.

## MCP server discovery reduction (2026-08-01)

The UE 5.8 tool-search adapter previously concatenated every toolset's full multi-line
documentation into the `list_toolsets` text result. A live call returned 50,951 characters
(about 12,738 tokens using the same bytes/4 estimate). The source-level change now lives in
`patches/ue58-mcp-tool-search-v2.patch`; full schema discovery remains available while
`list_toolsets` emits only the toolset name plus its first trimmed line, capped at 240 characters.

Using the current live catalog as input, the compact projection is about 5,605 characters
(about 1,402 estimated tokens), an estimated 89% reduction. After the editor rebuild and
restart, the live `list_toolsets` call returned exactly 5,605 characters in 56 lines with no
nested documentation lines. `describe_toolset` still returned the full JSON schema (the Material
toolset response was 26,445 characters with 22 tools), so detailed discovery remains available
on demand.

## Coverage and rollback status

| Optimization | Scope | Status | Rollback evidence |
|---|---|---|---|
| Cache-first routing | `HOTPATH.md`, `compact_context.ps1`, gate/Skill references | Implemented and measured | The Iris worktree is dirty; no isolated reverse patch yet |
| Gateway discovery cache | `mcp_gateway.ps1` (`tools.list`, `toolsets.list`, `toolset.describe`) | Implemented and tested | The Iris worktree is dirty; revert only the schema-cache block, not the whole file |
| UE toolset catalog compression | UE 5.8 MCP adapter source | Implemented, rebuilt, and live-verified | Reverse v3, then `patches/ue58-mcp-tool-search-v2.patch` |
| Full tool-result projection | Generic server-side JSON `fields`/`exclude`/`max_items` | Implemented and live-verified | `git apply -R` v2 patch |
| Structured MCP result migration | Explicit `call_tool.projection.structured` opt-in | Implemented and live-verified | `git apply -R` v2 patch; default text path unchanged |
| Persistent Gateway sessions | Gateway transport lifecycle | Implemented and live-verified | `mcp-session.json` is disposable; `-CloseSession` removes it |
| Warm Gateway daemon | Optional loopback process with session/HTTP-client reuse | Implemented and live-verified | Stop with a `shutdown` request; no UE plugin dependency |

Safety checks are intentionally not removed: doctor gating, mutation preconditions, independent
readback, timeout recovery, and explicit save boundaries are required behavior, not redundant
traffic.

The exact UE source change is reversible. The broader Iris documentation/script edits are not
currently one-command reversible because this working tree already contains earlier user and
UEAgent changes; do not use `git reset` or whole-file checkout. Create a clean checkpoint before
packaging a full hot-path rollback bundle.

## Opt-in result shaping and remote VibeUE sync (2026-08-02)

### What changed

The v2 UE patch (`patches/ue58-mcp-tool-search-v2.patch`) keeps the previous catalog compression
and adds three explicit controls:

| Control | Default | Effect |
|---|---|---|
| `describe_toolset.detail=summary` | `full` | Returns only tool names/descriptions. |
| `describe_toolset.tool_name=...` | empty | Returns one matching tool schema (full name or suffix). |
| `call_tool.projection` | absent | Server-side JSON field projection; never forwarded to the tool. |

Projection accepts dotted `fields`, dotted `exclude`, `max_items`, `structured`, and
`include_text`. It is generic rather than Material/Blueprint/Niagara-specific, so it can reduce
their graph/HLSL-shaped JSON without duplicating three service implementations. It does not cap
strings: HLSL and other logic text stay complete unless a caller explicitly removes that field.
`structured=true` is the token-saving path; `include_text=true` restores the compatibility copy.
Plain-text tool results and calls without projection are unchanged.

Example intent (the exact tool name/schema is still discovered live):

```json
{"tool_name":"export_material_graph","toolset_name":"editor_toolset.toolsets.material.MaterialTools","arguments":{"material_path":"/Game/M_Test"},"projection":{"fields":["material","expressions.class","connections"],"exclude":["expressions.properties","expressions.hlsl_code"],"max_items":128,"structured":true}}
```

### Verification state (2026-08-02)

- Final `AbyssEditor` Development build completed successfully, including
  `AbyssEditor-ModelContextProtocolEditor.dll`, its tests DLL, and the merged VibeUE Fab change.
- Doctor was `HEALTHY`; port 8000 was listening and the route resolved to `LIVE_READ` after the
  fresh receipt check. No asset was mutated or saved.
- Live catalog: 5,605 characters / 56 non-empty lines. Material `describe_toolset` full remained
  26,445 characters / 22 tools, while `detail=summary` was 10,898 characters and
  `tool_name=get_expressions` was 1,160 characters / 1 tool.
- Live read of `M_Wave_Base.M_Wave_Base` returned 164 expression refs as the default text result
  (16,054 chars). The same call with `projection.fields=["returnValue"], max_items=5` returned
  528 chars; `fields=["returnValue.refPath"], max_items=3, structured=true` returned only a
  structured `returnValue` array with three refs and no duplicate text content.
- The v2 patch reverse check passed against the current engine checkout
  (`git apply --reverse --check`).

### VibeUE remote sync

Fetched `https://github.com/kevinpbuckley/VibeUE.git` on 2026-08-02. `origin/master` remains the
pinned `271f487`; the active UE 5.8 branch is `origin/5-8` at `6a0617c`, adding only the Fab
`engine_version=all/any` filter in two files. The checkout was shallow, so the first merge attempt
was rejected as a false unrelated-history case. After `git fetch --unshallow origin`, the real
common ancestor was `3e16b1b`; `git merge origin/5-8` completed without conflicts as local merge
commit `bf96d6b`. Existing local VibeUE edits in Module/Material/Niagara were preserved.

Bootstrap remains pinned to `271f487` for reproducibility; the merged checkout is a local update,
not a moving baseline. To roll back only that merge after creating a clean checkpoint:

```powershell
git -C X:\Projects\Abyss\Plugins\VibeUE revert -m 1 bf96d6b
```

Do not reset the dirty checkout. The v2 engine changes can be reverted with
`git -C <UE_ROOT> apply -R <IRIS_ROOT>\work\UEAgent\patches\ue58-mcp-tool-search-v2.patch`.

## Platform-independent Gateway fallback (2026-08-02)

The fallback path no longer has to initialize and delete an MCP session for every action when the
caller supplies a project-local `Saved\UEAgent\mcp-session.json`. The gateway now:

1. validates the endpoint as unauthenticated loopback HTTP;
2. reads a TTL-bound session record under a file lock;
3. probes a reused session with `tools/list` before any action;
4. creates a fresh session when the probe fails (editor restart/expiry); and
5. persists the new last-used session ID, unless `-CloseSession` was requested.

Tool calls and mutations are never cached or automatically retried. The health probe prevents a
stale session from turning into a blind mutation retry. The gateway also exposes the server v2
`projection`, `describe_toolset.detail`, and `describe_toolset.tool_name` controls to non-native
clients. It rejects non-loopback HTTP endpoints so a fallback invocation cannot silently become a
remote unauthenticated client.

Live checks against Abyss passed:

```text
first gateway ping:  sessionMode=new,  sessionPersisted=true
second gateway ping: sessionMode=reused, sessionReused=true, sessionProbeMs=586
projected get_expressions: structured returnValue with 3 refs, no duplicate text
single-tool describe: 1 tool returned through the gateway
remote endpoint probe: rejected with unsafe_endpoint before network access
PowerShell parse: gateway, doctor, compact_context, bootstrap -> 0 errors
```

This session-aware path is the minimal platform-independent fallback and does not require a daemon.
The next decision was measurement-driven rather than speculative: a short benchmark exposed the
remaining process/connection overhead, so the optional warm daemon below was added.

The measured bottleneck was real, so the optional daemon was added without changing the normal
fallback contract. It accepts the same action envelope over `http://127.0.0.1:18765/`, serializes
requests, keeps one `HttpClient`, and closes the UE session on `shutdown`. A short Abyss benchmark:

| Path | Warm-call wall time |
|---|---:|
| Native MCP client `list_toolsets` | 270–333 ms |
| One-shot Gateway `ping` | 1,859–2,002 ms |
| Session-file Gateway `ping` | 1,334–1,347 ms |
| Warm Gateway daemon `ping` | 149–332 ms |

`-AutoDaemon` now starts the daemon in the background on a cold call, so the first action remains
close to the one-shot path instead of waiting for a second MCP handshake. The measured cold call
was 2,338 ms (one-shot baseline 1,859–2,002 ms); later calls through the PowerShell convenience
wrapper were about 0.9–1.0 s because that wrapper still starts PowerShell, while direct daemon HTTP
calls stayed at 0.15–0.33 s. Auto-start is therefore a lifecycle convenience, not a replacement for
a long-lived client when the lowest per-call latency matters.

The daemon therefore reaches the native-client latency range for repeated calls while remaining a
local, optional process. It is not started unless explicitly launched or `-AutoDaemon` is supplied;
explicit `shutdown` keeps the process boundary visible.

The default daemon port is `18765` rather than the commonly occupied `8765`. AutoDaemon probes
`/__ueagent_daemon` and requires the `ueagent-gateway-daemon` identity before forwarding; an
unrelated listener is treated as occupied and the action stays on the one-shot path.

## Token shaping phase 2 (2026-08-02)

The Gateway now exposes two small projection presets and a data-only output mode:

| Option | Projection | Output |
|---|---|---|
| `-ProjectionProfile refs` | `returnValue.refPath`, max 256, structured | normal envelope |
| `-ProjectionProfile compact` | `returnValue`, max 64, structured | normal envelope |
| `-DataOnly` | unchanged | emits only `data`; errors keep their envelope |

An explicit `projection` still overrides a profile. The profile is deliberately generic: it only
assumes the common `returnValue` shape and does not guess Material/Blueprint/Niagara semantic
fields. This keeps the preset from silently dropping logic or HLSL.

The changes pass PowerShell parsing and static checks. Live verification completed after AbyssEditor
startup (`doctor=HEALTHY`, port 8000 listening, current level `/Game/Bifrost/Maps/L_Bifrost`):

- `-DataOnly ping` returned only `reachable` and `topLevelToolCount` (10).
- `refs` returned all 164 expression references in 16,054 characters; this particular source
  shape was already ref-only, so the preset mainly standardizes the request.
- `compact` returned 64 references in 6,325 characters; an explicit three-item projection returned
  330 characters. Explicit projection correctly overrides the profile.

No asset mutation or save was performed during this verification.
