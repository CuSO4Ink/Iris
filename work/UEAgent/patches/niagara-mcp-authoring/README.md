# Niagara MCP Authoring Patches

This package contains only reusable UE 5.8 Niagara editor-authoring changes. It does not contain game assets, effect algorithms, content paths, tuning values, or project requirements.

## Contents

- `ue-5.8/niagaraeditor-export-authoring-apis.patch`
  - Makes `UNiagaraNode::ReallocatePins` callable by external editor tooling.
  - Exports `UNiagaraNodeWithDynamicPins::RequestNewTypedPin` and `IsAddPin`.
  - Exports `UNiagaraNodeCustomHlsl::InitAsCustomHlslDynamicInput`.
- `vibeue/scratchpad-simulation-stage-and-di-authoring.patch`
  - Registers scratch scripts in the correct System-asset collection.
  - Creates dynamic Niagara pins through the engine-supported API.
  - Adds generic Simulation Stage creation and Grid2D iteration configuration.
  - Adds self-managed RenderTarget2D and RasterizationGrid3D user-parameter authoring.
- `vibeue/vibeue-ueagent-authoring.patch`
  - Conflict-resolved composite for the pinned VibeUE baseline.
  - Includes the local UEAgent cache/material and embedded-script fixes plus the generic
    authoring patch above. Use this file instead of applying the two VibeUE patches together.
- `ue-5.8/niagaraeditor-export-authoring-apis-current.patch`
  - Revision-adapted engine export patch for the current UE 5.8 checkout used by UEAgent.
  - `ReallocatePins` is already exported/public in this revision, so only the remaining
    dynamic-pin and Custom HLSL declarations are changed.

The VibeUE patch was produced against upstream commit `271f487`.
The composite patch is also based on `271f487`; it is the resolved overlap between the local
UEAgent patch and the upstream Niagara authoring patch. The original files remain for provenance
and upstream comparison.

## Apply

Use a clean branch in each repository and check applicability before changing files:

```powershell
git -C <UE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch
git -C <UE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch

git -C <VIBEUE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch
git -C <VIBEUE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch
```

The composite VibeUE patch replaces `patches/vibeue-ueagent.patch` for the verified advanced
authoring profile; never apply both. UEAgent bootstrap applies it automatically when passed
`-ApplyNiagaraAuthoringProfile` and records the selected profile and patch fingerprints in the
target route. The normal profile continues to use the smaller core patch.

Then rebuild the editor target with the patched engine:

```powershell
<UE_ROOT>\Engine\Build\BatchFiles\Build.bat <ProjectName>Editor Win64 Development <ProjectPath>
```

Do not treat a Live Coding patch as sufficient validation. Restart the editor, verify the reflected API exists, create a disposable Niagara System, compile it, reopen it in the Niagara editor, and inspect the generated GPU HLSL.

## Revert

If the patches were applied but not committed:

```powershell
git -C <VIBEUE_ROOT> apply -R <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch
git -C <UE_ROOT> apply -R <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch
```

Review local changes before applying or reverting in a non-clean worktree.
