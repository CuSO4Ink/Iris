# Progressive disclosure implementation ledger (2026-08-02)

> Historical record: `progressive_audit.ps1` and the local `intent.list` index were retired on
> 2026-08-12; the measurements below remain evidence for the surviving compact views.

This phase implements the remaining high-value token reductions in the smallest additive form.
The canonical operating contract is `../PROGRESSIVE-DISCLOSURE.md`.

## Delivered

1. `compact_context.ps1` has `compact|detail` views. Compact is the default and carries only
   the next route, endpoint/project, receipt state, and sidecar identity/freshness facts.
2. `reflect_cache.ps1` has four read views: `summary`, direct `refs`, bounded named `detail`, and
   explicit `full`. It also has bounded `index`, `diff`, and `receipt` actions.
3. `progressive_audit.ps1` measures every view in bytes and a stable bytes/4 token estimate.
4. Gateway `intent.list` gives a local domain/intention index; unknown tools return
   `via=describe_toolset` instead of a fake callable name. The live schema remains the source of
   truth. Gateway `view=summary|refs` maps to existing compact projections without changing the
   default response contract.
5. HOTPATH, Skill, UEAgent brief, setup, and ReflectCache docs now point to one route and state
   the cache-first/intent/schema/projection order.

## Why these boundaries

- A cache read can answer saved-state questions without MCP, but it cannot answer dirty editor
  memory or prove a live mutation.
- Direct dependencies are enough for routing; recursive expansion would recreate the graph walk
  and inflate context. Each referenced asset owns an independent cache.
- A receipt summarizes a saved cache delta; it intentionally does not pretend to be an independent
  readback. Mutation still requires one writer, save authority, then a live readback.
- Full graph/HLSL remains available because truncating logic silently is unsafe. The caller must
  request it explicitly.

## Rollback map

| Item | Fallback |
|---|---|
| compact context | add `-View detail`; the old full object is still produced by that view |
| cache reader/audit | skip the scripts and use the sidecar/MCP SOP; they are offline/additive |
| intent index | skip `intent.list`; use normal schema discovery |
| Gateway projections | omit `-View`, `-ProjectionProfile`, and `-DataOnly` |
| schema/result server patch | reverse only `patches/ue58-mcp-tool-search-v2.patch` after a clean checkpoint |
| session/daemon | omit session/daemon flags or send daemon `shutdown`; native MCP is unchanged |

Never reset the dirty Iris, UE, or VibeUE worktrees as a rollback method.

## Verification

PowerShell AST parsing returned zero errors for `reflect_cache.ps1`, `progressive_audit.ps1`,
`compact_context.ps1`, `mcp_gateway.ps1`, `mcp_gateway_daemon.ps1`, and `doctor.ps1`. The offline
smoke matrix is intentionally runnable with UE closed: `intent.list`, cache views/index/diff/
receipt, audit, compact context, and quick doctor. Live calls must be rerun only after the user
starts a healthy editor and the live doctor passes.

Real Wave sidecar audit: summary 779 bytes/195 estimated tokens, refs 1,224/306, detail
8,423/2,106, full 15,785/3,947. These are bytes/4 comparisons, not tokenizer claims.

Live gate after the editor became available: `doctor -Profile live -View compact` returned
`HEALTHY`, UE 5.8.0, endpoint 8000, ten top-level tools. A `RequestBase64` gateway call then
returned exactly three `M_Wave_Base` expression refs through `fields=[returnValue.refPath],
max_items=3, structured=true, dataOnly=true`. No asset mutation or save occurred. Nested JSON
should use `-RequestBase64`/`-RequestFile` when the caller's shell would alter dotted fields.

## Gateway correctness follow-up

- `mcp_gateway.ps1` is now UTF-8 with BOM. Windows PowerShell 5.1 therefore decodes any
  non-ASCII diagnostic text consistently instead of parsing the no-BOM file as ANSI.
- Schema cache keys now include endpoint, action, toolset, `DescribeDetail`, and
  `DescribeToolName`. A full toolset schema, summary schema, and single-tool schema cannot reuse
  one another's entry. Cache entries retain `detail` and `toolName` for inspection.

Verification: PowerShell 5.1 executed `intent.list` successfully; direct key probes reported
distinct keys for full vs summary and full vs single-tool; AST parsing still reports zero errors.
Fresh daemon regression also passed: a new 18765 process answered the identity probe, daemon
`ping` returned ten top-level tools, Gateway forwarding returned the same health result, and
`shutdown` released the port. Three live Material schema requests produced three cache entries
with selectors `detail=`, `detail=summary`, and `tool=get_expressions`; no key was reused.

## Call-view follow-up

The remaining schema payload was still dominated by repeated toolset metadata, descriptions,
JSON-Schema wrappers, and JSON-in-text escaping. The additive v3 source patch
`patches/ue58-mcp-tool-search-v3-call-view.patch` now adds `detail=call`:

- one selected tool returns one structured-only object with `tool`, `effect`, `args`, and `returns`;
- a required argument keeps `!`, UE reference titles become `ue_ref<Class>`, and simple unions are
  preserved with `|`;
- `effect` is conservative (`read`, `write`, `save`, or `unknown`) and is routing metadata, not
  mutation authorization;
- `detail=full` remains the exact-schema validation path; `summary` remains the cheap readable list.

Gateway and daemon now send `detail=call` when `toolset.describe` has no explicit detail. They
also accept the shorter request keys `detail` and `toolName`. The Gateway schema cache sees the
effective `call` selector because defaulting happens before cache lookup, so old empty-detail
entries are safely missed rather than reused.

Before the 2026-08-03 rebuild, both paths detected the v2 error (`detail must be 'summary' or
'full'`) and retried once: an all-tool request fell back to `summary`, while a selected tool fell
back to `full`. This compatibility remains for older binaries without pretending that their
result is the compact call view.

Static checks passed: v3 reverse patch check, PowerShell AST parse for Gateway and daemon, and
`git diff --check`. Runtime proof completed on 2026-08-03 after a clean `Build.bat AbyssEditor
... -WaitMutex` rebuild and editor restart: raw MCP `detail=call` returned structured-only data,
and the selected `get_expressions` result classified as `read`. Rollback is `git apply -R` v3,
then v2, after a clean checkpoint, or per-call `-DescribeDetail full` while v3 is installed.

## Session/receipt and payload follow-up

The next pass keeps the existing files and route contract, rather than adding another cache:

- `doctor.ps1` records the endpoint listener PID, the project MCP session ID, and a fingerprint of
  the loaded MCP/VibeUE/Niagara plugin binaries. `compact_context.ps1` reuses a healthy receipt
  while those identities remain valid; the 300-second age is only a fallback when identity cannot
  be checked. The compact doctor view includes this small identity tuple so a persisted
  `doctor.json` remains useful without saving the full diagnostic receipt.
- Gateway and daemon write `Saved/UEAgent/doctor.invalidate.json` on transport/timeout errors or
  explicit close and discard the stale session record. A stale identity or marker yields
  `NEEDS_DOCTOR`, so the caller does not run a second compact pass after doctor.
- A successful reused-session `tools/list` probe is passed directly to `preflight`, `ping`, or
  `tools.list`; no second identical MCP request is issued.
- Schema cache keys now include the active MCP session ID. A new session keeps only live entries
  for that session, while direct no-session callers retain TTL behavior.
- Gateway normalisation prefers `structuredContent` even when legacy text is also present. Normal
  successful replies omit transport/session diagnostics unless `-Diagnostics` is requested;
  `-Envelope` restores compatibility for scripts, while `preflight` remains envelope-first for
  doctor.
- Known domain cards now skip local `intent.list` and `toolsets.list` when the candidate tool is
  already named. The hot path also asks for one logical mutation and a changed-region readback.

Offline checks for this pass: all six PowerShell scripts parse; a synthetic schema-cache probe
returned a hit for `session=sid-1` and a miss for `session=sid-2`; a synthetic MCP result containing
both `structuredContent` and duplicate text normalized to structured data only; compact context
returned `NEEDS_DOCTOR` for a non-cached asset with the invalidation marker present. Live Abyss
verification then measured a 4.6-4.7 s reused doctor, 0.41-0.55 s compact route, and 0.55-0.78 s
warm-daemon read in ten read-only cycles (10.906 s total). An artificially two-hour-old receipt
remained `FRESH` while PID/session/plugin identity was unchanged. The running editor rejected
`detail=call`, so Gateway/daemon now fetch `full` once and locally project the compact call view;
live selected-tool output was 291 bytes in the compact envelope versus 1,261 bytes for `full`.
The daemon also writes the existing session-scoped schema cache, and repeated live discovery hit
that cache without another MCP call. Model-facing success responses are data-only by default;
`-Envelope` preserves the old wrapper and `-Diagnostics` exposes transport/raw details. The
Verbose `Available toolsets:` error tails are now omitted by default and residual tool errors are
capped at 768 characters; diagnostics still exposes the raw MCP response. The
daemon retains the session probe's `tools/list` for the current session and clears it on session
rebuild/error, so repeated `ping`/`tools.list` calls do not rediscover the same tool table.
transport policy remains Gateway-default with a documented native-MCP performance override,
because making native MCP globally primary would reverse the previously recorded portability
decision.

Final live regression (2026-08-02): routed `compact_context` returned `LIVE_READ`/`FRESH`, and
`doctor -Profile live` returned `HEALTHY` for Abyss PID 53448. Default `ping`/`level.current`
were 41/46 chars; `-Envelope` and `-Diagnostics` remained compatible. With the old v2 editor,
selected Material call view was 291 bytes versus 1,261 bytes for `full`; call/full/call cache
isolation returned 291/1,261/290 bytes. A temporary AutoDaemon run produced 2.88 s cold,
1.27 s warm diagnostic, and 0.55 s raw-data ping; a second temporary daemon schema request hit
the existing session-scoped cache in 402 ms. All temporary daemons were shut down and no UE
asset was modified or saved.

The v3 rebuild was subsequently loaded on 2026-08-03. After dismissing Unreal's `Restore Packages`
prompt with `Skip Restore`, live doctor returned `HEALTHY`. A raw `detail=call` request returned
only `structuredContent` (no duplicate text part), and `get_expressions` reported `effect=read`.
The classifier fix strips the full toolset prefix before applying the read/write heuristic.
The resulting HEALTHY doctor output was written to the project receipt file; the next compact
route returned `LIVE_READ`/`FRESH`.

### Before/after route record

| Path | Before | After |
|---|---|---|
| stale non-cache task | `compact -> BLOCKED -> doctor -> compact -> live` | `compact -> NEEDS_DOCTOR -> doctor -> live` |
| reused-session preflight | session probe `tools/list` + preflight `tools/list` | one probe result feeds preflight |
| repeated schema discovery | TTL-only entry could cross editor sessions | active MCP session ID scopes the entry |
| normal Gateway success | `ok/action/data/transport` plus possible text+structured duplicate | `ok/action/data`; structured data wins; diagnostics are explicit |
| known domain discovery | optional `intent.list -> toolsets.list -> describe` | selected-tool `describe` directly |
| post-mutation verification | whole graph/system was easy to request | changed region plus compile/dirty invariant is the SOP |
