# Death Stranding waterfall decomposition pattern

Use this as a structural example, not as evidence for another capture.

## Why this case matters

The reference case exposed several reusable failure modes:

- an old report identified the wrong game despite executable/capture clues;
- the visible effect was split across principal mesh, splash billboards, wetness feedback, and later deferred-lighting passes;
- some submitted draws produced zero visible pixels;
- packed texture channels required Shader data-flow analysis;
- a material PS wrote GBuffer attributes but did not compute final lighting;
- FBX compatibility differed between Blender and another importer;
- the artist-facing deck needed core code plus links to full HLSL/FBX.

## Reusable subsystem model

### Principal water curtain

Look for several indexed mesh draws sharing a water material family. Separate independent meshes from adjacent submesh index ranges. Inspect scene-depth sampling, dual/offset flow sampling, normal unpacking, edge/depth masks, discard, motion vectors, and MRT writes.

### Splash particles

Look for 6-index instanced batches or similar billboards. Confirm per-instance transforms, packed shape/normal textures, soft-depth intersection, coverage/discard, and highlight/GBuffer writes. Do not equate the largest instance batch with the visible batch without target differences.

### Wetness/support map

Look for fullscreen/low-resolution feedback updates and later terrain/material consumers. Distinguish copying/modulation of previous wetness from injection of new wetness; one event may prove only part of the lifecycle.

### Deferred lighting

Trace from material MRTs into later passes:

- direct sun/light and shadow evaluation;
- AO, environment cubemap, local probes, SH/irradiance, SSR;
- HDR accumulation;
- fog/volumetric/post composition.

Present this as a chain rather than searching for one “final lighting Shader.”

## Artist-facing narrative pattern

Summarize the implementation as:

```text
Mesh defines the large silhouette.
Packed textures and time-offset sampling create flow and breakup.
Depth/masks define intersections and visibility.
Particles and wetness add contact and integration.
Deferred lighting turns GBuffer properties into the final lit result.
```

Replace every event/resource number with evidence from the active capture.
