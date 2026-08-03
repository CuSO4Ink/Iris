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
| `PERF-K16` | Rejected | `PerformanceService.frame_timing` reported multi-second game-thread values inconsistent with render/GPU timing. Do not use as performance evidence until an independent trace agrees. |
| `NNE-K17` | Observed | `AssetImportTask.save=false` did not keep a referenced NNE import transient; treat NNE import probes as potentially persistent and clean exact paths. |
| `NNE-K18` | Verified | Bulk deletion of a still-referenced Neural Profile chain crashed UE 5.8. Safe order: detach/read back → material → profile → model data → folder, verifying each deletion. |
| `SCENE-K19` | Observed | Nested `SceneTools.add_to_scene_from_class` stalled for 120 s with no Actor; the direct typed call succeeded in 17.5 s. Prefer direct creation until isolated otherwise. |
| `SSPR-K11` | Conditional / Verified | Bare `CreatePin` plus manual signature rebuild produced Niagara pin/signature index mismatch and compile/UI Array asserts. A patched UE 5.8 exporting the required APIs plus VibeUE `RequestNewTypedPin` passed the former crash sequence. The pinned portable baseline does not prove this fix. |
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
