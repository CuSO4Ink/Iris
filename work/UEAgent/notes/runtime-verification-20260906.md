# UEAgent runtime verification — 2026-09-06

The current package was applied to the installed UE 5.8.1 source engine, rebuilt, and exercised
through Gateway in a disposable project. This closes the generic runtime/save work; Abyss still
needs its missing VRM4U dependency before its own activation can be verified.

## Target and boundaries

- Engine: `E:/work/engine_work/Enigne/UE`, compatible changelist `55116800`.
- Engine VibeUE: `Engine/Plugins/AI/VibeUE`, reliable protocol `2.0.1`.
- Engine and VibeUE branch: `Aether/ueagent-reliability-20260906`; no commits were made.
- Probe: `D:/ForViolina/Iris/Iris/tmp/UEAgent/end-to-end/probe-project/UEAgentProbe.uproject`.
- Live work used route → Doctor → typed submit → terminal receipt → independent snapshot →
  exact-token save. Only disposable probe assets were authored.
- Existing engine/plugin/Iris index entries and unrelated dirty source were preserved.
- Real Niagara authoring tests used CPU emitters. This does not prove GPU output, PIE behavior,
  aesthetic quality, every Blueprint subclass, or a fresh installation on another machine.

## Fixes and observed results

| Area | Observed failure | Current result |
|---|---|---|
| Object identity | A missing explicit CDO/subobject could fall back to the primary asset. | Exact missing paths stay `exists=false`; CDO and child identities pass native and live checks. |
| Scratch ownership | Shared library scripts were visited by scratch DI healing. | Only private scripts in the caller package are editable/notified. Shared EmitterState remained clean and unchanged. |
| Niagara reads | Data-processing `RefreshAll` started compilation despite disabled simulation/auto-compile. | Input/topology reads no longer replace runtime compile objects; four direct readers stayed unchanged. |
| Input/save lifecycle | `SetStackInputData` returned before its compile settled, invalidating the save snapshot. | The typed setter waits for compilation. Input `23 → 24`, independent read and exact save passed. |
| Scratch invalidation | A changed ParticleRead binding left the old compiled dependency, including a circular-dependency warning. | Apply marks the owned script source unsynchronized before notify/compile/wait. The next compile and cold reload had no circular-dependency warning. |
| Blueprint cache | `NewVariables` omitted inherited CDO overrides. | `## Defaults` records editable inherited differences from the parent CDO; `InitialLifeSpan=11.500000` is saved and reloads as 11.5. |
| Gateway JSON | Empty arrays collapsed to null and failed daemon serialization; singleton arrays lost shape. | Direct and daemon paths preserve `[]`, singleton/nested arrays, null, false and empty reliable results. |
| Capability discovery | Advanced Doctor only described the earlier six Niagara extensions. | It also reports reflected scratch authoring and parameter hierarchy separately. |

The direct read additions are ObjectTools `list_properties`/`get_properties`, BlueprintTools
`get_default_object`, MaterialTools `get_property_input`, and Niagara `GetEmitterTopology`,
`GetStackInputData`, `GetUserVariables`, `GetUserParameterHierarchy`. Each was source-reviewed and
exercised with unchanged scoped snapshots. The explicit allow-list contains 46 entries; unreviewed
tools keep the existing queue requirement.

## Execution evidence

| Verification | Result |
|---|---|
| Actual `UnrealEditor Win64 Development` build | Passed after the final source changes. |
| Native `VibeUE.UEAgentReliable` regressions | 3 passed: CanonicalJson, ScratchOwnership, SnapshotIdentity. CanonicalJson reports that disabled fault-injection branches were skipped. |
| Gateway transport suite | 16 groups passed, including both target-binding boundaries, recovery, 8 MiB payloads, removed routes and JSON value shapes. |
| Installer regressions | 11 scenarios passed, including ordered/additive replay, dirty/index preservation, defaults, build dispatch, bootstrap and project-plugin shadow rejection. |
| Strict VibeUE patch replay | Base: 5 patches/32 paths; authoring: 6 patches/32 paths, applied without whitespace-relaxation switches. |
| Installed source/default check | Current default + Niagara authoring + engine extensions matched. |
| Final cold-start Doctor | HEALTHY; read, mutation, save, recovery, Niagara extensions, scratch authoring and parameter hierarchy present. |
| Final dirty state | Zero dirty packages and no active/queued command. |

The five save-hook checks included actual changed fields, not only sidecar timestamps:

| Asset type | Saved and independently checked |
|---|---|
| Material | Two-sided setting; `ProbeStrength=0.5` expression connected to Roughness; compile diagnostics passed. |
| MaterialFunction | Description `UEAgent save-hook smoke 20260906` and library exposure. |
| MaterialInstanceConstant | Parent reference and scalar override `ProbeStrength=0.75`. |
| Blueprint | Actor-to-Pawn parent change and CDO lifetime changes; inherited default 11.5 survived cold reload and appeared under Defaults. |
| NiagaraSystem | Spawn Count 24, 8×8×8 RasterizationGrid3D user parameter, scratch topology/HLSL, and saved private ownership. |

Four added authoring operations were executed: CreateEmitterAsset, AddParameterInputNode,
AddParticleReadNode and CreateRasterizationGrid3DUserParameter. RefreshModuleCallNodes, dynamic
Custom HLSL pins, connections, RemoveScratchPin, user-parameter grouping, apply and save also ran.
Removing the MapGet output removed its paired default pin; the retired name remained absent after
later compilation and reload. The final ParticleRead binding targets the independent ProbeSource
emitter and the `Probe Settings` category survives reload.

Both managed VibeUE save guards were tested: Blueprint SetProperty and Niagara ApplyChanges
changed memory while Content bytes remained identical until `ueagent_save`. Reusing a consumed
current-epoch token returned its immutable receipt without changing source/cache bytes. Old-epoch
tokens were rejected without writes. An actual Autosave invalidated an outstanding token with
`OUT_OF_BAND_SAVE`; its Saved/Autosaves file was distinguished from formal Content, and the later
task-required authoring/apply sequence completed with its own verified token. Autosave remains enabled.

One material connection also demonstrated the remaining snapshot boundary: package/root plus
expression scopes did not cover output wiring in the editor-only data object. Declaring that
returned object and performing the task-required compile supplied complete region evidence.
Package snapshots are not recursive graph exports; the SOP now makes this explicit.

## Abyss activation

`E:/work/engine_work/ue/abyss/Abyss.uproject` now resolves the engine-level VibeUE. The project
descriptor was moved byte-for-byte to
`Saved/UEAgent/RetiredVibeUE/VibeUE.uplugin.disabled`; the project plugin source remains intact.
Before this upgrade, the only differing source file between that duplicate and the engine copy
was the existing `VibeUE.Build.cs` warning policy. The engine policy was preserved.

Bootstrap and its static check passed with the existing
`default+niagara-authoring+engine-extensions` profile. VRM4U is the sole enabled plugin absent from
the project and engine plugin inventories. No production Abyss assets were changed, and a healthy
Abyss editor receipt has not been claimed. The old complex-Blueprint incidents remain scoped to
their original assets; the simple regression is not a universal resolution.

## Reproduction artifacts

Disposable commands, receipts, native reports, build logs and saved fixtures are under
`tmp/UEAgent/end-to-end/`. Key files are `engine-build-07.log`,
`native-test-report-final/index.json`, `gateway-transport-final.json`, `install-tests-final.json`,
`strict-patches-final.json`, `doctor-live-04.json`, `final-live-verification.json`, and
`cache-save-boundary-checks.json`. This note is the durable result; those files are disposable.
