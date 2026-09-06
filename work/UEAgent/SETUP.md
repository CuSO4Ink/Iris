# UEAgent setup

UEAgent is installed once into the UE 5.8 engine. A target project receives only two machine-local
bindings: `.mcp.json` for the MCP client and `Saved/UEAgent/route.json` for project routing.

The engine owns the common runtime:

- `ModelContextProtocol` and `EditorToolset` are engine plugins enabled by default.
- `PlatformCrypto` remains an engine-default dependency.
- `VibeUE` lives at `Engine/Plugins/AI/VibeUE` and is enabled by default.
- MCP defaults live in `Engine/Config/BaseEditorPerProjectUserSettings.ini`:
  `http://127.0.0.1:8000/mcp`, auto-start, and tool search.
- UEAgent reliable defaults live in `Engine/Config/BaseEditor.ini`.

The engine-level VibeUE checkout is the single patched copy for all projects. Build the target editor
after changing the engine or VibeUE plugin; project Bootstrap never clones, patches, enables, or
builds a project plugin.

## Stable baseline

| Dependency | Requirement |
|---|---|
| Unreal Engine | UE 5.8.1, compatible changelist `55116800` |
| VibeUE | engine plugin `Engine/Plugins/AI/VibeUE`, pinned commit from `STACK-MANIFEST.json` |
| Native MCP | engine-default `ModelContextProtocol` and `EditorToolset` |
| MCP endpoint | loopback `http://127.0.0.1:8000/mcp` |
| Windows | Git and Windows PowerShell |

Use `STACK-MANIFEST.json` for the exact engine patch packages, VibeUE revision, and install
verification. Those packages are engine-scoped; do not reapply them from a project Bootstrap.

## Install or check the engine

From the UEAgent root, run the installer on a UE 5.8.1 source checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_engine.ps1 `
  -EngineRoot "X:\UnrealEngine" -Profile niagara-authoring
```

Choose `base` for basic tools or `niagara-authoring` for the complete authoring package. Both
include MCP tool search; add `-EngineExtensions` when needed. Niagara Toolsets wrappers are part
of the authoring profile with their required exports.

If VibeUE is absent, the installer creates its engine-level checkout from the two manifest source
revisions on `Aether/ueagent`. It never resets, switches, or merges an existing checkout's branch.
It replays the ordered patches in a temporary Git index before writing source, resumes an installed
prefix, enables engine plugin defaults, updates only named INI settings, and builds
`UnrealEditor Win64 Development`. Conflicting source/profile upgrades require a source merge;
no relaxed-context application or marker-based success is used. Unrelated edits and the user's
Git index remain intact.

Use `-SkipBuild` for source/configuration installation with a separately managed build. Check an
existing installation using the same profile and optional capabilities:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_engine.ps1 `
  -EngineRoot "X:\UnrealEngine" -Profile niagara-authoring -CheckOnly
```

`-CheckOnly` verifies selected source patches and engine defaults without changing working files
or the user's index. It does not verify loaded binaries. Restart and use Doctor plus targeted
schema discovery after building; rebuild a project's editor target separately when needed.

## Niagara authoring package update

The imported authoring package adds parameter input, ParticleRead, emitter creation, scratch
module registration, `RefreshModuleCallNodes`, and `RemoveScratchPin`, plus the engine
parameter-hierarchy API. Apply the composite to the engine-level VibeUE checkout, then the
refresh patch, then the remaining runtime patches in `profiles.niagara-authoring.apply` order.
The source starts from `profiles.base.vibeue_merge_base_ref` and incorporates the pinned
`vibeue_ref`; the matching source revisions are recorded in the manifest. The installer keeps
Niagara Toolsets wrappers and their required engine export patch in the same profile.

These are packaged source changes. Rebuild and restart the target editor, then discover and
smoke-test the reflected methods through UEAgent before claiming they are installed.
Historical `-TargetProfile` / `-PreserveExistingVibeUE` installer commands in imported logs
do not apply to the current route-only Bootstrap.

## Configure a target project

From the UEAgent root, generate the project route and MCP client entry:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine"
```

This writes or updates only:

- `X:\Projects\MyGame\.mcp.json`, preserving other MCP servers;
- `X:\Projects\MyGame\Saved\UEAgent\route.json`.

The route records the target project, engine, endpoint, profile name, and current engine/VibeUE
revisions. Use `-Profile <name>` only to label an already-installed engine capability; it does
not install or select project plugins.

For an offline configuration check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\MyGame\MyGame.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -CheckOnly
```

Bootstrap does not accept the old project-install switches (`-ApplyAbyssProfile`,
`-ApplyMcpToolSearchPatch`, `-ApplyNiagaraAuthoringProfile`, or
`-ApplyEngineExtensionsProfile`). Select capabilities through `install_engine.ps1`, then use
Bootstrap to bind the project to that installation.

A project with `DisableEnginePluginsByDefault=true` cannot use the generic engine-default route;
remove that project override or keep the project on its own plugin configuration.

Abyss external plugins remain project-owned content. The generic Bootstrap does not copy, enable,
version, or claim VRM4U/Gaussian/other Abyss dependencies. Handle those dependencies separately
before using an Abyss project.

The installed engine target can be built with:

```powershell
<UE_ROOT>\Engine\Build\BatchFiles\Build.bat <ProjectName>Editor Win64 Development `
  -Project=<PROJECT> -WaitMutex -FromMsBuild
```

After the first engine installation or any plugin/engine change, restart the editor before live
work. `install_engine.ps1 -CheckOnly` validates selected source patches and engine defaults;
`bootstrap.ps1 -CheckOnly` validates defaults and project route files; `doctor.ps1` validates the
running editor.

## Run the mandatory preflight

From the target project root:

```powershell
$route = Get-Content -Raw .\Saved\UEAgent\route.json | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') -RouteFile .\Saved\UEAgent\route.json -Pretty
```

Doctor always performs the live route check; use `-View detail` only to diagnose a failed receipt.
For offline configuration validation use `bootstrap.ps1 -CheckOnly`.

For live work, save the Doctor receipt once and use it directly. The compact context router remains
available only when a cache-first saved-state read may avoid MCP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\doctor.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -OutFile .\Saved\UEAgent\doctor.json -Pretty
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $route.ueAgentRoot 'scripts\compact_context.ps1') `
  -RouteFile .\Saved\UEAgent\route.json -AssetPath /Game/... -Operation read -Pretty
```

When the envelope says `CACHE_READ`, use the adjacent `.uasset.ai.md` through
`scripts\reflect_cache.ps1` in the order `summary -> refs -> detail -> full`; do not start with
MCP. For a known domain, describe the selected tool directly. For an unknown domain, use the
cacheable `toolsets.list` result once, then treat the running `describe_toolset` response as
authoritative.

The default receipt checks endpoint safety and the live `ueagent_state` protocol/editor epoch/PID.
Add `-ProbeCapabilities` when the task needs the reliable control-surface inventory; missing
optional discovery metadata is reported under `live`/`capabilities` instead of becoming a second
task-policy contract. Source patch validation belongs to `install_engine.ps1 -CheckOnly`; project
binding checks belong to `bootstrap.ps1 -CheckOnly`. Describe domain toolsets when the task needs them.

Gateway infers the mechanical action from the tool. A normal call exposes only the tool and its
non-empty arguments; from the target project root it auto-loads `Saved/UEAgent/route.json`, while
other working directories pass `-RouteFile`. Keep complex arguments in a file instead of
PowerShell-escaped inline text:

```powershell
$gw = Join-Path $route.ueAgentRoot 'scripts\mcp_gateway.ps1'
powershell -File $gw -RouteFile .\Saved\UEAgent\route.json -Tool ueagent_state
powershell -File $gw -RouteFile .\Saved\UEAgent\route.json `
  -Tool ueagent_submit -ArgumentsFile .\Saved\UEAgent\submit.json
```

When work needs the packaged Niagara Toolsets extension, add
`-ProbeAdvancedCapabilities`. This describes only the two relevant toolsets and verifies that the
running editor binary—not merely its source tree—exports the patched methods.

## Offline recovery

If the receipt is `OFFLINE` and port 8000 has no listener, do not use UI automation. Ask the
user to run this once in the Unreal console:

```text
ModelContextProtocol.StartServer 8000
```

Then rerun the doctor. If Unreal reports `unable to bind`, inspect the exact listener PID first;
do not start more gateways or broadly terminate processes.

## Normal execution

Use [HOTPATH](skills/ue-mcp-workflows/HOTPATH.md). Installation/upgrade runs the installer and
build checks above. Ordinary tasks go from the project route to Gateway; Doctor is an optional
diagnostic and schema discovery is on demand. Session/schema caches are invalidated by session
identity or actual failure, not age. Gateway binds project/epoch once per session.

The default one-shot client can use `-AutoDaemon` for repeated work. The receiver checks endpoint
and session routing; the client does not ping the daemon before every call. An explicit mismatch
fails before dispatch. AutoDaemon may use one-shot only after an explicit pre-dispatch mismatch.
The daemon retains idle cleanup, bounded bodies and request timeouts.

The task executor uses protocol 3.0. Call known tools with `toolset`, `tool`, `arguments`;
declare `readOnly=true` for queries. Mutations use `commandId`, exact `scopes`, a typed `readback`
with `expect`, and optional `save=true`. Gateway waits locally. For a long task, `wait=false`
returns its command ID; query that ID if transport becomes uncertain. Independent save uses
`ueagent_save` with `command_id`. There are no snapshot/OCC hashes or signed save tokens.

For cache maintenance, `reflect_cache.ps1 -Action reconcile -RouteFile <route>` reports current,
stale and orphan sidecars. It does not compute hashes, infer renames, write a manifest or move
files. Regenerate disposable caches through their normal asset save/rebuild path. Cached data
does not describe dirty Editor state. Full diagnostic output is explicit and can go to a file.
