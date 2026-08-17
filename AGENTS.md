# Iris agent bootstrap

This file is the single AI bootstrap for the Iris workspace. Use the repository root as truth.

## Always on

- End every natural-language response with `唔呣。` on its own final line. Tool-only, pure-code,
  and pure-data responses are exempt.
- New file and directory names use English only; details are in `rules/naming.md`.
- Unreal Engine source branches created by the agent use the exact `Aether/` prefix unless the
  user specifies a different branch name.
- Preserve unrelated dirty work. Do not read `USAGE.ankoha.md` unless the user explicitly asks.

## Route by task

- Slash command: read `rules/commands.md` and execute the registered flow.
- Workspace governance: read `rules/maintainer/README.md` and its required references.
- Project work: read `notes/project-progress-methodology.md`, then `work/<project>/AI-BRIEF.md`
  and the task-related part of `BACKLOG.md`. Read `LOG.md` only when history is needed.
- General work: use `rules/README.md` and the root `README.md` as navigation.

Disposable environments, generated evidence, screenshots, runs, and one-off scripts belong under
`tmp/<project-or-task>/`, not in `work/`. `/checkpoint` flushes verified session progress into every
project touched; it does not commit, archive, or clean files.

For implementation and architecture decisions, prioritize the smallest working end-to-end feature
and forward progress. Add special controls only for concrete failures that could cause severe,
hard-to-recover harm; otherwise fix observed or reproducible bugs at the root cause. Keep one
current path, reuse existing foundations, and delete superseded paths in the same cutover. The
methodology is the full authority for these choices.

# Unreal live-work gate

## UE-related project brief rule

When creating or activating a UE-related project under Iris, its `AI-BRIEF.md` must put the
standard **UEAgent first** navigation block at the top, before project-specific execution
instructions. The block must link to `work/UEAgent/AGENTS.md` and the UEAgent hot path, and must
state the `route.json` -> `compact_context.ps1` -> `doctor.ps1` order plus the offline-analysis
exception. A project brief is read for task context only after the connection state is known.
The canonical `work/UEAgent/AI-BRIEF.md` is the gate source itself and is exempt from this
consumer-project marker.

Use `/project-init <项目名> --ue` as the canonical creation path. It marks the brief with
`<!-- iris-project-kind: ue -->` and inserts that navigation block; do not infer the UE marker
from the project name.

Do not create a second project-specific MCP gate or claim a route for a target that has not been
bootstrapped. If a UE-related project is offline-only or uses a different MCP (for example
RenderDoc), the block may be conditional, but any live Unreal work still enters through UEAgent.

## UE pre-dispatch invariants

These rules apply before any UEAgent Gateway request, including read-only calls:

- AI-generated Gateway requests that cross a `powershell.exe` process boundary must encode the
  complete UTF-8 JSON request with `-RequestBase64`, or use `-RequestFile` for large/multiline
  payloads. Never pass raw JSON through `-RequestJson`, `-ArgumentsJson`, or `-ProjectionJson` to a
  child PowerShell process. Use `-ScriptFile` only for Gateway actions that support script files;
  otherwise keep code such as Custom HLSL inside the encoded request. Build JSON from objects with
  `ConvertTo-Json`; do not hand-escape it.
- A local parameter/JSON parse failure before MCP dispatch is a known pre-dispatch failure: do not
  describe it as `RESULT_UNKNOWN`, do not claim UE was contacted, and do not retry a mutation.
- Any mutation preflight that locks HLSL/pass hashes must use one named asset version and one
  complete manifest generated from that version. Never mix hashes from historical baselines. On a
  mismatch, stop before the first mutation and verify against versioned source/history; do not
  accept the live hash merely because it is current.

For any task that reads live Unreal state or mutates a UE project:

1. Read `work/UEAgent/skills/ue-mcp-workflows/HOTPATH.md`.
2. Locate the target project's `Saved/UEAgent/route.json` and pass that path to
   `work/UEAgent/scripts/compact_context.ps1`; read the route or wrapper source only to diagnose
   a route/script failure.
3. On `CACHE_READ`, stop before MCP. On `NEEDS_DOCTOR`, run the routed `scripts/doctor.ps1` once
   and use its receipt directly. A `BLOCKED` result requires route repair. For `LIVE_READ`, load
   only the relevant domain card; add `AI-BRIEF.md`, the workflow Skill, and Core for mutation/save.
4. Follow the receipt and the relevant domain SOP. Cache/source/config/log analysis may proceed
   offline, but live mutation or save requires an allowed, task-gated path.

If the route is missing, bootstrap the target or remain offline. Do not use Computer Use to drive
Unreal Engine UI; ask the user to perform required UI steps.
