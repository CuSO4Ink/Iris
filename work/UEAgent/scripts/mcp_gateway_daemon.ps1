[CmdletBinding()]
param(
    [int]$ListenPort = 18765,
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp',
    [string]$SessionFile,
    [int]$SessionTtlSec = 900,
    [int]$TimeoutSec = 120,
    [int]$ParentPid = 0,
    [int]$MaxPrivateMemoryMB = 2048,
    [int]$HardRequestGraceSec = 15,
    [int]$MaxRequests = 1000,
    [int]$MaxUptimeSec = 7200,
    [int]$IdleTtlSec = 900,
    [int64]$MaxRequestBytes = 8388608,
    [int64]$MaxResponseBytes = 67108864,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http

$gateway = Join-Path $PSScriptRoot 'mcp_gateway.ps1'
$daemonEndpoint = $Endpoint
$daemonSessionFile = $SessionFile
$daemonSessionTtlSec = $SessionTtlSec
$daemonTimeoutSec = $TimeoutSec
. $gateway -AsLibrary
$Endpoint = $daemonEndpoint
$SessionFile = $daemonSessionFile
$SessionTtlSec = $daemonSessionTtlSec
$TimeoutSec = $daemonTimeoutSec
$null = Assert-LoopbackEndpoint $Endpoint
if (-not $SessionFile) {
    throw 'mcp_gateway_daemon.ps1 requires -SessionFile <project>\Saved\UEAgent\mcp-session.json.'
}

function Convert-ToJson($Object) {
    if ($Pretty) { return ($Object | ConvertTo-Json -Depth 80) }
    return ($Object | ConvertTo-Json -Depth 80 -Compress)
}

function Write-HttpJson($Context, $Object, $StatusCode = 200) {
    $json = Convert-ToJson $Object
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    if ($MaxResponseBytes -gt 0 -and $bytes.LongLength -gt $MaxResponseBytes) {
        throw "Gateway response exceeds ${MaxResponseBytes} bytes. Use a projection or a smaller detail view."
    }
    $Context.Response.StatusCode = $StatusCode
    $Context.Response.ContentType = 'application/json; charset=utf-8'
    $Context.Response.ContentLength64 = $bytes.Length
    $Context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $Context.Response.OutputStream.Close()
}

function Read-HttpRequestBody($Context) {
    $declared = $Context.Request.ContentLength64
    if ($MaxRequestBytes -gt 0 -and $declared -gt $MaxRequestBytes) {
        throw "Gateway request exceeds ${MaxRequestBytes} bytes."
    }
    $input = $null
    $buffer = $null
    $memory = $null
    try {
        $input = $Context.Request.InputStream
        $memory = [IO.MemoryStream]::new()
        $buffer = New-Object byte[] 65536
        while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($MaxRequestBytes -gt 0 -and ($memory.Length + $read) -gt $MaxRequestBytes) {
                throw "Gateway request exceeds ${MaxRequestBytes} bytes."
            }
            $memory.Write($buffer, 0, $read)
        }
        return [Text.Encoding]::UTF8.GetString($memory.ToArray())
    } finally {
        if ($memory) { $memory.Dispose() }
        if ($input) { $input.Dispose() }
    }
}

$client = [Net.Http.HttpClient]::new()
$client.Timeout = [Threading.Timeout]::InfiniteTimeSpan
$daemonStartedUtc = [DateTime]::UtcNow
$lastRequestUtc = $daemonStartedUtc
$requestCount = 0
$headers = $null
$sessionReused = $false
$sessionMode = 'new'
$lastProbeMs = $null
$reusedToolsList = $null
$toolsListCache = $null

function Invoke-DaemonMcpRpc($Method, $Params = $null, $Id = 2, $Timeout = $daemonTimeoutSec) {
    Invoke-McpRpc $Endpoint $script:headers $Method $Params $Id $Timeout $script:client $MaxResponseBytes
}

function Invoke-DaemonTopTool($Name, $Arguments, $Timeout = $daemonTimeoutSec) {
    Invoke-TopTool $Endpoint $script:headers $Name $Arguments $Timeout $script:client $MaxResponseBytes
}

function Get-DaemonBudgetFailure {
    if ($ParentPid -gt 0) {
        try {
            $parent = Get-Process -Id $ParentPid -ErrorAction Stop
            if ($parent.ProcessName -notmatch '(?i)(Editor|UnrealEditor)$') { return 'parent_invalid' }
        } catch { return 'parent_exited' }
    }
    if ($MaxRequests -gt 0 -and $requestCount -ge $MaxRequests) { return 'request_budget' }
    $uptime = ([DateTime]::UtcNow - $daemonStartedUtc).TotalSeconds
    if ($MaxUptimeSec -gt 0 -and $uptime -ge $MaxUptimeSec) { return 'uptime_budget' }
    $idle = ([DateTime]::UtcNow - $lastRequestUtc).TotalSeconds
    if ($IdleTtlSec -gt 0 -and $idle -ge $IdleTtlSec) { return 'idle_budget' }
    if ($MaxPrivateMemoryMB -gt 0) {
        try {
            $privateMb = (Get-Process -Id $PID -ErrorAction Stop).PrivateMemorySize64 / 1MB
            if ($privateMb -ge $MaxPrivateMemoryMB) { return 'memory_budget' }
        } catch { return 'daemon_exited' }
    }
    return $null
}

function Ensure-DaemonSession {
    if ($script:headers) { return }
    $script:lastProbeMs = $null
    $cached = Read-McpSession $Endpoint $SessionFile
    if ($cached) {
        $candidate = Get-McpSessionHeaders $cached.sessionId
        $probeTimer = [Diagnostics.Stopwatch]::StartNew()
        try {
            $probe = Invoke-McpRpc $Endpoint $candidate 'tools/list' @{} 2 ([Math]::Min($TimeoutSec, 10)) $script:client $MaxResponseBytes
            if ($probe -and -not $probe.error) {
                $script:headers = $candidate
                $script:sessionReused = $true
                $script:sessionMode = 'reused'
                $script:reusedToolsList = $probe
                $script:toolsListCache = $probe
                return
            }
        } catch {
            # A stopped editor or expired session is replaced below.
        } finally {
            $script:lastProbeMs = [int]$probeTimer.ElapsedMilliseconds
        }
    }
    $script:headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
    $script:sessionReused = $false
    $script:sessionMode = 'new'
    $script:reusedToolsList = $null
    $script:toolsListCache = $null
}

function Invoke-DaemonAction($Request) {
    $action = [string]$Request.action
    if (-not $action) { throw 'Request must include action.' }
    $probeTools = if ($script:reusedToolsList) { $script:reusedToolsList } else { $script:toolsListCache }
    $script:reusedToolsList = $null
    $schemaCacheable = $action -in @('tools.list', 'toolsets.list', 'toolset.describe')
    $schemaPath = if ($Request.schemaCacheFile) { [string]$Request.schemaCacheFile } else { $null }
    $schemaTtl = if ($Request.schemaCacheTtlSec) { [int]$Request.schemaCacheTtlSec } else { 300 }
    $schemaToolset = if ($action -eq 'toolset.describe') { [string]$Request.toolset } else { '' }
    $schemaDetail = if ($action -eq 'toolset.describe') {
        if ($Request.describeDetail) { [string]$Request.describeDetail }
        elseif ($Request.detail) { [string]$Request.detail }
        else { 'call' }
    } else { '' }
    $schemaToolName = if ($action -eq 'toolset.describe') {
        if ($Request.describeToolName) { [string]$Request.describeToolName }
        elseif ($Request.toolName) { [string]$Request.toolName }
        else { '' }
    } else { '' }
    $schemaSessionId = if ($script:headers -and $script:headers['Mcp-Session-Id']) { [string]$script:headers['Mcp-Session-Id'] } else { '' }
    if ($schemaCacheable -and $schemaPath) {
        $cached = Read-SchemaCacheEntry $action $Endpoint $schemaToolset $schemaPath $schemaDetail $schemaToolName $schemaSessionId
        if ($cached) { return $cached.data }
    }
    $projection = if ($Request.PSObject.Properties.Name -contains 'projection') { $Request.projection } else { $null }
    if ($null -eq $projection -and $Request.view -in @('summary', 'refs')) {
        $profile = if ($Request.view -eq 'refs') { 'refs' } else { 'compact' }
        $projection = Get-ProjectionProfile $profile
    }
    if ($null -eq $projection -and $Request.intent) {
        $intentProfile = Get-IntentProjectionProfile ([string]$Request.intent)
        if ($intentProfile) { $projection = Get-ProjectionProfile $intentProfile }
    }
    if ($null -eq $projection -and $Request.projectionProfile) {
        $projection = Get-ProjectionProfile ([string]$Request.projectionProfile)
    }
    switch ($action) {
        'preflight' {
            $top = @()
            $errors = [Collections.Generic.List[string]]::new()
            $toolsOk = $false
            $levelOk = $false
            $level = $null
            try {
                $raw = if ($probeTools) { $probeTools } else {
                    Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
                }
                if ($raw.error) { throw 'tools/list returned an error.' }
                $top = @($raw.result.tools | ForEach-Object { [string]$_.name } | Sort-Object -Unique)
                $toolsOk = $true
            } catch { $errors.Add("tools/list: $($_.Exception.Message)") }
            if ($toolsOk -and 'call_tool' -in $top) {
                try {
                    $raw = Invoke-DaemonTopTool 'call_tool' @{
                        toolset_name = 'editor_toolset.toolsets.scene.SceneTools'
                        tool_name = 'get_current_level'
                        arguments = @{}
                    } $TimeoutSec $script:client
                    $level = Normalize-ToolResult $raw
                    $levelOk = -not ($level -is [hashtable] -and $level.ok -eq $false)
                } catch { $errors.Add("current_level: $($_.Exception.Message)") }
            }
            return @{ toolsList = $toolsOk; topLevelTools = $top; currentLevelRead = $levelOk; currentLevel = $level; errors = @($errors) }
        }
        'ping' {
            $raw = if ($probeTools) { $probeTools } else {
                Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
            }
            return @{ reachable = (-not $raw.error); topLevelToolCount = @($raw.result.tools).Count }
        }
        'tools.list' {
            $raw = if ($probeTools) { $probeTools } else {
                Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
            }
            $data = $raw.result.tools
            if ($schemaPath) { Write-SchemaCacheEntry $action $Endpoint $schemaToolset $data $schemaPath $schemaTtl $schemaDetail $schemaToolName $schemaSessionId }
            return $data
        }
        'toolsets.list' {
            $data = Normalize-ToolResult (Invoke-DaemonTopTool 'list_toolsets' @{} $TimeoutSec)
            if ($schemaPath) { Write-SchemaCacheEntry $action $Endpoint $schemaToolset $data $schemaPath $schemaTtl $schemaDetail $schemaToolName $schemaSessionId }
            return $data
        }
        'toolset.describe' {
            if (-not $Request.toolset) { throw 'toolset.describe requires toolset.' }
            $describe = @{ toolset_name = [string]$Request.toolset }
            $describeDetail = if ($Request.describeDetail) { [string]$Request.describeDetail } elseif ($Request.detail) { [string]$Request.detail } else { 'call' }
            $describe.detail = $describeDetail
            if ($Request.describeToolName) { $describe.tool_name = [string]$Request.describeToolName }
            if ($Request.toolName) { $describe.tool_name = [string]$Request.toolName }
            $data = Normalize-ToolResult (Invoke-DaemonTopTool 'describe_toolset' $describe $TimeoutSec)
            if ($describeDetail -eq 'call' -and $data -is [hashtable] -and $data.ok -eq $false -and [string]$data.toolError -match "detail must") {
                # v2 servers do not know call; keep the daemon usable until the editor is rebuilt.
                $describeDetail = 'full'
                $describe.detail = $describeDetail
                $data = Normalize-ToolResult (Invoke-DaemonTopTool 'describe_toolset' $describe $TimeoutSec)
            }
            if ($schemaDetail -eq 'call' -and -not ($data -is [hashtable] -and $data.ok -eq $false)) {
                $data = Convert-ToCallView $data $schemaToolset $schemaToolName
            }
            if ($schemaPath) { Write-SchemaCacheEntry $action $Endpoint $schemaToolset $data $schemaPath $schemaTtl $schemaDetail $schemaToolName $schemaSessionId }
            return $data
        }
        'tool.call' {
            $toolset = [string]$Request.toolset
            $tool = [string]$Request.tool
            if (-not $tool) { throw 'tool.call requires tool.' }
            if (-not $toolset -and $tool.Contains('.')) {
                $index = $tool.LastIndexOf('.')
                $toolset = $tool.Substring(0, $index)
                $tool = $tool.Substring($index + 1)
            }
            $arguments = if ($Request.PSObject.Properties.Name -contains 'arguments') { $Request.arguments } else { @{} }
            $call = @{ tool_name = $tool; arguments = $arguments }
            if ($toolset) { $call.toolset_name = $toolset }
            if ($null -ne $projection) { $call.projection = $projection }
            return (Normalize-ToolResult (Invoke-DaemonTopTool 'call_tool' $call $TimeoutSec))
        }
        'direct.call' {
            if (-not $Request.tool) { throw 'direct.call requires tool.' }
            $arguments = if ($Request.PSObject.Properties.Name -contains 'arguments') { $Request.arguments } else { @{} }
            return (Normalize-ToolResult (Invoke-DaemonTopTool ([string]$Request.tool) $arguments $TimeoutSec))
        }
        'script.execute' {
            $scriptText = [string]$Request.script
            if (-not $scriptText -and $Request.scriptFile) {
                if (-not (Test-Path -LiteralPath $Request.scriptFile)) { throw "scriptFile not found: $($Request.scriptFile)" }
                $scriptText = Get-Content -Raw -LiteralPath $Request.scriptFile
            }
            if (-not $scriptText) { throw 'script.execute requires script or scriptFile.' }
            if ($scriptText -match '(?mi)^\s*(?:import\s+unreal(?:\s|,|$)|from\s+unreal(?:\s|\.|$))') {
                throw 'wrong_script_backend: script.execute targets ProgrammaticToolset and cannot run Unreal Python. Use python.execute or direct.call execute_python_code.'
            }
            $call = @{
                toolset_name = 'editor_toolset.toolsets.programmatic.ProgrammaticToolset'
                tool_name = 'execute_tool_script'
                arguments = @{ script = $scriptText }
            }
            if ($null -ne $projection) { $call.projection = $projection }
            return (Normalize-ToolResult (Invoke-DaemonTopTool 'call_tool' $call $TimeoutSec))
        }
        'python.execute' {
            $scriptText = [string]$Request.script
            $scriptName = '<ueagent-python>'
            if (-not $scriptText -and $Request.scriptFile) {
                if (-not (Test-Path -LiteralPath $Request.scriptFile)) { throw "scriptFile not found: $($Request.scriptFile)" }
                $resolvedPath = (Resolve-Path -LiteralPath $Request.scriptFile).Path
                $scriptText = Get-Content -Raw -LiteralPath $resolvedPath
                $scriptName = $resolvedPath
            }
            if (-not $scriptText) { throw 'python.execute requires script or scriptFile.' }
            $bootstrap = New-IsolatedPythonBootstrap $scriptText $scriptName
            return (Normalize-ToolResult (Invoke-DaemonTopTool 'execute_python_code' @{ code=$bootstrap } $TimeoutSec))
        }
        'level.current' {
            return (Normalize-ToolResult (Invoke-DaemonTopTool 'call_tool' @{
                toolset_name = 'editor_toolset.toolsets.scene.SceneTools'
                tool_name = 'get_current_level'
                arguments = @{}
            } $TimeoutSec))
        }
        default { throw "Unknown action: $action" }
    }
}

$listener = [Net.HttpListener]::new()
$prefix = "http://127.0.0.1:$ListenPort/"
$listener.Prefixes.Add($prefix)
$listener.Start()
Write-Output (Convert-ToJson @{ ready = $true; listen = $prefix; endpoint = $Endpoint })

try {
    $pendingContext = $null
    while ($listener.IsListening) {
        if (Get-DaemonBudgetFailure) { break }
        if (-not $pendingContext) { $pendingContext = $listener.GetContextAsync() }
        if (-not $pendingContext.Wait(1000)) { continue }
        $context = $pendingContext.Result
        $pendingContext = $null
        $lastRequestUtc = [DateTime]::UtcNow
        $requestCount++
        $stop = $false
        $requestGuardArmed = $false
        try {
            Start-GatewayProcessGuard $TimeoutSec $HardRequestGraceSec $MaxPrivateMemoryMB
            $requestGuardArmed = $true
            if ($context.Request.HttpMethod -ne 'POST') {
                Write-HttpJson $context @{ ok = $false; code = 'method_not_allowed' } 405
                continue
            }
            $body = Read-HttpRequestBody $context
            if (-not $body.Trim()) { throw 'Empty request body.' }
            $request = $body | ConvertFrom-Json
            if ($request.endpoint -and [string]$request.endpoint -ne $Endpoint) {
                throw 'Daemon endpoint is fixed at startup; request endpoint differs.'
            }
            if ($request.action -eq 'daemon.ping') {
                Write-HttpJson $context @{ ok = $true; service = 'ueagent-gateway-daemon'; protocol = 'ueagent-gateway-daemon-v1' }
            } elseif ($request.action -in @('close', 'shutdown')) {
                Invalidate-DoctorReceipt 'session_closed'
                Close-McpSession $Endpoint $script:headers
                Remove-McpSessionFile $SessionFile
                Write-HttpJson $context @{ ok = $true; action = [string]$request.action; closed = $true }
                $stop = $true
            } else {
                Ensure-DaemonSession
                $explicitResponseMode = ($request.PSObject.Properties.Name -contains 'dataOnly') -or
                    ($request.PSObject.Properties.Name -contains 'envelope')
                if (-not $explicitResponseMode -and
                    -not ($request.PSObject.Properties.Name -contains 'diagnostics' -and [bool]$request.diagnostics) -and
                    [string]$request.action -ne 'preflight') {
                    $request | Add-Member -NotePropertyName dataOnly -NotePropertyValue $true
                }
                $data = Invoke-DaemonAction $request
                $persisted = Write-McpSession $Endpoint $script:headers $SessionFile $SessionTtlSec
                if ($request.PSObject.Properties.Name -contains 'dataOnly' -and [bool]$request.dataOnly) {
                    Write-HttpJson $context $data
                } else {
                    $reply = @{
                        ok = $true
                        action = [string]$request.action
                        data = $data
                    }
                    if ($request.PSObject.Properties.Name -contains 'diagnostics' -and [bool]$request.diagnostics) {
                        $reply.transport = @{
                            mode = 'daemon'
                            sessionMode = $script:sessionMode
                            sessionReused = $script:sessionReused
                            sessionPersisted = $persisted
                            sessionProbeMs = $script:lastProbeMs
                        }
                    }
                    Write-HttpJson $context $reply
                }
            }
        } catch {
            Invalidate-DoctorReceipt 'daemon_error'
            $script:headers = $null
            $script:reusedToolsList = $null
            $script:toolsListCache = $null
            Remove-McpSessionFile $SessionFile
            try {
                Write-HttpJson $context @{ ok = $false; code = 'daemon_error'; message = $_.Exception.Message } 500
            } catch {
                try {
                    $context.Response.StatusCode = 500
                    $context.Response.ContentLength64 = 0
                    $context.Response.OutputStream.Close()
                } catch { }
            }
        } finally {
            try { $context.Response.Close() } catch { }
            try { $context.Close() } catch { }
            if ($requestGuardArmed) { Stop-GatewayProcessGuard }
        }
        if ($stop -or (Get-DaemonBudgetFailure)) { break }
    }
} finally {
    Close-McpSession $Endpoint $script:headers
    $listener.Stop()
    $listener.Close()
    $client.Dispose()
}
