# blender

## State

`active`

## Goal

- **Problem**: Existing Blender MCPs can control `bpy`, but broad tool catalogs and generated Python
  make tool selection expensive, behavior hard to verify, and long main-thread work able to freeze
  Blender.
- **Outcome**: A production-shaped BlenderAgent, parallel in concept to UEAgent, routes Codex intent
  through reusable operating guidance and stable MCP/CLI contracts, then reads back, measures,
  asserts, and captures evidence before save or export.
- **Smallest working feature**: In a disposable scene, use bounded MCP contracts to create one named
  primitive, read back its transform and mesh metrics, capture the viewport, assert the expected
  result, and save the verified `.blend` without arbitrary Python.

## Current Focus

Run the smallest feature against `blender-ai-mcp`'s `llm-guided` surface before writing a custom
server.

## Truth

- **Implementation truth**: No BlenderAgent implementation exists. Source inspection found that
  [`blender-ai-mcp`](https://github.com/PatrykIti/blender-ai-mcp) 3.3.0 at `4325315` provides a real
  small, goal-first guided surface and main-thread scheduling, but is a 2,425-file system with heavy
  vector/ML dependencies. [`glonorce/Blender_mcp`](https://github.com/glonorce/Blender_mcp) at
  `21e8048` provides a compact main-thread dispatcher, job manager, schema validation, geometry
  inspection, and subprocess rendering; its 499 offline unit tests pass. Its bridge still returns
  every tool schema from MCP `tools/list`, so its later intent filter does not reduce the initial MCP
  catalog load.
- **Runtime / external truth**: The machine-specific user environment variable `BLENDER_PATH`
  resolves to Blender 5.2.0 LTS and passed a factory-startup background `bpy` check. The absolute
  executable path is not stored in the repository. No addon was installed and no live scene read,
  mutation, screenshot, or save has been performed. Blender officially treats Python API threading
  as unsafe and supports `--background` for UI-less batch work.

## Implementation

- **Canonical path**: `Codex -> Blender Skill/AGENTS -> goal router -> MCP (interactive) or Blender
  CLI --background (batch) -> main-thread queue or subprocess -> bpy -> inspect/measure/assert/capture
  -> save/export`.
- **Reused foundation**: Evaluate `blender-ai-mcp` as the runnable guided baseline; reuse only proven
  dispatcher/job/inspection ideas from `glonorce/Blender_mcp`; use Blender's native background CLI.
  Codex Skills hold repeatable operating guidance. Agent-friendly CLI conventions shape exact reads,
  polling, and artifact paths. Tool Search is optional host capability, not an assumed MCP feature.

## Constraints

- All live `bpy` access runs on Blender's main thread. Blocking render, bake, export, and conversion
  move to a background Blender process and return a job identifier.
- Keep the public surface small and schema-validated; grow it from observed tasks. Arbitrary `bpy`
  execution is an explicit last-resort escape hatch, never the normal route.
- Every meaningful write has structured readback and deterministic verification; screenshots support
  visual judgment but do not replace measurements and assertions.
- Do not extract a shared Omni/UE/Blender runtime until repeated implementation makes sharing smaller.
- Do not copy `glonorce/Blender_mcp` code until its MIT `LICENSE` versus `Proprietary` package metadata
  mismatch is resolved; architecture observations remain usable as research input.
- Resolve the Blender executable from machine-local `BLENDER_PATH`; never commit a device-specific
  absolute path.
- Blender UI interaction is manual user work; do not use Computer Use.

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/blender/`.

## Document Map

- `AI-BRIEF.md`: goal and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
