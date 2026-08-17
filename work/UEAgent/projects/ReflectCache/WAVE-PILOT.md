# Wave cache pilot — 2026-07-29

Scope: `/Game/Bifrost/Ocean/Wave`. Read-only Asset Registry and graph inspection; no
`.uasset` was modified.

## Inventory

```text
55 packages = 37 active-name + 18 explicit backup/study packages
active: Blueprint 2, Material 6, MaterialFunction 1, MaterialInstance 4,
        MPC 1, NiagaraSystem 1, StaticMesh 10, Texture2D 9, RT2D 2, VolumeTexture 1
logic/override caches: 14 generated (6 M + 1 MF + 4 MI + 2 BP + 1 NS)
```

Active-name packages:

```text
BP: BP/BP_OceanInitial, BP/Tool/BP_HeightMapCreate1
M: BP/Tool/M_Calculate, BP/Tool/M_DebugPlane, BP/Tool/M_NiagaraVisibilityTest,
   BP/Tool/M_PostHeightMap, M_StylizedWater, M_Wave_Base
MF: MF_CoastlineWave
MI: BP/Tool/MI_DebugPlane_Bottom, BP/Tool/MI_DebugPlane_Top,
    M_StylizedWater_Inst, M_Wave_Base_Inst
MPC: BP/Tool/MPC_TopHeightABottomHeight
NS: NS/NS_InfiniteMesh
SM: Model/SM_Distant, Model/SM_FluxPlane{1x1,8x8,16x16,32x32,64x64,
    128x128,256x256,512x512,1024x1024}
T2D: BP/Tool/RT_HeightMap_Tex, New_Graph_output, New_Graph_output_normal,
     T_CoastField_Landscape, T_DefaultWaveProfile_Forard, T_DetailWaveTexture_01,
     T_OceanWave, T_Seafoam_03_NSH, T_WaveFoam_N
RT2D: BP/Tool/RT_HeightMap1, NewTextureRenderTarget2D
VT: T_OceanWave_Volume
```

Backups are inventoried but intentionally receive no cache. Name-based backup exclusion
does not imply they are safe to delete.

## Saved dependency spine

```text
L_Bifrost
|- BP_HeightMapCreate1
|  |- RT_HeightMap1
|  |- MPC_TopHeightABottomHeight -> M_PostHeightMap
|  `- /Game/Materials/DemoPublic/... debug mesh/materials
|- NS_InfiniteMesh
|  `- SM_FluxPlane32x32 + embedded clipmap scripts
`- M_Wave_Base_Inst
   |- M_Wave_Base -> MF_CoastlineWave
   |- RT_HeightMap1
   |- T_CoastField_Landscape
   `- T_DefaultWaveProfile_Forard
```

`L_Bifrost` referencing both `NS_InfiniteMesh` and `M_Wave_Base_Inst` suggests a placed
Niagara component supplies `User.Material Interface`; this is an inference, not cached
system truth. The currently loaded editor world contained no matching component, so the
placed override was not asserted.

## Findings that change decisions

```text
BP_OceanInitial: empty/trivial and no referencers.
BP_HeightMapCreate1: live, but its two planes still use DemoPublic mesh/material assets.
Local MI_DebugPlane_*: referenced only by the backup map; both parent DemoPublic M_DebugPlane.
M_StylizedWater + local instance: no referencers; instance parents DemoPublic M_StylizedWater.
M_Calculate: no referencers and reads external DemoPublic HeightMap_output.
NS_InfiniteMesh: 1216 = 256 + 5*192, therefore six clipmap levels, not nine.
NS custom HLSL: CameraForwardVector and MeshPosition are wired but unread.
NS User.Material Interface: saved system default is None.
19 active-name packages have zero Asset Registry referencers; candidates only, not deletion proof.
```

## Cache boundary selected by the pilot

```text
Material: exact compact node IR; MaterialFunction calls are paths only.
MaterialFunction: independent exact compact node IR and interface; nested functions are paths only.
MaterialInstance: parent + enabled overrides only; ignore serialized orphan overrides.
Blueprint: parent + declared vars/CDO defaults + decision-changing component defaults + deps
           + official BlueprintTools graph DSL, one section per graph.
NiagaraSystem: user vars + emitter/stage/module order + meaningful inputs + renderers + deps.
External Niagara scripts: paths to their own future cache, never inline.
Embedded Niagara scripts: compact nodes/links and full Custom HLSL inline because no package sidecar exists.
Leaf assets (mesh/texture/RT/MPC): dependency-index facts only unless a task needs class-specific data.
```

The old `list_scratch_modules` returned zero for this system's legacy embedded modules.
The verified VibeUE patch now finds five editable embedded graph calls with node counts
5/5/9/9/5 and refuses external packaged scripts. The effective Stack still contains only
`NMS_InitGrid`, `CameraSet001`, and `NMS_InifniteMeshSet001`; Stack topology, not the editable
script inventory, decides what enters the semantic cache body.

## Infinite surface optimization log — 2026-08-08

### Measured baseline and failed intermediate

- The previous nine-level layout submitted about 55,397,216 triangles per water pass and about
  110.8 million triangles across SingleLayerWater depth + water passes. L0 and L1 both used the
  256x256 plane and accounted for 84.8% of those triangles.
- The current saved intermediate has 124 particles: four center tiles plus ten 12-tile rings.
  Mesh density falls from 256 to 128/64/32/16/8 while tile size doubles per ring, for about
  2,594,432 triangles per pass.
- That intermediate removes most triangle cost but decimates twice: tile world size doubles while
  subdivisions halve. Vertex spacing therefore grows about 4x per ring, exposing triangles on
  steep shoreline WPO and producing visible ring transitions.

### FluidFlux reference behavior

- `NS_InfiniteSurfaceMesh` uses four center tiles plus five 12-tile near rings (64 tiles total).
- `BP_FluxSurface_Ocean` binds one fixed 128x128 mesh through `User.MeshGrid` for every near ring,
  so spatial density changes only with tile scale. This is about 2,097,152 triangles per pass.
- The horizon is a separate low-poly carrier (`SM_Distant`) with a separate distant material.
- Geometry offset and shading detail are separated: distant/low-density geometry drops expensive
  wave height while filtered normals and surface shading continue.

### Selected implementation

1. Replace the near layout with four center tiles plus five rings, all using the 128x128 plane.
2. Move coverage beyond the near rings to a separate `SM_Distant` low-poly renderer/path.
3. Before shoreline waves enter low-density geometry, smoothly fade only high-frequency height
   and horizontal curl/forward displacement. Preserve the low-frequency vertical wave shape.
4. Keep shoreline foam and the normal/detail branch active across the geometry fade so the
   transition does not become a flat or hard-cut band.
5. Verify saved topology, mesh bindings, compile state, material output wiring, particle/triangle
   counts, and then hand viewport appearance and final fade tuning to the user.

### Saved result

- `NS_InfiniteMesh` now spawns 68 particles: 64 near tiles plus four distant sectors.
- Renderer 0 uses only `SM_FluxPlane128x128` for the center and all five near rings. Renderers
  1-4 use `SM_Distant` at 0/90/180/270 degrees and select their particle through `LevelIndex`.
- The distant carrier inherits the outer near-tile scale instead of fitting its full bounds to
  the near square. With the current defaults its scale is 50, the join is at about 100 m, and
  the four flared sectors reach about 1.075 km from the system center.
- Estimated geometry is 2,097,864 triangles per pass: 2,097,152 near plus 712 distant. The water
  depth + water pair is about 4.196 million triangles before normal visibility/culling effects.
- `M_Wave_Base` reuses the dormant 6000-10000uu near fade. It now attenuates detail geometry WPO
  and only the XY portion of coastline displacement. Coastline Z height, foam, foam normal, and
  the coastline/wave normal composition remain connected without that fade.
- Niagara compiled `UpToDate` with no errors or warnings. Both assets were explicitly saved and
  their current cache hashes are `de94e63091c6f564148a50d88bdc8167d22cc86e` (Niagara) and
  `42c1f894081c92880ad3afc167ff47cfc6a0eaf8` (material).

### Transition fixes

- The first distant pass incorrectly reused `User.Material Interface`. On the 178-triangle
  carrier this kept near-field shoreline displacement, foam emissive, and the 7x highlight
  boost, which collapsed into the bright trailing ring at the near/far boundary.
- FluidFlux instead gives `MeshFar` its own `User.MaterialOceanFar` path. The Bifrost equivalent
  is `M_Wave_Distant_Inst`, a child of `M_Wave_Base_Inst_Current`; it inherits water colour,
  reflection, and normal tuning while overriding `WPOIntensity=0`,
  `FoamHighlightIntensity=0.03`, and `HighlightBoost=1`. The wave/foam texture remains inherited,
  so the transition keeps foam structure and foam normals instead of cutting them to black.
- All four `SM_Distant` renderers now bind that distant instance explicitly. Near tiles keep the
  full material and therefore retain shoreline foam and normals through the dense rings.
- A half-cell `smoothstep` soft snap was tested and reverted. It translated the whole mesh every
  frame while the renderers had motion vectors disabled and visibly aggravated the temporal
  artifact. The saved baseline again uses one shared 312.5uu hard-snapped anchor.
- Post-rollback compile state is `UpToDate`, not compiling or stale, with no errors or warnings.
  The Niagara asset and refreshed sidecar were saved.

### Latest viewport result and handoff

- User validation after the rollback reports no meaningful fix: moving the view still produces
  obvious trailing/ghosting and the mesh transition still jumps.
- Therefore soft snap is ruled out as the sole root cause. Do not reapply it, but do not treat
  the rollback as a fix for the temporal artifact.
- Current saved HLSL baseline is
  `floor(CameraPos.xy / BaseCellSize + 0.5f) * BaseCellSize`; compile and cache state are clean.
- Start the next context with one unsaved isolation test: disable the four distant renderers while
  leaving the 64 near tiles unchanged. If the artifact disappears, inspect near/far geometry and
  material continuity. If it remains, hold camera recentering fixed and compare temporal AA versus
  a non-temporal AA mode before changing the asset again.
- Keep each A/B reversible and change one variable at a time. The user performs viewport checks;
  UEAgent must not use Computer Use to drive Unreal UI.

Status: saved topology/performance work remains in place, but both the camera-motion ghosting and
the visible near/far transition are unresolved. No further smoothing change has been accepted.

Do not cache Blueprint compile state, Niagara compile/stack issues, editor selection, or dirty
memory; those are volatile live checks. Do not use Niagara `GetScriptGraphText` as the normal
cache body: in this pilot it produced 14.8–50.9 KB per embedded script for only 5–9 nodes.
