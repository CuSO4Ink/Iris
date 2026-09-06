# Animation SOP

## Address assets with full object scopes

VibeUE `AnimSequenceService` calls that receive only a package lease can fail
`UEditorAssetLibrary::LoadAsset` after a save/GC cycle, and preview-state calls may report
success flags while their out-result reports load failure. For reliable animation edits
(ANIMATION-20260814-VIBEUE-ANIM-GC-SCOPE):

- Pass the full `Asset.Asset` object path to VibeUE animation calls, not just the package.
- Declare both the bare package scope and the exact `object:/Game/...Asset.Asset` scope in
  preflight so the UObject stays loaded.
- Prefer the stateless `ApplyBoneRotation` path over a preview state split across queued
  commands; a preview that died between commands leaves later bake steps with nothing to bake.

## Verify after mutation

Read back the exact bone/curve values and the package dirty state from a different signal than
the mutation result. Treat a success flag paired with a load-failure out-result as
`RESULT_UNKNOWN`; do not retry before an independent readback.
