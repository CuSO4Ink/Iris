# UEAgent agent entry

UEAgent is the mandatory gate for AI work that depends on live Unreal Editor state.
This file is navigation only; detailed rules live in the hot path and the workflow Skill.

## Standard UE project brief block

Every UE project's `AI-BRIEF.md` starts with `<!-- iris-project-kind: ue -->` and a link to
this entry plus `skills/ue-mcp-workflows/HOTPATH.md`:

> **UEAgent first.** Locate the route, run `compact_context.ps1`, and stop on `CACHE_READ`.
> On `NEEDS_DOCTOR`, run `doctor.ps1` once before the first live call. Repair `BLOCKED`.
> Offline source/cache/config/log analysis may skip MCP but must not claim live UE state.
> Encode complete Gateway requests as UTF-8 Base64 (or use a request file); never pass raw JSON
> across a child PowerShell boundary. Mutation hash guards use one named asset-version manifest.

## Entry order

1. Read `skills/ue-mcp-workflows/HOTPATH.md` and locate `<project>/Saved/UEAgent/route.json`.
2. Run `scripts/compact_context.ps1` for the asset and operation; load route/script contents only
   when diagnosing their failure.
3. `CACHE_READ`: read the sidecar and do not call MCP. `NEEDS_DOCTOR`: run `doctor.ps1` once
   and use that receipt directly; do not run a second compact pass for the same task.
4. `LIVE_READ`: load one domain card. Reliable mutation/save: also load the Skill, Core, and target brief.
5. Snapshot -> submit -> terminal receipt -> independent snapshot. Save only with the receipt's
   exact one-use capability.

## Transport and safety

- For every AI-generated Gateway call crossing a `powershell.exe` boundary, build the complete
  request as an object, serialize it with `ConvertTo-Json`, and pass UTF-8 `-RequestBase64`.
  Use `-RequestFile` for large or multiline content and `-ScriptFile` only for actions that support
  it. Never hand-escape or pass raw JSON through `-RequestJson`, `-ArgumentsJson`, or
  `-ProjectionJson` to child PowerShell.
- Treat local parameter/JSON parse errors as known pre-dispatch failures, not `RESULT_UNKNOWN`.
  Do not claim UE was contacted or retry a mutation after such a failure.
- `CACHE_READ` uses no transport. Live calls use `scripts/mcp_gateway.ps1`; `-AutoDaemon` is
  only a repeated-call optimization. Gateway is the sole AI-facing live client; native MCP is the
  server it reaches, not an alternate client route. If the canonical typed surface cannot express
  the operation, stop at `BLOCKED` and add that operation or request the exact user step.
- A possible mutation timeout keeps its command identity and lease: poll, recover if needed, then
  read back before retrying.
- Hash-guarded mutations must use a complete expected-hash manifest from one named asset version.
  Never mix historical baselines; resolve a mismatch against versioned source/history before the
  first mutation instead of trusting the current live value.
- The Editor kernel is the single writer. Direct/Python mutations are denied. Discover tools,
  properties, pins, and OCC snapshots before queueing; save is a separate capability boundary.
- Do not use Computer Use to drive Unreal UI. Stop and give the user manual steps when UI or
  visual approval is required.

## On-demand references

Read `SETUP.md` only for install/recovery, `projects/ReflectCache/AI-BRIEF.md` for cache
implementation, `PROGRESSIVE-DISCLOSURE.md` for full measurements/rollback, and `BACKLOG.md`,
`LOG.md`, or `notes/mcp-pitfalls.md` only for maintenance or incident analysis.
