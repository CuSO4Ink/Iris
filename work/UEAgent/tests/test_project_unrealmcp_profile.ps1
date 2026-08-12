[CmdletBinding()]
param(
    [switch]$KeepArtifacts
)

$ErrorActionPreference = 'Stop'
$ueAgentRoot = Split-Path -Parent $PSScriptRoot
$bootstrap = Join-Path $ueAgentRoot 'scripts\bootstrap.ps1'
$doctor = Join-Path $ueAgentRoot 'scripts\doctor.ps1'
$systemPython = (Get-Command python.exe -ErrorAction Stop).Source
$tempBase = [IO.Path]::GetTempPath().TrimEnd('\')
$testRoot = Join-Path $tempBase ('ueagent-project-unrealmcp-test-' + [Guid]::NewGuid().ToString('N'))
$listener = $null

function Write-Utf8NoBom([string]$Path, [string]$Text) {
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Invoke-PowerShellJson([string]$ScriptPath, [string[]]$Arguments) {
    $lines = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "$ScriptPath exited $LASTEXITCODE`: $($lines -join [Environment]::NewLine)"
    }
    $jsonLine = @($lines | ForEach-Object { [string]$_ } | Where-Object { $_.Trim() }) |
        Select-Object -Last 1
    try {
        return ($jsonLine | ConvertFrom-Json)
    } catch {
        throw "Invalid JSON from $ScriptPath`: $($lines -join [Environment]::NewLine)"
    }
}

function Get-NormalizedSha256([string]$Path) {
    $text = [IO.File]::ReadAllText($Path)
    $text = $text -replace "`r`n", "`n" -replace "`r", "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    } finally {
        $sha.Dispose()
    }
}

try {
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    $engineRoot = Join-Path $testRoot 'EngineRoot'
    $projectRoot = Join-Path $testRoot 'FixtureProject'
    $uProject = Join-Path $projectRoot 'FixtureProject.uproject'
    $unrealMcpRoot = Join-Path $projectRoot 'Plugins\UnrealMCP'
    $venvRoot = Join-Path $unrealMcpRoot 'Python\.venv'
    $serverScript = Join-Path $unrealMcpRoot 'Python\unreal_mcp_server_advanced.py'
    $serverCwd = Join-Path $projectRoot 'Saved\Logs'

    Write-Utf8NoBom (Join-Path $engineRoot 'Engine\Build\Build.version') @'
{"MajorVersion":5,"MinorVersion":8,"PatchVersion":0}
'@
    Write-Utf8NoBom (Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealEditor.modules') @'
{"BuildId":"ueagent-fixture-build"}
'@
    Write-Utf8NoBom $uProject @'
{"FileVersion":3,"Plugins":[{"Name":"UnrealMCP","Enabled":true},{"Name":"VibeUE","Enabled":false}]}
'@
    Write-Utf8NoBom (Join-Path $unrealMcpRoot 'UnrealMCP.uplugin') @'
{"FileVersion":3,"FriendlyName":"UEAgent fixture","Modules":[]}
'@
    Write-Utf8NoBom (Join-Path $unrealMcpRoot 'Binaries\Win64\UnrealEditor.modules') @'
{"BuildId":"ueagent-fixture-build"}
'@
    $binary = Join-Path $unrealMcpRoot 'Binaries\Win64\UnrealEditor-UnrealMCP.dll'
    New-Item -ItemType Directory -Path (Split-Path -Parent $binary) -Force | Out-Null
    [IO.File]::WriteAllBytes($binary, [byte[]]@(0))
    New-Item -ItemType Directory -Path $serverCwd -Force | Out-Null

    Write-Utf8NoBom $serverScript @'
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ueagent-readonly-fixture")


@mcp.tool()
def skill_index() -> dict[str, str]:
    return {"status": "ok"}


@mcp.tool()
def get_project_info() -> dict[str, str]:
    return {"project": "FixtureProject", "level": "/Game/Fixture"}


@mcp.tool()
def read_blueprint_content() -> dict[str, str]:
    return {"status": "ok"}


@mcp.tool()
def analyze_blueprint_graph() -> dict[str, str]:
    return {"status": "ok"}


@mcp.tool()
def get_blueprint_variable_details() -> dict[str, str]:
    return {"status": "ok"}


@mcp.tool()
def get_blueprint_function_details() -> dict[str, str]:
    return {"status": "ok"}


def delete_asset() -> dict[str, str]:
    return {"status": "should-never-be-allowed"}


if os.path.exists(os.path.join(os.getcwd(), "expose-extra-tool")):
    mcp.tool()(delete_asset)


if __name__ == "__main__":
    mcp.run(transport="stdio")
'@

    & $systemPython -m venv --system-site-packages $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the fixture Python environment.' }
    $venvPython = Join-Path $venvRoot 'Scripts\python.exe'
    & $venvPython -c 'import mcp'
    if ($LASTEXITCODE -ne 0) { throw 'The fixture Python environment cannot import mcp.' }

    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $unrealPort = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    $serverName = 'fixture-unreal-project'

    $bootstrapArgs = @(
        '-UProject', $uProject,
        '-EngineRoot', $engineRoot,
        '-UseProjectUnrealMcp',
        '-ProjectUnrealMcpServerName', $serverName,
        '-ProjectUnrealMcpPort', [string]$unrealPort,
        '-SkipBuild'
    )
    $bootstrapOutput = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap @bootstrapArgs 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Bootstrap failed: $($bootstrapOutput -join [Environment]::NewLine)"
    }

    $routePath = Join-Path $projectRoot 'Saved\UEAgent\route.json'
    $route = Get-Content -Raw -LiteralPath $routePath | ConvertFrom-Json
    if ([string]$route.transport -ne 'project-unrealmcp-stdio' -or
        [string]$route.access -ne 'read-only' -or
        [string]$route.codexMcpServer -ne $serverName -or
        [int]$route.unrealPort -ne $unrealPort -or
        [string]$route.endpoint -ne "stdio://$serverName") {
        throw 'Bootstrap wrote an unexpected project UnrealMCP route.'
    }

    $checkOutput = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap @bootstrapArgs -CheckOnly 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Bootstrap -CheckOnly failed: $($checkOutput -join [Environment]::NewLine)"
    }

    $doctorArgs = @('-RouteFile', $routePath, '-Profile', 'live', '-View', 'detail')
    $healthyReadOnly = Invoke-PowerShellJson $doctor $doctorArgs
    if ([string]$healthyReadOnly.status -ne 'DEGRADED' -or
        $healthyReadOnly.capabilities.blueprintRead -ne $true -or
        $healthyReadOnly.capabilities.readOnly -ne $true -or
        [string]$healthyReadOnly.endpoint.transport -ne 'project-unrealmcp-stdio') {
        throw 'Doctor did not grant the expected proven read-only DEGRADED receipt.'
    }

    $extraToolMarker = Join-Path $serverCwd 'expose-extra-tool'
    [IO.File]::WriteAllText($extraToolMarker, '', [Text.UTF8Encoding]::new($false))
    $rejectedExtraTool = Invoke-PowerShellJson $doctor $doctorArgs
    if ([string]$rejectedExtraTool.status -ne 'OFFLINE' -or
        $rejectedExtraTool.capabilities.blueprintRead -ne $false -or
        'delete_asset' -notin @($rejectedExtraTool.live.unexpectedProjectTools)) {
        throw 'Doctor did not reject a tool outside the exact read-only allow-list.'
    }

    $manifestPath = Join-Path $ueAgentRoot 'STACK-MANIFEST.json'
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    foreach ($property in $manifest.patches.PSObject.Properties) {
        $patchPath = Join-Path $ueAgentRoot ($property.Name -replace '/', '\')
        if (-not (Test-Path -LiteralPath $patchPath)) { throw "Manifest patch is missing: $($property.Name)" }
        $actual = Get-NormalizedSha256 $patchPath
        if ($actual -ne [string]$property.Value) {
            throw "Manifest hash mismatch for $($property.Name): expected $($property.Value), found $actual"
        }
    }

    [pscustomobject]@{
        Passed = $true
        BootstrapCheckOnly = $true
        LiveReceipt = [string]$healthyReadOnly.status
        BlueprintRead = [bool]$healthyReadOnly.capabilities.blueprintRead
        ExtraToolRejected = $true
        ManifestPatchHashes = @($manifest.patches.PSObject.Properties).Count
    } | ConvertTo-Json -Depth 4
} finally {
    if ($listener) { $listener.Stop() }
    if (-not $KeepArtifacts -and (Test-Path -LiteralPath $testRoot)) {
        $resolvedRoot = [IO.Path]::GetFullPath($testRoot)
        $resolvedBase = [IO.Path]::GetFullPath($tempBase + '\')
        if (-not $resolvedRoot.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase) -or
            -not ([IO.Path]::GetFileName($resolvedRoot)).StartsWith('ueagent-project-unrealmcp-test-', [StringComparison]::Ordinal)) {
            throw "Refusing to remove unexpected test path: $resolvedRoot"
        }
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }
}
