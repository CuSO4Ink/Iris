---
name: ue-mcp-workflows
description: Operate Unreal Engine through the official UE MCP toolsets with verified, reversible workflows for materials, Custom HLSL nodes, Blueprints, actors and components, levels, lighting, viewport validation, and asset lifecycle. Use when inspecting, creating, editing, validating, or saving UE content through MCP, or when diagnosing an MCP capability or failure before touching production assets.
---

# UE MCP Workflows

Treat `UEAgent` as the source of truth. Do not install or copy this skill into a platform-specific skill directory unless the user explicitly asks for a migration.

## Route the task

Read [references/core.md](references/core.md) for every MCP task, then read only the relevant domain reference:

- Material graphs, Material Instances, Custom nodes, shaders: [references/materials.md](references/materials.md)
- Blueprint inspection or graph editing: [references/blueprints.md](references/blueprints.md)
- Actors, components, levels, lighting, folders, viewport checks: [references/scene-editing.md](references/scene-editing.md)

Use the UEAgent project root as the authority for transport and setup: `SETUP.md` plus `scripts/mcp_gateway.ps1`. Resolve paths relative to this Skill (`../..`), never from a machine-specific drive.

## Apply the mandatory workflow

1. Discover the active endpoint and tool schema. Never guess an unfamiliar tool, property, or pin name.
2. Resolve the current workspace project from the task or `/Game/<Project>` path. Read its `AI-BRIEF.md` and `BACKLOG.md` when present before mutation.
3. Read current UE state and record exact asset, object, subobject, level, and component paths.
4. Classify the action as read-only, reversible mutation, or high-risk save/delete/move/merge.
5. For an unverified capability, build the smallest isolated Probe outside production assets.
6. Apply one logical mutation batch with one writer. Use `ProgrammaticToolset` for repeated calls.
7. Verify through an independent readback, compile result, log query, fixed invariant, or user-visible result.
8. Restore temporary state and delete Probe assets. Verify cleanup with `exists=false`.
9. Save assets or levels only when the user has authorized that save boundary.
10. Run the postflight improvement check in `references/core.md`; record or fix material friction while the evidence is fresh.

## Protect evidence quality

Label knowledge as:

- **Verified**: reproduced by an isolated Probe with postconditions and cleanup.
- **Observed**: seen in a real project but not yet isolated.
- **Hypothesis**: a possible cause; never enforce it as an SOP.

Promote only Verified behavior into mandatory instructions. Put repeated connection, gateway, or project-local failures in `notes/mcp-pitfalls.md`.

## Respect visual authority

Separate structural verification from aesthetic approval. Report wiring, values, compile state, and controlled A/B evidence; do not claim visual quality from those signals.

Follow the UEAgent rule: ask the user before `CaptureViewport` or other screenshot operations. Prefer the user's live viewport review when available.

## Use bundled resources

- Run `scripts/probe_custom_inputs.py` through `ProgrammaticToolset.execute_tool_script` only when Custom input-array behavior must be reverified for the active UE/plugin version. It creates and cleans a temporary `/Game/MCPTests/M_CustomInputProbe` asset.
- Use the UEAgent project-root `bp_clipboard_to_ai.py` for user-exported Blueprint clipboard text. Keep that tool at project root until a platform migration explicitly packages it.
