# Reflect Cache Protocol

> Goal: let an AI understand saved UE graph assets without cold-walking them through MCP
> every session. This is not human documentation, a backup format, or cache-to-UE sync.
>
> Material v2 and MaterialFunction v1 automatic caches are verified. Blueprint,
> MaterialInstance, and Niagara formats are real Wave pilots, not automatic yet.

## Contract

- `.uasset` is truth; the Markdown file is disposable AI context.
- Direction is UE -> cache only. Never mutate UE from the cache alone.
- Optimize for minimum tokens and decisions, not human readability or exact recovery.
- Preserve the smallest exact representation that answers edit decisions: settings,
  interfaces, overrides, dependencies, graph topology, constants, and Custom code.
- Omit full node inventories, layout, screenshots, tutorials, audit prose, and tool logs.
- Optimize expected task tokens, not file size. Exact code IR may exceed 4 KB when that
  avoids the next cold graph walk.
- Each cache is a source sidecar: `<PackageFile>.ai.md`, for example
  `M_Wave_Base.uasset.ai.md`.
- Follow package boundaries. Never refactor a graph for cache quality.

## Progressive read contract

Use `../../scripts/reflect_cache.ps1` as the offline reader. The default is `summary`; expand
only as `refs`, a named `detail` section, then explicit `full`. `refs` contains direct
dependencies only and never recursively expands another cache. `-Action index` builds a bounded
asset/reverse-dependency index; it is not deletion proof. `-Action diff` returns bounded changed
lines, while `-Action receipt` returns only before/after digests and changed-section counts and
still requires independent MCP readback after a live save. See
`../../PROGRESSIVE-DISCLOSURE.md` for the shared route, measurement, and rollback contract.

## Automatic material MVP

Implementation: VibeUE editor module, `vibeue-material-cache-v2`.

```text
successful manual UMaterial/UMaterialFunction save
-> UPackage::PackageSavedWithContextEvent
-> existing ExportMaterialGraph()
-> deterministic compact renderer
-> UTF-8 temp file + atomic replace
```

- Enabled by default; skips cook, procedural save, autosave, failed save, commandlets,
  and unsupported packages.
- Output is always adjacent to the source package; only enable/disable is configured:

```ini
[VibeUE.MaterialAICache]
Enabled=True
```

- Manual backfill/recovery:

```text
VibeUE.MaterialAICache.Rebuild /Game/Path/M_A /Game/Path/MF_B
```

- UE Asset Registry, Content Browser, and default Cook ignore the `.md` sidecar.
  Source control policy and UE Migrate do not manage it automatically.
- Current production-verified boundary: `UMaterial` and `UMaterialFunction`. Rename/delete
  cleanup and automatic MaterialInstance/Blueprint/Niagara generation are deferred.

## Material compact format

Use short code blocks instead of tables and prose:

````markdown
# <AssetName> | AI material cache

```yaml
format: vibeue-material-cache-v2
src: /Game/...
file: ...
mtime: ...
size: ...
graph_sha1: ...
graph: {expressions: N, connections: N, outputs: N, parameter_nodes: N, parameter_names: N}
material: {domain: ..., blend: ..., shading: ..., use_material_attributes: ...}
```

## Params
```text
V: Color=(r,g,b,a), SharedVector=(...) x3
T: Mask=/Game/...
S=0: A, B, C
S=1: Speed, Weight
special: Param[value,group]
```

## Logic
```text
n000=P:Strength{DefaultValue=1.000000}
n001=MF:/Game/MF_Noise
n002=Multiply{ConstB=0.500000}(A=n000,B=n001.Result)
out.BaseColor=n002
root.n003=VolumetricAdvancedMaterialOutput(PhaseG=n004)
```

## Deps
```text
MF: /Game/MF_X x3
TEX: /Game/T_X x2
REROUTE: SignalA, SignalB
```

## Custom
```text
Description | inputs=[...] out=... code_sha1=... code~=...
```

## Flags
```text
Only facts likely to change an AI decision.
```
````

Rules:

- Group identical scalar defaults.
- Deduplicate shared parameter names and retain node multiplicity as `xN`.
- Prefer semantic aliases over expression object names.
- Use deterministic `n###` aliases from serialized top-level expression order; never
  persist exporter pointer IDs.
- Keep exact source pin, target pin, common constants, all material outputs, and
  independent `*Output` roots.
- Named Reroute declarations/usages form explicit IR links. Do not invent semantic names
  for anonymous nodes.
- Keep exact asset paths for dependencies.
- For a master material, record called MaterialFunctions and call counts; do not expand
  their internal graphs into the master cache.
- For a `Custom`/HLSL node, keep its inputs and compact semantic formula; do not copy
  full code unless the next edit requires it.
- Record only active material outputs; mention inactive legacy links only in `Flags`.
- Automatic caches use `mtime`, `size`, and a canonical `graph_sha1` of the emitted IR.
  Raw exporter pointer IDs are excluded.
- Automatic `Custom` entries keep description, input names, output type, code hash, and
  a short code prefix. Fetch only that node before editing when the prefix is insufficient.
- Exact logic may legitimately exceed 4 KB. Verified v2 sidecars are 14.8 KB for Wave
  and 27.7 KB for Cloud; do not discard topology just to hit a size target.

## Other graph-bearing formats

These formats were selected from the real Wave asset family. Full examples and evidence are
in `WAVE-PILOT.md` and the adjacent source sidecars.

### MaterialFunction v1

```text
format: vibeue-material-function-cache-v1
metadata + ordered Interface + Params + exact compact Logic + nested MF/texture/MPC Deps
```

Every packaged MaterialFunction owns one cache. A call site stores only its asset path and
pin connection; it never expands the called function. `Custom` nodes use the material rule.

### MaterialInstance v1

```text
format: vibeue-material-instance-cache-v1
parent + enabled scalar/vector/texture/static-switch overrides + orphan-override flags
```

Do not repeat inherited parameters or parent graph logic. Determine enabled overrides through
the editor API; serialized parameter arrays may contain orphan entries from an older parent.

### Blueprint v1

```text
format: vibeue-blueprint-cache-v1
parent + declared variables/CDO defaults + component structure/non-defaults + deps
+ one official BlueprintTools graph DSL section per event/function/macro/construction graph
```

Reuse `BlueprintTools.read_graph_dsl`; do not invent a second graph language. Keep only
component properties that change a decision. Do not dump giant default structs. Compile state,
placed-instance overrides, and dirty editor memory are live checks.

### NiagaraSystem v1

```text
format: vibeue-niagara-system-cache-v1
user variables + emitter/sim target + stage/module order + meaningful inputs + renderers + deps
```

- External Niagara module/function scripts are paths to independent future caches.
- Embedded system subobject/scratch scripts have no package sidecar, so inline compact node/link
  IR and full Custom HLSL when present.
- Do not store raw `GetScriptGraphText` by default; the Wave pilot returned 14.8–50.9 KB for
  graphs with only 5–9 nodes.
- Compile state, stack issues, and live component overrides remain targeted live queries.

## Freshness

Stop at the first cheap check that answers the question:

1. Derive `<PackageFile>.ai.md` from the `.uasset`; do not start with graph MCP.
2. Sidecar missing or older than the source -> run the asset type's regenerator when available.
3. Sidecar current and recognized -> read it; no cold full-graph MCP.
4. Material sidecar v1 is inventory only; rebuild with v2 or query the required graph region.
5. Only Material/MaterialFunction have a save hook in this MVP. For manual-pilot formats,
   stale means targeted MCP regeneration.
6. Before mutating UE, check live package dirty state and inspect only the region being
   changed. The cache describes the saved asset, not unsaved editor memory.
7. After a successful save, verify the cache file timestamp advanced. Manual regeneration
   is fallback, not the normal path.

SHA-256 is provenance/debug data, not the normal freshness check; mtime is cheaper.

## Export

The VibeUE save hook now performs one UE-side export, not per-node MCP calls:

1. Export the top-level graph once.
   Use official `get_expressions()` as the top-level count; recursive
   `list_expressions()` may duplicate function internals once per call.
2. Read parameter name/group/default, texture/function paths, Named Reroute links, every
   top-level connection, active material roots, and independent `*Output` nodes.
3. The exporter explicitly includes `MaterialAttributes`; do not repeat a second
   output-root MCP query for caches generated as `vibeue-material-cache-v2`.
4. Fold it into deterministic code IR plus compact parameter/dependency indexes.
5. Verify the `.uasset` mtime and package dirty state did not change during a read-only run.

Failure mode learned: verify the final sidecar, not only exporter counts. The v1 exporter
already returned every top-level connection and expression property, but its renderer
reduced them to counts and indexes. A self-consistent partial document can still omit the
logic needed by an AI.

Known `M_Wave_Base` trial facts:

- 164 expressions / 178 connections exported in about 0.1 s.
- Per-node multi-call auditing is unnecessary and previously caused editor stalls.
- The original raw export omitted Named Reroute relations and the active
  `MaterialAttributes` root. Both are now exported explicitly and covered by the MVP
  build; older VibeUE builds still require enrichment.

Legacy v1 verification baseline:

- UE 5.8 `AbyssEditor Win64 Development` build succeeded with warnings-as-errors.
- `VibeUE.MaterialAICache.Render` automation test passed headlessly.
- Real rebuilds produced Wave 164/178 (4.1 KB) and Cloud 308/396 (7.3 KB) without
  changing either `.uasset`; the current layout stores them as source sidecars.
- End-to-end save-hook check passed: Cloud `AuthoringStrength` was saved as `0.001`,
  restored to `0`, and saved again. Both saves produced one export and one atomic cache
  refresh; the final cache landed about 22 ms after the package timestamp, retained
  308/396 and `AuthoringStrength=0.000000`, and left no `.tmp` file.
- v1 is retained only as evidence for the save hook and sidecar lifecycle. It cannot
  answer wiring or formula questions.

Verified v2 evidence:

- UE 5.8 `AbyssEditor Win64 Development` build succeeded.
- `VibeUE.MaterialAICache.Render` passed headlessly (1/1), including changed session
  pointer IDs producing identical output.
- Wave exported 164 expressions / 178 connections into 164 IR nodes, 3 material outputs,
  and a wired `SingleLayerWaterMaterialOutput` root (14,762 bytes).
- Cloud exported 308 expressions / 396 connections into 308 IR nodes, 4 material outputs,
  and a wired `VolumetricAdvancedMaterialOutput` root (27,666 bytes).
- A second independent headless rebuild produced byte-identical SHA-256 values and did
  not advance either sidecar timestamp, proving deterministic output and no-op writes.
- Source `.uasset` SHA-256 values were unchanged and no `.tmp` file remained.
- Real `MF_CoastlineWave` exported 99 expressions / 108 connections, two inputs and two
  function outputs (9,271 bytes). Repeated headless rebuilds kept the same SHA-256 and
  timestamp, and the source package hash remained unchanged.
- The real `NS_InfiniteMesh` regression found five editable embedded graph calls
  (5/5/9/9/5 nodes) while excluding external packaged modules. Active Stack topology is
  still the authority for deciding which of those calls belongs in the semantic cache body.

## Promotion checklist

1. Cache answers a later AI planning question without a cold full-graph read.
2. A saved human edit changes mtime and triggers one regeneration.
3. An AI mutation performs targeted live verification, saves, then refreshes the cache.
4. Cache-assisted token/tool cost is lower than a cold graph walk.

## Wave-family pilot

The 2026-07-29 audit covered all 55 packages under `/Game/Bifrost/Ocean/Wave`: 37
active-name assets plus 18 explicit backups. Sidecars cover every active graph/override
asset (Material, MaterialFunction, MaterialInstance, Blueprint, Niagara); leaf meshes,
textures, RTs, and the MPC stay as dependency-index facts unless a task needs their
class-specific settings. See `WAVE-PILOT.md`.
