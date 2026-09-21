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

Grow bounded mutation contracts on the bridge side — create, rename, transform, delete — so the
slice's create step stops needing the `escapeHatch`. The job side is now bounded: `export`, `render`
and `convert` are manifest-driven kinds that own their Python and declare their own postconditions.
`bake` and animation render stay deliberately unbuilt until a real task defines their postconditions.

## Truth

- **Implementation truth**: No BlenderAgent implementation exists yet, but the chosen floor is
  installed, live and measured. [`mcp-for-blender`](https://github.com/ahujasid/mcp-for-blender)
  (renamed from `blender-mcp`; PyPI 2.0.0, MCP layer self-reports 1.30.0, addon `protocol_version 7`,
  `addon_version [1,7]`) is MIT, was pushed 2026-09-16, and depends only on `mcp>=1.9,<2` plus
  `httpx`. Its addon marshals every `bpy` call onto the main thread through socket thread →
  `queue.Queue` → `bpy.app.timers`, and already carries a Windows-specific `WinError 10054` fix for
  daemon handler threads outliving a server restart. The smallest feature passed twice: first through
  the MCP layer (9 calls, 23 assertions, 0 failures), then through `scripts/bl_gateway.py` speaking
  the addon's own socket (11 checks, 0 failures, six of them policy cases). The gateway route is the
  adopted one; the MCP-server route was measured and then dropped, because registering it in a host
  connector config couples Blender to one agent product. What the addon does **not** provide: any
  bounded mutation contract (the only write verb is `execute_code`; there is no `create_object`),
  cancellation, or progress. The gateway supplies cancellation and artifact verification on the job
  route, where the work runs in its own process; progress reporting is still absent everywhere. The
  server package additionally over-exposes its catalog — `tools/list`
  returns 31 tools totalling 21,536 description characters, 21 of them for PolyHaven / Sketchfab /
  Poly Pizza / Hyper3D / Hunyuan3D, all `enabled: False` here — which is moot on the gateway route but
  is the same defect that ruled out `glonorce`. Its self-reported `capabilities` list also omits
  `export_scene`, which the handler dict does expose, so the advertised surface and the real command
  surface disagree.
- **Demoted candidates**: [`blender-ai-mcp`](https://github.com/PatrykIti/blender-ai-mcp) is still
  v3.3.0 (Apache-2.0, 57 stars, last push 2026-06-27), unchanged since first inspected, and its
  default `mlx_local` vision path is dead weight on Windows; it remains the design reference for
  goal-first routing and macro-over-atomic layering. [`glonorce/Blender_mcp`](https://github.com/glonorce/Blender_mcp)
  has created == pushed == 2026-03-10 and 6 stars; research input only, including its BVH assembly
  analysis, and still not copyable until its MIT `LICENSE` versus `Proprietary` metadata mismatch is
  resolved. The official [Blender Lab MCP](https://www.blender.org/lab/mcp-server/) requires Blender
  5.1+, executes LLM-generated code with no guards by design (its own `weak_sandbox.py` is explicitly
  not a security barrier), and its devtalk thread was closed 2026-09-08 with the AI-policy question
  unanswered; not adopted.
- **Runtime / external truth**: verified on this device 2026-09-17. The earlier record that
  `BLENDER_PATH` resolves to Blender 5.2.0 LTS is **false here**: the variable was empty in User,
  Machine and process scope, and no `blender.exe` exists under `C:\Program Files`,
  `D:\Program Files` or `AppData\Local\Programs`. The usable runtime is the portable Blender 4.5.13
  LTS (hash `daeeeca98fb0`, built 2026-08-25) left by Kinesis at
  `D:\Violina\Iris\tmp\Kinesis\blender-portable\blender-4.5.13-windows-x64\blender.exe`, verified
  both headless and as a resident GUI session; `BLENDER_PATH` (User scope) now points at it and the
  absolute path is still not committed. Live scene read, mutation, viewport capture, glb export and
  `.blend` copy-save have all now been performed and asserted, so the previous "no live operation has
  been performed" no longer holds. Telemetry lives in the server package, is default-on to a hardcoded
  Supabase endpoint and includes `prompt_text`; the adopted gateway route never starts that package,
  so the live path has no telemetry surface, and addon consent is additionally persisted `False`
  through `save_userpref`. Events did leave this machine during the 11:14–11:19 evaluation run, before
  the switch was found. Blender officially still treats
  Python API threading as unsafe and supports `--background` for UI-less batch work.

## Implementation

- **Canonical path**: `agent host -> Blender Skill/AGENTS -> goal router -> scripts/bl_gateway.py
  (route.json, interactive) or Blender CLI --background (batch) -> addon main-thread queue or
  subprocess -> bpy -> readback/measure/assert/capture -> save/export -> receipt JSON`.
- **Integration shape**: host-agnostic, mirroring UEAgent's HOTPATH contract. A machine-local
  `route.json` (never committed) records host/port, the resolved `BLENDER_PATH`, and the probed addon
  and Blender versions. The gateway takes a request as a file or UTF-8 base64 — built from objects,
  never hand-escaped — waits locally, and writes a receipt to an out file. Any host that can run Bash
  can drive it, and nothing is registered in an agent product's connector config. A thin task-local
  driver under `tmp/blender/` pins the machine paths, exactly as `tmp/UEAgent/*/gw.ps1` does.
- **Job route**: `wait=false` is served by a separate `blender --background` process, launched
  detached so it outlives the per-call gateway and identified by a `jobId`. Submission requires a
  stable `commandId` — a replay returns the same job rather than launching a second one — exactly one
  of `job.script` or `job.code`, and a non-empty `job.expectArtifacts`. Polling resolves `running`,
  `succeeded`, `failed`, `crashed` (process gone with no status written), `timeout` and `cancelled`,
  and reports success only once every expected artifact exists, is non-empty and is newer than the
  job, so a clean exit that produced nothing still fails. `job_cancel` kills the process tree, which
  is the one thing the addon bridge cannot do. Without a `blendFile` the job runs `--factory-startup`,
  which also keeps the addon out of the job process so it cannot contend for port 9876 with the
  interactive session.
- **Bounded job kinds**: a manifest declares each kind's parameter schema, the Python it generates,
  and the artifacts it promises, so a bounded job never accepts `expectArtifacts` — the postcondition
  belongs to the contract, not the caller. `job_kinds` returns the catalog and schemas on demand.
  Parameters are validated before any process starts: unknown names, wrong types, disallowed enum
  values, wrong file suffixes and missing input files are all refused, so a typo costs a rejection
  rather than a crashed background job. `export` derives glb or fbx from the suffix. `render` refuses
  animation, because a frame sequence is not one verifiable artifact, and enables the `cycles` addon
  itself, since `--factory-startup` does not register Cycles. `convert` encodes the proven Kinesis
  BVH→FBX recipe, including the dummy cube skinned to the root bone that UE's importer requires.
- **Reused foundation**: the reused part is the **addon**, not the MCP server package. The gateway
  speaks the addon's own JSON/TCP protocol on port 9876 and inherits its main-thread marshalling,
  bounded reads (`get_scene_info`, `get_object_info`, `get_viewport_screenshot`, `get_addon_info`,
  `ping`) and `export_scene` for glb/fbx. Bypassing the `blender_mcp` server removes its telemetry
  surface structurally — and also removes its safe-mode AST validator, so the gateway supplies the
  write guard itself. Take goal-first routing and macro-over-atomic layering from `blender-ai-mcp` as
  design reference, and dispatcher/job/inspection plus BVH assembly ideas from
  `glonorce/Blender_mcp` as research input only. Use Blender's native background CLI for blocking
  work. Codex Skills hold repeatable operating guidance. Agent-friendly CLI conventions shape exact
  reads, polling, and artifact paths. Tool Search is optional host capability, not an assumed MCP
  feature.

## Constraints

- All live `bpy` access runs on Blender's main thread. Blocking render, bake, export, and conversion
  move to a background Blender process and return a job identifier.
- The bridge offers no cancellation and no progress channel, and a queued command holds the main
  thread for its entire duration — measured 2026-09-17: a 6 s block cost all 56 expected heartbeat
  beats and delayed a concurrent `ping` by 5,062 ms. A client-side timeout does not stop the
  Blender-side work, so anything long-running takes the CLI route instead of this bridge. The same
  `ping` costs 38.3 ms while a background job is running, which is the measured reason the split
  exists.
- Keep the public surface small and schema-validated; grow it from observed tasks. Arbitrary `bpy`
  execution is an explicit last-resort escape hatch, never the normal route.
- Every meaningful write has structured readback and deterministic verification; screenshots support
  visual judgment but do not replace measurements and assertions.
- Verification reads the reply body, not the transport status bit. Two measured ways a success flag
  lies: the MCP server returns `is_error=False` for a safe-mode rejection, and the addon returns
  `{"status":"success","result":{"error":"No filepath provided"}}`. The gateway fails the receipt on
  either. Artifact assertions carry mtime freshness, so a stale file from an earlier run cannot
  satisfy an existence check.
- Do not register Blender as a host MCP connector. The route stays repo-owned so any agent host can
  drive it through Bash, and so the telemetry-bearing server package stays out of the path.
- If the `blender_mcp` server is ever run anyway it must carry `BLENDER_MCP_DISABLE_TELEMETRY=1`:
  collection is default-on to a hardcoded Supabase endpoint and includes `prompt_text`, and the addon
  consent flag alone is not sufficient, since a minimal anonymous event still leaves the machine when
  consent is absent. Addon consent is already persisted `False` on this device.
- Because the gateway bypasses that server, its safe-mode AST validator is not in effect. The write
  guard is the gateway's own: `execute_code` requires an explicit `escapeHatch.reason`, every mutation
  requires a `commandId` and a readback, a failed readback refuses the save, and a reused `commandId`
  either replays the recorded terminal receipt or is rejected.
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
