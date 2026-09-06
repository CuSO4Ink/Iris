# Niagara MCP Authoring Patches

This package contains only reusable UE 5.8 Niagara editor-authoring changes. It does not contain game assets, effect algorithms, content paths, tuning values, or project requirements.

## Contents

- `vibeue/vibeue-ueagent-authoring.patch`
  - Conflict-resolved composite for the pinned VibeUE baseline.
  - Includes the UEAgent cache/material fixes plus Niagara authoring support.
- `vibeue/vibeue-refresh-module-call-nodes.patch`
  - Applies after the composite and before the runtime patches.
  - Adds `RefreshModuleCallNodes` and `RemoveScratchPin` for module signature refresh and
    removal of dangling mapped-variable pins.
- `ue-5.8/niagaraeditor-export-authoring-apis-current.patch`
  - Revision-adapted engine export patch verified against the official UE 5.8.1 release; it
    remains in the `ue-5.8` compatibility family.
  - This revision already exports the symbol but keeps `ReallocatePins` protected; the patch
    also moves it to the public section, alongside the dynamic-pin and Custom HLSL exports.
- `../vibeue-mcp-shutdown-guard.patch`
  - Independent VibeUE lifecycle hardening: rejects new and queued GameThread MCP work once
    Unreal exit begins, preventing calls from running after plugin teardown.
  - Install it with the engine-level VibeUE profile; the project route records only the selected profile
    and engine/VibeUE revisions;
    it is not folded into the Niagara composite.

The composite targets upstream `271f48771d077179fb597dc285ab5b898c5e8038` with the pinned public
`5-8` commit `6a0617cfb05aaced82d6613e88b1572fe7452eaa` merged in, as recorded in
`STACK-MANIFEST.json`. It replaces the base UEAgent patch for Niagara authoring.
Keep packaged patches as LF text; CRLF conversion can break strict application to LF source.

## Apply

Use the engine installer from the UEAgent root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_engine.ps1 `
  -EngineRoot "X:\UnrealEngine" -Profile niagara-authoring
```

It consumes `profiles.niagara-authoring.apply` in order, with MCP tool search, and installs the
full engine/VibeUE dependency set. The composite replaces the base UEAgent patch; an existing
incompatible profile requires a source merge. The installer preserves existing changes and never
silently relaxes patch context. `-CheckOnly` verifies source/defaults; `-SkipBuild` leaves building
to a separately managed engine build. Full installation and recovery details are in
[SETUP](../../SETUP.md).

Project Bootstrap then records routing to the installed engine-level VibeUE. Restart the built
editor, describe the new typed methods, and smoke-test a disposable Niagara System through
UEAgent before claiming target activation. A successful source installation is not live evidence.

## Revert

Review the exact Git changes in the engine and engine-level VibeUE checkout. Reverse dependent
patches in reverse manifest order, or use the owning source commits; do not remove the authoring
composite while later runtime patches still depend on it. Preserve unrelated source/config edits.
Rebuild and restart the affected editor after a source revert. The installer does not reset
checkouts or automatically revert a failed build.
