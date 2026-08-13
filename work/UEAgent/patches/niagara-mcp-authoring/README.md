# Niagara MCP Authoring Patches

This package contains only reusable UE 5.8 Niagara editor-authoring changes. It does not contain game assets, effect algorithms, content paths, tuning values, or project requirements.

## Contents

- `vibeue/vibeue-ueagent-authoring.patch`
  - Conflict-resolved composite for the pinned VibeUE baseline.
  - Includes the UEAgent cache/material fixes plus Niagara authoring support.
- `ue-5.8/niagaraeditor-export-authoring-apis-current.patch`
  - Revision-adapted engine export patch verified against the official UE 5.8.1 release; it
    remains in the `ue-5.8` compatibility family.
  - This revision already exports the symbol but keeps `ReallocatePins` protected; the patch
    also moves it to the public section, alongside the dynamic-pin and Custom HLSL exports.
- `../vibeue-mcp-shutdown-guard.patch`
  - Independent VibeUE lifecycle hardening: rejects new and queued GameThread MCP work once
    Unreal exit begins, preventing calls from running after plugin teardown.
  - Bootstrap applies it after either VibeUE profile and records its independent route fingerprint;
    it is not folded into the Niagara composite.

The composite patch is based on upstream commit `271f487` and is the only supported VibeUE
Niagara-authoring patch.

## Apply

Use a clean branch in each repository and check applicability before changing files:

```powershell
git -C <UE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch
git -C <UE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch

git -C <VIBEUE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch
git -C <VIBEUE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch

git -C <VIBEUE_ROOT> apply --check <IRIS_ROOT>\work\UEAgent\patches\vibeue-mcp-shutdown-guard.patch
git -C <VIBEUE_ROOT> apply <IRIS_ROOT>\work\UEAgent\patches\vibeue-mcp-shutdown-guard.patch
```

The composite VibeUE patch replaces `patches/vibeue-ueagent.patch` for the verified advanced
authoring profile; never apply both. UEAgent bootstrap applies it automatically when passed
`-ApplyNiagaraAuthoringProfile` and records the selected profile and patch fingerprints in the
target route. The normal profile continues to use the smaller core patch.

Bootstrap always applies the shutdown guard after the selected VibeUE profile. `-CheckOnly` and
doctor validate both its normalized SHA-256 and reverse-applicability in the target checkout.

The shutdown guard is deliberately separate and minimal. It blocks work that has not started;
it does not wait for an already-running tool. Keep the MCP caller serialized during editor exit
until a later patch adds an explicit in-flight counter if that stronger guarantee is required.

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
