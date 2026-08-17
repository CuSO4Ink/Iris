# Quality gates

## Capture and evidence

- [ ] Capture path, executable, API, and final image agree.
- [ ] Frame summary is saved.
- [ ] Every major claim has event/resource evidence.
- [ ] Confirmed/inferred/unconfirmed language is consistent.
- [ ] Event order is not inferred globally from IDs alone.
- [ ] Zero-visible-output events are described precisely.

## Textures

- [ ] Raw and presentation versions are separate.
- [ ] Packed RGBA textures have four channel exports.
- [ ] Color-space and display transformations are recorded.
- [ ] Channel roles are tied to Shader operations.

## Shaders

- [ ] Full raw disassembly is preserved.
- [ ] Semantic HLSL contains explanatory comments.
- [ ] Reconstruction caveat is present.
- [ ] GBuffer output is not mislabeled as final lighting.
- [ ] Later direct/indirect/composition passes are traced when relevant.

## Meshes

- [ ] Counts and bounds match the decoded source.
- [ ] Index offsets/base vertex/submesh ranges are recorded.
- [ ] UV/normal/tangent/color preservation is checked.
- [ ] FBX imports into Blender with expected counts.
- [ ] CSV/OBJ fallback is retained for importer failures.

## Markdown and PDF

- [ ] Headings are factual and consistent.
- [ ] Images and file links resolve.
- [ ] PDF pages were rendered and visually inspected.
- [ ] Code and tables remain readable.
- [ ] Unsupported conclusions are removed or downgraded.

## PowerPoint

- [ ] Current user-edited deck was used as source when supplied.
- [ ] Original was backed up before overwrite.
- [ ] Untouched slides render identically or differences are explained.
- [ ] No text overflow, accidental overlap, or broken image crop exists.
- [ ] Core code is readable and full files are linked.
- [ ] FBX/HLSL links are relative and targets exist.
- [ ] Slide numbering does not unintentionally disturb user edits.

## Portable package

- [ ] Package opens after moving to another directory.
- [ ] Relative links still resolve.
- [ ] File hashes/manifest are generated.
- [ ] No `.rdc`, temporary dumps, secrets, or unrelated files are included unless explicitly requested.
- [ ] Delivery contains only requested artifacts.

Completion requires all applicable gates, not all possible gates.
