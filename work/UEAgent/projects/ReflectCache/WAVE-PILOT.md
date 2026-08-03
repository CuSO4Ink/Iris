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

Do not cache Blueprint compile state, Niagara compile/stack issues, editor selection, or dirty
memory; those are volatile live checks. Do not use Niagara `GetScriptGraphText` as the normal
cache body: in this pilot it produced 14.8–50.9 KB per embedded script for only 5–9 nodes.
