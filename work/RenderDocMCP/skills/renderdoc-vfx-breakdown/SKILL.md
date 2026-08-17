---
name: renderdoc-vfx-breakdown
description: Analyze a loaded RenderDoc capture and produce an evidence-backed VFX or rendering breakdown covering draw calls, meshes, shaders, textures, packed channels, deferred lighting, particles, auxiliary systems, and performance implications. Use when an AI agent must turn an .rdc frame into technical Markdown/PDF, an artist-facing presentation, semantic HLSL, exported FBX/CSV, texture channel evidence, or a portable delivery package while preserving user-edited templates and distinguishing confirmed facts from inference.
---

# RenderDoc VFX Breakdown

## Purpose

Turn one RenderDoc frame into a reproducible technical case rather than a screenshot-based guess. Trace the effect from geometry and material outputs through later lighting/composition passes, then deliver both engineering evidence and an artist-readable summary.

Do not bundle prior project artifacts inside this skill. Treat user-provided PPT, PDF, MD, Shader, FBX, images, and captures as external inputs referenced by path.

## Portability contract

- Treat tool names as capabilities, not fixed product APIs. Use the platform's available RenderDoc MCP server, replay API, qrenderdoc Python console, or exported evidence files.
- If a named presentation, PDF, document, or spreadsheet skill is unavailable, use the platform's equivalent authoring tool while keeping the same render-and-verify quality gates.
- Never assume a repository path, home directory, executable path, capture path, or output root. Resolve them from the current workspace or user input.
- Keep the skill folder read-only during analysis. Write case evidence and deliverables into a separate workspace.
- Do not claim live capture verification when the current platform cannot access RenderDoc. Mark the result blocked or evidence-limited instead.

## Required reading

Read only the references needed for the current stage:

- Read [workflow.md](references/workflow.md) before starting a new capture analysis.
- Read [evidence-standard.md](references/evidence-standard.md) before writing conclusions.
- Read [renderdoc-mcp-operations.md](references/renderdoc-mcp-operations.md) when querying RenderDoc.
- Read [deliverable-standard.md](references/deliverable-standard.md) before creating MD, PDF, PPT, Shader, FBX, or a portable package.
- Read [quality-gates.md](references/quality-gates.md) before declaring completion.
- Read [case-manifest.md](references/case-manifest.md) when creating the case manifest.
- Read [death-stranding-pattern.md](references/death-stranding-pattern.md) only when a waterfall/water VFX case needs an example decomposition pattern.

## Operating contract

1. Preserve the user's active capture and edited deliverables. Never overwrite a user-edited PPT, document, mesh, or shader without explicit authorization and a backup.
2. Use the live capture as the source of truth. Verify executable, API, capture path, final image, and frame statistics before reusing an old report.
3. Record event IDs and resource IDs for every technical claim.
4. Separate `confirmed`, `inferred`, and `unconfirmed` statements. Never promote a plausible visual interpretation to a confirmed implementation fact.
5. Analyze the whole rendering chain. A material GBuffer shader is not the final lighting shader in a deferred renderer.
6. Preserve raw evidence. Store original disassembly, raw texture exports, buffer metadata, and pipeline JSON alongside readable reconstructions.
7. Keep final presentation copy concise. Put complete Shader and mesh data behind relative links.

## Workflow

### 1. Establish the case

- Confirm the target effect, intended audience, capture path, output directory, and whether an edited PPT/MD is authoritative.
- Create a separate case workspace; never use this skill directory as an output workspace.
- Create `case.json` using [case-manifest.md](references/case-manifest.md).

### 2. Pass the identity gate

- Query capture status and frame summary.
- Record executable, graphics API, resolution, action/draw/dispatch counts, and loaded capture path.
- Export or inspect the final color image.
- Resolve conflicts between filename, old reports, executable metadata, and visible content before analysis.

Do not continue with inherited game-specific conclusions until identity is confirmed.

### 3. Build the frame map

- Inventory top-level markers, render passes, depth passes, compute passes, copies, and Present.
- Group candidate draws by shader, vertex/index buffers, render targets, and bound textures.
- Do not assume event IDs form a globally monotonic timeline across command lists.
- Cache expensive search results instead of repeatedly scanning the whole frame.

### 4. Decompose the effect

Analyze each relevant subsystem independently:

- principal mesh or water curtain;
- particles, spray, foam, mist, decals, or billboards;
- wetness, feedback maps, local masks, or global support systems;
- direct lighting, shadowing, indirect/environment lighting, reflection, volumetrics, and post-composition.

For every draw/dispatch, capture:

- event ID and call type;
- index/vertex/instance counts;
- VS/PS/CS resource IDs;
- vertex/index buffer identities and offsets;
- render targets and depth target;
- texture/SRV/UAV bindings;
- blend, depth, cull, and raster state;
- visible-pixel evidence or lack of it.

### 5. Prove visibility and role

- Compare relevant color targets and depth before/after the event, or use pixel history/overlays where available.
- Distinguish “submitted,” “shader executed,” and “produced visible pixels.”
- Treat a zero-visible-pixel draw as a real submitted draw, not as proof of CPU culling failure.
- Call it performance waste only after timing/counter evidence or a justified cost analysis; state uncertainty.

### 6. Export and validate assets

- Export mesh data to CSV first when vertex layout interpretation is uncertain.
- Preserve position, indices, UVs, normals/tangents, vertex color, submesh boundaries, and coordinate-system notes.
- Produce FBX when requested, retain CSV/OBJ fallback, and validate FBX through a Blender round trip.
- Export textures in raw form plus viewable previews. For packed RGBA textures, export all four channels separately.
- Label display stretching, gamma conversion, remapping, or false color; never present a stretched preview as raw data.

### 7. Reconstruct Shader logic

- Save complete VS/PS/CS disassembly before interpretation.
- Produce semantic HLSL with comments explaining the main operations.
- Mark semantic HLSL as non-byte-identical and not necessarily compile-ready.
- Derive packed-channel roles from actual Shader operations, not appearance alone.
- In deferred rendering, trace later full-screen/compute consumers of the GBuffer to locate direct light, shadows, environment light, AO, reflection, volumetrics, and final composition.

### 8. Create deliverables

Follow [deliverable-standard.md](references/deliverable-standard.md). Produce only the artifacts requested by the user, but keep the evidence workspace capable of supporting:

- technical reference MD;
- concise artist/TA MD;
- rendered and verified PDF;
- artist/TA PPT using the user's current edited deck as the template when provided;
- raw Shader disassembly and semantic HLSL/HLSLI;
- FBX plus CSV/OBJ fallbacks;
- texture previews and RGBA channel sheets;
- portable package with relative links;
- evidence manifest and QA record.

Use the installed presentation, PDF, document, and spreadsheet skills when their file types are involved. Follow their render-and-verify requirements.

### 9. Run quality gates

Run every applicable gate in [quality-gates.md](references/quality-gates.md). Do not declare completion merely because files exist.

## Stop conditions

Stop and report the exact blocker when:

- no capture is loaded or the RenderDoc bridge is unavailable;
- capture identity cannot be resolved;
- the requested conclusion requires evidence absent from the frame;
- a mesh layout cannot be interpreted safely;
- the user-edited template cannot be preserved by the available presentation tooling;
- completing the request requires overwriting user work without authorization.

Offer the smallest additional capture, event, screenshot, or user decision that would unblock the work.
