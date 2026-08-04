param(
    [string]$RequestFile,
    [string]$RequestJson,
    [string]$RequestBase64,
    [switch]$FromStdin,
    [string]$Action,
    [string]$Toolset,
    [string]$Tool,
    [string]$ArgumentsJson = '{}',
    [string]$ArgumentsFile,
    [string]$ScriptFile,
    [string]$Script,
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp',
    [int]$TimeoutSec = 120,
    [string]$SchemaCacheFile,
    [int]$SchemaCacheTtlSec = 300,
    [string]$SessionFile,
    [int]$SessionTtlSec = 900,
    [switch]$ReuseSession,
    [switch]$CloseSession,
    [string]$ProjectionJson,
    [string]$ProjectionFile,
    [string]$DescribeDetail,
    [string]$DescribeToolName,
    [string]$DaemonUrl,
    [int]$DaemonPort = 18765,
    [switch]$AutoDaemon,
    [string]$ProjectionProfile,
    [ValidateSet('summary', 'refs', 'detail', 'full')]
    [string]$View,
    [string]$Intent,
    [switch]$DataOnly,
    [switch]$Envelope,
    [switch]$Diagnostics,
    [string]$OutFile,
    [switch]$Pretty,
    [switch]$AsLibrary
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http

function Write-JsonResult($Object) {
    $json = if ($Pretty) {
        $Object | ConvertTo-Json -Depth 80
    } else {
        $Object | ConvertTo-Json -Depth 80 -Compress
    }
    if ($OutFile) {
        [System.IO.File]::WriteAllText($OutFile, $json, [System.Text.UTF8Encoding]::new($false))
    } else {
        $json
    }
}

function Fail($Message, $Code = 'gateway_error', $Raw = $null) {
    if ($Code -in @('result_unknown', 'exception', 'missing_session_id', 'daemon_unavailable')) {
        Invalidate-DoctorReceipt $Code
        Remove-McpSessionFile $SessionFile
    }
    Write-JsonResult @{ ok = $false; code = $Code; message = $Message; raw = $Raw }
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
    if ($RequestJson) {
        return ($RequestJson | ConvertFrom-Json)
    }
    if ($FromStdin) {
        $json = [Console]::In.ReadToEnd()
        if (-not $json.Trim()) { Fail 'No JSON received from stdin.' 'empty_stdin' }
        return ($json | ConvertFrom-Json)
    }
    if ($Action) {
        $request = [ordered]@{ action = $Action; endpoint = $Endpoint; timeoutSec = $TimeoutSec }
        if ($Toolset) { $request.toolset = $Toolset }
        if ($Tool) { $request.tool = $Tool }
        if ($ScriptFile) { $request.scriptFile = $ScriptFile }
        if ($Script) { $request.script = $Script }
        if ($SchemaCacheFile) { $request.schemaCacheFile = $SchemaCacheFile }
        if ($SchemaCacheTtlSec) { $request.schemaCacheTtlSec = $SchemaCacheTtlSec }
        if ($SessionFile) { $request.sessionFile = $SessionFile }
        if ($SessionTtlSec) { $request.sessionTtlSec = $SessionTtlSec }
        if ($ReuseSession) { $request.reuseSession = $true }
        if ($CloseSession) { $request.closeSession = $true }
        if ($DescribeDetail) { $request.describeDetail = $DescribeDetail }
        if ($DescribeToolName) { $request.describeToolName = $DescribeToolName }
        if ($DaemonUrl) { $request.daemonUrl = $DaemonUrl }
        if ($DaemonPort) { $request.daemonPort = $DaemonPort }
        if ($AutoDaemon) { $request.autoDaemon = $true }
        if ($ProjectionProfile) { $request.projectionProfile = $ProjectionProfile }
        if ($View) { $request.view = $View }
        if ($Intent) { $request.intent = $Intent }
        if ($DataOnly) { $request.dataOnly = $true }
        if ($Envelope) { $request.envelope = $true }
        if ($Diagnostics) { $request.diagnostics = $true }
        $argsText = $ArgumentsJson
        if ($ArgumentsFile) {
            if (-not (Test-Path -LiteralPath $ArgumentsFile)) { Fail "ArgumentsFile not found: $ArgumentsFile" 'arguments_file_not_found' }
            $argsText = Get-Content -Raw -LiteralPath $ArgumentsFile
        }
        if ($argsText) { $request.arguments = ($argsText | ConvertFrom-Json) }
        $projectionText = $ProjectionJson
        if ($ProjectionFile) {
            if (-not (Test-Path -LiteralPath $ProjectionFile)) { Fail "ProjectionFile not found: $ProjectionFile" 'projection_file_not_found' }
            $projectionText = Get-Content -Raw -LiteralPath $ProjectionFile
        }
        if ($projectionText -and $projectionText.Trim()) { $request.projection = ($projectionText | ConvertFrom-Json) }
        return [pscustomobject]$request
    }
    Fail 'Provide -RequestFile, -RequestJson, -RequestBase64, -FromStdin, or -Action.' 'missing_request'
}

function Try-ParseJsonText($Text) {
    if ($null -eq $Text -or -not ([string]$Text).Trim()) { return $Text }
    try { return ([string]$Text | ConvertFrom-Json) } catch { return $Text }
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
            return [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch [IO.IOException] {
            Start-Sleep -Milliseconds 40
        }
    }
    throw "Timed out waiting for MCP session lock: $lockPath"
}

function Exit-SessionFileLock($Path, $Lock) {
    if ($Lock) {
        $Lock.Dispose()
        $lockPath = "$Path.lock"
        Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    }
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
        $expires = [DateTime]::Parse([string]$entry.expiresAtUtc).ToUniversalTime()
        if ($expires -le [DateTime]::UtcNow) { return $null }
        return $entry
    } catch {
        return $null
    } finally {
        Exit-SessionFileLock $Path $lock
    }
}

function Write-McpSession($Url, $Headers, $Path, $TtlSec) {
    if (-not $Path -or -not $Headers -or -not $Headers['Mcp-Session-Id'] -or $TtlSec -le 0) { return $false }
    $parent = Split-Path -Parent $Path
    if (-not $parent -or -not (Test-Path -LiteralPath $parent)) { return $false }
    $lock = $null
    try {
        $lock = Enter-SessionFileLock $Path
        $now = [DateTime]::UtcNow
        $entry = [ordered]@{
            schema = 'ueagent-mcp-session-v1'
            endpoint = [string]$Url
            sessionId = [string]$Headers['Mcp-Session-Id']
            createdAtUtc = $now.ToString('o')
            lastUsedAtUtc = $now.ToString('o')
            expiresAtUtc = $now.AddSeconds($TtlSec).ToString('o')
        }
        [IO.File]::WriteAllText($Path, ($entry | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
        return $true
    } catch {
        return $false
    } finally {
        Exit-SessionFileLock $Path $lock
    }
}

function Remove-McpSessionFile($Path) {
    if ($Path) { Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue }
}

function Invalidate-DoctorReceipt($Reason) {
    if (-not $SessionFile) { return }
    $parent = Split-Path -Parent $SessionFile
    if (-not $parent -or -not (Test-Path -LiteralPath $parent)) { return }
    $path = Join-Path $parent 'doctor.invalidate.json'
    try {
        $entry = [ordered]@{
            schema = 'ueagent-doctor-invalidation-v1'
            invalidatedAtUtc = [DateTime]::UtcNow.ToString('o')
            reason = [string]$Reason
        }
        [IO.File]::WriteAllText($path, ($entry | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    } catch {
        # Receipt invalidation is advisory; never replace the transport error with file noise.
    }
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

function Test-GatewayDaemon($Url) {
    if (-not (Test-GatewayPort $Url)) { return $false }
    try {
        $probeUrl = $Url.TrimEnd('/') + '/__ueagent_daemon'
        $response = Invoke-WebRequest -Uri $probeUrl -Method Post -Headers @{ 'Content-Type' = 'application/json' } `
            -Body '{"action":"daemon.ping"}' -UseBasicParsing -TimeoutSec 2
        $parsed = $response.Content | ConvertFrom-Json
        return ($parsed.ok -eq $true -and $parsed.service -eq 'ueagent-gateway-daemon')
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
        # Optional binding: memory/idle/request budgets still protect a manually started daemon.
    }
    return 0
}

function Start-GatewayDaemon($Url, $Port, $McpUrl, $SessionPath, $TtlSec, $Timeout, [switch]$Wait) {
    if (Test-GatewayPort $Url) {
        if (Test-GatewayDaemon $Url) { return $true }
        throw "Gateway daemon URL is occupied by another service: $Url"
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
                '-SessionTtlSec', [string]$TtlSec,
                '-TimeoutSec', [string]$Timeout,
                '-MaxPrivateMemoryMB', '2048',
                '-MaxRequests', '1000',
                '-MaxUptimeSec', '7200',
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
                if (Test-GatewayDaemon $Url) { $ready = $true; break }
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
    $json = (Get-DaemonRequest $Request) | ConvertTo-Json -Depth 80 -Compress
    $response = Invoke-WebRequest -Uri $Url -Method Post -Headers @{ 'Content-Type' = 'application/json' } `
        -Body $json -UseBasicParsing -TimeoutSec $TimeoutSec
    $parsed = $response.Content | ConvertFrom-Json
    $hasOk = $parsed.PSObject.Properties.Name -contains 'ok'
    if ($hasOk -and $parsed.ok -ne $true) {
        Write-JsonResult $parsed
        exit 1
    }
    Write-JsonResult $parsed
    exit 0
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
        default { throw "Unknown projection profile: $Name. Available profiles: refs, compact, identity, topology, logic, runtime, hlsl, changed (domain.intent aliases supported)." }
    }
}

function Get-IntentProjectionProfile($IntentName) {
    if (-not $IntentName) { return $null }
    $key = ([string]$IntentName).Trim().ToLowerInvariant().Replace('_', '-').Replace('.', '-')
    if ($key -match '(identity|topology|logic|runtime|hlsl|script|changed|changed-readback)$') { return $key }
    return $null
}

function Get-CompactSchemaType($Schema, $Label = '') {
    if ($null -eq $Schema) { return 'json' }
    $union = $null
    if ($Schema.PSObject.Properties.Name -contains 'anyOf') { $union = @($Schema.anyOf) }
    elseif ($Schema.PSObject.Properties.Name -contains 'oneOf') { $union = @($Schema.oneOf) }
    if ($null -ne $union) {
        $types = @($union | ForEach-Object { Get-CompactSchemaType $_ $Label } | Where-Object { $_ -and $_ -ne 'null' } | Select-Object -Unique)
        if ($types.Count) { return ($types -join '|') }
        return 'json'
    }
    $type = [string]$Schema.type
    if ($type -eq 'array') {
        $item = if ($Schema.PSObject.Properties.Name -contains 'items') { Get-CompactSchemaType $Schema.items $Label } else { 'json' }
        return $item + '[]'
    }
    if ($type -eq 'object') {
        $properties = $Schema.properties
        if ($properties -and $properties.PSObject.Properties.Name -contains 'refPath') {
            $lowerLabel = ([string]$Label).ToLowerInvariant()
            if ($lowerLabel.Contains('material') -and ($lowerLabel.Contains('function') -or $lowerLabel.Contains('or'))) {
                return 'ue_ref<Material|MaterialFunction>'
            }
            return 'ue_ref<Object>'
        }
        return 'object'
    }
    $title = [string]$Schema.title
    if ($title) {
        $leaf = ($title -split '[/.]')[-1]
        return 'ue_ref<' + $leaf + '>'
    }
    if ($type) { return $type }
    return 'json'
}

function Get-CompactToolName($Toolset, $FullName) {
    $toolsetLeaf = (([string]$Toolset) -split '\.')[-1]
    $toolLeaf = [string]$FullName
    $prefix = [string]$Toolset + '.'
    if ($toolLeaf.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        $toolLeaf = $toolLeaf.Substring($prefix.Length)
    } else {
        $toolLeaf = (($toolLeaf -split '\.')[-1])
    }
    return $toolsetLeaf + '.' + $toolLeaf
}

function Get-CompactEffect($Name, $Description) {
    $leafName = (([string]$Name) -split '\.')[-1]
    $lower = ($leafName + ' ' + ([string]$Description)).ToLowerInvariant()
    if ($lower.Contains('save')) { return 'save' }
    foreach ($word in @('create', 'add', 'delete', 'remove', 'update', 'set_', 'write', 'modify', 'edit', 'rename', 'move', 'execute')) {
        if ($lower.StartsWith($word) -or $lower.Contains(' ' + $word) -or $lower.Contains('_' + $word) -or $lower.Contains('.' + $word)) { return 'write' }
    }
    foreach ($word in @('get', 'list', 'find', 'read', 'describe', 'inspect', 'query', 'search', 'check', 'validate', 'discover')) {
        if ($lower.StartsWith($word) -or $lower.Contains(' ' + $word) -or $lower.Contains('_' + $word) -or $lower.Contains('.' + $word)) { return 'read' }
    }
    return 'unknown'
}

function Convert-ToCallView($Data, $Toolset, $ToolName = '') {
    if ($null -eq $Data) { return $null }
    if ($Data.PSObject.Properties.Name -contains 'tool' -and
        $Data.PSObject.Properties.Name -contains 'args' -and
        $Data.PSObject.Properties.Name -contains 'returns') { return $Data }
    if (-not ($Data.PSObject.Properties.Name -contains 'tools')) { return $Data }
    $tools = @($Data.tools)
    if ($ToolName) {
        $tools = @($tools | Where-Object {
            $full = [string]$_.name
            $full -eq ([string]$Toolset + '.' + [string]$ToolName) -or (($full -split '\.')[-1] -eq [string]$ToolName)
        })
    }
    if ($tools.Count -eq 0) { return $Data }
    $views = @()
    foreach ($tool in $tools) {
        $args = [ordered]@{}
        $input = $tool.inputSchema
        $required = @()
        if ($input -and $input.PSObject.Properties.Name -contains 'required') { $required = @($input.required | ForEach-Object { [string]$_ }) }
        if ($input -and $input.properties) {
            foreach ($property in @($input.properties.PSObject.Properties)) {
                $type = Get-CompactSchemaType $property.Value $property.Name
                if ($required -contains $property.Name) { $type += '!' }
                $args[$property.Name] = $type
            }
        }
        $returns = [ordered]@{}
        $output = $tool.outputSchema
        if ($output -and $output.properties) {
            foreach ($property in @($output.properties.PSObject.Properties)) {
                $returns[$property.Name] = Get-CompactSchemaType $property.Value $property.Name
            }
        }
        $views += [ordered]@{
            tool = Get-CompactToolName $Toolset $tool.name
            effect = Get-CompactEffect $tool.name $tool.description
            args = $args
            returns = $returns
        }
    }
    if ($ToolName -or $views.Count -eq 1) { return $views[0] }
    return [ordered]@{ tools = $views }
}

function Compress-ToolError($Text) {
    $value = [string]$Text
    $marker = $value.IndexOf('Available toolsets:', [StringComparison]::OrdinalIgnoreCase)
    if ($marker -ge 0) { $value = $value.Substring(0, $marker).TrimEnd() + ' Available toolsets omitted.' }
    if ($value.Length -gt 768) { $value = $value.Substring(0, 768).TrimEnd() + '...' }
    return $value
}

function Get-DaemonRequest($Request) {
    $allowed = @(
        'action', 'toolset', 'tool', 'scriptFile', 'script', 'arguments',
        'describeDetail', 'describeToolName', 'detail', 'toolName',
        'projection', 'projectionProfile', 'view', 'intent',
        'dataOnly', 'envelope', 'diagnostics', 'schemaCacheFile', 'schemaCacheTtlSec'
    )
    $forward = [ordered]@{}
    foreach ($name in $allowed) {
        if ($Request.PSObject.Properties.Name -contains $name) { $forward[$name] = $Request.$name }
    }
    return [pscustomobject]$forward
}

function Get-IntentIndex($Filter = $null) {
    return (Get-IntentIndexData $Filter)
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

function Get-IntentIndexData($Filter = $null) {
    $domains = [ordered]@{
        material = [ordered]@{
            summary = 'identity, material settings, cache freshness'
            intents = [ordered]@{
                expressions = [ordered]@{ toolset = 'MaterialTools'; tool = 'get_expressions' }
                parameters = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
                references = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
            }
        }
        'material-function' = [ordered]@{
            summary = 'function interface, call sites, function graph'
            intents = [ordered]@{
                interface = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
                graph = [ordered]@{ toolset = 'MaterialTools'; tool = 'get_expressions' }
                references = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
            }
        }
        'material-instance' = [ordered]@{
            summary = 'parent material and active overrides'
            intents = [ordered]@{
                overrides = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
                parent = [ordered]@{ toolset = 'MaterialTools'; tool = $null; via = 'describe_toolset' }
            }
        }
        blueprint = [ordered]@{
            summary = 'components, variables, event and function graphs'
            intents = [ordered]@{
                summary = [ordered]@{ toolset = 'BlueprintTools'; tool = $null; via = 'describe_toolset' }
                graph = [ordered]@{ toolset = 'BlueprintTools'; tool = 'read_graph_dsl' }
                references = [ordered]@{ toolset = 'BlueprintTools'; tool = $null; via = 'describe_toolset' }
            }
        }
        niagara = [ordered]@{
            summary = 'system, emitters, module order, runtime overrides'
            intents = [ordered]@{
                summary = [ordered]@{ toolset = 'NiagaraTools'; tool = $null; via = 'describe_toolset' }
                stack = [ordered]@{ toolset = 'NiagaraTools'; tool = $null; via = 'describe_toolset' }
                runtime = [ordered]@{ toolset = 'NiagaraTools'; tool = 'GetRuntimeState' }
            }
        }
        scene = [ordered]@{
            summary = 'level, components, actual overrides'
            intents = [ordered]@{
                level = [ordered]@{ toolset = 'SceneTools'; tool = 'get_current_level' }
                references = [ordered]@{ toolset = 'SceneTools'; tool = $null; via = 'describe_toolset' }
            }
        }
    }
    $selected = if ($Filter) {
        if (-not $domains.Contains($Filter)) { throw "Unknown intent domain: $Filter" }
        [ordered]@{ $Filter = $domains[$Filter] }
    } else { $domains }
    return [ordered]@{
        schema = 'ueagent-intent-index-v1'
        source = 'local-routing-hint'
        authority = 'running describe_toolset response'
        defaultView = 'summary'
        defaultDescribeDetail = 'call'
        expansion = @('summary', 'refs', 'detail', 'full')
        domains = $selected
    }
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
            $expires = [DateTime]::Parse([string]$entry.expiresAtUtc).ToUniversalTime()
            if ($expires -gt [DateTime]::UtcNow) { return $entry }
        }
    } catch {
        # A corrupt or stale schema cache is disposable; fall through to live discovery.
    }
    return $null
}

function Write-SchemaCacheEntry($Action, $Url, $Toolset, $Data, $Path, $TtlSec, $Detail = '', $ToolName = '', $SessionId = '') {
    if (-not $Path -or $TtlSec -le 0) { return }
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
            [string]$_.sessionId -eq $SessionId -and
            ([DateTime]::Parse([string]$_.expiresAtUtc).ToUniversalTime() -gt $now)
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
        expiresAtUtc = [DateTime]::UtcNow.AddSeconds($TtlSec).ToString('o')
        data = $Data
    }
    $cache = [ordered]@{ schema = 'ueagent-schema-cache-v1'; entries = $entries }
    try {
        [IO.File]::WriteAllText($Path, ($cache | ConvertTo-Json -Depth 80), [Text.UTF8Encoding]::new($false))
    } catch {
        # Discovery still succeeded; cache persistence is only an optimization.
    }
}

function Normalize-ToolResult($RpcMessage) {
    if ($null -eq $RpcMessage) { return $null }
    if ($RpcMessage.error) { return @{ ok = $false; rpcError = $RpcMessage.error } }
    $result = $RpcMessage.result
    if ($null -eq $result) { return $null }
    if ($result.isError -eq $true) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        return @{ ok = $false; toolError = (Compress-ToolError ($texts -join "`n")) }
    }
    if ($null -ne $result.structuredContent) {
        return $result.structuredContent
    }
    if ($result.content) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        if ($texts.Count -eq 1) { return (Try-ParseJsonText $texts[0]) }
        if ($texts.Count -gt 1) { return @($texts | ForEach-Object { Try-ParseJsonText $_ }) }
    }
    return $result
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
        $response.EnsureSuccessStatusCode() | Out-Null
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
            $reader = [IO.StreamReader]::new($streamTask.Result)
            $chars = New-Object char[] 8192
            $messageBuilder = [Text.StringBuilder]::new()
            $responseBytes = 0L
            while ($true) {
                $remainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
                $read = $reader.ReadAsync($chars, 0, $chars.Length)
                if (-not $read.Wait($remainingMs)) {
                    $cts.Cancel()
                    throw [TimeoutException]::new("MCP $Method timed out reading JSON-RPC id $Id.")
                }
                $count = $read.Result
                if ($count -eq 0) { break }
                if ($MaxResponseBytes -gt 0) {
                    $responseBytes += [Text.Encoding]::UTF8.GetByteCount($chars, 0, $count)
                    if ($responseBytes -gt $MaxResponseBytes) {
                        throw "MCP $Method response exceeds ${MaxResponseBytes} bytes. Use a projection or a smaller detail view."
                    }
                }
                $messageBuilder.Append($chars, 0, $count) | Out-Null
            }
            $messageText = $messageBuilder.ToString()
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
        $chars = New-Object char[] 8192
        $lineBuilder = [Text.StringBuilder]::new()
        $responseBytes = 0L
        while ($true) {
            $remainingMs = [Math]::Max(1, [int](($Timeout * 1000) - $timer.ElapsedMilliseconds))
            if ($remainingMs -le 1) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out waiting for JSON-RPC id $Id.")
            }
            $read = $reader.ReadAsync($chars, 0, $chars.Length)
            if (-not $read.Wait($remainingMs)) {
                $cts.Cancel()
                throw [TimeoutException]::new("MCP $Method timed out waiting for JSON-RPC id $Id.")
            }
            $count = $read.Result
            if ($count -eq 0) {
                if ($lineBuilder.Length -eq 0) {
                    $preview = @($seenLines) -join ' | '
                    throw "MCP $Method ended before JSON-RPC id $Id. Response preview: $preview"
                }
                $line = $lineBuilder.ToString()
                $lineBuilder.Clear() | Out-Null
                $line = $line.Trim()
                if (-not $line) { continue }
                if ($seenLines.Count -lt 3) { $seenLines.Add($line.Substring(0, [Math]::Min(200, $line.Length))) }
                $json = if ($line.StartsWith('data:')) { $line.Substring(5).Trim() } else { $line }
                if ($json -and $json -ne '[DONE]') {
                    try { $message = $json | ConvertFrom-Json } catch { $message = $null }
                    if ($message -and [string]$message.id -eq [string]$Id) { return $message }
                }
                $preview = @($seenLines) -join ' | '
                throw "MCP $Method ended before JSON-RPC id $Id. Response preview: $preview"
            }
            if ($MaxResponseBytes -gt 0) {
                $responseBytes += [Text.Encoding]::UTF8.GetByteCount($chars, 0, $count)
                if ($responseBytes -gt $MaxResponseBytes) {
                    throw "MCP $Method response exceeds ${MaxResponseBytes} bytes. Use a projection or a smaller detail view."
                }
            }
            for ($index = 0; $index -lt $count; $index++) {
                $char = $chars[$index]
                if ($char -eq "`n") {
                    $line = $lineBuilder.ToString().Trim()
                    $lineBuilder.Clear() | Out-Null
                    if (-not $line) { continue }
                    if ($seenLines.Count -lt 3) { $seenLines.Add($line.Substring(0, [Math]::Min(200, $line.Length))) }
                    $json = if ($line.StartsWith('data:')) { $line.Substring(5).Trim() } else { $line }
                    if (-not $json -or $json -eq '[DONE]') { continue }
                    try { $message = $json | ConvertFrom-Json } catch { continue }
                    if ([string]$message.id -eq [string]$Id) { return $message }
                } elseif ($char -ne "`r") {
                    $lineBuilder.Append($char) | Out-Null
                }
            }
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

function Invoke-TopTool($Url, $Headers, $Name, $Arguments, $Timeout = 120, [Net.Http.HttpClient]$Client = $null, [int64]$MaxResponseBytes = 67108864) {
    Invoke-McpRpc $Url $Headers 'tools/call' @{ name = $Name; arguments = $Arguments } 2 $Timeout $Client $MaxResponseBytes
}

if ($AsLibrary) { return }

$headers = $null
$sessionReused = $false
$sessionPersisted = $false
$sessionMode = 'ephemeral'
$sessionProbeMs = $null
$reusedToolsList = $null
$cachedSession = $null
$autoDaemonWarning = $null
try {
    $request = Parse-Request
    if ($request.endpoint) { $Endpoint = [string]$request.endpoint }
    if ($request.timeoutSec) { $TimeoutSec = [int]$request.timeoutSec }
    if ($request.schemaCacheFile) { $SchemaCacheFile = [string]$request.schemaCacheFile }
    if ($request.schemaCacheTtlSec) { $SchemaCacheTtlSec = [int]$request.schemaCacheTtlSec }
    if ($request.sessionFile) { $SessionFile = [string]$request.sessionFile }
    if ($request.sessionTtlSec) { $SessionTtlSec = [int]$request.sessionTtlSec }
    if ($request.PSObject.Properties.Name -contains 'reuseSession') { $ReuseSession = [bool]$request.reuseSession }
    if ($request.PSObject.Properties.Name -contains 'closeSession') { $CloseSession = [bool]$request.closeSession }
    if ($request.daemonUrl) { $DaemonUrl = [string]$request.daemonUrl }
    if ($request.daemonPort) { $DaemonPort = [int]$request.daemonPort }
    if ($request.PSObject.Properties.Name -contains 'autoDaemon') { $AutoDaemon = [bool]$request.autoDaemon }
    if ($request.projectionProfile) { $ProjectionProfile = [string]$request.projectionProfile }
    if ($request.view) { $View = [string]$request.view }
    if ($request.intent) { $Intent = [string]$request.intent }
    if ($request.PSObject.Properties.Name -contains 'dataOnly') { $DataOnly = [bool]$request.dataOnly }
    if ($request.PSObject.Properties.Name -contains 'envelope') { $Envelope = [bool]$request.envelope }
    if ($request.PSObject.Properties.Name -contains 'diagnostics') { $Diagnostics = [bool]$request.diagnostics }
    if ($request.describeDetail) { $DescribeDetail = [string]$request.describeDetail }
    if ($request.describeToolName) { $DescribeToolName = [string]$request.describeToolName }
    if ($request.detail) { $DescribeDetail = [string]$request.detail }
    if ($request.toolName) { $DescribeToolName = [string]$request.toolName }
    $Projection = if ($request.PSObject.Properties.Name -contains 'projection') { $request.projection } else { $null }
    if ($null -eq $Projection -and -not $ProjectionProfile -and $View -in @('summary', 'refs')) {
        $ProjectionProfile = if ($View -eq 'refs') { 'refs' } else { 'compact' }
    }
    if ($null -eq $Projection -and -not $ProjectionProfile) {
        $intentProfile = Get-IntentProjectionProfile $Intent
        if ($intentProfile) { $ProjectionProfile = $intentProfile }
    }
    if ($null -eq $Projection -and $ProjectionProfile) { $Projection = Get-ProjectionProfile $ProjectionProfile }
    $action = [string]$request.action
    if (-not $action) { Fail 'Request must include action.' 'missing_action' }

    $explicitResponseMode = ($request.PSObject.Properties.Name -contains 'dataOnly') -or
        ($request.PSObject.Properties.Name -contains 'envelope')
    if ($Envelope) { $DataOnly = $false }
    elseif ($Diagnostics) { $DataOnly = $false }
    elseif (-not $explicitResponseMode -and $action -ne 'preflight') {
        $DataOnly = $true
        $request | Add-Member -NotePropertyName dataOnly -NotePropertyValue $true
    }

    # Unknown discovery is compact by default; callers that need the old payload ask for full explicitly.
    if ($action -eq 'toolset.describe' -and -not $DescribeDetail) {
        $DescribeDetail = 'call'
        if ($request.PSObject.Properties.Name -contains 'describeDetail') { $request.describeDetail = $DescribeDetail }
        else { $request | Add-Member -NotePropertyName describeDetail -NotePropertyValue $DescribeDetail }
    }

    if ($action -eq 'intent.list') {
        $intentData = Get-IntentIndex $Intent
        if ($DataOnly) { Write-JsonResult $intentData } else {
            Write-JsonResult @{ ok = $true; action = $action; data = $intentData }
        }
        exit 0
    }
    $null = Assert-LoopbackEndpoint $Endpoint

    if ($AutoDaemon -and -not $SessionFile -and $SchemaCacheFile) {
        $SessionFile = Join-Path (Split-Path -Parent $SchemaCacheFile) 'mcp-session.json'
    }
    if ($SessionFile) { $ReuseSession = $true }

    if ($ReuseSession -and $SessionFile) {
        $cachedSession = Read-McpSession $Endpoint $SessionFile
    }

    $schemaCacheable = $action -in @('tools.list', 'toolsets.list', 'toolset.describe')
    $cacheToolset = if ($action -eq 'toolset.describe') { [string]$request.toolset } else { '' }
    $cacheSessionId = if ($cachedSession) { [string]$cachedSession.sessionId } else { '' }
    if ($schemaCacheable) {
        $cached = Read-SchemaCacheEntry $action $Endpoint $cacheToolset $SchemaCacheFile $DescribeDetail $DescribeToolName $cacheSessionId
        if ($cached) {
            if ($DataOnly) { Write-JsonResult $cached.data } else {
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
            if (Test-GatewayDaemon $DaemonUrl) {
                $forwardToDaemon = $true
            } else {
                # Start in the background and execute this first action through the safe one-shot path.
                # Later calls see the ready daemon and avoid process/session setup overhead.
                try {
                    $null = Start-GatewayDaemon $DaemonUrl $DaemonPort $Endpoint $SessionFile $SessionTtlSec $TimeoutSec
                } catch {
                    $autoDaemonWarning = $_.Exception.Message
                }
            }
        } elseif ($DaemonUrl) {
            if (Test-GatewayDaemon $DaemonUrl) {
                $forwardToDaemon = $true
            } else {
                Fail "Gateway daemon is not available or failed identity check: $DaemonUrl" 'daemon_unavailable'
            }
        }
        if ($forwardToDaemon) {
            if ($request.PSObject.Properties.Name -notcontains 'endpoint') {
                $request | Add-Member -NotePropertyName endpoint -NotePropertyValue $Endpoint
            }
            if ($request.PSObject.Properties.Name -notcontains 'sessionFile' -and $SessionFile) {
                $request | Add-Member -NotePropertyName sessionFile -NotePropertyValue $SessionFile
            }
            if ($request.PSObject.Properties.Name -notcontains 'sessionTtlSec') {
                $request | Add-Member -NotePropertyName sessionTtlSec -NotePropertyValue $SessionTtlSec
            }
            Invoke-GatewayDaemonRequest $DaemonUrl $request
        }
    }

    if ($ReuseSession -and $SessionFile) {
        if ($cachedSession) {
            $probeTimer = [Diagnostics.Stopwatch]::StartNew()
            $candidateHeaders = Get-McpSessionHeaders $cachedSession.sessionId
            try {
                $probe = Invoke-McpRpc $Endpoint $candidateHeaders 'tools/list' @{} 2 ([Math]::Min($TimeoutSec, 10))
                if ($probe -and -not $probe.error) {
                    $headers = $candidateHeaders
                    $sessionReused = $true
                    $sessionMode = 'reused'
                    $reusedToolsList = $probe
                }
            } catch {
                # Stale, expired, or editor-restart sessions are replaced below.
            } finally {
                $sessionProbeMs = [int]$probeTimer.ElapsedMilliseconds
            }
        }
    }
    if (-not $headers) {
        $headers = New-McpSession $Endpoint ([Math]::Min($TimeoutSec, 30))
        $sessionMode = 'new'
    }
    $data = $null
    $raw = $null

    switch ($action) {
        'preflight' {
            $probeErrors = [Collections.Generic.List[string]]::new()
            $topLevelTools = @()
            $currentLevel = $null
            $toolsListOk = $false
            $currentLevelOk = $false

            try {
                $toolsRaw = if ($reusedToolsList) { $reusedToolsList } else {
                    Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
                }
                $reusedToolsList = $null
                if (-not $toolsRaw -or $toolsRaw.error) { throw 'tools/list returned no usable response.' }
                $topLevelTools = @($toolsRaw.result.tools | ForEach-Object { [string]$_.name } | Sort-Object -Unique)
                $toolsListOk = $true
            } catch {
                $probeErrors.Add("tools/list: $($_.Exception.Message)")
            }

            if ($toolsListOk -and 'call_tool' -in $topLevelTools) {
                try {
                    $levelRaw = Invoke-TopTool $Endpoint $headers 'call_tool' @{
                        toolset_name = 'editor_toolset.toolsets.scene.SceneTools'
                        tool_name = 'get_current_level'
                        arguments = @{}
                    } $TimeoutSec
                    $currentLevel = Normalize-ToolResult $levelRaw
                    if ($currentLevel -is [hashtable] -and $currentLevel.ok -eq $false) {
                        throw ($currentLevel | ConvertTo-Json -Depth 10 -Compress)
                    }
                    $currentLevelOk = $true
                } catch {
                    $probeErrors.Add("current_level: $($_.Exception.Message)")
                }
            }

            $data = @{
                toolsList = $toolsListOk
                topLevelTools = $topLevelTools
                currentLevelRead = $currentLevelOk
                currentLevel = $currentLevel
                errors = @($probeErrors)
            }
        }
        'ping' {
            $raw = if ($reusedToolsList) { $reusedToolsList } else {
                Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
            }
            $reusedToolsList = $null
            $data = @{ reachable = $true; topLevelToolCount = @($raw.result.tools).Count }
        }
        'tools.list' {
            $raw = if ($reusedToolsList) { $reusedToolsList } else {
                Invoke-McpRpc $Endpoint $headers 'tools/list' @{} 2 $TimeoutSec
            }
            $reusedToolsList = $null
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
            if ($DescribeDetail -eq 'call' -and $data -is [hashtable] -and $data.ok -eq $false -and [string]$data.toolError -match "detail must") {
                # v2 servers do not know call; keep the gateway usable until the editor is rebuilt.
                $fallbackDetail = 'full'
                $describeArguments.detail = $fallbackDetail
                $raw = Invoke-TopTool $Endpoint $headers 'describe_toolset' $describeArguments $TimeoutSec
                $data = Normalize-ToolResult $raw
            }
            if ($DescribeDetail -eq 'call' -and -not ($data -is [hashtable] -and $data.ok -eq $false)) {
                $data = Convert-ToCallView $data $request.toolset $DescribeToolName
            }
        }
        'tool.call' {
            $toolset = [string]$request.toolset
            $tool = [string]$request.tool
            if (-not $tool) { Fail 'tool.call requires tool.' 'missing_tool' }
            if (-not $toolset -and $tool.Contains('.')) {
                $index = $tool.LastIndexOf('.')
                $toolset = $tool.Substring(0, $index)
                $tool = $tool.Substring($index + 1)
            }
            $arguments = @{}
            if ($request.PSObject.Properties.Name -contains 'arguments') { $arguments = $request.arguments }
            $callArguments = @{ tool_name = $tool; arguments = $arguments }
            if ($toolset) { $callArguments.toolset_name = $toolset }
            if ($null -ne $Projection) { $callArguments.projection = $Projection }
            $raw = Invoke-TopTool $Endpoint $headers 'call_tool' $callArguments $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        'direct.call' {
            $tool = [string]$request.tool
            if (-not $tool) { Fail 'direct.call requires tool.' 'missing_tool' }
            $arguments = @{}
            if ($request.PSObject.Properties.Name -contains 'arguments') { $arguments = $request.arguments }
            $raw = Invoke-TopTool $Endpoint $headers $tool $arguments $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        'script.execute' {
            $scriptText = [string]$request.script
            if (-not $scriptText -and $request.scriptFile) {
                $path = [string]$request.scriptFile
                if (-not (Test-Path -LiteralPath $path)) { Fail "scriptFile not found: $path" 'script_file_not_found' }
                $scriptText = Get-Content -Raw -LiteralPath $path
            }
            if (-not $scriptText) { Fail 'script.execute requires script or scriptFile.' 'missing_script' }
            $raw = Invoke-TopTool $Endpoint $headers 'call_tool' @{
                toolset_name = 'editor_toolset.toolsets.programmatic.ProgrammaticToolset'
                tool_name = 'execute_tool_script'
                arguments = @{ script = $scriptText }
                projection = $Projection
            } $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        'level.current' {
            $raw = Invoke-TopTool $Endpoint $headers 'call_tool' @{
                toolset_name = 'editor_toolset.toolsets.scene.SceneTools'
                tool_name = 'get_current_level'
                arguments = @{}
            } $TimeoutSec
            $data = Normalize-ToolResult $raw
        }
        default { Fail "Unknown action: $action" 'unknown_action' }
    }

    if ($data -is [hashtable] -and $data.ok -eq $false) {
        $errorResult = [ordered]@{ ok = $false; action = $action; error = $data }
        if ($Diagnostics) {
            $errorResult.endpoint = $Endpoint
            $errorResult.raw = $raw
        }
        Write-JsonResult $errorResult
        exit 1
    }
    if ($ReuseSession -and $SessionFile) {
        $sessionPersisted = Write-McpSession $Endpoint $headers $SessionFile $SessionTtlSec
    }
    if ($schemaCacheable) {
        $cacheSessionId = if ($headers -and $headers['Mcp-Session-Id']) { [string]$headers['Mcp-Session-Id'] } else { '' }
        Write-SchemaCacheEntry $action $Endpoint $cacheToolset $data $SchemaCacheFile $SchemaCacheTtlSec $DescribeDetail $DescribeToolName $cacheSessionId
    }
    $result = @{ ok = $true; action = $action; endpoint = $Endpoint; data = $data }
    if ($schemaCacheable) { $result.cached = $false }
    if ($Diagnostics) {
        $result.transport = @{
            sessionMode = $sessionMode
            sessionReused = $sessionReused
            sessionPersisted = $sessionPersisted
            sessionProbeMs = $sessionProbeMs
        }
        if ($autoDaemonWarning) { $result.transport.autoDaemonWarning = $autoDaemonWarning }
    }
    if ($DataOnly) { Write-JsonResult $data } else { Write-JsonResult $result }
} catch {
    $isTimeout = ($_.Exception -is [Net.WebException] -and
        $_.Exception.Status -eq [Net.WebExceptionStatus]::Timeout) -or
        $_.Exception.Message -match '(?i)timed? ?out|timeout|操作超时'
    $code = if ($isTimeout) { 'result_unknown' } else { 'exception' }
    Invalidate-DoctorReceipt $code
    Remove-McpSessionFile $SessionFile
    Fail $_.Exception.Message $code
} finally {
    $keepSession = $ReuseSession -and $SessionFile -and $sessionPersisted -and -not $CloseSession
    if (-not $keepSession) {
        Close-McpSession $Endpoint $headers
        if ($CloseSession) {
            Invalidate-DoctorReceipt 'session_closed'
            Remove-McpSessionFile $SessionFile
        }
    }
}
