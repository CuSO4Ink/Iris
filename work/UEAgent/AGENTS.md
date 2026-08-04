# UEAgent agent entry

UEAgent is the mandatory gate for AI work that depends on live Unreal Editor state.
This file is navigation only; detailed rules live in the hot path and the workflow Skill.

## Standard UE project brief block

Every UE project's `AI-BRIEF.md` starts with `<!-- iris-project-kind: ue -->` and a link to
this entry plus `skills/ue-mcp-workflows/HOTPATH.md`:

> **UEAgent first.** Read the route, run `compact_context.ps1`, and stop on `CACHE_READ`.
> On `NEEDS_DOCTOR`, run `doctor.ps1` once before the first live call. Repair `BLOCKED`.
> Offline source/cache/config/log analysis may skip MCP but must not claim live UE state.

## Entry order

1. Read `skills/ue-mcp-workflows/HOTPATH.md` and `<project>/Saved/UEAgent/route.json`.
2. Run `scripts/compact_context.ps1` for the asset and operation.
3. `CACHE_READ`: read the sidecar and do not call MCP. `NEEDS_DOCTOR`: run `doctor.ps1` once
   and use that receipt directly; do not run a second compact pass for the same task.
4. `LIVE_READ`: load one domain card. Mutation/save: also load the Skill, Core, and target brief.
5. Continue only on the route/receipt's authority; verify independently and save explicitly.

## Transport and safety

- `CACHE_READ` uses no transport. Live calls use `scripts/mcp_gateway.ps1`; `-AutoDaemon` is
  for repeated calls. Native/platform MCP is a fallback only when the receipt is healthy and
  Gateway fails before the operation or lacks a needed client feature.
- A possible mutation timeout is `RESULT_UNKNOWN`: read back before retrying or switching transport.
- One writer per UE object. Discover tools, properties, and pins before writing. Save/delete/
  move/merge/Undo/Redo/level commit are separate explicit boundaries.
- Do not use Computer Use to drive Unreal UI. Stop and give the user manual steps when UI or
  visual approval is required.

## On-demand references

Read `SETUP.md` only for install/recovery, `projects/ReflectCache/AI-BRIEF.md` for cache
implementation, `PROGRESSIVE-DISCLOSURE.md` for full measurements/rollback, and `BACKLOG.md`,
`LOG.md`, or `notes/mcp-pitfalls.md` only for maintenance or incident analysis.
