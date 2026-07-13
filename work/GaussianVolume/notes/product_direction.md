# GaussianVolume Product Direction

## Current Position

GaussianVolume is a research renderer and runtime kernel for continuous anisotropic Gaussian density fields. It is not currently validated as a replacement for VDB playback, ordinary ray marching, Niagara, or 3D Gaussian Splatting.

The existing technical value is:

- analytic ray-Gaussian optical depth and transmittance;
- single scattering, ambient and powder-style shading;
- sparse primitive data uploaded to Unreal Engine;
- a working UE Compute Shader rendering loop;
- a VDB/dense-volume to Gaussian conversion path.

## Product Hypothesis

The most realistic small product direction is **structured Gaussian Field FX**: a tool for sparse, directional, art-directed volumetric effects such as aurora bands, energy strands, magic trails, and atmospheric filaments.

The hypothesis is not that Gaussian rendering is universally faster. The narrower hypothesis is that a spline/field-driven Gaussian representation can combine:

1. explicit structural control from curves or emitters;
2. continuous volumetric appearance from density integration;
3. transformable and LOD-friendly primitives;
4. one shared field for rendering, beam attenuation, Niagara, materials, and gameplay queries.

## Minimal Validation

Build one UE demo with:

- spline-to-anisotropic-Gaussian generation;
- high-level controls for flow, thickness, density, breakup, emission and LOD;
- analytic volume rendering;
- one field query consumed by Niagara or a light beam;
- comparison against Niagara Ribbon and ordinary ray marching / 3D texture.

Measure visual stability, GPU time, memory, editability, LOD behavior and the number of downstream systems using the same field.

## Stop Condition

Do not expand into a general VDB or cloud renderer unless the focused demo shows a measurable workflow or runtime benefit. If it does not, keep GaussianVolume as a completed graphics research prototype and document the comparison honestly.

## Relationship to Existing Directions

- VDB proxy / distant LOD remains a secondary application path.
- Bifrost can provide a visual testbed for aurora or energy-field effects, but GaussianVolume should not replace its current cloud raymarch or stellar core without benchmark evidence.
- Standard 3DGS is related at the representation level but is not the rendering or product target; this project treats Gaussians as density primitives rather than screen-space radiance splats.
