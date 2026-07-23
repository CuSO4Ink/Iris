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
    [string]$OutFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'

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
        $argsText = $ArgumentsJson
        if ($ArgumentsFile) {
            if (-not (Test-Path -LiteralPath $ArgumentsFile)) { Fail "ArgumentsFile not found: $ArgumentsFile" 'arguments_file_not_found' }
            $argsText = Get-Content -Raw -LiteralPath $ArgumentsFile
        }
        if ($argsText) { $request.arguments = ($argsText | ConvertFrom-Json) }
        return [pscustomobject]$request
    }
    Fail 'Provide -RequestFile, -RequestJson, -RequestBase64, -FromStdin, or -Action.' 'missing_request'
}

function Parse-SseOrJson($Content) {
    if ($null -eq $Content -or -not $Content.Trim()) { return $null }
    $trimmed = $Content.Trim()
    if ($trimmed.StartsWith('{')) { return ($trimmed | ConvertFrom-Json) }
    foreach ($line in ($Content -split "`r?`n")) {
        $line = $line.Trim()
        if ($line.StartsWith('data:')) {
            $json = $line.Substring(5).Trim()
            if ($json -and $json -ne '[DONE]') { return ($json | ConvertFrom-Json) }
        }
    }
    return $null
}

function Try-ParseJsonText($Text) {
    if ($null -eq $Text -or -not ([string]$Text).Trim()) { return $Text }
    try { return ([string]$Text | ConvertFrom-Json) } catch { return $Text }
}

function Normalize-ToolResult($RpcMessage) {
    if ($null -eq $RpcMessage) { return $null }
    if ($RpcMessage.error) { return @{ ok = $false; rpcError = $RpcMessage.error } }
    $result = $RpcMessage.result
    if ($null -eq $result) { return $null }
    if ($result.isError -eq $true) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        return @{ ok = $false; toolError = ($texts -join "`n") }
    }
    if ($result.content) {
        $texts = @($result.content | Where-Object type -eq 'text' | ForEach-Object { [string]$_.text })
        if ($texts.Count -eq 1) { return (Try-ParseJsonText $texts[0]) }
        if ($texts.Count -gt 1) { return @($texts | ForEach-Object { Try-ParseJsonText $_ }) }
    }
    return $result
}

function New-McpSession($Url) {
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
    $response = Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 30
    $sessionId = $response.Headers['Mcp-Session-Id']
    if ($sessionId -is [array]) { $sessionId = $sessionId[0] }
    if (-not $sessionId) { Fail 'Server did not return Mcp-Session-Id.' 'missing_session_id' $response.Content }
    $headers['Mcp-Session-Id'] = $sessionId
    Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' -UseBasicParsing -TimeoutSec 30 | Out-Null
    return $headers
}

function Invoke-McpRpc($Url, $Headers, $Method, $Params = $null, $Id = 2, $Timeout = 120) {
    $payload = @{ jsonrpc = '2.0'; id = $Id; method = $Method }
    if ($null -ne $Params) { $payload.params = $Params }
    $response = Invoke-WebRequest -Uri $Url -Method Post -Headers $Headers -Body ($payload | ConvertTo-Json -Depth 80) -UseBasicParsing -TimeoutSec $Timeout
    return Parse-SseOrJson $response.Content
}

function Invoke-TopTool($Url, $Headers, $Name, $Arguments, $Timeout = 120) {
    Invoke-McpRpc $Url $Headers 'tools/call' @{ name = $Name; arguments = $Arguments } 2 $Timeout
}

try {
    $request = Parse-Request
    if ($request.endpoint) { $Endpoint = [string]$request.endpoint }
    if ($request.timeoutSec) { $TimeoutSec = [int]$request.timeoutSec }
    $action = [string]$request.action
    if (-not $action) { Fail 'Request must include action.' 'missing_action' }

    $headers = New-McpSession $Endpoint
    $data = $null
    $raw = $null

    switch ($action) {
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
            $raw = Invoke-TopTool $Endpoint $headers 'describe_toolset' @{ toolset_name = [string]$request.toolset } $TimeoutSec
            $data = Normalize-ToolResult $raw
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
            $raw = Invoke-TopTool $Endpoint $headers 'call_tool' $callArguments $TimeoutSec
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
        Write-JsonResult @{ ok = $false; action = $action; endpoint = $Endpoint; error = $data; raw = $raw }
        exit 1
    }
    Write-JsonResult @{ ok = $true; action = $action; endpoint = $Endpoint; data = $data }
} catch {
    Fail $_.Exception.Message 'exception'
}
