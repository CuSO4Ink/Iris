---
name: ue-mcp-workflows
description: Safe, cache-first Unreal Engine 5.8 MCP workflow with bounded discovery/results, one-writer mutations, independent readback, and explicit save boundaries.
---

# UE MCP workflows

Read [HOTPATH.md](HOTPATH.md) first. It is the only default route. This Skill adds live operation
rules; it does not replace the route or create a second project gate. The complete contract and
rollback map is [PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

## Gate and transport

1. Read the target `Saved/UEAgent/route.json` and run `compact_context.ps1`.
2. `CACHE_READ` means read the recognized sidecar and stop before MCP.
3. `NEEDS_DOCTOR` means run `doctor.ps1` once and use that receipt directly.
4. Reuse a receipt/schema cache only while Editor PID, MCP session, and plugin fingerprint match.
   Restart, reconnect, timeout, transport failure, explicit close, plugin reload, or toolset change
   invalidates them. TTL is fallback only.
5. `HEALTHY` permits proven live reads and task-gated mutation; `DEGRADED` permits cache plus
   proven reads; `OFFLINE` is local analysis; `BLOCKED` requires repair. A mutation timeout is
   `RESULT_UNKNOWN`; read back before retrying.

Gateway (`../../scripts/mcp_gateway.ps1`) is the default live transport; `-AutoDaemon` is for
repeated calls. Native/platform MCP is a fallback only when the receipt is healthy and Gateway
fails before the operation or lacks a required client feature. A trusted native client may bypass
Gateway for ordinary calls when no projection/session/debug shaping is needed. Neither transport
bypasses authority, one-writer, or readback rules.

Pass `-SchemaCacheFile <project>\Saved\UEAgent\schema-cache.json` for discovery and, for repeated
Gateway calls, project-local `mcp-session.json` with `-SessionFile ... -ReuseSession`; use
`-CloseSession` only for explicit shutdown. Cache discovery only; never cache calls or mutations.
Machine files remain uncommitted.

## Minimize discovery and payload

- Known domain/tool: skip `intent.list` and `toolsets.list`; describe one tool with `detail=call`.
- Unknown entry: use `intent.list` only for routing, then authoritative `describe_toolset`.
- `detail=summary` is for names/descriptions. `detail=full` is only for exact JSON Schema
  validation or recovery.
- Use `-ProjectionProfile identity|topology|logic|runtime|hlsl|changed` (domain aliases accepted).
  Choose one view; HLSL/script is explicit and never silently truncated.
- Prefer structured/data-only success. `-Envelope` is legacy compatibility; `-Diagnostics` is
  transport/session debugging. Do not request full graphs, images/base64, recursive dependencies,
  or duplicate text plus structured data by default.
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
5. Probe unverified capabilities outside production assets.
6. Apply one logical mutation with one writer. Batch only a known-safe call shape.
7. Verify independently through targeted readback, compile/log/invariant/runtime evidence.
8. Clean probes (`exists=false`) and save only inside the user's explicit boundary.

## Evidence and UI

Record friction in `../../notes/mcp-pitfalls.md` as Verified, Observed, or Hypothesis with
provenance; promote only after controlled verification. Structural evidence belongs to AI and
visual/aesthetic approval to the user. Never use Computer Use to drive Unreal UI; provide manual
steps when an editor gesture or visual decision is required.

Bundled probes: `scripts/probe_custom_inputs.py` and `../../bp_clipboard_to_ai.py`.
