[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [string]$Endpoint,
    [string]$Profile = 'generic',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')

function Get-RouteEngineState($EngineRoot, $StackManifest) {
    $vibePath = Join-Path $EngineRoot 'Engine\Plugins\AI\VibeUE'
    $vibeDescriptor = Get-Descriptor (Join-Path $vibePath 'VibeUE.uplugin') 'VibeUE'
    $vibeRevisionFallback = "descriptor:$($vibeDescriptor.Version)-$($vibeDescriptor.VersionName)"
    [pscustomobject]@{
        VibeUEPath = $vibePath
        VibeUERevision = Get-GitRevision $vibePath 'VibeUE' $vibeRevisionFallback
        EngineRevision = Get-GitRevision $EngineRoot 'UE 5.8 engine' ("cl-$($StackManifest.engine.compatible_changelist)")
    }
}

function Assert-LoopbackEndpoint($Endpoint) {
    $uri = [Uri]$Endpoint
    if ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
        throw 'The UE MCP endpoint must remain unauthenticated loopback HTTP.'
    }
    $uri
}

function Write-McpClientConfig($ProjectRoot, $Endpoint) {
    $mcpPath = Join-Path $ProjectRoot '.mcp.json'
    $mcp = if (Test-Path -LiteralPath $mcpPath) {
        Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    } else {
        [pscustomobject]@{}
    }
    if ($null -eq $mcp) {
        $mcp = [pscustomobject]@{}
    }
    if (-not ($mcp.PSObject.Properties.Name -contains 'mcpServers') -or $null -eq $mcp.mcpServers) {
        Set-JsonProperty $mcp 'mcpServers' ([pscustomobject]@{}) | Out-Null
    }
    Set-JsonProperty $mcp.mcpServers 'ue-editor' ([pscustomobject]@{
        type = 'streamable-http'
        url = $Endpoint
    })
    Write-Utf8NoBom $mcpPath (($mcp | ConvertTo-Json -Depth 20) + [Environment]::NewLine)
    return $mcpPath
}

function Write-UeAgentRoute($ProjectRoot, $UProject, $EngineRoot, $Endpoint, $Profile, $EngineState) {
    $routeDir = Join-Path $ProjectRoot 'Saved\UEAgent'
    New-Item -ItemType Directory -Path $routeDir -Force | Out-Null
    $routePath = Join-Path $routeDir 'route.json'
    $route = [ordered]@{
        schema = 'ueagent-route-v1'
        ueAgentRoot = (Split-Path $PSScriptRoot -Parent)
        uProject = $UProject
        engineRoot = $EngineRoot
        endpoint = $Endpoint
        profile = $Profile
        vibeUERevision = $EngineState.VibeUERevision
        engineRevision = $EngineState.EngineRevision
    }
    Write-Utf8NoBom $routePath (($route | ConvertTo-Json -Depth 10) + [Environment]::NewLine)
    return $routePath
}

function Assert-ProjectRoute($ProjectRoot, $UProject, $EngineRoot, $Endpoint, $Profile, $EngineState) {
    $mcpPath = Join-Path $ProjectRoot '.mcp.json'
    $routePath = Join-Path $ProjectRoot 'Saved\UEAgent\route.json'
    foreach ($required in @($mcpPath, $routePath)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Project UEAgent file not found: $required"
        }
    }
    $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    if ($mcp.mcpServers.'ue-editor'.url -ne $Endpoint) {
        throw "MCP endpoint is not configured as $Endpoint."
    }
    $route = Get-Content -Raw -LiteralPath $routePath | ConvertFrom-Json
    foreach ($pair in @(
        @('schema', 'ueagent-route-v1'),
        @('ueAgentRoot', (Split-Path $PSScriptRoot -Parent)),
        @('uProject', $UProject),
        @('engineRoot', $EngineRoot),
        @('endpoint', $Endpoint),
        @('profile', $Profile),
        @('vibeUERevision', $EngineState.VibeUERevision),
        @('engineRevision', $EngineState.EngineRevision)
    )) {
        if ([string]$route.($pair[0]) -ne [string]$pair[1]) {
            throw "UEAgent route mismatch for $($pair[0]): $($route.($pair[0]))"
        }
    }
}

$UProject = Resolve-RequiredPath $UProject 'UProject'
$EngineRoot = Resolve-RequiredPath $EngineRoot 'Engine root'
$projectRoot = Split-Path $UProject -Parent
$project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
$projectVibeDescriptor = Join-Path $projectRoot 'Plugins\VibeUE\VibeUE.uplugin'
if (Test-Path -LiteralPath $projectVibeDescriptor) {
    throw "Project-local VibeUE shadows the engine installation: $projectVibeDescriptor. Merge and preserve its source changes in the engine copy, then retire the project plugin descriptor before binding this route."
}
if ($project.PSObject.Properties.Name -contains 'DisableEnginePluginsByDefault' -and
    [bool]$project.DisableEnginePluginsByDefault) {
    throw "The project disables engine plugins by default; remove DisableEnginePluginsByDefault before using the generic UEAgent bootstrap: $UProject"
}

$stackManifest = Read-UeAgentStackManifest (Split-Path $PSScriptRoot -Parent)
if (-not $PSBoundParameters.ContainsKey('Endpoint')) {
    $Endpoint = [string]$stackManifest.runtime.endpoint
}
$uri = Assert-LoopbackEndpoint $Endpoint
if ($uri.Port -ne ([Uri]$stackManifest.runtime.endpoint).Port -or $uri.AbsolutePath -ne ([Uri]$stackManifest.runtime.endpoint).AbsolutePath) {
    throw "The generic bootstrap uses the engine MCP endpoint $([string]$stackManifest.runtime.endpoint). Project-specific MCP ports are no longer written by bootstrap."
}
if ($Profile -notmatch '^[A-Za-z0-9][A-Za-z0-9+._-]*$') {
    throw "Invalid route profile name: $Profile"
}

$engineState = if ($CheckOnly) {
    Assert-EngineInstallation $EngineRoot $stackManifest
} else {
    Get-RouteEngineState $EngineRoot $stackManifest
}
if ($CheckOnly) {
    Assert-ProjectRoute $projectRoot $UProject $EngineRoot $Endpoint $Profile $engineState
    Write-Host "UEAgent generic static check passed for $([IO.Path]::GetFileNameWithoutExtension($UProject))." -ForegroundColor Green
    exit 0
}

$mcpPath = Write-McpClientConfig $projectRoot $Endpoint
$routePath = Write-UeAgentRoute $projectRoot $UProject $EngineRoot $Endpoint $Profile $engineState
Write-Host "UEAgent route configured for $([IO.Path]::GetFileNameWithoutExtension($UProject))." -ForegroundColor Green
Write-Host "MCP client: $mcpPath"
Write-Host "Route: $routePath"
Write-Host "Engine plugins and MCP defaults are installed globally; use Gateway with $routePath. Doctor is available for diagnostics."
