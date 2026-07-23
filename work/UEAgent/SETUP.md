# UEAgent portable setup

This repository contains the complete AI/MCP operating layer. Machine-specific paths are inputs, not project configuration.

## Stable external dependencies

| Dependency | Requirement | Stable source |
|---|---|---|
| Unreal Engine | UE 5.8 with the native `ModelContextProtocol` and `EditorToolset` plugins | [Epic UE source](https://github.com/EpicGames/UnrealEngine) / [official MCP guide](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor) |
| VibeUE | commit `271f48771d077179fb597dc285ab5b898c5e8038` | [kevinpbuckley/VibeUE](https://github.com/kevinpbuckley/VibeUE) |
| Git and PowerShell | Required by the bootstrap on Windows | System tools |

The local `toon-5.8-port` branch and its uncommitted NiagaraToolsets changes are **not** UEAgent dependencies.

## Configure a UE project

Run from this directory with paths from the current machine:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\Abyss\Abyss.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -Launch
```

The bootstrap:

1. verifies the native UE MCP plugins;
2. clones VibeUE and pins the verified commit;
3. enables `ModelContextProtocol`, `EditorToolset`, and `VibeUE` in the `.uproject`;
4. writes portable project defaults for port `8000`, auto-start, and Tool Search;
5. merges the local agent endpoint into the UE project's `.mcp.json`;
6. builds the editor and optionally launches it.

It refuses to overwrite a dirty VibeUE checkout. Use `-SkipBuild` only when the matching binaries already exist.

## Verify

Static configuration:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 `
  -UProject "X:\Projects\Abyss\Abyss.uproject" `
  -EngineRoot "X:\UnrealEngine" `
  -CheckOnly
```

Live endpoint after the editor starts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\mcp_gateway.ps1 -Action ping
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\mcp_gateway.ps1 -Action toolsets.list
```

Do not assert fixed tool counts: UE and VibeUE register tools dynamically. Verify required tool names and toolsets from the live endpoint.

## Agent connection

An MCP-native agent reads the generated `.mcp.json`. An agent without native MCP support calls the repository-owned `scripts/mcp_gateway.ps1`; no external Access Pack is required.

The endpoint is unauthenticated and loopback-only. The AI client and Unreal Editor must run on the same machine.
