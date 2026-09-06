[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RouteFile,
    [int]$TimeoutSec = 30,
    [switch]$ProbeCapabilities,
    [switch]$ProbeAdvancedCapabilities,
    [ValidateSet('compact', 'detail')]
    [string]$View = 'compact',
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
$authoritativeReadTools = @('ueagent_snapshot', 'ueagent_batch_read')
$mutationTools = @('ueagent_submit', 'ueagent_get_job')
$saveTools = @('ueagent_save')
$recoveryTools = @('ueagent_recover', 'ueagent_cancel')

function Test-ToolInputEnumValue($Tools, $ToolName, $PropertyName, $ExpectedValue) {
    $tool = @($Tools | Where-Object { [string]$_.name -eq [string]$ToolName } | Select-Object -First 1)
    if ($tool.Count -eq 0 -or -not $tool[0].inputSchema.properties) { return $false }
    $property = $tool[0].inputSchema.properties.($PropertyName)
    return $null -ne $property -and [string]$ExpectedValue -in @($property.enum | ForEach-Object { [string]$_ })
}

function Invoke-GatewayProbe($Action, $Url, $Seconds, $Toolset = $null, $SessionFile = $null, $DescribeDetail = $null, $Tool = $null) {
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
    if ($Tool) { $arguments += @('-Tool', $Tool) }
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

$UProject = [string]$route.uProject
$EngineRoot = [string]$route.engineRoot
$Endpoint = [string]$route.endpoint

$projectRoot = $null
if (-not $UProject) {
    Add-Issue 'Route uProject is required.'
} elseif (-not (Test-Path -LiteralPath $UProject)) {
    Add-Issue "UProject not found: $UProject"
} else {
    $UProject = (Resolve-Path -LiteralPath $UProject).Path
    $projectRoot = Split-Path $UProject -Parent
}

if (-not $Endpoint) { Add-Issue 'Route endpoint is required.' }
$uri = $null
$endpointSafe = [Uri]::TryCreate($Endpoint, [UriKind]::Absolute, [ref]$uri)
if (-not $endpointSafe -or $uri.Scheme -ne 'http' -or
    $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    Add-Issue "Endpoint must be unauthenticated loopback HTTP: $Endpoint"
    $endpointSafe = $false
}

$gatewaySessionFile = if ($projectRoot) { Join-Path $projectRoot 'Saved\UEAgent\mcp-session.json' } else { $null }
$stateProbe = $null
$capabilityProbe = $null
$capabilitiesProbed = $ProbeCapabilities.IsPresent -or $ProbeAdvancedCapabilities.IsPresent
$toolsListOk = $false
$callViewAvailable = $false
$reliableStateRead = $false
$editorPidAvailable = $false
$editorPid = 0
$reliableState = $null
$topToolNames = @()
$requiredTopTools = @('list_toolsets', 'describe_toolset', 'call_tool')
$missingMetaTools = @($requiredTopTools)

if ($endpointSafe) {
    $stateProbe = Invoke-GatewayProbe 'direct.call' $Endpoint $TimeoutSec $null $gatewaySessionFile $null 'ueagent_state'
    if ($stateProbe.ok) {
        $reliableState = $stateProbe.data
        if ($reliableState -and [string]$reliableState.protocol_version -and
            [string]$reliableState.editor_epoch) {
            $reliableStateRead = $true
        } else {
            Add-Issue 'ueagent_state returned no protocol_version or editor_epoch.'
        }
    } else {
        Add-Issue "MCP state read failed: $($stateProbe.code) $($stateProbe.message)"
    }

    if ($capabilitiesProbed) {
        $capabilityProbe = Invoke-GatewayProbe 'tools.list' $Endpoint $TimeoutSec $null $gatewaySessionFile
        if ($capabilityProbe.ok) {
            $listedTools = @($capabilityProbe.data)
            $topToolNames = @($listedTools | ForEach-Object { [string]$_.name } | Sort-Object -Unique)
            $toolsListOk = $true
            $callViewAvailable = Test-ToolInputEnumValue $listedTools 'describe_toolset' 'detail' 'call'
            $missingMetaTools = @($requiredTopTools | Where-Object { $_ -notin $topToolNames })
        } else {
            Add-Issue "MCP capability probe failed: $($capabilityProbe.code) $($capabilityProbe.message)"
        }
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
        } else {
            Add-Issue 'Reliable state has no editor PID.'
        }
        if ($projectRoot -and ([IO.Path]::GetFullPath([string]$reliableState.project_file)).Replace('\','/') -ine ([IO.Path]::GetFullPath($UProject)).Replace('\','/')) {
            Add-Issue "Reliable state belongs to another project: $([string]$reliableState.project_file)"
        }
    }
}

$niagaraToolsetsExtensionLive = $false
$niagaraParameterHierarchyLive = $false
$niagaraScratchAuthoringLive = $false
if ($ProbeAdvancedCapabilities) {
    if (-not $stateProbe -or -not $stateProbe.ok -or -not $capabilityProbe -or -not $capabilityProbe.ok) {
        Add-Issue 'Advanced Niagara capability probe requires a healthy live route and capability probe.'
    } else {
        # Capability verification only needs tool names. Avoid full schemas here because the
        # Niagara system toolset is large enough to exceed the bounded gateway response budget.
        $systemProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_System' $gatewaySessionFile 'summary'
        $componentProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'NiagaraToolsets.NiagaraToolset_Component' $gatewaySessionFile 'summary'
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
            $niagaraParameterHierarchyLive = @('GetUserParameterHierarchy', 'SetUserParameterCategory' | Where-Object {
                $suffix = ".$_"
                -not @($systemNames | Where-Object { ([string]$_).EndsWith($suffix) }).Count
            }).Count -eq 0
            if (-not $niagaraParameterHierarchyLive) {
                Add-Issue 'Running editor is missing Niagara user-parameter hierarchy tools.'
            }
        }
        $scratchProbe = Invoke-GatewayProbe 'toolset.describe' $Endpoint $TimeoutSec 'VibeUE.NiagaraScratchPadService' $gatewaySessionFile 'summary'
        if ($scratchProbe.ok) {
            $scratchNames = @($scratchProbe.data.tools.name)
            $missingScratchTools = @(
                @('CreateEmitterAsset', 'AddParameterInputNode', 'AddParticleReadNode',
                  'CreateRasterizationGrid3DUserParameter', 'RefreshModuleCallNodes', 'RemoveScratchPin') |
                    Where-Object {
                        $suffix = ".$_"
                        -not @($scratchNames | Where-Object { ([string]$_).EndsWith($suffix) }).Count
                    }
            )
            $niagaraScratchAuthoringLive = $missingScratchTools.Count -eq 0
            if ($missingScratchTools.Count) {
                Add-Issue "Running editor is missing scratch authoring tools: $($missingScratchTools -join ', ')"
            }
        } else {
            Add-Issue 'Advanced scratch authoring description failed.'
        }
    }
}

$reliableProjectMatches = -not $reliableStateRead -or -not $projectRoot -or
    ([IO.Path]::GetFullPath([string]$reliableState.project_file)).Replace('\','/') -ieq ([IO.Path]::GetFullPath($UProject)).Replace('\','/')
$editorLive = ($reliableStateRead -and [bool]$reliableState.enabled -and
    [string]$reliableState.protocol_version -eq $reliableProtocolVersion -and
    -not [string]::IsNullOrWhiteSpace([string]$reliableState.editor_epoch) -and
    $editorPidAvailable -and $reliableProjectMatches)
$authoritativeReadLive = if ($capabilitiesProbed) {
    $editorLive -and (@($authoritativeReadTools | Where-Object { $_ -in $topToolNames }).Count -gt 0)
} else { $null }
$mutationLive = if ($capabilitiesProbed) {
    $editorLive -and (@($mutationTools | Where-Object { $_ -notin $topToolNames }).Count -eq 0)
} else { $null }
$saveLive = if ($capabilitiesProbed) {
    $mutationLive -and (@($saveTools | Where-Object { $_ -notin $topToolNames }).Count -eq 0)
} else { $null }
$recoveryLive = if ($capabilitiesProbed) {
    $editorLive -and (@($recoveryTools | Where-Object { $_ -notin $topToolNames }).Count -eq 0)
} else { $null }
$status = if (-not $projectRoot -or -not $endpointSafe) {
    'BLOCKED'
} elseif (-not $stateProbe -or -not $stateProbe.ok -or -not $reliableStateRead) {
    'OFFLINE'
} elseif (-not $editorLive) {
    'DEGRADED'
} else {
    'HEALTHY'
}

$capabilities = [ordered]@{
    officialToolSearch = if ($capabilitiesProbed) { ($toolsListOk -and $missingMetaTools.Count -eq 0 -and $callViewAvailable) } else { $null }
    compactCallView = if ($capabilitiesProbed) { $callViewAvailable } else { $null }
    editorLive = $editorLive
    authoritativeRead = $authoritativeReadLive
    mutation = $mutationLive
    save = $saveLive
    recovery = $recoveryLive
    niagaraToolsetsExtension = if ($ProbeAdvancedCapabilities) { $niagaraToolsetsExtensionLive } else { $null }
    niagaraParameterHierarchy = if ($ProbeAdvancedCapabilities) { $niagaraParameterHierarchyLive } else { $null }
    niagaraScratchAuthoring = if ($ProbeAdvancedCapabilities) { $niagaraScratchAuthoringLive } else { $null }
}
$identity = [ordered]@{
    editorPid = if ($editorPidAvailable) { $editorPid } else { $null }
    editorEpoch = if ($reliableStateRead) { [string]$reliableState.editor_epoch } else { $null }
}
$checkedAtUtc = [DateTime]::UtcNow.ToString('o')
$output = if ($View -eq 'compact') {
    $compact = [ordered]@{
        schema = 'ueagent-doctor-compact-v1'
        status = $status
        checkedAtUtc = $checkedAtUtc
        identity = $identity
        capabilities = $capabilities
    }
    if ($ProbeAdvancedCapabilities) { $compact.niagaraToolsetsExtension = $niagaraToolsetsExtensionLive }
    if ($reliableStateRead) {
        $busy = [ordered]@{}
        if ([string]$reliableState.active_command_id) { $busy.activeCommandId = [string]$reliableState.active_command_id }
        if ([int]$reliableState.queued_jobs -gt 0) { $busy.queued = [int]$reliableState.queued_jobs }
        if ([bool]$reliableState.performance_frozen) { $busy.performanceFrozen = $true }
        if ([int]$reliableState.dirty_package_count) { $busy.dirtyPackageCount = [int]$reliableState.dirty_package_count }
        if ($busy.Count) { $compact.reliable = $busy }
    }
    if ($issues.Count) { $compact.issues = @($issues | Select-Object -First 3) }
    $compact
} else {
    $detailReliable = if ($reliableStateRead) {
        [ordered]@{
            protocolVersion = [string]$reliableState.protocol_version
            editorEpoch = [string]$reliableState.editor_epoch
            editorPid = [int]$reliableState.editor_pid
            activeCommandId = [string]$reliableState.active_command_id
            lastReceiptId = [string]$reliableState.last_receipt_id
            queued = [int]$reliableState.queued_jobs
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
        endpoint = [ordered]@{ url = $Endpoint; loopbackSafe = $endpointSafe; gatewayPreflight = [bool]($stateProbe -and $stateProbe.ok) }
        identity = $identity
        live = [ordered]@{
            capabilitiesProbed = $capabilitiesProbed
            toolsList = if ($capabilitiesProbed) { $toolsListOk } else { $null }
            topLevelTools = $topToolNames
            missingMetaTools = if ($capabilitiesProbed) { $missingMetaTools } else { $null }
            missingAuthoritativeReadTools = if ($capabilitiesProbed) { @($authoritativeReadTools | Where-Object { $_ -notin $topToolNames }) } else { $null }
            missingMutationTools = if ($capabilitiesProbed) { @($mutationTools | Where-Object { $_ -notin $topToolNames }) } else { $null }
            missingSaveTools = if ($capabilitiesProbed) { @($saveTools | Where-Object { $_ -notin $topToolNames }) } else { $null }
            missingRecoveryTools = if ($capabilitiesProbed) { @($recoveryTools | Where-Object { $_ -notin $topToolNames }) } else { $null }
            toolsetDiscoveryAvailable = ('list_toolsets' -in $topToolNames -and 'describe_toolset' -in $topToolNames)
            callViewAvailable = $callViewAvailable
            reliableStateRead = $reliableStateRead
            reliable = $detailReliable
            advancedCapabilityProbe = $ProbeAdvancedCapabilities.IsPresent
        }
        capabilities = $capabilities
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
