# MCP evidence ledger

This is an evidence index, not mandatory operating context. Stable rules live in the relevant
`skills/ue-mcp-workflows/references/` document.

## Record policy

- Use `SOURCE-ID` for imported records and `DOMAIN-YYYYMMDD-SLUG` for new UEAgent records.
  Never allocate another global K-number; parallel projects already collided on K11/K17/K18.
- **Observed** means a real incident without an isolated reproduction.
- **Verified** means a Probe or controlled rerun established the behavior and postconditions.
- **Conditional** means verified only for the named UE/plugin build.
- Promote behavior, not anecdotes, into an SOP. Keep source/version provenance here.

## Evidence index

| ID | State | Evidence and current route |
|---|---|---|
| `CORE-20260709-PAYLOAD` | Verified | Large base64/image results were truncated above the gateway despite larger output limits. Prefer user viewport or a tool-owned file path. Promoted to Core/Scene. |
| `UEA-K7` | Verified | Changing existing UObject array elements while resizing caused ambiguous structural diffs. Full staged read-modify-write passed. Promoted to Core. |
| `UEA-K8` | Observed ×2 | `ProgrammaticToolset` could not pythonize material-property enums such as `MP_BaseColor` and `MP_PixelDepthOffset`; direct typed calls worked. |
| `UEA-K9` | Observed | `list_properties` exposed `MaterialExpressionCustom.showCode`, but `set_properties` rejected it as read-only. |
| `UEA-K10` | Observed ×2 | `AssetTools.get_referencers` raised on an empty result instead of returning an empty list. Exact-path cleanup plus `exists=false` was used. |
| `OCEAN-K11` | Observed | `MaterialTools.get_property_input` returned `expression` as a ref-path string although the schema described an object reference. Consumers must accept either shape. |
| `OCEAN-K12` | Observed | `TextureTools.get_size` rejected render targets and volume textures; `ObjectTools.get_properties` supplied dimensions/format. |
| `OCEAN-K13` | Observed | `find_assets.asset_type` rejected bare `NiagaraSystem`; omit an unverified class filter and verify returned classes. |
| `OCEAN-K14` | Observed | Niagara compile-state query timed out on `NS_InfiniteMesh` while summary/topology/input/renderer reads worked. Treat timeout as unknown and use narrower diagnostics. |
| `OCEAN-K15` | Observed | Large Niagara graph text containing escaped HLSL comments produced invalid gateway JSON. Return a smaller payload or extract raw text without JSON parsing. |
| `OCEAN-20260803-FIND-ACTORS-REQUIRED-EMPTY` | Observed | Live `SceneTools.find_actors` required `tag` and `collision_channels` even when both filters were unused; discover the call schema and pass `tag=""`, `collision_channels=[]`. |
| `OCEAN-20260803-FUNCTION-EXPORT-TIMEOUT` | Observed | `MaterialNodeService.ExportFunctionGraph` on the 101-node coastline function consumed a core until the 120 s gateway timeout. Use the saved sidecar plus targeted typed node reads for small edits instead of exporting the full graph live. |
| `MATERIAL-20260803-VIBEUE-LIST-EXPRESSIONS-TIMEOUT` | Observed ×2 | `MaterialNodeService.ListExpressions` recursively expanded native `WorldAlignedTexture`/`WorldAlignedNormal` internals and hit the 120 s gateway timeout, while official `MaterialTools.get_expressions` returned the material's top-level refs in seconds. Prefer the official top-level read and targeted pin/property calls. |
| `MATERIAL-20260804-MI-UPDATE-IMPLICIT-SAVE` | Verified / current UE-plugin build | In controlled single-variable A/B runs, `MaterialEditingLibrary.set_material_instance_scalar_parameter_value` returned `false` but changed the scalar and advanced the `.uasset` without an explicit save. The first run also refreshed the ReflectCache sidecar; a later run left that sidecar stale. Treat the setter as a save boundary, independently live-read the value, never retry from its boolean alone, and do not assume the cache hook ran. |
| `MATERIAL-20260804-PACKAGE-MODIFY-IMPLICIT-SAVE` | Observed | After unsaved material graph edits, `Package.modify(true)` plus two material-instance scalar setters caused both the parent material and instance `.uasset` timestamps to advance and both packages to read back clean, without an explicit save/update/refresh call. Treat this combined path as a save boundary until isolated; do not use it to preserve a visual-approval checkpoint. |
| `MATERIAL-20260804-RECOMPILE-DEFERRED-SAVE` | Observed / current UE-plugin build | Setting one `MaterialExpressionVolumetricAdvancedMaterialOutput` property and calling `MaterialEditingLibrary.recompile_material` returned with the parent material Dirty=true; about two seconds later it was clean and both `.uasset` and ReflectCache sidecar timestamps had advanced, without an explicit save. `GetMaterialDiagnostics` is read-only by source contract. Treat this edit/recompile path as a possible deferred save boundary and keep an exact rollback value. |
| `BIFROST-20260804-VOLUME-POST-EDIT-CHANGE` | Observed | A synchronous Interchange VolumeTexture reimport completed before Python raised because `VolumeTexture` exposes no `post_edit_change()` wrapper. Treat this as possible partial mutation: do not retry; independently read back import source, dimensions, settings, and dirty state. The explicit property writes already mark the asset dirty. |
| `OCEAN-20260803-OBJECT-PROPERTY-CALL-SHAPE` | Observed | `ObjectTools.get_properties` requires `instance={refPath}` rather than an `object` path, while `set_properties.values` is a serialized JSON string. Use the `detail=call` schema before property reads/writes. |
| `OCEAN-20260803-MATERIAL-DIAGNOSTICS-D3D12-CRASH` | Observed | A live `MaterialNodeService.GetMaterialDiagnostics` call was dispatched; 3.4 s later UE 5.8 crashed during BasePass in `FD3D12ResourceBinder::SetTexture` with `EXCEPTION_ACCESS_VIOLATION`. The concurrent client and causality are not isolated, so avoid this broad diagnostic on the live SingleLayerWater chain; use saved graph cache plus targeted function-node reads and ordinary dirty/compile readback. |
| `PERF-K16` | Rejected | `PerformanceService.frame_timing` reported multi-second game-thread values inconsistent with render/GPU timing. Do not use as performance evidence until an independent trace agrees. |
| `NNE-K17` | Observed | `AssetImportTask.save=false` did not keep a referenced NNE import transient; treat NNE import probes as potentially persistent and clean exact paths. |
| `NNE-K18` | Verified | Bulk deletion of a still-referenced Neural Profile chain crashed UE 5.8. Safe order: detach/read back → material → profile → model data → folder, verifying each deletion. |
| `SCENE-K19` | Observed | Nested `SceneTools.add_to_scene_from_class` stalled for 120 s with no Actor; the direct typed call succeeded in 17.5 s. Prefer direct creation until isolated otherwise. |
| `SSPR-K11` | Verified profile | Bare `CreatePin` plus manual signature rebuild produced Niagara pin/signature index mismatch and compile/UI Array asserts. The verified `niagara-authoring` profile exports the required UE 5.8 APIs and routes VibeUE through `RequestNewTypedPin`; use that profile for dynamic pin mutation. |
| `SSPR-K17` | Observed ×2 | Calling `NiagaraScratchPadService` inside `ProgrammaticToolset` timed out at about 34 s and 204 s with no graph mutation. A scoped top-level `execute_python_code → unreal.NiagaraScratchPadService` call completed and was read back. |
| `SSPR-K18` | Observed | `ApplyChanges=false` plus empty compile messages hid the real rejection in `LogTemp`: stale scratch copies contained duplicate anonymous MapGet pins. Inspect `LogTemp: Error: ApplyChanges` before assuming asynchronous compile. |
| `SOURCE-UEAGENT-878558E-NIAGARA-AUTHORING` | Packaged / Unverified | Remote generic Niagara authoring overlapped local embedded-script/cache changes in `UNiagaraScratchPadService`. The resolved composite is under `patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch`; it replaces, rather than layers on, the core VibeUE patch and requires the matching engine export patch. Runtime/build proof is still pending. |

## Promoted rules

- Independent readback: `references/core.md`.
- Large payload and manual visual approval: `references/core.md` and
  `references/scene-editing.md`.
- Material pin discovery: `references/materials.md`.
- Niagara scratch capability, call shape, Apply diagnostics, and cross-frame validation:
  `references/niagara.md`.
