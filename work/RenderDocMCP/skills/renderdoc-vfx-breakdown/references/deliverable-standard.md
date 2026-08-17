# Deliverable standard

## Delivery set

Produce only requested artifacts. A complete case can contain:

```text
delivery-root/
  effect-breakdown.pptx
  Docs/
    technical-reference.md
    artist-summary.md
    technical-reference.pdf
  Assets/
    HLSL/
    Shaders-Raw/
    Meshes/
    Textures/
    Archives/
  evidence-manifest.json
```

Do not hardcode a prior case's files into the skill. Populate this structure from the active case workspace.

## Technical Markdown

Include:

1. final frame and conclusion;
2. key event table;
3. principal draw family and mesh evidence;
4. VS/PS/CS analysis with raw links;
5. texture table and packed-channel evidence;
6. particles/support systems analyzed to the same standard;
7. deferred-lighting trace when applicable;
8. implementation summary;
9. confirmed/inferred/unconfirmed boundary.

Use factual headings, not questions. Keep event/resource IDs visible.

## Artist/TA Markdown

Answer in plain language:

- what mesh is used;
- what shading path/model is used;
- what the material does;
- what textures/channels control;
- what particles/wetness/support systems add;
- what an artist can tune.

Keep detailed proof in links or the technical reference.

## PDF

- Generate from the technical MD or document source.
- Preserve image captions and readable code.
- Render every page to images and visually inspect it.
- Fix clipping, orphan headings, tiny text, broken paths, and missing images.

## PowerPoint

When the user provides an edited deck, treat that exact file as the visual template:

- make a backup;
- preserve all untouched slides and objects;
- duplicate a compatible slide when a new page is needed;
- do not restyle or regenerate the deck from scratch;
- compare unchanged slide renders before/after when possible.

Recommended narrative for an artist/TA breakdown:

1. minimal cover;
2. one-page recipe;
3. mesh/draw families with screenshots and FBX links;
4. shading path/model;
5. packed texture with RGBA channels;
6. material Shader core;
7. deferred-lighting page when the material only writes GBuffer;
8. particle system and particle packed texture;
9. wetness/global support system;
10. concise rebuild takeaway if the source deck has that pattern.

Use core code only on slides. Link complete HLSL and FBX with relative paths.

## Shader delivery

For each relevant shader:

- raw disassembly `.txt`;
- pipeline/reflection `.json` when useful;
- semantic `.hlsl` entry;
- shared `.hlsli` implementation when variants share logic.

Place this notice near reconstructed code:

> Semantic reconstruction from captured disassembly; not original source and not guaranteed byte-identical or directly compile-ready.

## Mesh delivery

Deliver FBX plus CSV/OBJ fallback when requested. Include a manifest with:

- source event;
- vertex/index/triangle counts;
- bounds;
- attribute list;
- coordinate conversion;
- Blender validation counts;
- known importer limitations.

## Texture delivery

For packed textures provide:

- full RGBA preview;
- R/G/B/A channel images;
- raw file or lossless export;
- format, dimensions, color space, and transformations;
- channel-role table tied to Shader evidence.

## Portable links

- Use paths relative to the PPT/package root.
- Keep PPT and `Assets/`/`Docs/` in fixed relative positions.
- Test after copying the entire package to another directory.
- Warn that Office can show a security prompt for local external links.

## Naming

Prefer stable semantic names with event/resource IDs:

```text
water_main_event9135.fbx
water_ps_191859_event9135.txt
water_ps_191859_event9135.hlsl
packed_flow_resource6813975_rgba.png
packed_flow_resource6813975_r.png
```
