[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RouteFile,
    [int]$TimeoutSec = 30,
    [switch]$ProbeAdvancedCapabilities,
    [ValidateSet('compact', 'detail')]
    [string]$View = 'compact',
    [int]$ProcessGuardMaxPrivateMemoryMB = 1024,
    [string]$OutFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')
$ueAgentRoot = Split-Path $PSScriptRoot -Parent
$gateway = Join-Path $PSScriptRoot 'mcp_gateway.ps1'
$issues = [Collections.Generic.List[string]]::new()

function Add-Issue($Message) {
    if (-not $issues.Contains([string]$Message)) { $issues.Add([string]$Message) }
}

$stackManifest = $null
try {
    $stackManifest = Read-UeAgentStackManifest $ueAgentRoot
} catch {
    Add-Issue $_.Exception.Message
}
$reliableProtocolVersion = if ($stackManifest) { [string]$stackManifest.runtime.reliable_protocol } else { '' }
$mutationTransport = if ($stackManifest) { [string]$stackManifest.runtime.mutation_transport } else { '' }
$requiredReliableTools = if ($stackManifest) { @($stackManifest.runtime.control_tools | ForEach-Object { [string]$_ }) } else { @() }

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

function Invoke-GatewayProbe($Action, $Url, $Seconds, $Toolset = $null, $SessionFile = $null, $DescribeDetail = $null, $MaxPrivateMemoryMB = 1024) {
    $hostExe = (Get-Command powershell.exe -ErrorAction Stop).Source
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $gateway,
        '-Action', $Action,
        '-Endpoint', $Url,
        '-TimeoutSec', $Seconds,
        '-ProcessGuardMaxPrivateMemoryMB', [string]$MaxPrivateMemoryMB,
        '-Envelope'
    )
    if ($Toolset) { $arguments += @('-Toolset', $Toolset) }
    if ($SessionFile) { $arguments += @('-SessionFile', $SessionFile) }
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

$RouteFile = (Resolve-Path -LiteralPath $RouteFile -ErrorAction Stop).Path
try { $route = Get-Content -Raw -LiteralPath $RouteFile | ConvertFrom-Json }
catch { throw "Invalid route file: $($_.Exception.Message)" }
if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported route schema: $($route.schema)" }

$routeTransport = [string]$route.transport
foreach ($pair in @(
    @('transport', 'native-http'),
    @('access', 'task-gated-write'),
    @('reliableProtocol', $reliableProtocolVersion),
    @('mutationTransport', $mutationTransport)
)) {
    if ([string]$route.($pair[0]) -ne [string]$pair[1]) {
        Add-Issue "Reliable route mismatch for $($pair[0]); expected $($pair[1])."
    }
}
$UProject = [string]$route.uProject
$EngineRoot = [string]$route.engineRoot
$Endpoint = [string]$route.endpoint

$projectRoot = $null
$projectName = $null
if (-not $UProject) {
    Add-Issue 'Route uProject is required.'
} elseif (-not (Test-Path -LiteralPath $UProject)) {
    Add-Issue "UProject not found: $UProject"
} else {
    $UProject = (Resolve-Path -LiteralPath $UProject).Path
    $projectRoot = Split-Path $UProject -Parent
    $projectName = [IO.Path]::GetFileNameWithoutExtension($UProject)
}

if (-not $EngineRoot) {
    Add-Issue 'Route engineRoot is required.'
} elseif (-not (Test-Path -LiteralPath $EngineRoot)) {
    Add-Issue "Engine root not found: $EngineRoot"
} else {
    $EngineRoot = (Resolve-Path -LiteralPath $EngineRoot).Path
}

if (-not $Endpoint) { Add-Issue 'Route endpoint is required.' }
$uri = $null
$endpointSafe = [Uri]::TryCreate($Endpoint, [UriKind]::Absolute, [ref]$uri)
if (-not $endpointSafe -or $uri.Scheme -ne 'http' -or
    $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    Add-Issue "Endpoint must be unauthenticated loopback HTTP: $Endpoint"
    $endpointSafe = $false
}

$listener = $false
$gatewaySessionFile = if ($projectRoot) { Join-Path $projectRoot 'Saved\UEAgent\mcp-session.json' } else { $null }
$pluginFingerprint = Get-PluginFingerprint $projectRoot $EngineRoot $projectName
$listenerPids = @()
$preflightProbe = $null
$toolsListOk = $false
$callViewAvailable = $false
$reliableStateRead = $false
$editorPidAvailable = $false
$reliableState = $null
$topToolNames = @()
$requiredTopTools = @('list_toolsets', 'describe_toolset', 'call_tool')
$missingMetaTools = @($requiredTopTools)
$missingReliableTools = @($requiredReliableTools)

if ($endpointSafe) {
    $listener = Test-TcpListener $uri
}

if ($listener) {
    $preflightProbe = Invoke-GatewayProbe 'preflight' $Endpoint $TimeoutSec $null $gatewaySessionFile $null $ProcessGuardMaxPrivateMemoryMB
    if ($preflightProbe.ok) {
        $toolsListOk = [bool]$preflightProbe.data.toolsList
        $callViewAvailable = [bool]$preflightProbe.data.callViewAvailable
        $reliableStateRead = [bool]$preflightProbe.data.reliableStateRead
        $reliableState = $preflightProbe.data.reliableState
        $topToolNames = @($preflightProbe.data.topLevelTools | Sort-Object -Unique)
        $missingMetaTools = @($requiredTopTools | Where-Object { $_ -notin $topToolNames })
        $missingReliableTools = @($requiredReliableTools | Where-Object { $_ -notin $topToolNames })
        foreach ($probeError in @($preflightProbe.data.errors)) {
            Add-Issue "MCP preflight: $probeError"
        }
    } else {
        Add-Issue "MCP preflight failed: $($preflightProbe.code) $($preflightProbe.message)"
    }
    if ($toolsListOk -and $missingMetaTools.Count -gt 0) {
        Add-Issue "Missing MCP meta tools: $($missingMetaTools -join ', ')"
    }
    if ($toolsListOk -and $missingReliableTools.Count -gt 0) {
        Add-Issue "Missing reliable UEAgent control tools: $($missingReliableTools -join ', ')"
    }
    if ($toolsListOk -and -not $callViewAvailable) {
        Add-Issue 'The running editor does not expose the native MCP detail=call schema.'
    }
    if ($reliableStateRead) {
        if (-not [bool]$reliableState.enabled) {
            Add-Issue 'The editor reliable execution kernel is present but disabled.'
        }
        if ([string]$reliableState.protocol_version -ne $reliableProtocolVersion) {
            Add-Issue "Reliable protocol mismatch: $([string]$reliableState.protocol_version)"
        }
        if (-not [string]$reliableState.editor_epoch) {
            Add-Issue 'Reliable state has no editor epoch.'
        }
        $editorPid = [int]$reliableState.editor_pid
        if ($editorPid -gt 0) {
            $editorPidAvailable = $true
            $listenerPids = @($editorPid)
        } else {
            Add-Issue 'Reliable state has no editor PID.'
        }
        if ($projectRoot -and [string]$reliableState.project -ne [IO.Path]::GetFileNameWithoutExtension($UProject)) {
            Add-Issue "Reliable state belongs to another project: $([string]$reliableState.project)"
        }
    }
}

$niagaraToolsetsExtensionLive = $false
if ($ProbeAdvancedCapabilities) {
    if (-not $listener -or -not $preflightProbe -or -not $preflightProbe.ok) {
        Add-Issue 'Advanced Niagara capability probe requires a healthy live MCP preflight.'
    } else {
        # Capability verification only needs tool names. Avoid full schemas here because the
        # Niagara system toolset is large enough to exceed the bounded gateway response budget.
        $systemProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_System' $gatewaySessionFile 'summary' $ProcessGuardMaxPrivateMemoryMB
        $componentProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_Component' $gatewaySessionFile 'summary' $ProcessGuardMaxPrivateMemoryMB
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

$status = if (-not $projectRoot -or -not $endpointSafe) {
    'BLOCKED'
} elseif (-not $listener -or -not $preflightProbe -or -not $preflightProbe.ok -or -not $toolsListOk) {
    'OFFLINE'
} elseif ($issues.Count -gt 0 -or $missingMetaTools.Count -gt 0 -or
          $missingReliableTools.Count -gt 0 -or -not $reliableStateRead) {
    'DEGRADED'
} else {
    'HEALTHY'
}

if ($status -eq 'HEALTHY' -and $projectRoot) {
    $invalidationPath = Join-Path $projectRoot 'Saved\UEAgent\doctor.invalidate.json'
    Remove-Item -LiteralPath $invalidationPath -Force -ErrorAction SilentlyContinue
}

$reliableKernelLive = ($reliableStateRead -and [bool]$reliableState.enabled -and
    [string]$reliableState.protocol_version -eq $reliableProtocolVersion -and
    -not [string]::IsNullOrWhiteSpace([string]$reliableState.editor_epoch) -and
    $editorPidAvailable -and $missingReliableTools.Count -eq 0)
$capabilities = [ordered]@{
    officialToolSearch = ($toolsListOk -and $missingMetaTools.Count -eq 0 -and $callViewAvailable)
    compactCallView = $callViewAvailable
    reliableKernel = $reliableKernelLive
    niagaraToolsetsExtension = if ($ProbeAdvancedCapabilities) { $niagaraToolsetsExtensionLive } else { $null }
}
$identity = [ordered]@{
    listenerPids = $listenerPids
    pluginFingerprint = $pluginFingerprint
    editorEpoch = if ($reliableStateRead) { [string]$reliableState.editor_epoch } else { $null }
}
$checkedAtUtc = [DateTime]::UtcNow.ToString('o')
$output = if ($View -eq 'compact') {
    $compact = [ordered]@{
        schema = 'ueagent-doctor-compact-v1'
        status = $status
        checkedAtUtc = $checkedAtUtc
        identity = $identity
    }
    if ($ProbeAdvancedCapabilities) { $compact.niagaraToolsetsExtension = $niagaraToolsetsExtensionLive }
    if ($reliableStateRead) {
        $busy = [ordered]@{}
        if ([string]$reliableState.active_command_id) { $busy.activeCommandId = [string]$reliableState.active_command_id }
        if (@($reliableState.queued_command_ids).Count) { $busy.queued = @($reliableState.queued_command_ids).Count }
        if ([bool]$reliableState.performance_frozen) { $busy.performanceFrozen = $true }
        if ([int]$reliableState.dirty_package_count) { $busy.dirtyPackageCount = [int]$reliableState.dirty_package_count }
        if ($busy.Count) { $compact.reliable = $busy }
    }
    if ($status -ne 'HEALTHY' -and $issues.Count) { $compact.issues = @($issues | Select-Object -First 3) }
    $compact
} else {
    $allowed = @(switch ($status) {
        'HEALTHY' { @('CACHE_ONLY', 'LIVE_READ', 'RELIABLE_MUTATION_QUEUE', 'SAVE_CAPABILITY_GATED') }
        'DEGRADED' { @('CACHE_ONLY', 'PROVEN_LIVE_READ_ONLY') }
        'OFFLINE' { @('SOURCE_CACHE_CONFIG_LOG_ONLY') }
        default { @('ROUTE_REPAIR_ONLY') }
    })
    $blocked = @(switch ($status) {
        'HEALTHY' { @('DIRECT_MUTATION_BYPASS', 'UNAUTHORISED_SAVE_DELETE_MOVE_MERGE', 'UNVERIFIED_CAPABILITY', 'UI_AUTOMATION') }
        'DEGRADED' { @('LIVE_MUTATION', 'SAVE', 'DESTRUCTIVE_ACTION', 'UI_AUTOMATION') }
        'OFFLINE' { @('LIVE_STATE_CLAIMS', 'LIVE_MUTATION', 'SAVE', 'UI_AUTOMATION') }
        default { @('MCP_OPERATION', 'UI_AUTOMATION') }
    })
    $detailReliable = if ($reliableStateRead) {
        [ordered]@{
            protocolVersion = [string]$reliableState.protocol_version
            editorEpoch = [string]$reliableState.editor_epoch
            editorPid = [int]$reliableState.editor_pid
            activeCommandId = [string]$reliableState.active_command_id
            lastReceiptId = [string]$reliableState.last_receipt_id
            queued = @($reliableState.queued_command_ids).Count
            performanceFrozen = [bool]$reliableState.performance_frozen
            dirtyPackageCount = [int]$reliableState.dirty_package_count
        }
    } else { $null }
    [ordered]@{
        schema = 'ueagent-doctor-v1'
        view = $View
        status = $status
        checkedAtUtc = $checkedAtUtc
        project = [ordered]@{ uproject = $UProject; engineRoot = $EngineRoot; routeFile = $RouteFile }
        endpoint = [ordered]@{ url = $Endpoint; transport = $routeTransport; loopbackSafe = $endpointSafe; listener = $listener }
        identity = $identity
        live = [ordered]@{
            toolsList = $toolsListOk
            topLevelTools = $topToolNames
            missingMetaTools = $missingMetaTools
            missingReliableTools = $missingReliableTools
            toolsetDiscoveryAvailable = ('list_toolsets' -in $topToolNames -and 'describe_toolset' -in $topToolNames)
            callViewAvailable = $callViewAvailable
            reliableStateRead = $reliableStateRead
            reliable = $detailReliable
            advancedCapabilityProbe = $ProbeAdvancedCapabilities.IsPresent
        }
        capabilities = $capabilities
        allowed = $allowed
        blocked = $blocked
        resultUnknownRule = 'Poll the command receipt first; if it is unavailable, recover/read back before retrying. Never blind-retry a mutation.'
        issues = @($issues)
    }
}

$json = if ($Pretty) { $output | ConvertTo-Json -Depth 20 } else { $output | ConvertTo-Json -Depth 20 -Compress }
if ($OutFile) {
    $parent = Split-Path $OutFile -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
    [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
} else {
    $json
}
