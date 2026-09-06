param(
    [string]$RouteFile,
    [string]$RequestFile,
    [string]$RequestBase64,
    [switch]$FromStdin,
    [string]$Action,
    [string]$Toolset,
    [string]$Tool,
    [string]$ArgumentsFile,
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp',
    [int]$TimeoutSec = 120,
    [string]$SchemaCacheFile,
    [string]$SessionFile,
    [switch]$CloseSession,
    [string]$ProjectionFile,
    [string]$DescribeDetail,
    [string]$DescribeToolName,
    [string]$DaemonUrl,
    [int]$DaemonPort = 18765,
    [switch]$AutoDaemon,
    [string]$ProjectionProfile,
    [switch]$Envelope,
    [switch]$Diagnostics,
    [string]$OutFile,
    [switch]$Pretty,
    [switch]$AsLibrary
)

$ErrorActionPreference = 'Stop'
$DataOnly = $false
Add-Type -AssemblyName System.Net.Http

if (-not ('UEAgent.LimitedStreamReader' -as [type])) {
    Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace UEAgent
{
    public static class LimitedStreamReader
    {
        public static async Task<string> ReadUtf8Async(Stream stream, long maxBytes, CancellationToken cancellationToken)
        {
            byte[] chunk = new byte[81920];
            using (MemoryStream buffer = new MemoryStream())
            {
                while (true)
                {
                    int count = await stream.ReadAsync(chunk, 0, chunk.Length, cancellationToken).ConfigureAwait(false);
                    if (count == 0)
                    {
                        break;
                    }
                    long nextLength = buffer.Length + count;
                    if ((maxBytes > 0 && nextLength > maxBytes) || nextLength > int.MaxValue)
                    {
                        throw new InvalidDataException("MCP response exceeds the configured byte limit.");
                    }
                    buffer.Write(chunk, 0, count);
                }
                return new UTF8Encoding(false, true).GetString(buffer.GetBuffer(), 0, (int)buffer.Length);
            }
        }
    }
}
'@
}

function Write-JsonResult($Object) {
    $json = if ($null -eq $Object) {
        'null'
    } elseif ($Pretty) {
        ConvertTo-Json -InputObject $Object -Depth 80
    } else {
        ConvertTo-Json -InputObject $Object -Depth 80 -Compress
    }
    if ($OutFile) {
        [System.IO.File]::WriteAllText($OutFile, $json, [System.Text.UTF8Encoding]::new($false))
    } else {
        $json
    }
}

function Fail($Message, $Code = 'gateway_error', $Raw = $null) {
    if ($Code -in @('result_unknown', 'missing_session_id')) {
        Remove-McpSessionFile $SessionFile
    }
    $errorResult = [ordered]@{ ok = $false; code = $Code; message = $Message }
    if ($null -ne $Raw) { $errorResult.raw = $Raw }
    Write-JsonResult $errorResult
    exit 1
}

function Parse-Request {
    if ($RequestFile) {
        if (-not (Test-Path -LiteralPath $RequestFile)) { Fail "RequestFile not found: $RequestFile" 'request_file_not_found' }
        return (Get-Content -Raw -LiteralPath $RequestFile | ConvertFrom-Json)
    }
    if ($RequestBase64) {
        $json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($RequestBase64))
        return ($json | ConvertFrom-Json)
    }
    if ($FromStdin) {
        $json = [Console]::In.ReadToEnd()
        if (-not $json.Trim()) { Fail 'No JSON received from stdin.' 'empty_stdin' }
        return ($json | ConvertFrom-Json)
    }
    if ($Action -or $Tool -or $Toolset) {
        $request = [ordered]@{ endpoint = $Endpoint; timeoutSec = $TimeoutSec }
        if ($Action) { $request.action = $Action }
        if ($Toolset) { $request.toolset = $Toolset }
        if ($Tool) { $request.tool = $Tool }
        if ($SchemaCacheFile) {
            $request.schemaCacheFile = $SchemaCacheFile
        }
        if ($SessionFile) { $request.sessionFile = $SessionFile }
        if ($CloseSession) { $request.closeSession = $true }
        if ($DescribeDetail) { $request.describeDetail = $DescribeDetail }
        if ($DescribeToolName) { $request.describeToolName = $DescribeToolName }
        if ($DaemonUrl) { $request.daemonUrl = $DaemonUrl }
        if ($DaemonPort) { $request.daemonPort = $DaemonPort }
        if ($AutoDaemon) { $request.autoDaemon = $true }
        if ($ProjectionProfile) { $request.projectionProfile = $ProjectionProfile }
        if ($Envelope) { $request.envelope = $true }
        if ($Diagnostics) { $request.diagnostics = $true }
        if ($ArgumentsFile) {
            if (-not (Test-Path -LiteralPath $ArgumentsFile)) { Fail "ArgumentsFile not found: $ArgumentsFile" 'arguments_file_not_found' }
            $request.arguments = (Get-Content -Raw -LiteralPath $ArgumentsFile | ConvertFrom-Json)
        }
        if ($ProjectionFile) {
            if (-not (Test-Path -LiteralPath $ProjectionFile)) { Fail "ProjectionFile not found: $ProjectionFile" 'projection_file_not_found' }
            $request.projection = (Get-Content -Raw -LiteralPath $ProjectionFile | ConvertFrom-Json)
        }
        return [pscustomobject]$request
    }
    Fail 'Provide a request source, -Tool, -Toolset, or -Action.' 'missing_request'
}

function Try-ParseJsonText($Text) {
    if ($null -eq $Text -or -not ([string]$Text).Trim()) { return $Text }
    try { return ,([string]$Text | ConvertFrom-Json) } catch { return $Text }
}

function Assert-LoopbackEndpoint($Url) {
    $uri = $null
    if (-not [Uri]::TryCreate([string]$Url, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
        Fail "Endpoint must be unauthenticated loopback HTTP: $Url" 'unsafe_endpoint'
    }
    return $uri
}

function Enter-SessionFileLock($Path, $TimeoutMs = 3000) {
    if (-not $Path) { return $null }
    $parent = Split-Path -Parent $Path
    if (-not $parent -or -not (Test-Path -LiteralPath $parent)) { return $null }
    $lockPath = "$Path.lock"
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.ElapsedMilliseconds -lt $TimeoutMs) {
        try {
            return [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch [IO.IOException] {
            Start-Sleep -Milliseconds 40
        }
    }
    throw "Timed out waiting for MCP session lock: $lockPath"
}

function Exit-SessionFileLock($Path, $Lock) {
    if ($Lock) { $Lock.Dispose() }
}

function Read-McpSession($Url, $Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    $lock = $null
    try {
        $lock = Enter-SessionFileLock $Path
        $entry = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        if ($entry.schema -ne 'ueagent-mcp-session-v1' -or
            [string]$entry.endpoint -ne [string]$Url -or
            -not $entry.sessionId) { return $null }
        return $entry
    } catch {
        return $null
    } finally {
        Exit-SessionFileLock $Path $lock
    }
}

function Write-McpSession($Url, $Headers, $Path) {
    if (-not $Path -or -not $Headers['Mcp-Session-Id']) { return [pscustomobject]@{ reusable = $false; written = $false } }
    $lock = $null
    try {
        $parent = Split-Path -Parent $Path
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        $lock = Enter-SessionFileLock $Path
        $id = [string]$Headers['Mcp-Session-Id']
        $binding = if ($script:TaskBindings) { $script:TaskBindings["$Url|$id"] } else { $null }
        if (-not $binding -and (Test-Path -LiteralPath $Path)) {
            try { $previous = [IO.File]::ReadAllText($Path) | ConvertFrom-Json; if ($previous.sessionId -eq $id) { $binding = $previous.binding } } catch { }
        }
        $entry = [ordered]@{ schema = 'ueagent-mcp-session-v1'; endpoint = $Url; sessionId = $id; binding = $binding }
        $json = $entry | ConvertTo-Json -Depth 8 -Compress
        if ((Test-Path -LiteralPath $Path) -and [IO.File]::ReadAllText($Path) -eq $json) { return [pscustomobject]@{ reusable = $true; written = $false } }
        [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
        return [pscustomobject]@{ reusable = $true; written = $true }
    } finally { Exit-SessionFileLock $Path $lock }
}

function Remove-McpSessionFile($Path) {
    if ($Path) { Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue }
}

function Get-McpSessionHeaders($SessionId) {
    return @{
        'Content-Type' = 'application/json'
        'Accept' = 'application/json, text/event-stream'
        'Mcp-Session-Id' = [string]$SessionId
    }
}

function Test-GatewayPort($Url) {
    $uri = $null
    if (-not [Uri]::TryCreate([string]$Url, [UriKind]::Absolute, [ref]$uri)) { return $false }
    $tcp = [Net.Sockets.TcpClient]::new()
    try {
        $task = $tcp.ConnectAsync($uri.Host, $uri.Port)
        if (-not $task.Wait(250)) { return $false }
        return $tcp.Connected
    } catch {
        return $false
    } finally {
        $tcp.Dispose()
    }
}

function Test-GatewayDaemon($Url, $TargetEndpoint, $TargetSessionFile = '') {
    if (-not (Test-GatewayPort $Url)) { return $false }
    try {
        $probeUrl = $Url.TrimEnd('/') + '/__ueagent_daemon'
        $response = Invoke-WebRequest -Uri $probeUrl -Method Post -Headers @{ 'Content-Type' = 'application/json' } `
            -Body '{"action":"daemon.ping"}' -UseBasicParsing -TimeoutSec 2
        $parsed = $response.Content | ConvertFrom-Json
        if ($parsed.ok -ne $true -or $parsed.service -ne 'ueagent-gateway-daemon' -or
            [string]$parsed.endpoint -cne [string]$TargetEndpoint) { return $false }
        if ($TargetSessionFile -and (-not $parsed.sessionFile -or
            [IO.Path]::GetFullPath([string]$parsed.sessionFile) -ine [IO.Path]::GetFullPath([string]$TargetSessionFile))) {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Get-EndpointListenerPid($Url) {
    try {
        $uri = [Uri]$Url
        $connections = @(Get-NetTCPConnection -State Listen -LocalPort $uri.Port -ErrorAction Stop |
            Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::1', '::') })
        if ($connections.Count -gt 0) { return [int]$connections[0].OwningProcess }
    } catch {
        # Optional process binding; idle and request/response bounds also apply to manual daemons.
    }
    return 0
}

function Start-GatewayDaemon($Url, $Port, $McpUrl, $SessionPath, $Timeout, [switch]$Wait) {
    if (Test-GatewayPort $Url) {
        if (Test-GatewayDaemon $Url $McpUrl $SessionPath) { return $true }
        throw "Gateway daemon URL is occupied by another service or target: $Url"
    }
    if (-not $SessionPath) { throw 'AutoDaemon requires -SessionFile <project>\Saved\UEAgent\mcp-session.json.' }
    $daemonScript = Join-Path $PSScriptRoot 'mcp_gateway_daemon.ps1'
    if (-not (Test-Path -LiteralPath $daemonScript)) { throw "Gateway daemon script not found: $daemonScript" }
    $lock = $null
    $lockKey = "$SessionPath.daemon"
    try {
        $lock = Enter-SessionFileLock $lockKey 3000
        if (-not (Test-GatewayPort $Url)) {
            $hostExe = (Get-Command powershell.exe -ErrorAction Stop).Source
            $parentPid = Get-EndpointListenerPid $McpUrl
            $daemonArgs = @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemonScript,
                '-ListenPort', [string]$Port,
                '-Endpoint', $McpUrl,
                '-SessionFile', $SessionPath,
                '-TimeoutSec', [string]$Timeout,
                '-IdleTtlSec', '900',
                '-MaxRequestBytes', '8388608',
                '-MaxResponseBytes', '67108864'
            )
            if ($parentPid -gt 0) { $daemonArgs += @('-ParentPid', [string]$parentPid) }
            $process = Start-Process -FilePath $hostExe -ArgumentList $daemonArgs -WindowStyle Hidden -PassThru
            if (-not $Wait) { return $true }
            $ready = $false
            foreach ($attempt in 1..32) {
                Start-Sleep -Milliseconds 250
                if ($process.HasExited) { break }
                if (Test-GatewayDaemon $Url $McpUrl $SessionPath) { $ready = $true; break }
            }
            if (-not $ready) {
                $state = if ($process.HasExited) { "exited ($($process.ExitCode))" } else { 'not ready' }
                throw "Gateway daemon failed to start: $state"
            }
        }
        return $true
    } finally {
        Exit-SessionFileLock $lockKey $lock
    }
}

function Invoke-GatewayDaemonRequest($Url, $Request) {
    $json = (Get-DaemonRequest $Request $SchemaCacheFile $Endpoint $SessionFile) | ConvertTo-Json -Depth 80 -Compress
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Post -Headers @{ 'Content-Type' = 'application/json' } `
            -Body $json -UseBasicParsing -TimeoutSec $TimeoutSec
        $parsed = $response.Content | ConvertFrom-Json
    } catch {
        if ($_.ErrorDetails.Message) {
            try { $knownError = $_.ErrorDetails.Message | ConvertFrom-Json; if ($knownError.code) { return ,$knownError } } catch { }
        }
        if (-not $_.Exception.Response) { throw }
        $stream = $_.Exception.Response.GetResponseStream()
        $cts = [Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds($TimeoutSec))
        try {
            $body = [UEAgent.LimitedStreamReader]::ReadUtf8Async($stream,67108864,$cts.Token).GetAwaiter().GetResult()
            $parsed = $body | ConvertFrom-Json
            if (-not $parsed.code) { throw 'Daemon HTTP failure has no structured error.' }
        } finally { $stream.Dispose(); $cts.Dispose() }
    }
    # Windows PowerShell adds an ETS Count property to a root JSON array. A fresh
    # array preserves the JSON shape when this already-shaped daemon reply is serialized.
    if ($parsed -is [array]) { return ,($parsed.Clone()) }
    return $parsed
}

function Get-ProjectionProfile($Name) {
    $key = ([string]$Name).Trim().ToLowerInvariant().Replace('_', '-').Replace('.', '-')
    $aliases = @{
        'material-identity' = 'identity'; 'blueprint-identity' = 'identity'; 'niagara-identity' = 'identity'
        'material-topology' = 'topology'; 'blueprint-topology' = 'topology'; 'niagara-topology' = 'topology'
        'material-logic' = 'logic'; 'blueprint-logic' = 'logic'; 'niagara-logic' = 'logic'
        'material-runtime' = 'runtime'; 'blueprint-runtime' = 'runtime'; 'niagara-runtime' = 'runtime'
        'material-hlsl' = 'hlsl'; 'blueprint-hlsl' = 'hlsl'; 'niagara-hlsl' = 'hlsl'
        'material-script' = 'hlsl'; 'blueprint-script' = 'hlsl'; 'niagara-script' = 'hlsl'
        'changed-region' = 'changed'; 'changed-readback' = 'changed'
        'material-changed-region' = 'changed'; 'blueprint-changed-region' = 'changed'; 'niagara-changed-region' = 'changed'
        'material-changed-readback' = 'changed'; 'blueprint-changed-readback' = 'changed'; 'niagara-changed-readback' = 'changed'
    }
    if ($aliases.ContainsKey($key)) { $key = $aliases[$key] }
    switch ($key) {
        'refs' {
            return [ordered]@{ fields = @('returnValue.refPath'); max_items = 256; structured = $true }
        }
        'compact' {
            return [ordered]@{ fields = @('returnValue'); max_items = 64; structured = $true }
        }
        'identity' {
            return [ordered]@{ fields = @(
                'returnValue.refPath', 'returnValue.assetPath', 'returnValue.package', 'returnValue.name',
                'returnValue.class', 'returnValue.type', 'returnValue.parent', 'returnValue.material',
                'returnValue.status', 'returnValue.compileStatus', 'returnValue.dirty', 'returnValue.saved'
            ); max_items = 32; structured = $true }
        }
        'topology' {
            return [ordered]@{ fields = @(
                'returnValue.refPath', 'returnValue.assetPath', 'returnValue.name', 'returnValue.class',
                'returnValue.nodes.id', 'returnValue.nodes.name', 'returnValue.nodes.class', 'returnValue.nodes.type',
                'returnValue.expressions.id', 'returnValue.expressions.name', 'returnValue.expressions.class', 'returnValue.expressions.type',
                'returnValue.connections', 'returnValue.links', 'returnValue.pinLinks', 'returnValue.outputs',
                'returnValue.graphs.name', 'returnValue.graphs.refPath', 'returnValue.emitters.name', 'returnValue.emitters.refPath',
                'returnValue.stages.name', 'returnValue.stages.refPath', 'returnValue.modules.name', 'returnValue.modules.refPath',
                'returnValue.components.name', 'returnValue.components.refPath', 'returnValue.dependencies'
            ); exclude = @('returnValue.nodes.properties', 'returnValue.expressions.properties'); max_items = 256; structured = $true }
        }
        'logic' {
            return [ordered]@{ fields = @(
                'returnValue.refPath', 'returnValue.assetPath', 'returnValue.nodes', 'returnValue.expressions',
                'returnValue.graph', 'returnValue.graphs', 'returnValue.connections', 'returnValue.links',
                'returnValue.pinLinks', 'returnValue.execution', 'returnValue.operations', 'returnValue.statements', 'returnValue.logic'
            ); exclude = @(
                'returnValue.nodes.layout', 'returnValue.nodes.properties', 'returnValue.nodes.hlsl', 'returnValue.nodes.hlslCode',
                'returnValue.expressions.layout', 'returnValue.expressions.properties', 'returnValue.expressions.hlsl', 'returnValue.expressions.hlslCode'
            ); max_items = 512; structured = $true }
        }
        'runtime' {
            return [ordered]@{ fields = @(
                'returnValue.refPath', 'returnValue.assetPath', 'returnValue.status', 'returnValue.compile',
                'returnValue.compileStatus', 'returnValue.dirty', 'returnValue.saved', 'returnValue.runtime',
                'returnValue.runtimeState', 'returnValue.component', 'returnValue.overrides', 'returnValue.effectiveInputs',
                'returnValue.renderers', 'returnValue.parameters', 'returnValue.warnings', 'returnValue.errors'
            ); max_items = 128; structured = $true }
        }
        'hlsl' {
            return [ordered]@{ fields = @(
                'returnValue.hlsl', 'returnValue.hlslCode', 'returnValue.generatedHlsl', 'returnValue.generated_hlsl',
                'returnValue.customHlsl', 'returnValue.custom_hlsl', 'returnValue.script', 'returnValue.scriptText',
                'returnValue.code', 'returnValue.source'
            ); max_items = 64; structured = $true }
        }
        'changed' {
            return [ordered]@{ fields = @(
                'returnValue.refPath', 'returnValue.assetPath', 'returnValue.changed', 'returnValue.changedRegion',
                'returnValue.changedNodes', 'returnValue.nodes', 'returnValue.changedPins', 'returnValue.pins',
                'returnValue.changedProperties', 'returnValue.properties', 'returnValue.connections', 'returnValue.compile',
                'returnValue.compileStatus', 'returnValue.dirty', 'returnValue.saved', 'returnValue.status',
                'returnValue.errors', 'returnValue.warnings'
            ); exclude = @('returnValue.nodes.properties', 'returnValue.nodes.hlsl', 'returnValue.nodes.hlslCode'); max_items = 128; structured = $true }
        }
        default { throw "Unknown projection profile: $Name. Available profiles: refs, compact, identity, topology, logic, runtime, hlsl, changed." }
    }
}

function Resolve-GatewayProjection($Request) {
    if ($Request.PSObject.Properties.Name -contains 'projection') { return $Request.projection }
    if ([string]$Request.projectionProfile) { return (Get-ProjectionProfile ([string]$Request.projectionProfile)) }
    if ([string]$Request.action -eq 'tool.call') { return [ordered]@{ structured = $true } }
    return $null
}

function Resolve-GatewayRequest($Request) {
    if ($null -eq $Request) { throw 'Request is empty.' }
    $properties = @($Request.PSObject.Properties.Name)
    $actionName = if ($properties -contains 'action') { ([string]$Request.action).Trim().ToLowerInvariant() } else { '' }
    if ($actionName -eq 'call') { $actionName = '' }
    if ($actionName -eq 'describe') { $actionName = 'toolset.describe' }
    if (-not $actionName) {
        if ($properties -contains 'describeToolName' -or $properties -contains 'describeDetail') {
            $actionName = 'toolset.describe'
        } elseif ([string]$Request.tool) {
            $actionName = if ([string]$Request.toolset -or ([string]$Request.tool).Contains('.')) {
                'tool.call'
            } elseif (([string]$Request.tool).StartsWith('ueagent_', [StringComparison]::OrdinalIgnoreCase)) {
                'direct.call'
            } else {
                'tool.call'
            }
        } elseif ([string]$Request.toolset) {
            $actionName = 'toolset.describe'
        }
    }
    if ($properties -contains 'action') { $Request.action = $actionName }
    else { $Request | Add-Member -NotePropertyName action -NotePropertyValue $actionName }
    return $Request
}

function Get-GatewayRequestError($Request) {
    $actionName = [string]$Request.action
    if (-not $actionName) { return [ordered]@{ code = 'missing_action'; message = 'Request must identify a tool, toolset, or action.' } }
    if ($actionName -notin @('preflight', 'ping', 'tools.list', 'toolsets.list', 'toolset.describe', 'tool.call', 'direct.call', 'daemon.ping', 'close', 'shutdown')) {
        return [ordered]@{ code = 'unknown_action'; message = "Unknown action: $actionName" }
    }
    if ($actionName -eq 'toolset.describe' -and -not [string]$Request.toolset) {
        return [ordered]@{ code = 'missing_toolset'; message = 'toolset.describe requires toolset.' }
    }
    if ($actionName -in @('tool.call', 'direct.call') -and -not [string]$Request.tool) {
        return [ordered]@{ code = 'missing_tool'; message = "$actionName requires tool." }
    }
    return $null
}

function Test-GatewayFailure($Value) {
    if ($null -eq $Value) { return $false }
    if ($Value -is [Collections.IDictionary]) {
        return (($Value.Contains('ok') -and $Value['ok'] -eq $false) -or
            ($Value.Contains('success') -and $Value['success'] -eq $false))
    }
    $properties = @($Value.PSObject.Properties.Name)
    return (($properties -contains 'ok' -and $Value.ok -eq $false) -or
        ($properties -contains 'success' -and $Value.success -eq $false))
}

function Test-AiEmptyValue($Value) {
    if ($null -eq $Value) { return $true }
    if ($Value -is [string]) { return $Value.Length -eq 0 }
    if ($Value -is [Collections.IDictionary]) { return $Value.Count -eq 0 }
    if ($Value -is [pscustomobject]) { return @($Value.PSObject.Properties).Count -eq 0 }
    if ($Value -is [Collections.IEnumerable]) { return @($Value).Count -eq 0 }
    return $false
}

function Convert-ToAiValue($Value, [bool]$Sparse = $false, [string]$PropertyName = '') {
    if ($null -eq $Value) { return $null }
    if ($PropertyName -eq 'result' -and $Value -is [string]) {
        $parsed = Try-ParseJsonText $Value
        if ($parsed -isnot [string] -or [string]$parsed -ne [string]$Value) {
            return ,(Convert-ToAiValue $parsed $false)
        }
    }
    if ($Value -is [Collections.IDictionary] -or $Value -is [pscustomobject]) {
        $result = [ordered]@{}
        $entries = if ($Value -is [Collections.IDictionary]) {
            @($Value.Keys | ForEach-Object { [pscustomobject]@{ Name = [string]$_; Value = $Value[$_] } })
        } else {
            @($Value.PSObject.Properties | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Value = $_.Value } })
        }
        foreach ($entry in $entries) {
            $name = [string]$entry.Name
            $raw = $entry.Value
            if ($name -in @('ok', 'success') -and $raw -eq $true) { continue }
            if ($Sparse -and $name -eq 'command_succeeded') { continue }
            if ($Sparse -and $name -in @('performance_frozen', 'dirty_packages_truncated', 'replayed', 'automatic', 'allow_preexisting_dirty_save') -and $raw -eq $false) { continue }
            if ($Sparse -and $name -eq 'enabled' -and $raw -eq $true) { continue }
            if ($Sparse -and $name -in @('accepted_at', 'started_at', 'finished_at', 'saved_at', 'recovered_at')) { continue }
            $childSparse = $Sparse -and $name -notin @('data', 'values', 'returnValue', 'result')
            $child = Convert-ToAiValue $raw $childSparse $name
            if ($childSparse -and (Test-AiEmptyValue $child)) { continue }
            $result[$name] = $child
        }
        if ($result.Count -eq 1 -and $result.Contains('returnValue')) { return ,$result.returnValue }
        if ($Sparse -and $result.Count -eq 0) { return $null }
        return [pscustomobject]$result
    }
    if ($Value -is [Collections.IEnumerable] -and $Value -isnot [string]) {
        $items = [Collections.Generic.List[object]]::new()
        foreach ($item in $Value) {
            $child = Convert-ToAiValue $item $Sparse
            if (-not $Sparse -or -not (Test-AiEmptyValue $child)) { $items.Add($child) }
        }
        return ,$items.ToArray()
    }
    return $Value
}

function Compress-GatewayData($Data, $Request) {
    $toolName = if ($Request) { [string]$Request.tool } else { '' }
    $sparse = $toolName.StartsWith('ueagent_', [StringComparison]::OrdinalIgnoreCase)
    $compressed = Convert-ToAiValue $Data $sparse
    if ($toolName.Equals('ueagent_state', [StringComparison]::OrdinalIgnoreCase) -and $compressed -is [pscustomobject]) {
        foreach ($diagnosticField in @('project', 'engine_version', 'job_count', 'read_only_tool_count')) {
            $compressed.PSObject.Properties.Remove($diagnosticField)
        }
    }
    return ,$compressed
}

function Test-ToolInputEnumValue($Tools, $ToolName, $PropertyName, $ExpectedValue) {
    $tool = @($Tools | Where-Object { [string]$_.name -eq [string]$ToolName } | Select-Object -First 1)
    if ($tool.Count -eq 0 -or -not $tool[0].inputSchema.properties) { return $false }
    $property = $tool[0].inputSchema.properties.($PropertyName)
    return $null -ne $property -and [string]$ExpectedValue -in @($property.enum | ForEach-Object { [string]$_ })
}

function Compress-ToolError($Text) {
    $value = [string]$Text
    foreach ($label in @('Function schema Json -', 'Available toolsets:')) {
        $marker = $value.IndexOf($label, [StringComparison]::OrdinalIgnoreCase)
        if ($marker -ge 0) { $value = $value.Substring(0, $marker).TrimEnd(); break }
    }
    if ($value.Length -gt 384) { $value = $value.Substring(0, 384).TrimEnd() + '...' }
    return $value
}

function Get-DaemonRequest($Request, [string]$DefaultSchemaCacheFile,
    [string]$TargetEndpoint = $Endpoint, [string]$TargetSessionFile = $SessionFile) {
    $allowed = @(
        'action', 'toolset', 'tool', 'arguments', 'expectedProject', 'commandId', 'readOnly', 'scopes', 'readback', 'save', 'allowPreexistingDirtySave', 'wait',
        'describeDetail', 'describeToolName', 'projection', 'projectionProfile',
        'envelope', 'diagnostics'
    )
    $forward = [ordered]@{ endpoint = $TargetEndpoint }
    if ($script:route) { $forward.expectedProject = [string]$script:route.uProject }
    if ($TargetSessionFile) { $forward.sessionFile = $TargetSessionFile }
    foreach ($name in $allowed) {
        if ($Request.PSObject.Properties.Name -contains $name) { $forward[$name] = $Request.$name }
    }
    if ([string]$Request.action -in @('tools.list', 'toolsets.list', 'toolset.describe')) {
        $cacheFile = if ($Request.schemaCacheFile) { [string]$Request.schemaCacheFile } else { $DefaultSchemaCacheFile }
        if ($cacheFile) {
            $forward.schemaCacheFile = $cacheFile
        }
    }
    return [pscustomobject]$forward
}

function Get-SchemaCacheKey($Action, $Url, $Toolset, $Detail = '', $ToolName = '', $SessionId = '') {
    $parts = @(
        [string]$Action,
        [string]$Url,
        [string]$Toolset,
        "detail=$([string]$Detail)",
        "tool=$([string]$ToolName)",
        "session=$([string]$SessionId)"
    )
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($parts -join '|')))
}

function Read-SchemaCacheEntry($Action, $Url, $Toolset, $Path, $Detail = '', $ToolName = '', $SessionId = '') {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $cache = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        if ($cache.schema -ne 'ueagent-schema-cache-v1') { return $null }
        if ($SessionId -and @($cache.entries | Where-Object { [string]$_.sessionId -eq $SessionId }).Count -eq 0) { return $null }
        $key = Get-SchemaCacheKey $Action $Url $Toolset $Detail $ToolName $SessionId
        foreach ($entry in @($cache.entries)) {
            if ($entry.key -ne $key) { continue }
            return $entry
        }
    } catch {
        # A corrupt or stale schema cache is disposable; fall through to live discovery.
    }
    return $null
}

function Write-SchemaCacheEntry($Action, $Url, $Toolset, $Data, $Path, $Detail = '', $ToolName = '', $SessionId = '') {
    if (-not $Path) { return }
    $parent = Split-Path $Path -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { return }
    $entries = @()
    if (Test-Path -LiteralPath $Path) {
        try {
            $existing = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
            if ($existing.schema -eq 'ueagent-schema-cache-v1') { $entries = @($existing.entries) }
        } catch { $entries = @() }
    }
    $key = Get-SchemaCacheKey $Action $Url $Toolset $Detail $ToolName $SessionId
    $now = [DateTime]::UtcNow
    if ($SessionId) {
        $entries = @($entries | Where-Object {
            [string]$_.sessionId -eq $SessionId -and $_.key -ne $key
        })
    } else {
        $entries = @($entries | Where-Object { $_.key -ne $key })
    }
    $entries += [ordered]@{
        key = $key
        action = $Action
        toolset = $Toolset
        detail = $Detail
        toolName = $ToolName
        sessionId = $SessionId
        createdAtUtc = [DateTime]::UtcNow.ToString('o')
        data = $Data
    }
    $cache = [ordered]@{ schema = 'ueagent-schema-cache-v1'; entries = $entries }
    try {
        [IO.File]::WriteAllText($Path, ($cache | ConvertTo-Json -Depth 80 -Compress), [Text.UTF8Encoding]::new($false))
    } catch {
        # Discovery still succeeded; cache persistence is only an optimization.
    }
}

function Normalize-ToolResult($RpcMessage) {
    if ($null -eq $RpcMessage) { return $null }
    if ($RpcMessage.error) { return [ordered]@{ ok = $false; code = 'rpc_error'; error = $RpcMessage.error } }
    $result = $RpcMessage.result
    if ($null -eq $result) { return $null }
    if ($result.isError -eq $true) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        if ($texts.Count -eq 1) {
            $structuredError = Try-ParseJsonText $texts[0]
            if ($structuredError -is [pscustomobject] -and $structuredError.error_code) { return ,$structuredError }
        }
        return [ordered]@{ ok = $false; code = 'tool_error'; message = (Compress-ToolError ($texts -join "`n")) }
    }
    if ($null -ne $result.structuredContent) {
        return ,$result.structuredContent
    }
    if ($result.content) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        if ($texts.Count -eq 1) { return ,(Try-ParseJsonText $texts[0]) }
        if ($texts.Count -gt 1) { return ,@($texts | ForEach-Object { Try-ParseJsonText $_ }) }
    }
    return $result
}

function Test-McpSessionInvalidError($ErrorRecord) {
    return [string]$ErrorRecord.Exception.Message -like 'MCP_SESSION_INVALID:*'
}

function Close-McpSession($Url, $Headers) {
    if (-not $Headers -or -not $Headers['Mcp-Session-Id']) { return }
    try {
        Invoke-WebRequest -Uri $Url -Method Delete -Headers $Headers -UseBasicParsing -TimeoutSec 2 | Out-Null
    } catch {
        # Session cleanup is best-effort; never replace the actual tool result with cleanup noise.
    }
}

function New-McpSession($Url, $Timeout = 30) {
    $headers = @{ 'Content-Type' = 'application/json'; 'Accept' = 'application/json, text/event-stream' }
    $body = @{
        jsonrpc = '2.0'
        id = 1
        method = 'initialize'
        params = @{
            protocolVersion = '2024-11-05'
            capabilities = @{}
            clientInfo = @{ name = 'ueagent-gateway'; version = '1.0' }
        }
    } | ConvertTo-Json -Depth 30
    $response = Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -Body $body -UseBasicParsing -TimeoutSec $Timeout
    $sessionId = $response.Headers['Mcp-Session-Id']
    if ($sessionId -is [array]) { $sessionId = $sessionId[0] }
    if (-not $sessionId) { Fail 'Server did not return Mcp-Session-Id.' 'missing_session_id' $response.Content }
    $headers['Mcp-Session-Id'] = $sessionId
    try {
        Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' -UseBasicParsing -TimeoutSec $Timeout | Out-Null
    } catch {
        Close-McpSession $Url $headers
        throw
    }
    return $headers
}

function Invoke-McpRpc($Url, $Headers, $Method, $Params = $null, $Id = 2, $Timeout = 120, [Net.Http.HttpClient]$Client = $null, [int64]$MaxResponseBytes = 67108864) {
    $payload = @{ jsonrpc = '2.0'; id = $Id; method = $Method }
    if ($null -ne $Params) { $payload.params = $Params }
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, $Url)
    $request.Content = [Net.Http.StringContent]::new(
        ($payload | ConvertTo-Json -Depth 80),
        [Text.Encoding]::UTF8,
        'application/json'
    )
    $request.Headers.TryAddWithoutValidation('Accept', 'application/json, text/event-stream') | Out-Null
    foreach ($entry in $Headers.GetEnumerator()) {
        if ($entry.Key -notin @('Content-Type', 'Accept')) {
            $request.Headers.TryAddWithoutValidation([string]$entry.Key, [string]$entry.Value) | Out-Null
        }
    }

    $ownsClient = $false
    if (-not $Client) {
        $Client = [Net.Http.HttpClient]::new()
        $Client.Timeout = [Threading.Timeout]::InfiniteTimeSpan
        $ownsClient = $true
    }
    $response = $null
    $reader = $null
    $cts = [Threading.CancellationTokenSource]::new()
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $seenLines = [Collections.Generic.List[string]]::new()
    try {
        $send = $client.SendAsync($request, [Net.Http.HttpCompletionOption]::ResponseHeadersRead, $cts.Token)
        if (-not $send.Wait([TimeSpan]::FromSeconds($Timeout))) {
            $cts.Cancel()
            throw [TimeoutException]::new("MCP $Method timed out waiting for response headers.")
        }
        $response = $send.Result
        if (-not $response.IsSuccessStatusCode) {
            $errorRead = $response.Content.ReadAsStringAsync()
            $errorRemainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
            $errorBody = if ($errorRead.Wait($errorRemainingMs)) { [string]$errorRead.Result } else { '<body timeout>' }
            if ($errorBody.Length -gt 8192) { $errorBody = $errorBody.Substring(0, 8192) + '…' }
            if ([int]$response.StatusCode -eq 404) {
                try {
                    $sessionError = $errorBody | ConvertFrom-Json
                    if ([int]$sessionError.error.code -eq -32600 -and
                        [string]$sessionError.error.message -match '^Unknown session id .+ client should reinitialize$') {
                        throw "MCP_SESSION_INVALID: $Method"
                    }
                } catch {
                    if (Test-McpSessionInvalidError $_) { throw }
                }
            }
            throw "MCP $Method HTTP $([int]$response.StatusCode) $($response.ReasonPhrase): $errorBody"
        }
        if ($MaxResponseBytes -gt 0 -and $response.Content.Headers.ContentLength -and
            $response.Content.Headers.ContentLength -gt $MaxResponseBytes) {
            throw "MCP $Method response exceeds ${MaxResponseBytes} bytes. Use a projection or a smaller detail view."
        }
        $mediaType = [string]$response.Content.Headers.ContentType.MediaType
        if ($mediaType -ne 'text/event-stream') {
            $streamTask = $response.Content.ReadAsStreamAsync()
            $streamRemainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
            if (-not $streamTask.Wait($streamRemainingMs)) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out opening the JSON-RPC stream for id $Id.")
            }
            $read = [UEAgent.LimitedStreamReader]::ReadUtf8Async($streamTask.Result, $MaxResponseBytes, $cts.Token)
            $remainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
            if (-not $read.Wait($remainingMs)) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out reading JSON-RPC id $Id.")
            }
            $messageText = $read.Result
            $message = $messageText | ConvertFrom-Json
            if ([string]$message.id -ne [string]$Id) {
                throw "MCP $Method returned JSON-RPC id $($message.id), expected $Id."
            }
            return $message
        }
        $streamTask = $response.Content.ReadAsStreamAsync()
        $streamRemainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
        if (-not $streamTask.Wait($streamRemainingMs)) {
            $cts.Cancel()
            throw [TimeoutException]::new("MCP $Method timed out opening the JSON-RPC stream for id $Id.")
        }
        $reader = [IO.StreamReader]::new($streamTask.Result)
        $responseBytes = 0L
        while ($true) {
            $remainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
            if ($remainingMs -le 1) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out waiting for JSON-RPC id $Id.")
            }
            $read = $reader.ReadLineAsync()
            if (-not $read.Wait($remainingMs)) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out waiting for JSON-RPC id $Id.")
            }
            $line = $read.Result
            if ($null -eq $line) {
                $preview = @($seenLines) -join ' | '
                throw "MCP $Method ended before JSON-RPC id $Id. Response preview: $preview"
            }
            if ($MaxResponseBytes -gt 0) {
                # Count CRLF conservatively even when the peer used LF. The response byte ceiling
                # protects the client without imposing a separate process-kill policy.
                $responseBytes += [Text.Encoding]::UTF8.GetByteCount([string]$line) + 2L
                if ($responseBytes -gt $MaxResponseBytes) {
                    throw "MCP $Method response exceeds ${MaxResponseBytes} bytes. Use a projection or a smaller detail view."
                }
            }
            $line = $line.Trim()
            if (-not $line) { continue }
            if ($seenLines.Count -lt 3) { $seenLines.Add($line.Substring(0, [Math]::Min(200, $line.Length))) }
            $json = if ($line.StartsWith('data:')) { $line.Substring(5).Trim() } else { $line }
            if (-not $json -or $json -eq '[DONE]') { continue }
            try { $message = $json | ConvertFrom-Json } catch { continue }
            if ([string]$message.id -eq [string]$Id) { return $message }
        }
    } finally {
        try { $cts.Cancel() } catch { }
        if ($reader) { $reader.Dispose() }
        if ($response) { $response.Dispose() }
        $request.Dispose()
        $cts.Dispose()
        if ($ownsClient) { $Client.Dispose() }
    }
}

function Invoke-TaskCall($Request, [scriptblock]$Invoke) {
    $tool = [string]$Request.tool
    if ($tool -eq 'ueagent_state') { $stateArguments = if ($Request.arguments) { $Request.arguments } else { @{} }; return ,(& $Invoke $tool $stateArguments) }
    $expectedProject = [string]$Request.expectedProject
    if (-not $expectedProject -and $script:route) { $expectedProject = [string]$script:route.uProject }
    $sessionPath = if ($Request.sessionFile) { [string]$Request.sessionFile } else { $SessionFile }
    if (-not $expectedProject -and $sessionPath) {
        $targetRoute = Join-Path (Split-Path -Parent $sessionPath) 'route.json'
        if (Test-Path -LiteralPath $targetRoute) { $expectedProject = [string](Get-Content -Raw -LiteralPath $targetRoute | ConvertFrom-Json).uProject }
    }
    if (-not $expectedProject) { throw 'Task calls require a project route or expectedProject.' }
    $expectedProject = [IO.Path]::GetFullPath($expectedProject).Replace('\','/')
    $sessionId = [string]$script:headers['Mcp-Session-Id']
    $key = "$Endpoint|$sessionId"
    if (-not $script:TaskBindings) { $script:TaskBindings = @{} }
    $binding = $script:TaskBindings[$key]
    if (-not $binding -and $sessionPath) {
        $stored = Read-McpSession $Endpoint $sessionPath
        if ($stored -and [string]$stored.sessionId -eq $sessionId) { $binding = $stored.binding }
    }
    if (-not $binding) {
        $state = & $Invoke 'ueagent_state' @{}
        if ([string]$state.protocol_version -ne '3.0.0' -or -not $state.enabled -or -not $state.editor_epoch) {
            throw 'Editor does not expose the enabled UEAgent 3.0 task executor.'
        }
        $binding = [pscustomobject]@{ project = ([IO.Path]::GetFullPath([string]$state.project_file)).Replace('\','/'); epoch = [string]$state.editor_epoch }
    }
    if (-not ([string]$binding.project).Equals($expectedProject, [StringComparison]::OrdinalIgnoreCase)) { return [pscustomobject]@{ success = $false; error_code = 'PROJECT_MISMATCH'; error = 'Project does not match the session-bound Editor.' } }
    $script:TaskBindings[$key] = $binding
    $arguments = @{}
    if ($Request.arguments) {
        if ($Request.arguments -is [Collections.IDictionary]) { foreach($name in $Request.arguments.Keys) { $arguments[$name] = $Request.arguments[$name] } }
        else { foreach($property in $Request.arguments.PSObject.Properties) { $arguments[$property.Name] = $property.Value } }
    }
    $isControl = $tool.StartsWith('ueagent_', [StringComparison]::OrdinalIgnoreCase)
    $readOnly = $false
    if (-not $isControl) {
        $toolset = [string]$Request.toolset
        $targetType = 'toolset'
        if ([string]$Request.action -eq 'direct.call') { $targetType = 'vibeue' }
        elseif (-not $toolset -and $tool.Contains('.')) {
            $index = $tool.LastIndexOf('.')
            $toolset = $tool.Substring(0,$index); $tool = $tool.Substring($index+1)
        }
        $readOnly = [bool]$Request.readOnly
        $commandId = if ($Request.commandId) { [string]$Request.commandId } else { [guid]::NewGuid().ToString() }
        $Request | Add-Member -NotePropertyName commandId -NotePropertyValue $commandId -Force
        $arguments = @{ command_id = $commandId; target_type = $targetType; toolset_name = $toolset; tool_name = $tool; arguments = $arguments; read_only = $readOnly }
        foreach($mapping in @(@('scopes','scopes'),@('readback','readback'),@('save','save'),@('allowPreexistingDirtySave','allow_preexisting_dirty_save'))) {
            if ($Request.PSObject.Properties.Name -contains $mapping[0]) { $arguments[$mapping[1]] = $Request.($mapping[0]) }
        }
        $tool = 'ueagent_submit'
    } elseif ($tool -eq 'ueagent_submit') { $readOnly = [bool]$arguments.read_only }
    $arguments.expected_project = $expectedProject
    $arguments.editor_epoch = [string]$binding.epoch
    $commandId = [string]$arguments.command_id
    $script:DispatchedCommandId = $commandId
    $result = & $Invoke $tool $arguments
    if ([string]$result.error_code -eq 'EDITOR_CHANGED') { $script:TaskBindings.Remove($key) }
    if ($tool -eq 'ueagent_submit' -and $result.state -ne 'terminal' -and -not (Test-GatewayFailure $result) -and $Request.wait -ne $false) {
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $delay = 100
        while ($result.state -ne 'terminal') {
            if ($watch.Elapsed.TotalSeconds -ge [Math]::Max(1, $TimeoutSec - 5)) {
                return [pscustomobject]@{ success = $false; error_code = 'WAIT_TIMEOUT'; command_id = $commandId; state = [string]$result.state; error = 'Task may still be running. Query this command_id; do not submit again.' }
            }
            Start-Sleep -Milliseconds $delay
            $delay = [Math]::Min(1000, $delay * 2)
            $result = & $Invoke 'ueagent_get_job' @{ command_id = $commandId; expected_project = $expectedProject; editor_epoch = [string]$binding.epoch }
            if (Test-GatewayFailure $result) { break }
        }
    }
    if ($readOnly -and $result.state -eq 'terminal' -and -not (Test-GatewayFailure $result)) { return ,$result.result }
    return ,$result
}

function Invoke-TopTool($Url, $Headers, $Name, $Arguments, $Timeout = 120, [Net.Http.HttpClient]$Client = $null, [int64]$MaxResponseBytes = 67108864) {
    Invoke-McpRpc $Url $Headers 'tools/call' @{ name = $Name; arguments = $Arguments } 2 $Timeout $Client $MaxResponseBytes
}

if ($AsLibrary) { return }

$endpointExplicit = $PSBoundParameters.ContainsKey('Endpoint')
$sessionExplicit = $PSBoundParameters.ContainsKey('SessionFile')
$schemaCacheExplicit = $PSBoundParameters.ContainsKey('SchemaCacheFile')
if (-not $RouteFile) {
    $localRoute = Join-Path (Get-Location) 'Saved\UEAgent\route.json'
    if (Test-Path -LiteralPath $localRoute) { $RouteFile = $localRoute }
}
if ($RouteFile) {
    try {
        $route = Get-Content -Raw -LiteralPath $RouteFile | ConvertFrom-Json
        if ([string]$route.schema -ne 'ueagent-route-v1' -or -not [string]$route.endpoint -or -not [string]$route.uProject) {
            throw 'Route must contain schema=ueagent-route-v1, endpoint, and uProject.'
        }
        if (-not $endpointExplicit) { $Endpoint = [string]$route.endpoint }
        $savedRoot = Join-Path (Split-Path -Parent ([string]$route.uProject)) 'Saved\UEAgent'
        if (-not $sessionExplicit) { $SessionFile = Join-Path $savedRoot 'mcp-session.json' }
        if (-not $schemaCacheExplicit) { $SchemaCacheFile = Join-Path $savedRoot 'schema-cache.json' }
    } catch {
        Fail $_.Exception.Message 'route_invalid'
    }
}

$headers = $null
$sessionReused = $false
$sessionReusable = $false
$sessionFileWritten = $false
$sessionMode = 'ephemeral'
$sessionRecovered = $false
$cachedSession = $null
$autoDaemonWarning = $null
$operationStarted = $false
$operationCompleted = $false
try {
    try {
        $request = Parse-Request
    } catch {
        Fail $_.Exception.Message 'request_invalid'
    }
    $request = Resolve-GatewayRequest $request
    $legacyFields = @('view', 'intent', 'detail', 'toolName') | Where-Object {
        $request.PSObject.Properties.Name -contains $_
    }
    if ($legacyFields) {
        Fail "Unsupported request field(s): $($legacyFields -join ', '). Use projectionProfile, describeDetail, and describeToolName." 'unsupported_request_field'
    }
    if ($request.endpoint) { $Endpoint = [string]$request.endpoint }
    if ($request.timeoutSec) { $TimeoutSec = [int]$request.timeoutSec }
    if ($request.schemaCacheFile) { $SchemaCacheFile = [string]$request.schemaCacheFile }
    if ($request.sessionFile) { $SessionFile = [string]$request.sessionFile }
    if ($request.PSObject.Properties.Name -contains 'closeSession') { $CloseSession = [bool]$request.closeSession }
    if ($request.daemonUrl) { $DaemonUrl = [string]$request.daemonUrl }
    if ($request.daemonPort) { $DaemonPort = [int]$request.daemonPort }
    if ($request.PSObject.Properties.Name -contains 'autoDaemon') { $AutoDaemon = [bool]$request.autoDaemon }
    if ($request.PSObject.Properties.Name -contains 'envelope') { $Envelope = [bool]$request.envelope }
    if ($request.PSObject.Properties.Name -contains 'diagnostics') { $Diagnostics = [bool]$request.diagnostics }
    if ($request.describeDetail) { $DescribeDetail = [string]$request.describeDetail }
    if ($request.describeToolName) { $DescribeToolName = [string]$request.describeToolName }
    $requestError = Get-GatewayRequestError $request
    if ($requestError) { Fail $requestError.message $requestError.code }
    $action = [string]$request.action
    if ($request.projectionProfile) {
        try { $null = Get-ProjectionProfile ([string]$request.projectionProfile) }
        catch { Fail $_.Exception.Message 'projection_invalid' }
    }

    $DataOnly = -not $Envelope -and -not $Diagnostics

    # Unknown discovery is compact by default; callers that need the old payload ask for full explicitly.
    if ($action -eq 'toolset.describe' -and -not $DescribeDetail) {
        $DescribeDetail = 'call'
        if ($request.PSObject.Properties.Name -contains 'describeDetail') { $request.describeDetail = $DescribeDetail }
        else { $request | Add-Member -NotePropertyName describeDetail -NotePropertyValue $DescribeDetail }
    }

    $null = Assert-LoopbackEndpoint $Endpoint

    if ($AutoDaemon -and -not $SessionFile -and $SchemaCacheFile) {
        $SessionFile = Join-Path (Split-Path -Parent $SchemaCacheFile) 'mcp-session.json'
    }
    if ($SessionFile) {
        $cachedSession = Read-McpSession $Endpoint $SessionFile
    }

    $schemaCacheable = $action -in @('tools.list', 'toolsets.list', 'toolset.describe')
    $cacheToolset = if ($action -eq 'toolset.describe') { [string]$request.toolset } else { '' }
    $cacheSessionId = if ($cachedSession) { [string]$cachedSession.sessionId } else { '' }
    if ($schemaCacheable) {
        $cached = Read-SchemaCacheEntry $action $Endpoint $cacheToolset $SchemaCacheFile $DescribeDetail $DescribeToolName $cacheSessionId
        if ($cached) {
            $operationCompleted = $true
            if ($DataOnly) { Write-JsonResult (Compress-GatewayData $cached.data $request) } else {
                Write-JsonResult @{ ok = $true; action = $action; endpoint = $Endpoint; cached = $true; data = $cached.data }
            }
            exit 0
        }
    }

    $forwardToDaemon = $false
    if ($AutoDaemon -or $DaemonUrl) {
        if (-not $DaemonUrl) { $DaemonUrl = "http://127.0.0.1:$DaemonPort/" }
        $null = Assert-LoopbackEndpoint $DaemonUrl
        if ($AutoDaemon -and $action -notin @('close', 'shutdown')) {
            if (Test-GatewayPort $DaemonUrl) {
                $forwardToDaemon = $true
            } else {
                # Start in the background and execute this first action through the safe one-shot path.
                # Later calls see the ready daemon and avoid process/session setup overhead.
                try {
                    $null = Start-GatewayDaemon $DaemonUrl $DaemonPort $Endpoint $SessionFile $TimeoutSec
                } catch {
                    $autoDaemonWarning = $_.Exception.Message
                }
            }
        } elseif ($DaemonUrl) {
            if (Test-GatewayPort $DaemonUrl) {
                $forwardToDaemon = $true
            } else {
                Fail "Gateway daemon is unavailable or bound to another endpoint/session: $DaemonUrl" 'daemon_unavailable'
            }
        }
        if ($forwardToDaemon) {
            $operationStarted = $true
            $daemonResponse = Invoke-GatewayDaemonRequest $DaemonUrl $request
            if ($AutoDaemon -and [string]$daemonResponse.code -in @('endpoint_mismatch','session_mismatch')) {
                # Receiver explicitly rejected before MCP dispatch; use the same request once locally.
                $operationStarted = $false
                $autoDaemonWarning = [string]$daemonResponse.message
            } else {
                $operationCompleted = $true
                Write-JsonResult $daemonResponse
                if (Test-GatewayFailure $daemonResponse) { exit 1 }
                exit 0
            }
        }
    }

    try { $Projection = Resolve-GatewayProjection $request }
    catch { Fail $_.Exception.Message 'projection_invalid' }

    if ($SessionFile) {
        if ($cachedSession) {
            $headers = Get-McpSessionHeaders $cachedSession.sessionId
            $sessionReused = $true
            $sessionMode = 'reused'
        }
    }
    if (-not $headers) {
        $headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
        $sessionMode = 'new'
    }
    $data = $null
    $raw = $null

    while ($true) {
        $operationStarted = $true
        try {
            switch ($action) {
        'preflight' {
            $probeErrors = [Collections.Generic.List[string]]::new()
            $topLevelTools = @()
            $callViewAvailable = $false
            $reliableState = $null
            $toolsListOk = $false
            $reliableStateOk = $false

            try {
                $toolsRaw = Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
                if (-not $toolsRaw -or $toolsRaw.error) { throw 'tools/list returned no usable response.' }
                $listedTools = @($toolsRaw.result.tools)
                $topLevelTools = @($listedTools | ForEach-Object { [string]$_.name } | Sort-Object -Unique)
                $callViewAvailable = Test-ToolInputEnumValue $listedTools 'describe_toolset' 'detail' 'call'
                $toolsListOk = $true
            } catch {
                if (Test-McpSessionInvalidError $_) { throw }
                $probeErrors.Add("tools/list: $($_.Exception.Message)")
            }

            if (-not $toolsListOk -or 'ueagent_state' -in $topLevelTools) {
                try {
                    $stateRaw = Invoke-TopTool $Endpoint $headers 'ueagent_state' @{} $TimeoutSec
                    $reliableState = Normalize-ToolResult $stateRaw
                    if ($reliableState.ok -eq $false -or $reliableState.success -eq $false) {
                        throw ($reliableState | ConvertTo-Json -Depth 10 -Compress)
                    }
                    if (-not $reliableState -or -not [string]$reliableState.protocol_version -or
                        -not [string]$reliableState.editor_epoch) {
                        throw 'ueagent_state returned no protocol_version or editor_epoch.'
                    }
                    $reliableStateOk = $true
                } catch {
                    if (Test-McpSessionInvalidError $_) { throw }
                    $probeErrors.Add("ueagent_state: $($_.Exception.Message)")
                }
            }

            $data = @{
                toolsList = $toolsListOk
                topLevelTools = $topLevelTools
                callViewAvailable = $callViewAvailable
                livenessRead = $reliableStateOk
                reliableStateRead = $reliableStateOk
                reliableState = $reliableState
                errors = @($probeErrors)
            }
        }
        'ping' {
            $raw = Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
            $data = @{ reachable = $true; topLevelToolCount = @($raw.result.tools).Count }
        }
        'tools.list' {
            $raw = Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
            $data = $raw.result.tools
        }
        'toolsets.list' {
            $raw = Invoke-TopTool $Endpoint $headers 'list_toolsets' @{} $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        'toolset.describe' {
            if (-not $request.toolset) { Fail 'toolset.describe requires toolset.' 'missing_toolset' }
            $describeArguments = @{ toolset_name = [string]$request.toolset }
            if ($DescribeDetail) { $describeArguments.detail = $DescribeDetail }
            if ($DescribeToolName) { $describeArguments.tool_name = $DescribeToolName }
            $raw = Invoke-TopTool $Endpoint $headers 'describe_toolset' $describeArguments $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        { $_ -in @('tool.call','direct.call') } {
            $data = Invoke-TaskCall $request { param($name,$argsObject) Normalize-ToolResult (Invoke-TopTool $Endpoint $headers $name $argsObject $TimeoutSec) }
        }
                default { Fail "Unknown action: $action" 'unknown_action' }
            }
            break
        } catch {
            if (-not $sessionRecovered -and (Test-McpSessionInvalidError $_)) {
                # UE rejects an unknown session before dispatching the JSON-RPC method.
                $operationStarted = $false
                $sessionRecovered = $true
                $headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
                $sessionReused = $false
                $sessionMode = 'recovered'
                continue
            }
            throw
        }
    }
    $operationCompleted = $true
    if ($SessionFile) {
        $persistence = Write-McpSession $Endpoint $headers $SessionFile
        $sessionReusable = [bool]$persistence.reusable
        $sessionFileWritten = [bool]$persistence.written
    }

    if (Test-GatewayFailure $data) {
        $modelError = Compress-GatewayData $data $request
        if ($DataOnly) {
            Write-JsonResult $modelError
            exit 1
        }
        $errorResult = [ordered]@{ ok = $false; action = $action; error = $data }
        if ($Diagnostics) {
            $errorResult.endpoint = $Endpoint
            $errorResult.raw = $raw
        }
        Write-JsonResult $errorResult
        exit 1
    }
    if ($schemaCacheable) {
        $cacheSessionId = if ($headers -and $headers['Mcp-Session-Id']) { [string]$headers['Mcp-Session-Id'] } else { '' }
        Write-SchemaCacheEntry $action $Endpoint $cacheToolset $data $SchemaCacheFile $DescribeDetail $DescribeToolName $cacheSessionId
    }
    $result = @{ ok = $true; action = $action; endpoint = $Endpoint; data = $data }
    if ($schemaCacheable) { $result.cached = $false }
    if ($Diagnostics) {
        $result.transport = @{
            sessionMode = $sessionMode
            sessionReused = $sessionReused
            sessionReusable = $sessionReusable
            sessionFileWritten = $sessionFileWritten
        }
        if ($autoDaemonWarning) { $result.transport.autoDaemonWarning = $autoDaemonWarning }
    }
    if ($DataOnly) { Write-JsonResult (Compress-GatewayData $data $request) } else { Write-JsonResult $result }
} catch {
    $isTimeout = ($_.Exception -is [Net.WebException] -and
        $_.Exception.Status -eq [Net.WebExceptionStatus]::Timeout) -or
        $_.Exception.Message -match '(?i)timed? ?out|timeout|操作超时'
    $code = if ($operationCompleted) { 'response_error' } elseif ($isTimeout -and $operationStarted) { 'result_unknown' } else { 'exception' }
    $message = $_.Exception.Message
    if ($script:DispatchedCommandId) { $message += " command_id=$($script:DispatchedCommandId); query before retrying." }
    Fail $message $code
} finally {
    $keepSession = $SessionFile -and $sessionReusable -and -not $CloseSession
    if (-not $keepSession) {
        Close-McpSession $Endpoint $headers
        if ($CloseSession) { Remove-McpSessionFile $SessionFile }
    }
}
