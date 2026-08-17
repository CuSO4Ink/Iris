---
name: ue-mcp-workflows
description: Safe, cache-first Unreal Engine 5.8 MCP workflow with bounded discovery/results, one-writer mutations, independent readback, and explicit save boundaries.
---

# UE MCP workflows

Read [HOTPATH.md](HOTPATH.md) first. It is the only default route. This Skill adds live operation
rules; it does not replace the route or create a second project gate. The complete contract and
rollback map is [PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

## Gate and transport

1. Locate the target `Saved/UEAgent/route.json` and run `compact_context.ps1`; load route or wrapper
   contents only to diagnose a failure.
2. `CACHE_READ` means read the recognized sidecar and stop before MCP.
3. `NEEDS_DOCTOR` means run `doctor.ps1` once and use that receipt directly.
4. Reuse a receipt while Editor PID/epoch and plugin fingerprint match. MCP sessions are disposable;
   schema-cache entries remain scoped to the current session. Restart, ambiguous transport failure,
   explicit close, plugin reload, or toolset change invalidates the relevant state. If identity
   cannot be checked, discard the receipt.
5. `HEALTHY` permits proven live reads and task-gated mutation; `DEGRADED` permits cache plus
   proven reads; `OFFLINE` is local analysis; `BLOCKED` requires repair. A mutation timeout is
   `RESULT_UNKNOWN`; read back before retrying.

Gateway (`../../scripts/mcp_gateway.ps1`) is the only AI-facing live client; `-AutoDaemon` is a
repeated-call optimization on that same path. Native MCP is the server behind Gateway, not another
client route. If Gateway and the fixed `ueagent_*` surface cannot express the operation, add the
missing typed operation or stop. Never bypass the canonical path.

For AI-generated calls crossing a child `powershell.exe` boundary, serialize the complete request
object with `ConvertTo-Json` and use UTF-8 `-RequestBase64`; use `-RequestFile` for large or
multiline requests and `-ScriptFile` only for actions that support it. Never hand-escape raw JSON
into `-RequestJson`, `-ArgumentsJson`, or `-ProjectionJson`. A local parse failure before dispatch
is known not to have reached UE and is not `RESULT_UNKNOWN`.

Pass `-SchemaCacheFile <project>\Saved\UEAgent\schema-cache.json` for discovery and, for repeated
Gateway calls, project-local `mcp-session.json` with `-SessionFile ...`; reuse is automatic. Use
`-CloseSession` only for explicit shutdown. Cache discovery only; never cache calls or mutations.
Machine files remain uncommitted.

## Minimize discovery and payload

- Known domain/tool: skip `toolsets.list`; describe one tool with `detail=call`.
- Unknown entry: use the cacheable `toolsets.list` result, then authoritative `describe_toolset`.
- `detail=summary` is for names/descriptions. `detail=full` is only for exact JSON Schema
  validation or recovery.
- Known calls expose only tool, non-empty arguments, and an optional toolset/projection profile;
  Gateway infers the mechanical action, response mode, session route, and structured-only result.
- Use `-ProjectionProfile identity|topology|logic|runtime|hlsl|changed` (domain aliases accepted).
  Choose one view; HLSL/script is explicit and never silently truncated.
- Default model output is sparse but semantic: standard envelopes, positive success flags, empty
  reliable fields, derived success, timings, and nested JSON escaping are removed. Reliable
  identity/outcome/hash/save/error fields are never removed. Use `-Diagnostics` only for a scoped
  transport incident; do not expose raw transport envelopes during ordinary work.
- Cache views expand `summary -> refs -> detail -> full`; functions/scripts remain references to
  independent caches and are never inlined.

## Load only the needed rules

For `LIVE_READ`, load one domain card after the receipt. For mutation/save or an unfamiliar/high-
risk capability, also load `references/core.md` and the target project brief:

- Material, MaterialFunction, MaterialInstance, Custom HLSL: `references/materials.md`
- Blueprint: `references/blueprints.md`
- Niagara: `references/niagara.md`
- Actor/component/level/lighting/viewport: `references/scene-editing.md`
- Cache implementation/freshness/save hooks: `../../projects/ReflectCache/AI-BRIEF.md`

Do not load the full ReflectCache protocol for an ordinary read.

## Execute safely

1. Try `<Asset>.uasset.ai.md` first for saved-state reads; stop if current and sufficient.
2. Read the target brief/task after the route is known.
3. Discover exact tools, UObject properties, object paths, and graph pins; never guess.
4. Classify read, reversible mutation, or high-risk save/delete/move/merge.
5. For hash-guarded mutations, require one named asset version and a complete manifest derived from
   that version; never combine historical baselines. Resolve any mismatch before the first setter.
6. Probe unverified capabilities outside production assets.
7. Apply one logical mutation with one writer. Batch only a known-safe call shape.
8. Verify independently through targeted readback, compile/log/invariant/runtime evidence.
9. Clean probes (`exists=false`) and save only inside the user's explicit boundary.

## Evidence and UI

Record friction in `../../notes/mcp-pitfalls.md` as Verified, Observed, or Hypothesis with
provenance; promote only after controlled verification. Structural evidence belongs to AI and
visual/aesthetic approval to the user. Never use Computer Use to drive Unreal UI; provide manual
steps when an editor gesture or visual decision is required.
