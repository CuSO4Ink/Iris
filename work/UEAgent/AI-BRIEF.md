# UEAgent

UEAgent is the routing and task execution layer for Unreal Engine 5.8.1. Native MCP remains
the server; Gateway is the AI-facing client; VibeUE hosts the typed task executor.

Use [HOTPATH](skills/ue-mcp-workflows/HOTPATH.md) as the single entry. The user authorized the
K1–K5 simplification and R01–R25 cuts on 2026-09-06. Protocol 3.0 removes universal snapshots,
OCC/hash checks, signed save tokens, duplicated discovery gates and model-driven polling.
See [execution semantics](RELIABLE-EXECUTION.md). The cutover passed real build, cold reload, typed mutation/readback/save and negative-path
tests. See [current evidence](notes/minimal-execution-20260906.md); the older runtime note below
describes the preceding 2.0.1 installation.

Authority: live Editor for dirty/runtime state; .uasset for saved truth; sidecars for disposable
saved-state context; task records for command results and exact save eligibility.

## Installation and local verification

`scripts/install_engine.ps1` consumes the manifest's selected engine patch lists, installs VibeUE
under `Engine/Plugins/AI/VibeUE`, enables engine defaults, and invokes the engine editor build.
`-CheckOnly` validates installed source/defaults; project `bootstrap.ps1` writes and checks routing.
The standalone Niagara Toolsets profile was folded into `niagara-authoring`, which includes its
required engine exports. Project-specific external plugins remain project-owned.

The 2026-09-06 verification includes an actual UE 5.8.1 rebuild, native regressions, cold starts,
typed authoring and controlled saves on a disposable project. Protocol 3.0 subsequently replaced
mandatory Doctor/independent snapshot rounds with session binding and targeted readback.
All five cache types refreshed with their changed fields. Exact CDO snapshots, private scratch
ownership, Niagara compile completion/invalidation, and eight reviewed direct readers were
verified. Gateway preserves empty/singleton arrays, null, false, and empty receipt payloads.
See [runtime evidence](notes/runtime-verification-20260906.md) for scope and limitations.

Abyss now routes to the engine-level VibeUE; its duplicate project descriptor was preserved under
`Saved/UEAgent/RetiredVibeUE`. Its project source is intact. VRM4U is still missing, so Abyss itself
has not been cold-started or live-verified on this installation.

## File boundary

`work/UEAgent/` contains only durable policy, source, tests, patches, and verified documentation.
Temporary engine/plugin clones, install smokes, reproduction bundles, captures, and test output go
under `tmp/UEAgent/<task>/` and are removed after verification; do not recreate project-local
`out/` or `_tmp/` directories.

## On-demand map

- `skills/ue-mcp-workflows/`: hot path, Skill, Core, and domain cards.
- `scripts/`: engine installation, project routing, Doctor, Gateway, daemon, cache reader/reconciler.
- `patches/`: portable UE/VibeUE extensions recorded in the manifest.
- `RELIABLE-EXECUTION.md`: command queue, OCC, receipts, recovery, and save capability contract.
- `projects/ReflectCache/`: cache implementation and evidence.
- `notes/`: verified/observed version-specific friction.
- `PROGRESSIVE-DISCLOSURE.md`: full views, measurements, and rollback history.
