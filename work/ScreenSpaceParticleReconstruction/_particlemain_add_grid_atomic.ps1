param(
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp'
)

$ErrorActionPreference = 'Stop'
$headers = @{
    'Content-Type' = 'application/json'
    'Accept' = 'application/json, text/event-stream'
}

function Parse-Response([string]$Content) {
    $trimmed = $Content.Trim()
    if ($trimmed.StartsWith('{')) {
        return ($trimmed | ConvertFrom-Json)
    }
    foreach ($line in ($Content -split "`r?`n")) {
        $candidate = $line.Trim()
        if ($candidate.StartsWith('data:')) {
            $json = $candidate.Substring(5).Trim()
            if ($json -and $json -ne '[DONE]') {
                return ($json | ConvertFrom-Json)
            }
        }
    }
    throw 'No JSON response from MCP.'
}

function Invoke-Rpc(
    [hashtable]$CallHeaders,
    [string]$Method,
    [object]$Params,
    [int]$Id
) {
    $payload = @{
        jsonrpc = '2.0'
        id = $Id
        method = $Method
        params = $Params
    } | ConvertTo-Json -Depth 80
    $response = Invoke-WebRequest `
        -Uri $Endpoint `
        -Method Post `
        -Headers $CallHeaders `
        -Body $payload `
        -UseBasicParsing `
        -TimeoutSec 120
    return Parse-Response $response.Content
}

$initialize = @{
    jsonrpc = '2.0'
    id = 1
    method = 'initialize'
    params = @{
        protocolVersion = '2024-11-05'
        capabilities = @{}
        clientInfo = @{
            name = 'ueagent-atomic-grid-setup'
            version = '1.0'
        }
    }
} | ConvertTo-Json -Depth 30
$initResponse = Invoke-WebRequest `
    -Uri $Endpoint `
    -Method Post `
    -Headers $headers `
    -Body $initialize `
    -UseBasicParsing `
    -TimeoutSec 30
$sessionId = $initResponse.Headers['Mcp-Session-Id']
if ($sessionId -is [array]) {
    $sessionId = $sessionId[0]
}
if (-not $sessionId) {
    throw 'MCP session id was not returned.'
}
$headers['Mcp-Session-Id'] = $sessionId
Invoke-WebRequest `
    -Uri $Endpoint `
    -Method Post `
    -Headers $headers `
    -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' `
    -UseBasicParsing `
    -TimeoutSec 30 | Out-Null

$scriptPath = (
    'C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\' +
    '_particlemain_create_user_grid_di.py'
)
$pythonCode = (
    "import unreal`n" +
    "script_path=r'$scriptPath'`n" +
    "with open(script_path,'r',encoding='utf-8') as handle:`n" +
    "    source=handle.read()`n" +
    "exec(compile(source,script_path,'exec'))"
)
$createResponse = Invoke-Rpc $headers 'tools/call' @{
    name = 'call_tool'
    arguments = @{
        tool_name = 'execute_python_code'
        arguments = @{ code = $pythonCode }
    }
} 2

$addRequestPath = (
    'C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\' +
    '_particlemain_req_add_user_grid_only.json'
)
$addRequest = Get-Content -Raw -LiteralPath $addRequestPath |
    ConvertFrom-Json
$addResponse = Invoke-Rpc $headers 'tools/call' @{
    name = 'call_tool'
    arguments = @{
        toolset_name = 'NiagaraToolsets.NiagaraToolset_System'
        tool_name = 'AddUserVariables'
        arguments = $addRequest.arguments
    }
} 3

[pscustomobject]@{
    create = $createResponse
    add = $addResponse
} | ConvertTo-Json -Depth 80
