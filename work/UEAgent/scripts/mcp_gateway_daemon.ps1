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
    $cached = Read-McpSession $Endpoint $SessionFile
    if ($cached) {
        $script:headers = Get-McpSessionHeaders $cached.sessionId
        $script:sessionReused = $true
        $script:sessionMode = 'reused'
        return
    }
    $script:headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
    $script:sessionReused = $false
    $script:sessionMode = 'new'
}

function Invoke-DaemonAction($Request) {
    $action = [string]$Request.action
    if (-not $action) { throw 'Request must include action.' }
    $schemaCacheable = $action -in @('tools.list', 'toolsets.list', 'toolset.describe')
    $schemaPath = if ($Request.schemaCacheFile) { [string]$Request.schemaCacheFile } else { $null }
    $schemaTtl = if ($Request.schemaCacheTtlSec) { [int]$Request.schemaCacheTtlSec } else { 300 }
    $schemaToolset = if ($action -eq 'toolset.describe') { [string]$Request.toolset } else { '' }
    $schemaDetail = if ($action -eq 'toolset.describe') {
        if ($Request.describeDetail) { [string]$Request.describeDetail }
        else { 'call' }
    } else { '' }
    $schemaToolName = if ($action -eq 'toolset.describe') {
        if ($Request.describeToolName) { [string]$Request.describeToolName }
        else { '' }
    } else { '' }
    $schemaSessionId = if ($script:headers -and $script:headers['Mcp-Session-Id']) { [string]$script:headers['Mcp-Session-Id'] } else { '' }
    if ($schemaCacheable -and $schemaPath) {
        $cached = Read-SchemaCacheEntry $action $Endpoint $schemaToolset $schemaPath $schemaDetail $schemaToolName $schemaSessionId
        if ($cached) { return $cached.data }
    }
    $projection = Resolve-GatewayProjection $Request
    switch ($action) {
        'preflight' {
            $top = @()
            $callViewAvailable = $false
            $errors = [Collections.Generic.List[string]]::new()
            $toolsOk = $false
            $reliableStateOk = $false
            $reliableState = $null
            try {
                $raw = Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
                if ($raw.error) { throw 'tools/list returned an error.' }
                $listedTools = @($raw.result.tools)
                $top = @($listedTools | ForEach-Object { [string]$_.name } | Sort-Object -Unique)
                $callViewAvailable = Test-ToolInputEnumValue $listedTools 'describe_toolset' 'detail' 'call'
                $toolsOk = $true
            } catch {
                if (Test-McpSessionInvalidError $_) { throw }
                $errors.Add("tools/list: $($_.Exception.Message)")
            }
            if ($toolsOk -and 'ueagent_state' -in $top) {
                try {
                    $raw = Invoke-DaemonTopTool 'ueagent_state' @{} $TimeoutSec
                    $reliableState = Normalize-ToolResult $raw
                    if ($reliableState.ok -eq $false -or $reliableState.success -eq $false -or
                        -not [string]$reliableState.protocol_version -or -not [string]$reliableState.editor_epoch) {
                        throw 'ueagent_state returned no usable protocol/editor identity.'
                    }
                    $reliableStateOk = $true
                } catch {
                    if (Test-McpSessionInvalidError $_) { throw }
                    $errors.Add("ueagent_state: $($_.Exception.Message)")
                }
            }
            return @{
                toolsList = $toolsOk
                topLevelTools = $top
                callViewAvailable = $callViewAvailable
                livenessRead = $reliableStateOk
                reliableStateRead = $reliableStateOk
                reliableState = $reliableState
                errors = @($errors)
            }
        }
        'ping' {
            $raw = Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
            return @{ reachable = (-not $raw.error); topLevelToolCount = @($raw.result.tools).Count }
        }
        'tools.list' {
            $raw = Invoke-DaemonMcpRpc 'tools/list' @{} 2 $TimeoutSec
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
            $describeDetail = if ($Request.describeDetail) { [string]$Request.describeDetail } else { 'call' }
            $describe.detail = $describeDetail
            if ($Request.describeToolName) { $describe.tool_name = [string]$Request.describeToolName }
            $data = Normalize-ToolResult (Invoke-DaemonTopTool 'describe_toolset' $describe $TimeoutSec)
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
        $transportStarted = $false
        $operationStarted = $false
        $operationCompleted = $false
        try {
            Start-GatewayProcessGuard $TimeoutSec $HardRequestGraceSec $MaxPrivateMemoryMB
            $requestGuardArmed = $true
            if ($context.Request.HttpMethod -ne 'POST') {
                Write-HttpJson $context @{ ok = $false; code = 'method_not_allowed' } 405
                continue
            }
            try {
                $body = Read-HttpRequestBody $context
                if (-not $body.Trim()) { throw 'Empty request body.' }
                $request = Resolve-GatewayRequest ($body | ConvertFrom-Json)
            } catch {
                Write-HttpJson $context ([ordered]@{ ok = $false; code = 'request_invalid'; message = $_.Exception.Message }) 400
                continue
            }
            $legacyFields = @('view', 'intent', 'detail', 'toolName') | Where-Object {
                $request.PSObject.Properties.Name -contains $_
            }
            if ($legacyFields) {
                Write-HttpJson $context ([ordered]@{ ok = $false; code = 'unsupported_request_field'; message = "Unsupported request field(s): $($legacyFields -join ', ')." }) 400
                continue
            }
            if ($request.endpoint -and [string]$request.endpoint -ne $Endpoint) {
                Write-HttpJson $context @{ ok = $false; code = 'endpoint_mismatch'; message = 'Daemon endpoint is fixed at startup.' } 400
                continue
            }
            $requestError = Get-GatewayRequestError $request
            if ($requestError) {
                Write-HttpJson $context ([ordered]@{ ok = $false; code = $requestError.code; message = $requestError.message }) 400
                continue
            }
            try {
                $resolvedProjection = Resolve-GatewayProjection $request
                if ($null -ne $resolvedProjection -and $request.PSObject.Properties.Name -notcontains 'projection') {
                    $request | Add-Member -NotePropertyName projection -NotePropertyValue $resolvedProjection
                }
            } catch {
                Write-HttpJson $context ([ordered]@{ ok = $false; code = 'projection_invalid'; message = $_.Exception.Message }) 400
                continue
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
                $transportStarted = $true
                Ensure-DaemonSession
                $dataOnly = -not [bool]$request.envelope -and -not [bool]$request.diagnostics
                $sessionRecovered = $false
                $operationStarted = $true
                try {
                    $data = Invoke-DaemonAction $request
                } catch {
                    if (-not $sessionRecovered -and (Test-McpSessionInvalidError $_)) {
                        # UE rejects an unknown session before dispatching the JSON-RPC method.
                        $sessionRecovered = $true
                        $operationStarted = $false
                        $script:headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
                        $script:sessionReused = $false
                        $script:sessionMode = 'recovered'
                        $operationStarted = $true
                        $data = Invoke-DaemonAction $request
                    } else {
                        throw
                    }
                }
                $operationCompleted = $true
                $persistence = Write-McpSession $Endpoint $script:headers $SessionFile $SessionTtlSec
                if ($dataOnly) {
                    Write-HttpJson $context (Compress-GatewayData $data $request)
                } else {
                    $reply = if (Test-GatewayFailure $data) {
                        [ordered]@{ ok = $false; action = [string]$request.action; error = $data }
                    } else {
                        [ordered]@{ ok = $true; action = [string]$request.action; data = $data }
                    }
                    if ($request.PSObject.Properties.Name -contains 'diagnostics' -and [bool]$request.diagnostics) {
                        $reply.transport = @{
                            mode = 'daemon'
                            sessionMode = $script:sessionMode
                            sessionReused = $script:sessionReused
                            sessionReusable = [bool]$persistence.reusable
                            sessionFileWritten = [bool]$persistence.written
                        }
                    }
                    Write-HttpJson $context $reply
                }
            }
        } catch {
            $code = if ($operationCompleted) { 'response_error' } elseif ($operationStarted) { 'result_unknown' } elseif ($transportStarted) { 'daemon_unavailable' } else { 'daemon_error' }
            if (-not $operationCompleted -and $transportStarted) {
                Invalidate-DoctorReceipt $code
                $script:headers = $null
                Remove-McpSessionFile $SessionFile
            }
            try {
                $statusCode = if ($operationCompleted) { 200 } else { 500 }
                Write-HttpJson $context ([ordered]@{ ok = $false; code = $code; message = $_.Exception.Message }) $statusCode
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
    Remove-McpSessionFile $SessionFile
    $listener.Stop()
    $listener.Close()
    $client.Dispose()
}
