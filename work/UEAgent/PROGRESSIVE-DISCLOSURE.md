# UEAgent progressive disclosure contract

This is the canonical record for the token-reduction route. It is an operational contract, not
an additional MCP server or a second project gate.

## One route

```text
route.json
  -> compact_context.ps1 -View compact
  -> CACHE_READ: read sidecar
  -> NEEDS_DOCTOR: doctor.ps1 once, then use its receipt directly
  -> LIVE_READ / LIVE_MUTATE_TASK_GATED from that receipt
  -> intent.list (only when domain/tool entry is unknown)
  -> live transport: Gateway (default; -AutoDaemon for repeated calls)
     -> platform/native MCP (fallback only on pre-operation Gateway failure)
  -> describe one known tool detail=call (structured-only)
  -> summary / one-tool call view only when routing needs it
  -> targeted call projection
  -> detail only for the missing block
  -> full only when explicitly justified
```

The target project still enters through `work/UEAgent/AGENTS.md` and
`skills/ue-mcp-workflows/HOTPATH.md`. `compact_context` is a router, not evidence of live UE
state. `doctor -Profile quick` only checks static route/listener readiness; it never authorizes a
live call. Use the live profile before MCP. Gateway and the platform/native client are equivalent
transports to the same endpoint; Gateway is the default route, while the platform client is only a
fallback when the receipt is still healthy and the failure is local to Gateway. An unhealthy
endpoint stays blocked/offline. A mutation timeout remains `RESULT_UNKNOWN` and requires readback
before switching.

## Views and bounds

| Layer | Command/result | Contains | Does not contain |
|---|---|---|---|
| summary | `reflect_cache.ps1 -Action read -View summary` | identity, freshness, format, counts, next hints | graph body |
| refs | `... -View refs` | direct `/Game/...` dependencies, bounded | recursive dependency expansion |
| detail | `... -View detail -Section Logic` | selected compact blocks, bounded by `-MaxItems` | unrelated sections |
| full | `... -View full` | raw sidecar or selected full section | no automatic truncation |

The default is always the first layer. A caller must name the next layer. `full` is an escape
hatch, not a normal cache read. `reflect_cache` never expands a referenced MaterialFunction,
Blueprint, Niagara script, or dependency automatically; each asset has its own sidecar.
Model-facing Gateway actions now default to data-only success responses. Use `-Envelope` for the
legacy `{ok, action, data}` wrapper, and `-Diagnostics` only when transport details are needed.
Pass `-View summary|refs`, a projection profile, or an explicit projection when a live call needs
the same bounds. Errors retain a compact envelope; raw server payloads require diagnostics.

For live MCP, use the same idea:

```powershell
# local routing hint; does not contact MCP
powershell -File .\scripts\mcp_gateway.ps1 -Action intent.list -Intent material -DataOnly

# compact call view is the default; this does not return JSON Schema
powershell -File .\scripts\mcp_gateway.ps1 -Action toolset.describe `
  -Toolset <toolset> -DataOnly

# names/descriptions only, when routing needs a readable list
powershell -File .\scripts\mcp_gateway.ps1 -Action toolset.describe `
  -Toolset <toolset> -DescribeDetail summary -DataOnly

# one exact compact callable shape
powershell -File .\scripts\mcp_gateway.ps1 -Action toolset.describe `
  -Toolset <toolset> -DescribeToolName <tool> -DataOnly

# complete schema only for validation or recovery
powershell -File .\scripts\mcp_gateway.ps1 -Action toolset.describe `
  -Toolset <toolset> -DescribeDetail full -DescribeToolName <tool> -DataOnly

# shape only the fields required by the task
powershell -File .\scripts\mcp_gateway.ps1 -Action tool.call `
  -Toolset <toolset> -Tool <tool> -ProjectionProfile refs -DataOnly
```

`intent.list` and `toolsets.list` are routing indexes, not authoritative schemas. When a domain
card already names the candidate toolset/tool, skip both and request one `describe_toolset` with
the selected `tool_name`. Tool names and arguments still come from the running response. An
explicit projection overrides a preset.
`structured=true` avoids the duplicate legacy text part; HLSL/code strings are not silently
shortened.

The `call` view is the lowest-cost authoritative discovery response. A single-tool result is one
object (`tool`, `effect`, `args`, `returns`), not `tools:[...]`; an all-tool call view uses one
`tools` array because there is no selected tool. Required arguments carry `!`; UE object schemas
become `ue_ref<Class>` and unions remain `|`-joined. `effect` is a conservative server heuristic
and may be `unknown`; never treat it as permission. `full` remains the only source for exact JSON
Schema validation.
If a pre-v3 editor rejects `call`, Gateway/daemon retry once with `full` and locally project the
result into the same compact call view. This saves model context immediately, but not the
server-to-Gateway wire bytes; the v3 server patch is still required for that.

Successful doctor receipts are session-bound. `compact_context.ps1` reuses them while the stored
listener PID, MCP session ID, and plugin binary fingerprint remain unchanged, with the old TTL
only as a fallback when identity cannot be checked. Gateway/daemon transport failures write a
small invalidation marker beside the receipt; editor restart, session replacement, explicit close,
plugin rebuild/reload, and a changed fingerprint require a new doctor. A `NEEDS_DOCTOR` result is
terminal for that routing pass: run doctor once and do not rerun compact_context merely to
recompute the same state.

## Freshness and mutation receipt

The sidecar is saved-state context. `.uasset` remains the only truth, and dirty editor memory is
always a live query. The cheap freshness test is source/sidecar mtime plus the declared source
size; `graph_sha1` and `sha256` are provenance, not permission to skip a required live check.

After a save, compare the old and new sidecars without echoing the whole graph:

```powershell
powershell -File .\scripts\reflect_cache.ps1 -Action receipt `
  -Sidecar <after>.uasset.ai.md -BaseSidecar <before>.uasset.ai.md `
  -ChangeAction material.save -Pretty
```

The receipt lists changed sections and counts, before/after digests, and explicitly says that an
independent MCP readback is still required for a live mutation. `diff` remains available when the
bounded added/removed lines are needed. A no-delta receipt is not proof that an unsaved editor
change did nothing; it only describes two saved sidecars.

## Index and measurement

`reflect_cache.ps1 -Action index -ProjectRoot <project>` scans sidecars and emits direct
dependency/reverse-dependency facts. It is intentionally bounded by `-MaxItems`; it is not a
garbage collector and cannot prove an asset is safe to delete.

`progressive_audit.ps1 -Sidecar <sidecar>` measures UTF-8 bytes and a stable `bytes/4` token
estimate for all four views. The estimate is for comparison only, not a model tokenizer count.

Real `M_Wave_Base.uasset.ai.md` measurement (2026-08-02): summary 779 bytes/195 estimated
tokens, refs 1,224/306, detail 8,423/2,106, full 15,785/3,947. The first two views therefore
remove about 92–95% of this saved-state payload; the exact ratio changes with the asset.

## Implemented optimizations and rollback

| Change | Scope | Default | Safe fallback/rollback |
|---|---|---|---|
| compact context envelope | `compact_context.ps1` | compact | `-View detail`; offline route still works |
| session-bound doctor receipt | `compact_context.ps1` + `doctor.ps1` | identity reuse; TTL fallback | remove `identity`/invalidation support and use the old TTL gate |
| `NEEDS_DOCTOR` handoff | compact context + Skill/HOTPATH | no second compact pass | treat it as `BLOCKED` and run the old two-pass route |
| reused-session tools/list | Gateway + daemon preflight | reuse probe result | issue a second `tools/list` for compatibility |
| session-scoped schema cache | `schema-cache.json` | same MCP session | omit session selector and use TTL-only cache |
| structured result preference | Gateway normalizer | structuredContent when present | parse legacy text content |
| cache-first sidecar reader | `reflect_cache.ps1` | summary | call MCP only when missing/stale/insufficient; delete this additive script if unused |
| intent index | `mcp_gateway.ps1 intent.list` | opt-in | skip it and run normal discovery |
| schema/detail selection | Gateway + UE v2/v3 call-view patches | call by default in Gateway/daemon | `-DescribeDetail full`; reverse v3, then v2 |
| bounded response presets | Gateway `refs|compact` | opt-in | explicit projection or unshaped call |
| data-only success | Gateway default | model-facing default | `-Envelope` restores compatibility wrapper |
| persistent session | project `Saved/UEAgent/mcp-session.json` | opt-in | omit session flags; `-CloseSession` removes the record |
| warm daemon | loopback `18765` | opt-in | use one-shot gateway/native MCP; POST `shutdown` |
| change receipt/audit | ReflectCache scripts | opt-in | retain normal readback and inspect raw sidecar |

Gateway correctness guards are part of the contract: `mcp_gateway.ps1` is UTF-8 with BOM for
Windows PowerShell 5.1, and schema cache keys include `DescribeDetail`, `DescribeToolName`, and
the active MCP session ID. Changing any of these is a compatibility change and requires repeating
the PowerShell 5.1 parse and cache-key collision checks.

The UE source projection/catalog patch is independently reversible with the exact patches recorded
under `patches/ue58-mcp-tool-search-v2.patch` and
`patches/ue58-mcp-tool-search-v3-call-view.patch` (`git apply -R` v3, then v2, after a clean
checkpoint). Do not reset the dirty Iris or VibeUE worktrees to roll back this table; revert only
the named change.

## Verification record

Every implementation change in this phase was checked with PowerShell AST parsing. Offline smoke
checks must cover: `intent.list`, `reflect_cache` summary/refs/detail/full/diff/receipt/index,
`progressive_audit`, `compact_context -View compact`, and `doctor -Profile quick`.

Live MCP checks are separate: run the live doctor after the editor is up, then verify one shaped
read and one mutation readback. If UE is offline or crashed, report that state; do not substitute
static checks for a live claim.

This phase's live read passed on the available editor: live doctor `HEALTHY` (UE 5.8.0, ten
top-level tools), followed by a data-only `RequestBase64` call returning three exact
`M_Wave_Base` refs with `fields=[returnValue.refPath]`, `max_items=3`, and `structured=true`.
No UE asset was changed or saved.

The Gateway follow-up passed a fresh daemon start/identity/ping/shutdown cycle on 18765 and a
three-entry live schema-cache check (full, summary, single-tool) with distinct keys.
