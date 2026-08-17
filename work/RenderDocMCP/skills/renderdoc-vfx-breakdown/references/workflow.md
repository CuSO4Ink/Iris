# End-to-end workflow

## Contents

1. Intake
2. Identity and frame audit
3. Candidate discovery
4. Draw-family analysis
5. Texture analysis
6. Shader analysis
7. Mesh export
8. Lighting trace
9. Documentation
10. Packaging

## 1. Intake

Record before querying:

- target effect and screen region;
- expected game/build, without treating it as fact;
- user-facing audience: rendering engineer, TA, or effects artist;
- requested artifacts;
- authoritative edited files and whether they may be modified;
- capture and output paths.

Create a case workspace outside the skill:

```text
case-root/
  case.json
  evidence/
    frame/
    events/
    textures/raw/
    textures/channels/
    shaders/dxbc/
    shaders/hlsl/
    meshes/csv/
    meshes/fbx/
  docs/
  slides/
  qa/
  delivery/
```

## 2. Identity and frame audit

Verify all of the following:

- loaded capture path;
- executable path;
- graphics API;
- resolution and primary color target;
- final image content;
- frame action/draw/dispatch totals.

If an old report disagrees with executable metadata and pixels, correct the report rather than rationalizing the mismatch.

Save an identity record in `case.json` and one final-frame image in `evidence/frame/`.

## 3. Candidate discovery

Start broad:

1. Get the frame summary and marker tree.
2. Find the main GBuffer/color pass that contains the target pixels.
3. Enumerate candidate mesh, particle, and support-system draws.
4. Group by shared shaders and resources.
5. Narrow with output differences, pixel history, mesh view, shader searches, and texture bindings.

Do not choose the largest draw by index/instance count as the visible effect without proof.

## 4. Draw-family analysis

Create one event table per subsystem. Include:

| Field | Requirement |
|---|---|
| Event | Exact event ID and command |
| Geometry | Indices, vertices, instances, offsets |
| Pipeline | VS/PS/CS IDs; blend/depth/cull state |
| Inputs | VB/IB, textures, buffers, constants |
| Outputs | MRT/UAV/depth resource IDs and formats |
| Visibility | Visible, zero-difference, or not tested |
| Interpretation | Confirmed role plus alternatives |

When several events share VB/IB/shaders and adjacent index ranges, describe them as submeshes of one asset only after confirming the bindings and offsets.

## 5. Texture analysis

For each bound texture:

1. Save metadata: resource ID, format, size, mips, array slices, color space.
2. Save raw export when possible.
3. Save a viewable preview with transformations documented.
4. Export R, G, B, and A separately for packed textures.
5. Search Shader operations that consume each component.
6. Assign roles per channel as confirmed/inferred/unconfirmed.

Do not call an RGB texture a normal map solely because it looks blue. Confirm decoding, normalization, tangent-frame use, or reflection naming plus data flow.

## 6. Shader analysis

For every relevant stage:

- save complete disassembly;
- save pipeline/reflection JSON;
- identify constant-buffer groups and resource slots;
- write a semantic HLSL reconstruction;
- comment time/UV animation, unpacking, mask construction, depth fade, discard, GBuffer encoding, lighting, and output writes;
- link each high-level claim to instruction ranges or recognizable operations.

Keep short entry variants in `.hlsl` and shared implementations in `.hlsli` when that mirrors the reconstructed organization. Explain that the final `i` means include.

## 7. Mesh export

Record:

- vertex stride and attribute formats;
- index format, index offset, base vertex, and submesh ranges;
- coordinate-system conversion and winding changes;
- exported vertex/triangle counts and bounds.

Export CSV before FBX when decoding is new. Validate counts after FBX import. If Blender opens a file but another DCC rejects it, retain the validated CSV/OBJ and document importer compatibility instead of claiming the mesh is empty.

## 8. Lighting trace

In deferred rendering, separate:

1. material/GBuffer writer;
2. direct-light and shadow pass;
3. environment/indirect light and reflection accumulation;
4. volumetric/fog/cloud composition;
5. tone mapping and presentation.

Do not label the material PS “final lighting.” Trace consumers of its GBuffer outputs and the HDR accumulation resource.

## 9. Documentation

Write the technical reference first. It stabilizes event/resource facts. Derive the artist-facing MD and PPT from that source; do not independently rewrite technical claims in each artifact.

Use concise, oral wording for artist-facing content:

- what mesh is used;
- which shading model/path is used;
- what the material does in one sentence;
- which textures are used and what each channel controls;
- which support systems create contact and integration.

## 10. Packaging

Keep links relative to the PPT/package root. Do not include the `.rdc` unless explicitly requested; captures can be huge and may contain proprietary resources.

Create hashes for delivered files and verify the package from a moved test directory when portability matters.
