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

For any task that reads live Unreal state or mutates a UE project:

1. Read `work/UEAgent/skills/ue-mcp-workflows/HOTPATH.md`.
2. Read the target project's `Saved/UEAgent/route.json` and run `work/UEAgent/scripts/compact_context.ps1`.
3. On `CACHE_READ`, stop before MCP. On `NEEDS_DOCTOR`, run the routed `scripts/doctor.ps1` once
   and use its receipt directly. A `BLOCKED` result requires route repair. For `LIVE_READ`, load
   only the relevant domain card; add `AI-BRIEF.md`, the workflow Skill, and Core for mutation/save work.
4. Follow the receipt and the relevant domain SOP; cache/source/config/log analysis may proceed
   offline, but live mutation or save requires an allowed, task-gated path.

If the route is missing, bootstrap the target or remain offline. Do not use Computer Use to drive
Unreal Engine UI; ask the user to perform required UI steps.
