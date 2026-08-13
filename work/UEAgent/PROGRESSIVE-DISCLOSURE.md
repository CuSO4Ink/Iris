# UEAgent progressive disclosure contract

This is the canonical record for the token-reduction route. It is an operational contract, not
an additional MCP server or a second project gate.

## One route

```text
route.json
  -> compact_context.ps1 -View compact
  -> CACHE_READ: read sidecar
  -> NEEDS_DOCTOR: doctor.ps1 once, then use its receipt directly
  -> LIVE_READ / LIVE_MUTATE_RELIABLE_QUEUE from that receipt
  -> live client: Gateway (-AutoDaemon only for repeated calls on the same path)
     -> native MCP server -> fixed ueagent_* surface
  -> describe one known tool detail=call (structured-only)
  -> summary / one-tool call view only when routing needs it
  -> targeted read projection, or snapshot -> ueagent_submit -> receipt
  -> detail only for the missing block
  -> full only when explicitly justified
```

The target project still enters through `work/UEAgent/AGENTS.md` and
`skills/ue-mcp-workflows/HOTPATH.md`. `compact_context` is a router, not evidence of live UE
state. Doctor has one RouteFile-based live profile; use `bootstrap -CheckOnly` for offline setup
validation. Gateway is the only AI-facing client; native MCP is its server, not an alternate client
route. If Gateway or the fixed `ueagent_*` surface cannot express an operation, extend that
canonical typed surface or stop at `BLOCKED`. A mutation timeout keeps its command identity: poll
its receipt, recover an older-epoch journal if needed, then read back before any replay.

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
Model-facing calls expose only tool, non-empty arguments, and an optional toolset/projection
profile. Gateway infers direct/registry/describe routing, structured-only transport, and data-only
output after binding endpoint/session/cache from `-RouteFile` or the target project's current
directory. The result removes standard envelopes, duplicate text, positive success flags, lone
`returnValue`, empty/derived reliable fields, timings, fixed-state diagnostics, and nested JSON
escaping. Semantic values and every reliable identity/outcome/hash/save/error field remain. Use
`-Diagnostics` only for a scoped transport incident; ordinary model-facing calls never request raw
envelopes.
Pass `-View summary|refs`, a projection profile, or an explicit projection when a live call
needs the same bounds. Profiles are `identity`, `topology`, `logic`, `runtime`, `hlsl`, and
`changed`; domain aliases (`material.topology`, `blueprint.logic`, `niagara.runtime`) are accepted.
Errors retain a compact envelope; raw server payloads require diagnostics.

For live MCP, use the same idea:

```powershell
# names/descriptions only when the domain is unknown; the result may come from Schema Cache
powershell -File .\scripts\mcp_gateway.ps1 -Action toolsets.list

# compact call view is the default; this does not return JSON Schema
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset>

# names/descriptions only, when routing needs a readable list
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> -DescribeDetail summary

# one exact compact callable shape
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> -DescribeToolName <tool>

# complete schema only for validation or recovery
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> `
  -DescribeDetail full -DescribeToolName <tool>

# shape only the fields required by an explicitly allow-listed read
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> `
  -Tool <tool> -ProjectionProfile refs

# domain-scoped live views; choose one, never request the whole graph by default
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> `
  -Tool <tool> -ProjectionProfile material.topology
powershell -File .\scripts\mcp_gateway.ps1 -Toolset <toolset> `
  -Tool <tool> -ProjectionProfile niagara.runtime
```

`tool.call` is limited to the reviewed read-only allow-list; the Gateway exposes no script or
Python execution action. Mutations use `ueagent_submit` after an authoritative snapshot, and
large results are externalized instead of expanded into the progressive-disclosure view.

`toolsets.list` is a routing catalog, not an authoritative schema. When a domain card already
names the candidate toolset/tool, skip it and request one `describe_toolset` with
the selected `tool_name`. Tool names and arguments still come from the running response. An
explicit projection overrides a preset. Gateway requests structured results and removes duplicate
text before model exposure; HLSL/code strings are not silently shortened.

The `call` view is the lowest-cost authoritative discovery response. A single-tool result is one
object (`tool`, `effect`, `args`, `returns`), not `tools:[...]`; an all-tool call view uses one
`tools` array because there is no selected tool. Required arguments carry `!`; UE object schemas
become `ue_ref<Class>` and unions remain `|`-joined. `effect` is a conservative server heuristic
and may be `unknown`; never treat it as permission. `full` remains the only source for exact JSON
Schema validation. Gateway/daemon require the native call-view response and do not reconstruct it
client-side. Doctor checks the running `describe_toolset.detail` enum before granting a live route.

Successful doctor receipts are editor-bound. `compact_context.ps1` reuses them while the stored
Editor PID from `ueagent_state`, loaded project binary fingerprint, and reliable kernel epoch remain
unchanged. If that identity cannot be checked, discard the receipt. MCP session IDs are disposable
client leases and do not invalidate an otherwise current editor receipt.
Gateway/daemon ambiguous transport failures write a small invalidation marker beside the receipt;
editor restart, explicit close, plugin rebuild/reload, and a changed fingerprint require a new
doctor. Normal session replacement invalidates its discovery/schema cache, not the matching editor
receipt. A `NEEDS_DOCTOR` result is
terminal for that routing pass: run doctor once and do not rerun compact_context merely to
recompute the same state.

## Freshness and lifecycle

The sidecar is saved-state context. `.uasset` remains the only truth, and dirty editor memory is
always a live query. The cheap freshness test is source/sidecar mtime plus the declared source
size; the reader also rejects unsupported cache formats. `graph_sha1` remains in compact views;
sidecar `sha256` is computed only for explicit `full` or reconcile. Both are provenance, not
permission to skip a required live check.

Run lifecycle maintenance after a Content Browser rename/delete or a cache generator/plugin
change:

```powershell
powershell -File .\scripts\reflect_cache.ps1 -Action reconcile `
  -RouteFile <project>\Saved\UEAgent\route.json -Repair
```

The reconciler records a manifest, rehomes only a unique source-hash match, and quarantines
unresolved sidecars under `Saved\UEAgent\cache-orphans`; it never deletes them. A sidecar remains
saved-state context even when its lifecycle metadata is current; unsaved Editor memory always
requires live MCP.

Use ordinary source-control or text diff tools when two saved sidecars must be compared. Cache
differences never replace the reliable command receipt or independent live readback.

## Measurement

Recorded `M_Wave_Base.uasset.ai.md` measurement (2026-08-02): summary 779 bytes/195 estimated
tokens, refs 1,224/306, detail 8,423/2,106, full 15,785/3,947. The first two views therefore
remove about 92–95% of this saved-state payload; the exact ratio changes with the asset.

## Current optimizations

| Concern | Current contract |
|---|---|
| context route | compact result first; expand only the missing block |
| live identity | exact Editor PID/epoch/fingerprint match; unverifiable identity is invalid |
| doctor handoff | run once on `NEEDS_DOCTOR` and use that receipt directly |
| discovery | one known-tool call view; full schema only for validation or recovery |
| saved-state reads | current Reflect Cache first; live state always requires authoritative read |
| model response | bounded structured data without duplicate transport envelopes |
| live client | Gateway only; `-AutoDaemon` keeps the same path warm |
| mutation | fixed `ueagent_*` surface, one queued writer, receipt, independent readback |
| cache lifecycle | reconcile after rename/delete/generator change |
| documentation | navigation entry plus only the task-relevant contract and domain card |

These are one current contract, not selectable modes. A replacement updates every active caller,
test, and document and deletes the superseded path in the same change. Rollback reverts the whole
change to a verified state; it never restores two supported runtime paths.

Gateway correctness guards are part of the contract: `mcp_gateway.ps1` is UTF-8 with BOM for
Windows PowerShell 5.1, and schema cache keys include `DescribeDetail`, `DescribeToolName`, and
the active MCP session ID. Replacing any of these requires an atomic cutover and repetition of the
PowerShell 5.1 parse and cache-key collision checks.

The UE source projection/catalog patch is independently reversible as
`patches/ue58-mcp-tool-search.patch` (`git apply -R` after a clean checkpoint). Do not reset the
dirty Iris or VibeUE worktrees to roll back this table; revert only the named change.

## Verification record

Every implementation change in this phase was checked with PowerShell AST parsing. Offline smoke
checks must cover `reflect_cache` summary/refs/detail/full/reconcile and
`compact_context -View compact`; live checks use the single Doctor profile.

Live MCP checks are separate: run the live doctor after the editor is up, then verify one shaped
read and one mutation readback. If UE is offline or crashed, report that state; do not substitute
static checks for a live claim.

This phase's live read passed on the available editor: live doctor `HEALTHY` (UE 5.8.0, ten
top-level tools), followed by a data-only `RequestBase64` call returning three exact
`M_Wave_Base` refs with `fields=[returnValue.refPath]`, `max_items=3`, and `structured=true`.
No UE asset was changed or saved.

The UE 5.8.1 upgrade was then verified against official commit
`71fe36aac5a8df5ccd66c763ffc902b29b6a9c43`: the full 3,794-action `AbyssEditor` build and
`VibeUE.UEAgentReliable.CanonicalJson` automation passed. Live doctor returned `HEALTHY` with
ToolSearch, VibeUE, the reliable kernel, and Niagara authoring available. An ordinary native
`tools/call` returned `application/json`; a no-write queued command passed receipt, replay,
snapshot/OCC, and direct-mutation rejection checks with zero dirty or saved packages.

The Gateway follow-up passed a fresh daemon start/identity/ping/shutdown cycle on 18765 and a
three-entry live schema-cache check (full, summary, single-tool) with distinct keys.

The projection/lifecycle follow-up passed PowerShell 5.1 AST parsing for all seven scripts. Profile
probes resolved `material.topology`, `blueprint.logic`, and `niagara.changed-readback` to bounded
structured projections. An isolated fixture proved the reconciler's unique source-hash rename
repair and orphan quarantine; it moved no real Abyss asset. A read-only Abyss audit found 27
sidecars: 21 fresh, 3 stale, and 3 orphaned; no repair was run against the user project.

The context-entry follow-up reduced the four UEAgent entry files to about 3.4k estimated tokens
when all four are needed, and reduced ordinary navigation (`AGENTS.md` + `HOTPATH.md`) to about
1.3k. These are stable `bytes/4` comparisons, not model-token counts. The same seven-script AST
check and an Abyss `M_Wave_Base` `CACHE_READ` route passed after the documentation-only change.
