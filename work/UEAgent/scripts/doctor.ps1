[CmdletBinding()]
param(
    [string]$RouteFile,
    [string]$UProject,
    [string]$EngineRoot,
    [string]$Endpoint,
    [int]$TimeoutSec = 30,
    [ValidateSet('quick', 'live')]
    [string]$Profile = 'live',
    [switch]$ProbeAdvancedCapabilities,
    [ValidateSet('compact', 'detail')]
    [string]$View = 'compact',
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
$ueAgentRoot = Split-Path $PSScriptRoot -Parent
$gateway = Join-Path $PSScriptRoot 'mcp_gateway.ps1'
$issues = [Collections.Generic.List[string]]::new()
$warnings = [Collections.Generic.List[string]]::new()

function Add-Issue($Message) {
    if (-not $issues.Contains([string]$Message)) { $issues.Add([string]$Message) }
}

function Add-Warning($Message) {
    if (-not $warnings.Contains([string]$Message)) { $warnings.Add([string]$Message) }
}

function Test-PluginEnabled($Project, $Name) {
    @($Project.Plugins | Where-Object { $_.Name -eq $Name -and $_.Enabled }).Count -gt 0
}

function Test-GitPatchApplied($Repository, $Patch) {
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & git -C $Repository apply --reverse --check $Patch 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Get-NormalizedFileSha256($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $text = [IO.File]::ReadAllText($Path)
    $text = $text -replace "`r`n", "`n" -replace "`r", "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($text)))).Replace('-', '')
    } finally {
        $sha.Dispose()
    }
}

function Test-TcpListener([Uri]$Uri) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($Uri.Host, $Uri.Port)
        if (-not $task.Wait(1000)) { return $false }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Invoke-GatewayProbe($Action, $Url, $Seconds, $Toolset = $null, $SessionFile = $null, $DescribeDetail = $null) {
    $hostExe = (Get-Command powershell.exe -ErrorAction Stop).Source
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $gateway,
        '-Action', $Action,
        '-Endpoint', $Url,
        '-TimeoutSec', $Seconds,
        '-Envelope'
    )
    if ($Toolset) { $arguments += @('-Toolset', $Toolset) }
    if ($SessionFile) { $arguments += @('-SessionFile', $SessionFile, '-ReuseSession') }
    if ($DescribeDetail) { $arguments += @('-DescribeDetail', $DescribeDetail) }
    $output = & $hostExe @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = (@($output) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    try {
        $parsed = $text | ConvertFrom-Json
        $message = if ($parsed.message) {
            [string]$parsed.message
        } elseif ($parsed.error) {
            [string]($parsed.error | ConvertTo-Json -Depth 10 -Compress)
        } else {
            $null
        }
        [pscustomobject]@{
            ok = ($exitCode -eq 0 -and $parsed.ok -eq $true)
            exitCode = $exitCode
            data = $parsed.data
            code = $parsed.code
            message = $message
        }
    } catch {
        [pscustomobject]@{
            ok = $false
            exitCode = $exitCode
            data = $null
            code = 'invalid_gateway_output'
            message = $text
        }
    }
}

function Read-McpSessionSnapshot($Path, $ExpectedEndpoint) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $entry = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        if ($entry.schema -ne 'ueagent-mcp-session-v1' -or
            [string]$entry.endpoint -ne [string]$ExpectedEndpoint -or -not $entry.sessionId) { return $null }
        return $entry
    } catch {
        return $null
    }
}

function Get-PluginFingerprint($ProjectRoot, $EngineRoot) {
    $patterns = @()
    if ($ProjectRoot) {
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\*.uplugin')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\*.uplugin')
    }
    if ($EngineRoot) {
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\*.uplugin')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\*.uplugin')
    }
    $files = @($patterns | ForEach-Object { Get-ChildItem -Path $_ -File -ErrorAction SilentlyContinue })
    if ($files.Count -eq 0) { return $null }
    $stamp = @($files | Sort-Object FullName | ForEach-Object {
        "$($_.FullName)|$($_.Length)|$($_.LastWriteTimeUtc.ToString('o'))"
    }) -join "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($stamp)))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

$route = $null
if (-not $RouteFile -and -not $UProject) {
    $candidate = Join-Path (Get-Location) 'Saved\UEAgent\route.json'
    if (Test-Path -LiteralPath $candidate) { $RouteFile = $candidate }
}
if ($RouteFile) {
    if (Test-Path -LiteralPath $RouteFile) {
        $RouteFile = (Resolve-Path -LiteralPath $RouteFile).Path
        try {
            $route = Get-Content -Raw -LiteralPath $RouteFile | ConvertFrom-Json
            if ($route.schema -ne 'ueagent-route-v1') {
                Add-Issue "Unsupported route schema: $($route.schema)"
            }
        } catch {
            Add-Issue "Invalid route file: $($_.Exception.Message)"
        }
    } else {
        Add-Issue "Route file not found: $RouteFile"
    }
}
$vibeUEProfile = if ($route -and $route.PSObject.Properties.Name -contains 'vibeUEProfile') {
    [string]$route.vibeUEProfile
} else {
    'base'
}
if ($vibeUEProfile -notin @('base', 'niagara-authoring')) {
    Add-Issue "Unsupported UEAgent VibeUE profile: $vibeUEProfile"
}
if (-not $route) {
    Add-Issue 'No valid UEAgent route was supplied; direct parameters are diagnostic-only.'
}

if (-not $UProject -and $route) { $UProject = [string]$route.uProject }
if (-not $EngineRoot -and $route) { $EngineRoot = [string]$route.engineRoot }
if (-not $Endpoint -and $route) { $Endpoint = [string]$route.endpoint }

$project = $null
$projectRoot = $null
if (-not $UProject) {
    Add-Issue 'UProject is required directly or through route.json.'
} elseif (-not (Test-Path -LiteralPath $UProject)) {
    Add-Issue "UProject not found: $UProject"
} else {
    $UProject = (Resolve-Path -LiteralPath $UProject).Path
    $projectRoot = Split-Path $UProject -Parent
    try {
        $project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
    } catch {
        Add-Issue "Invalid uproject JSON: $($_.Exception.Message)"
    }
}

$mcpPath = if ($projectRoot) { Join-Path $projectRoot '.mcp.json' } else { $null }
$configuredEndpoint = $null
if ($mcpPath -and (Test-Path -LiteralPath $mcpPath)) {
    try {
        $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
        $configuredEndpoint = [string]$mcp.mcpServers.'ue-editor'.url
    } catch {
        Add-Issue "Invalid .mcp.json: $($_.Exception.Message)"
    }
} elseif ($projectRoot) {
    Add-Issue "Missing project MCP config: $mcpPath"
}
if (-not $Endpoint) { $Endpoint = $configuredEndpoint }
if (-not $Endpoint) { $Endpoint = 'http://127.0.0.1:8000/mcp' }
if ($configuredEndpoint -and $configuredEndpoint -ne $Endpoint) {
    Add-Issue "Route endpoint differs from project .mcp.json: $configuredEndpoint"
}

$uri = $null
$endpointSafe = [Uri]::TryCreate($Endpoint, [UriKind]::Absolute, [ref]$uri)
if (-not $endpointSafe -or $uri.Scheme -ne 'http' -or
    $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    Add-Issue "Endpoint must be unauthenticated loopback HTTP: $Endpoint"
    $endpointSafe = $false
}

$nativeMcpEnabled = $false
$editorToolsetEnabled = $false
$vibeUEEnabled = $false
$niagaraToolsetsEnabled = $false
if ($project) {
    $nativeMcpEnabled = Test-PluginEnabled $project 'ModelContextProtocol'
    $editorToolsetEnabled = Test-PluginEnabled $project 'EditorToolset'
    $vibeUEEnabled = Test-PluginEnabled $project 'VibeUE'
    $niagaraToolsetsEnabled = Test-PluginEnabled $project 'NiagaraToolsets'
    if (-not $nativeMcpEnabled) { Add-Issue 'ModelContextProtocol is not enabled in the uproject.' }
    if (-not $editorToolsetEnabled) { Add-Issue 'EditorToolset is not enabled in the uproject.' }
    if (-not $vibeUEEnabled) { Add-Warning 'VibeUE is not enabled; official MCP may still be healthy.' }
}

$settingsPath = if ($projectRoot) {
    Join-Path $projectRoot 'Config\DefaultEditorPerProjectUserSettings.ini'
} else {
    $null
}
if ($settingsPath -and (Test-Path -LiteralPath $settingsPath) -and $endpointSafe) {
    $settings = Get-Content -Raw -LiteralPath $settingsPath
    foreach ($expected in @(
        "ServerUrlPath=$($uri.AbsolutePath)",
        "ServerPortNumber=$($uri.Port)",
        'bAutoStartServer=True',
        'bEnableToolSearch=True'
    )) {
        if ($settings -notmatch "(?m)^$([regex]::Escape($expected))\r?$") {
            Add-Issue "Missing MCP project setting: $expected"
        }
    }
} elseif ($projectRoot) {
    Add-Issue "Missing MCP project settings: $settingsPath"
}

$engineVersion = $null
if ($EngineRoot) {
    if (Test-Path -LiteralPath $EngineRoot) {
        $EngineRoot = (Resolve-Path -LiteralPath $EngineRoot).Path
        $buildVersionPath = Join-Path $EngineRoot 'Engine\Build\Build.version'
        if (Test-Path -LiteralPath $buildVersionPath) {
            try {
                $buildVersion = Get-Content -Raw -LiteralPath $buildVersionPath | ConvertFrom-Json
                $engineVersion = "$($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion)"
                if ($buildVersion.MajorVersion -ne 5 -or $buildVersion.MinorVersion -ne 8) {
                    Add-Issue "UE 5.8 required; found $engineVersion."
                }
            } catch {
                Add-Issue "Invalid Build.version: $($_.Exception.Message)"
            }
        } else {
            Add-Issue "Missing engine Build.version: $buildVersionPath"
        }
        foreach ($pluginPath in @(
            'Engine\Plugins\Experimental\ModelContextProtocol\ModelContextProtocol.uplugin',
            'Engine\Plugins\Experimental\Toolsets\EditorToolset\EditorToolset.uplugin'
        )) {
            $fullPluginPath = Join-Path $EngineRoot $pluginPath
            if (-not (Test-Path -LiteralPath $fullPluginPath)) {
                Add-Issue "Missing native MCP plugin: $fullPluginPath"
            }
        }
    } else {
        Add-Issue "Engine root not found: $EngineRoot"
    }
} else {
    Add-Warning 'EngineRoot was not supplied; engine/plugin files were not statically checked.'
}

$vibeUERevision = $null
$vibeUEDirty = $null
$vibeUEPatchApplied = $false
$engineNiagaraPatchApplied = $false
$vibeUEAuthoringPatchApplied = $false
$engineNiagaraAuthoringPatchApplied = $false
$vibePatchPath = if ($vibeUEProfile -eq 'niagara-authoring') {
    Join-Path $ueAgentRoot 'patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch'
} else {
    Join-Path $ueAgentRoot 'patches\vibeue-ueagent.patch'
}
$engineNiagaraPatchPath = Join-Path $ueAgentRoot 'patches\ue58-niagara-toolsets.patch'
$engineNiagaraAuthoringPatchPath = Join-Path $ueAgentRoot 'patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch'
if ($projectRoot) {
    $vibePath = Join-Path $projectRoot 'Plugins\VibeUE'
    if (Test-Path -LiteralPath (Join-Path $vibePath '.git')) {
        if (Get-Command git -ErrorAction SilentlyContinue) {
            $vibeUERevision = ((& git -C $vibePath rev-parse HEAD 2>$null) | Select-Object -First 1)
            if ($vibeUERevision) { $vibeUERevision = $vibeUERevision.Trim() }
            $vibeUEDirty = [bool](& git -C $vibePath status --porcelain 2>$null)
            if ($route -and $route.vibeUEPatchSha256) {
                if (-not (Test-Path -LiteralPath $vibePatchPath)) {
                    Add-Issue "Routed VibeUE patch is missing: $vibePatchPath"
                } elseif ((Get-NormalizedFileSha256 $vibePatchPath) -ne [string]$route.vibeUEPatchSha256) {
                    Add-Issue 'Routed VibeUE patch checksum differs from UEAgent.'
                } else {
                    $vibeUEPatchApplied = Test-GitPatchApplied $vibePath $vibePatchPath
                    if (-not $vibeUEPatchApplied) { Add-Issue 'The routed UEAgent VibeUE patch is not applied.' }
                    $vibeUEAuthoringPatchApplied = ($vibeUEProfile -eq 'niagara-authoring' -and $vibeUEPatchApplied)
                }
            }
            if ($vibeUEDirty) {
                if ($vibeUEPatchApplied) {
                    Add-Warning 'VibeUE contains the packaged UEAgent patch and is intentionally dirty.'
                } else {
                    Add-Warning 'VibeUE has local changes; capabilities may differ from the pinned baseline.'
                }
            }
            if ($route -and $route.vibeUERef -and $vibeUERevision -ne [string]$route.vibeUERef) {
                Add-Warning "VibeUE revision differs from route baseline: $vibeUERevision"
            }
        } else {
            Add-Warning 'Git is unavailable; VibeUE revision was not checked.'
        }
    } elseif ($vibeUEEnabled) {
        Add-Warning "Enabled VibeUE is not a Git checkout: $vibePath"
    }
}

if ($EngineRoot -and $route -and $route.engineNiagaraPatchSha256) {
    if (-not (Test-Path -LiteralPath $engineNiagaraPatchPath)) {
        Add-Issue "Routed Niagara Toolsets patch is missing: $engineNiagaraPatchPath"
    } elseif ((Get-NormalizedFileSha256 $engineNiagaraPatchPath) -ne [string]$route.engineNiagaraPatchSha256) {
        Add-Issue 'Routed Niagara Toolsets patch checksum differs from UEAgent.'
    } elseif (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        Add-Issue 'Routed Niagara Toolsets patch requires a source-engine Git checkout.'
    } else {
        $engineNiagaraPatchApplied = Test-GitPatchApplied $EngineRoot $engineNiagaraPatchPath
        if (-not $engineNiagaraPatchApplied) { Add-Issue 'The routed Niagara Toolsets patch is not applied.' }
    }
}

if ($vibeUEProfile -eq 'niagara-authoring') {
    if (-not $EngineRoot) {
        Add-Issue 'The Niagara authoring profile requires EngineRoot for static patch validation.'
    } elseif (-not $route.engineNiagaraAuthoringPatchSha256) {
        Add-Issue 'The Niagara authoring profile is missing its engine patch fingerprint.'
    } elseif (-not (Test-Path -LiteralPath $engineNiagaraAuthoringPatchPath)) {
        Add-Issue "Routed Niagara authoring patch is missing: $engineNiagaraAuthoringPatchPath"
    } elseif ((Get-NormalizedFileSha256 $engineNiagaraAuthoringPatchPath) -ne [string]$route.engineNiagaraAuthoringPatchSha256) {
        Add-Issue 'Routed Niagara authoring patch checksum differs from UEAgent.'
    } elseif (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        Add-Issue 'Routed Niagara authoring patch requires a source-engine Git checkout.'
    } else {
        $engineNiagaraAuthoringPatchApplied = Test-GitPatchApplied $EngineRoot $engineNiagaraAuthoringPatchPath
        if (-not $engineNiagaraAuthoringPatchApplied) {
            Add-Issue 'The routed Niagara authoring engine patch is not applied.'
        }
    }
}

$listener = $false
$gatewaySessionFile = if ($projectRoot) { Join-Path $projectRoot 'Saved\UEAgent\mcp-session.json' } else { $null }
$sessionSnapshot = $null
$pluginFingerprint = Get-PluginFingerprint $projectRoot $EngineRoot
$listenerPids = @()
$preflightProbe = $null
$toolsListOk = $false
$currentLevelRead = $false
$currentLevel = $null
$topToolNames = @()
$missingMetaTools = @('list_toolsets', 'describe_toolset', 'call_tool')

if ($endpointSafe) {
    $listener = Test-TcpListener $uri
    if ($listener -and (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        try {
            $listenerPids = @(
                Get-NetTCPConnection -State Listen -LocalPort $uri.Port -ErrorAction Stop |
                    Select-Object -ExpandProperty OwningProcess -Unique
            )
        } catch {
            Add-Warning "Could not identify listener PID: $($_.Exception.Message)"
        }
    }
}

if ($listener -and $Profile -eq 'live') {
    $preflightProbe = Invoke-GatewayProbe 'preflight' $Endpoint $TimeoutSec $null $gatewaySessionFile
    if ($preflightProbe.ok) {
        $toolsListOk = [bool]$preflightProbe.data.toolsList
        $currentLevelRead = [bool]$preflightProbe.data.currentLevelRead
        $currentLevel = $preflightProbe.data.currentLevel
        $topToolNames = @($preflightProbe.data.topLevelTools | Sort-Object -Unique)
        $missingMetaTools = @(
            @('list_toolsets', 'describe_toolset', 'call_tool') |
                Where-Object { $_ -notin $topToolNames }
        )
        foreach ($probeError in @($preflightProbe.data.errors)) {
            Add-Issue "MCP preflight: $probeError"
        }
    } else {
        Add-Issue "MCP preflight failed: $($preflightProbe.code) $($preflightProbe.message)"
    }
    if ($toolsListOk -and $missingMetaTools.Count -gt 0) {
        Add-Issue "Missing MCP meta tools: $($missingMetaTools -join ', ')"
    }
}

if ($Profile -eq 'quick' -and $ProbeAdvancedCapabilities) {
    Add-Issue 'ProbeAdvancedCapabilities requires -Profile live.'
}

$niagaraToolsetsExtensionLive = $false
if ($ProbeAdvancedCapabilities -and $Profile -eq 'live') {
    if (-not $listener -or -not $engineNiagaraPatchApplied) {
        Add-Issue 'Advanced Niagara capability probe requires a live endpoint and the routed engine patch.'
    } else {
        $systemProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_System' $gatewaySessionFile 'full'
        $componentProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_Component' $gatewaySessionFile 'full'
        if (-not $systemProbe.ok -or -not $componentProbe.ok) {
            Add-Issue 'Advanced Niagara toolset description failed.'
        } else {
            $systemNames = @($systemProbe.data.tools.name)
            $componentNames = @($componentProbe.data.tools.name)
            $missingAdvancedTools = @(
                @('GetScriptGraphText', 'GetScriptCustomHlsl', 'GetScriptRapidIterationParameters', 'GetScriptObject', 'SetScriptCustomHlsl') |
                    Where-Object { ".$_" -notin @($systemNames | ForEach-Object { ([string]$_).Substring(([string]$_).LastIndexOf('.')) }) }
            )
            if (-not @($componentNames | Where-Object { ([string]$_).EndsWith('.GetRuntimeState') }).Count) {
                $missingAdvancedTools += 'GetRuntimeState'
            }
            if ($missingAdvancedTools.Count) {
                Add-Issue "Running editor is missing patched Niagara tools: $($missingAdvancedTools -join ', ')"
            } else {
                $niagaraToolsetsExtensionLive = $true
            }
        }
    }
}

if ($gatewaySessionFile) {
    $sessionSnapshot = Read-McpSessionSnapshot $gatewaySessionFile $Endpoint
}

$status = if (-not $UProject -or -not $project -or -not $endpointSafe) {
    'BLOCKED'
} elseif ($Profile -eq 'quick') {
    if (-not $listener) { 'OFFLINE' } elseif ($issues.Count -gt 0) { 'DEGRADED' } else { 'READY' }
} elseif (-not $listener -or -not $preflightProbe -or -not $preflightProbe.ok -or -not $toolsListOk) {
    'OFFLINE'
} elseif ($issues.Count -gt 0 -or $missingMetaTools.Count -gt 0 -or -not $currentLevelRead) {
    'DEGRADED'
} else {
    'HEALTHY'
}

if ($status -eq 'HEALTHY' -and $projectRoot) {
    $invalidationPath = Join-Path $projectRoot 'Saved\UEAgent\doctor.invalidate.json'
    Remove-Item -LiteralPath $invalidationPath -Force -ErrorAction SilentlyContinue
}

$allowed = @(switch ($status) {
    'HEALTHY' { @('CACHE_ONLY', 'LIVE_READ', 'LIVE_WRITE_TASK_GATED') }
    'READY' { @('CACHE_ONLY', 'ROUTE_CHECKED') }
    'DEGRADED' { @('CACHE_ONLY', 'PROVEN_LIVE_READ_ONLY') }
    'OFFLINE' { @('SOURCE_CACHE_CONFIG_LOG_ONLY') }
    default { @('ROUTE_REPAIR_ONLY') }
})
$blocked = @(switch ($status) {
    'HEALTHY' { @('UNAUTHORISED_SAVE_DELETE_MOVE_MERGE', 'UNVERIFIED_CAPABILITY', 'UI_AUTOMATION') }
    'READY' { @('LIVE_STATE_CLAIMS', 'LIVE_MUTATION', 'SAVE', 'UI_AUTOMATION') }
    'DEGRADED' { @('LIVE_MUTATION', 'SAVE', 'DESTRUCTIVE_ACTION', 'UI_AUTOMATION') }
    'OFFLINE' { @('LIVE_STATE_CLAIMS', 'LIVE_MUTATION', 'SAVE', 'UI_AUTOMATION') }
    default { @('MCP_OPERATION', 'UI_AUTOMATION') }
})

$receipt = [ordered]@{
    schema = 'ueagent-doctor-v1'
    profile = $Profile
    view = $View
    status = $status
    checkedAtUtc = [DateTime]::UtcNow.ToString('o')
    project = [ordered]@{
        uproject = $UProject
        engineRoot = $EngineRoot
        engineVersion = $engineVersion
        routeFile = $RouteFile
    }
    endpoint = [ordered]@{
        url = $Endpoint
        loopbackSafe = $endpointSafe
        listener = $listener
        listenerPids = $listenerPids
    }
    identity = [ordered]@{
        listenerPids = $listenerPids
        mcpSessionId = if ($sessionSnapshot) { [string]$sessionSnapshot.sessionId } else { $null }
        mcpSessionExpiresAtUtc = if ($sessionSnapshot) { [string]$sessionSnapshot.expiresAtUtc } else { $null }
        pluginFingerprint = $pluginFingerprint
    }
    static = [ordered]@{
        nativeMcpEnabled = $nativeMcpEnabled
        editorToolsetEnabled = $editorToolsetEnabled
        vibeUEEnabled = $vibeUEEnabled
        niagaraToolsetsEnabled = $niagaraToolsetsEnabled
        vibeUEProfile = $vibeUEProfile
        vibeUERevision = $vibeUERevision
        vibeUEDirty = $vibeUEDirty
        vibeUEPatchApplied = $vibeUEPatchApplied
        vibeUEAuthoringPatchApplied = $vibeUEAuthoringPatchApplied
        engineNiagaraPatchApplied = $engineNiagaraPatchApplied
        engineNiagaraAuthoringPatchApplied = $engineNiagaraAuthoringPatchApplied
    }
    live = [ordered]@{
        toolsList = $toolsListOk
        topLevelTools = $topToolNames
        missingMetaTools = $missingMetaTools
        toolsetDiscoveryAvailable = ('list_toolsets' -in $topToolNames -and 'describe_toolset' -in $topToolNames)
        currentLevelRead = $currentLevelRead
        currentLevel = $currentLevel
        advancedCapabilityProbe = $ProbeAdvancedCapabilities.IsPresent
    }
    capabilities = [ordered]@{
        officialToolSearch = ($missingMetaTools.Count -eq 0 -and $toolsListOk)
        vibeUE = ($vibeUEEnabled -and 'execute_python_code' -in $topToolNames)
        niagara = ($niagaraToolsetsEnabled -and $missingMetaTools.Count -eq 0)
        reflectCacheSaveHook = if ($vibeUEPatchApplied) { 'PRESENT_UNVERIFIED' } else { 'UNVERIFIED' }
        niagaraToolsetsExtension = if ($niagaraToolsetsExtensionLive) { 'VERIFIED_LIVE' } elseif ($engineNiagaraPatchApplied) { 'PRESENT_UNVERIFIED' } else { 'UNVERIFIED' }
        niagaraScratchPinAuthoring = if ($vibeUEAuthoringPatchApplied -and $engineNiagaraAuthoringPatchApplied) { 'PRESENT_VERIFIED' } else { 'UNVERIFIED' }
    }
    allowed = $allowed
    blocked = $blocked
    resultUnknownRule = 'After a possible mutation timeout, read back before retrying.'
    issues = @($issues)
    warnings = @($warnings)
}

$output = if ($View -eq 'compact') {
    [ordered]@{
        schema = 'ueagent-doctor-compact-v1'
        status = $status
        next = switch ($status) {
            'READY' { 'doctor -Profile live' }
            'HEALTHY' { 'LIVE_READ' }
            'DEGRADED' { 'CACHE_READ or targeted live read' }
            'OFFLINE' { 'SOURCE_CACHE_CONFIG_LOG_ONLY' }
            default { 'ROUTE_REPAIR_ONLY' }
        }
        checkedAtUtc = $receipt.checkedAtUtc
        endpoint = [ordered]@{ url = $Endpoint; loopbackSafe = $endpointSafe; listener = $listener }
        identity = [ordered]@{
            listenerPids = $listenerPids
            mcpSessionId = if ($sessionSnapshot) { [string]$sessionSnapshot.sessionId } else { $null }
            pluginFingerprint = $pluginFingerprint
        }
        engineVersion = $engineVersion
        capabilities = [ordered]@{
            officialToolSearch = ($missingMetaTools.Count -eq 0 -and $toolsListOk)
            vibeUE = ($vibeUEEnabled -and 'execute_python_code' -in $topToolNames)
            niagara = ($niagaraToolsetsEnabled -and $missingMetaTools.Count -eq 0)
            niagaraAuthoring = ($vibeUEAuthoringPatchApplied -and $engineNiagaraAuthoringPatchApplied)
        }
        issues = @($issues | Select-Object -First 3)
        warnings = @($warnings | Select-Object -First 3)
        expand = 'doctor -Profile live -View detail'
    }
} else { $receipt }

if ($Pretty) { $output | ConvertTo-Json -Depth 20 } else { $output | ConvertTo-Json -Depth 20 -Compress }
