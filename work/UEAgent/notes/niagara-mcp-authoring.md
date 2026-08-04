# UE 5.8 Niagara Scratch Pad / Simulation Stage MCP Authoring

This document records reusable engineering knowledge for authoring Niagara graphs through editor tooling. It intentionally excludes effect-specific assets, algorithms, parameter values, and production content.

Related patch package: `../patches/niagara-mcp-authoring/README.md`.

Current Abyss source status (2026-08-04): the revision-adapted UE 5.8 export patch and the
advanced VibeUE Niagara delta (Simulation Stage, Grid2D, RenderTarget2D, RasterizationGrid3D,
and dynamic Custom HLSL pins) are applied to the local working tree. The VibeUE tree is at
`bf96d6b` with pre-existing UEAgent edits, so the pinned composite patch was reconciled rather
than blindly layered. The route stays unactivated until the patched editor is rebuilt and
validated. The separate `../patches/vibeue-mcp-shutdown-guard.patch` now gates queued MCP work
during Unreal shutdown; it is a lifecycle guard, not a full in-flight drain. The first rebuild
found that this UE revision exported but still protected `ReallocatePins`; the current engine
patch now moves that declaration to `public`, and the incremental `AbyssEditor` build succeeds.

The verified UEAgent profile is installed with `scripts/bootstrap.ps1 -ApplyNiagaraAuthoringProfile`.
Bootstrap applies the revision-adapted engine export patch and the VibeUE composite together,
records `vibeUEProfile=niagara-authoring`, and never applies the core VibeUE patch alongside it.

## 1. Why engine exports are required

Niagara dynamic nodes maintain more state than their visible `UEdGraphPin` array. Custom HLSL and Parameter Map nodes also maintain Add pins, hidden default pins, type metadata, and function signatures.

External editor tooling must use the same APIs as the Niagara editor:

- `UNiagaraNode::ReallocatePins`
- `UNiagaraNodeWithDynamicPins::RequestNewTypedPin`
- `UNiagaraNodeWithDynamicPins::IsAddPin`
- `UNiagaraNodeCustomHlsl::InitAsCustomHlslDynamicInput`

In UE 5.8 these APIs are not all publicly exported for another editor module. The engine patch makes the minimum required declarations public/exported; it does not change Niagara runtime or shader semantics.

## 2. Never create dynamic pins with bare `CreatePin`

Calling `CreatePin` directly on `UNiagaraNodeCustomHlsl`, `UNiagaraNodeParameterMapGet`, or `UNiagaraNodeParameterMapSet` can produce a graph that looks plausible but has invalid internal metadata.

Typical failures include:

- Custom HLSL `Signature.Inputs` or `Signature.Outputs` no longer matching pin order.
- Missing Add pins or hidden default pins.
- An Array range assertion in `UNiagaraNodeCustomHlsl::BuildParameterMapHistory`.
- A module that compiles but cannot be opened in the Niagara editor.
- A data-interface input that becomes an anonymous runtime clone with default dimensions or zero attributes.

Required flow:

1. Allocate/reallocate the node so Niagara creates its structural pins.
2. Add typed pins through `RequestNewTypedPin`.
3. Preserve the Parameter Map input/output chain.
4. Notify the graph and owning script of the change.
5. Compile, save, close, and reopen the asset as an independent structural check.

## 3. System assets and scratch-script ownership

The Niagara editor selects scratch scripts according to its asset edit mode.

For a Niagara System asset, editable scratch scripts must be registered in:

```text
UNiagaraSystem::ScratchPadScripts
```

Putting the script only in an emitter scratch container may still leave a stack node and may even compile, but the System editor cannot create the expected script view model. The visible symptoms are a missing scratch icon, empty Details, or a module that cannot be opened.

Tooling that loads and edits a `UNiagaraSystem` should therefore:

- create the scratch `UNiagaraScript` with the System as its owner;
- add it to `System->ScratchPadScripts`;
- include System scratch scripts when listing and applying changes.

## 4. Simulation Stage authoring

A generic particle Simulation Stage requires more than a script with `ParticleSimulationStageScript` usage.

The editor-side operation should:

1. Locate the versioned emitter data.
2. Create `UNiagaraSimulationStageGeneric` under the emitter.
3. assign a unique `SimulationStageName`;
4. create its `UNiagaraScript` and set usage to `ParticleSimulationStageScript`;
5. initialize merge identifiers expected by Niagara versioning;
6. add the stage through the emitter/version API;
7. refresh the owning System.

For tooling APIs, a stable location string such as:

```text
SimulationStage:<StageName>
```

allows the same scratch-module creation function to target Particle Spawn, Particle Update, Emitter scripts, or a named Simulation Stage.

## 5. Grid2D iteration configuration

Configuring a Simulation Stage to iterate a `Grid2DCollection` should explicitly set:

- iteration source to Data Interface;
- the fully qualified Niagara variable identifying the Grid DI;
- element count/dispatch behavior expected by the stage;
- stage read/write bindings;
- enabled state and execution behavior.

Do not infer success from the display name alone. Read the stored stage properties back after authoring and inspect the generated script usage and data-interface bindings.

## 6. Self-managed RenderTarget2D parameters

For a per-System-instance render target, author a `UNiagaraDataInterfaceRenderTarget2D` user parameter and configure it as self-managed:

```text
bInheritUserParameterSettings = false
Size = explicit width and height
Format = explicit project-appropriate format
Filter = explicit
Mip generation = explicit
```

The useful distinction is between:

- an external `UTextureRenderTarget2D` asset supplied through a user object parameter; and
- a RenderTarget2D data interface whose `RenderTarget` child resource is created and owned by the Niagara System instance.

Renderer material bindings that need the latter must bind the DI child resource, not an empty texture parameter.

## 7. RasterizationGrid3D parameter authoring

`UNiagaraDataInterfaceRasterizationGrid3D` exposes subclass fields that generic UObject/Python property wrappers may not reliably author.

A dedicated editor API should set and read back at least:

- X/Y/Z resolution;
- attribute count;
- precision/quantization;
- reset value;
- clear-before-non-iteration-stage;
- any max-axis or world-bbox behavior relevant to dispatch.

When using it as a 2D atomic buffer, Z can be one slice, but the tooling remains generic and should not assume a particular effect.

Integer atomics require an explicit fixed-point contract:

```text
encoded = round(value * scale)
atomic add encoded
decoded = encoded / scale
```

Validate overflow limits, contribution bounds, and clear ownership separately from graph compilation.

## 8. Simulation Stage side effects and particle writes

A stage that only writes an external data interface should not accidentally write `Particles.*`.

Writing a debug marker to a particle attribute can change generated metadata to `WritesParticles=true`. That can alter partial-particle-update behavior and may overwrite particle attributes that the stage did not preserve.

Keep diagnostic execution values module-local when particle mutation is not part of the stage contract. Verify generated stage metadata, not only the Scratch graph.

## 9. Compiler liveness can remove particle attributes

Reading an attribute only inside Custom HLSL side effects does not guarantee that the GPU data set stores and reloads it.

Inspect generated HLSL:

- the producer stage must store the attribute;
- the consumer Simulation Stage must load it;
- renderer bindings or another recognized consumer may be needed to keep the attribute live.

A Custom HLSL expression mentioning `Particles.Position` is not proof that runtime data was loaded for that field.

## 10. Compile, save, rebind, then observe a GPU frame

Asset mutation and runtime validation should be separate operations:

1. Author the graph or stage.
2. Apply changes.
3. Compile and inspect all messages.
4. Save.
5. Rebind or reinitialize the component.
6. Let the editor/render thread produce GPU frames.
7. Read back the active runtime resource in a later request.

A single editor-thread request that mutates, compiles, activates, and immediately reads a GPU resource can produce a false black result because the render thread has not executed the new work.

## 11. Runtime resource identity

Reinitializing Niagara components can leave multiple transient render targets or data-interface instances in memory.

Do not select the first object matching a size/format. Correlate candidates with:

- the active Niagara component;
- current override parameters;
- object creation order;
- dimensions and format;
- recent nonzero statistics.

For sparse data, inspect native resolution or targeted regions. A downsampled probe can miss valid single-pixel writes.

## 12. Additional hard rules

- Do not read and write the same RenderTarget data interface in one Simulation Stage; UE rejects or invalidates the read.
- Give clearing a single owner. For grids, confirm pre-stage clear behavior; for render targets, confirm full-domain overwrite or an explicit clear pass.
- A successful tool response proves only that the call returned. It does not prove that the Niagara asset, generated HLSL, runtime DI, renderer binding, and visual output are all correct.
- Do a full DLL build when adding reflected APIs. A Live Coding patch file is not evidence that the main editor DLL contains the new symbol.
- After restarting, verify the reflected API with `hasattr` or an actual disposable call.
- Keep PIE UObject references in short-lived local scopes. Clear Python references before ending PIE to avoid package-GC assertions.
- Serialize gateway requests. A timed-out caller may leave a request or helper process alive; confirm process identity before cleanup.

## 13. Minimal validation matrix

| Layer | Required evidence |
| --- | --- |
| Graph structure | Asset reopens; dynamic pins and Parameter Map chain are intact |
| Niagara compile | Aggregate status up to date; zero errors and warnings |
| Generated code | Required attributes appear in store/load paths |
| Stage metadata | Correct usage, iteration source, DI binding, and particle-write flag |
| Runtime DI | Expected dimensions, format, attributes, and clear policy |
| GPU execution | A later-frame readback shows a known probe value |
| Renderer/material | Binding targets the active DI child resource and expected UV/input pin |
| Lifecycle | Reinitialize, PIE exit, and cold editor restart succeed |

No single row substitutes for the others.
