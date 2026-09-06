[CmdletBinding()]
param(
    [int]$SuccessPayloadBytes = 8388608,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
$gateway = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway.ps1'
$fixture = Join-Path $PSScriptRoot 'mcp_gateway_mock_server.py'
$python = (Get-Command python -ErrorAction Stop).Source
$tempBase = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../tmp/UEAgent'))
$testRoot = Join-Path $tempBase ('ueagent-gateway-test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testRoot

function Get-FreePort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally {
        $listener.Stop()
    }
}

function Wait-LoopbackPort([int]$Port, [int]$TimeoutMs = 5000) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.ElapsedMilliseconds -lt $TimeoutMs) {
        $client = [Net.Sockets.TcpClient]::new()
        try {
            $connect = $client.ConnectAsync('127.0.0.1', $Port)
            if ($connect.Wait(100) -and $client.Connected) { return }
        } catch {
        } finally {
            $client.Dispose()
        }
        Start-Sleep -Milliseconds 25
    }
    throw "Fixture did not listen on port $Port within ${TimeoutMs}ms."
}

function Start-Fixture([string]$Mode, [int]$PayloadBytes) {
    $port = Get-FreePort
    $stdout = Join-Path $testRoot "$Mode-$port-server.stdout.txt"
    $stderr = Join-Path $testRoot "$Mode-$port-server.stderr.txt"
    $process = Start-Process -FilePath $python -ArgumentList @(
        $fixture,
        '--port', [string]$port,
        '--mode', $Mode,
        '--payload-bytes', [string]$PayloadBytes
    ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try {
        Wait-LoopbackPort $port
    } catch {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        throw
    }
    return [pscustomobject]@{ Process=$process; Port=$port; Stdout=$stdout; Stderr=$stderr }
}

function Stop-Fixture($Server) {
    if ($Server -and $Server.Process -and -not $Server.Process.HasExited) {
        Stop-Process -Id $Server.Process.Id -Force
        $Server.Process.WaitForExit(2000) | Out-Null
    }
}

function Write-TestSession([string]$Path, [int]$Port, [string]$SessionId, [DateTime]$CreatedAtUtc, [DateTime]$ExpiresAtUtc) {
    $entry = [ordered]@{
        schema = 'ueagent-mcp-session-v1'
        endpoint = "http://127.0.0.1:$Port/mcp"
        sessionId = $SessionId
        binding = $null
    }
    [IO.File]::WriteAllText($Path, ($entry | ConvertTo-Json -Depth 4 -Compress), [Text.UTF8Encoding]::new($false))
}

function Invoke-GatewayProbe(
    [string]$Name,
    [int]$Port,
    [int]$TimeoutSec,
    [int]$MaxWaitMs,
    [string]$Action = 'direct.call',
    [string]$Tool = 'ueagent_state',
    [string]$SessionFile
) {
    $stdout = Join-Path $testRoot "$Name-gateway.stdout.txt"
    $stderr = Join-Path $testRoot "$Name-gateway.stderr.txt"
    $output = Join-Path $testRoot "$Name-result.json"
    $requestJson = @{ action=$Action; tool=$Tool; arguments=@{} } | ConvertTo-Json -Compress
    $requestBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($requestJson))
    $gatewayArguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $gateway,
        '-RequestBase64', $requestBase64,
        '-Endpoint', "http://127.0.0.1:$Port/mcp",
        '-TimeoutSec', [string]$TimeoutSec,
        '-OutFile', $output
    )
    if ($SessionFile) { $gatewayArguments += @('-SessionFile', $SessionFile) }
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $gatewayArguments -PassThru -WindowStyle Hidden

    $watch = [Diagnostics.Stopwatch]::StartNew()
    $peakPrivateBytes = 0L
    while (-not $process.HasExited -and $watch.ElapsedMilliseconds -lt $MaxWaitMs) {
        try {
            $process.Refresh()
            $peakPrivateBytes = [Math]::Max($peakPrivateBytes, $process.PrivateMemorySize64)
        } catch {
        }
        Start-Sleep -Milliseconds 25
    }
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit(2000) | Out-Null
        throw "$Name gateway process exceeded the ${MaxWaitMs}ms test deadline."
    }
    $process.WaitForExit()
    $process.Refresh()
    $exitCode = $null
    try { $exitCode = [int]$process.ExitCode } catch { }
    return [pscustomobject]@{
        Name=$Name
        Pid=$process.Id
        ExitCode=$exitCode
        ElapsedMs=$watch.ElapsedMilliseconds
        PeakPrivateMB=[Math]::Round($peakPrivateBytes / 1MB, 2)
        Output=$output
        Stdout=$stdout
        Stderr=$stderr
    }
}

function Invoke-DaemonSessionProbe([int]$McpPort, [int]$MaxWaitMs) {
    $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
    $listenPort = Get-FreePort
    $sessionFile = Join-Path $testRoot 'daemon-stale-session.json'
    Write-TestSession $sessionFile $McpPort 'stale-session' ([DateTime]::UtcNow.AddMinutes(-2)) ([DateTime]::UtcNow.AddMinutes(10))
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemon,
        '-ListenPort', [string]$listenPort,
        '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
        '-SessionFile', $sessionFile,
        '-TimeoutSec', '10',
        '-IdleTtlSec', '60'
    ) -PassThru -WindowStyle Hidden
    try {
        Wait-LoopbackPort $listenPort 5000
        $client = [Net.Http.HttpClient]::new()
        try {
            $content = [Net.Http.StringContent]::new('{"action":"preflight"}', [Text.Encoding]::UTF8, 'application/json')
            try { $response = $client.PostAsync("http://127.0.0.1:$listenPort/", $content).Result }
            finally { $content.Dispose() }
            try {
                $body = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
                if (-not $response.IsSuccessStatusCode -or $body.toolsList -ne $true) {
                    throw "Daemon stale-session recovery failed: status=$([int]$response.StatusCode) body=$($body | ConvertTo-Json -Compress)"
                }
            } finally { $response.Dispose() }
        } finally { $client.Dispose() }
        $stored = Get-Content -Raw -LiteralPath $sessionFile | ConvertFrom-Json
        if ([string]$stored.sessionId -ne 'fixture-session') { throw 'Daemon did not persist the recovered session.' }
        return [pscustomobject]@{ Name='daemon_preflight_stale_session_recovery_once'; ExitCode=0 }
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit(2000) | Out-Null
        }
    }
}

function Invoke-DaemonLifecycleProbe([int]$McpPort) {
    $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
    $listenPort = Get-FreePort
    $sessionFile = Join-Path $testRoot 'daemon-lifecycle-session.json'
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemon,
        '-ListenPort', [string]$listenPort,
        '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
        '-SessionFile', $sessionFile,
        '-TimeoutSec', '10',
        '-IdleTtlSec', '60'
    ) -PassThru -WindowStyle Hidden
    try {
        Wait-LoopbackPort $listenPort 5000
        $client = [Net.Http.HttpClient]::new()
        try {
            foreach ($requestText in @(
                '{"action":"direct.call","tool":"ueagent_state","arguments":{}}',
                '{"action":"direct.call","tool":"ueagent_state","arguments":{}}'
            )) {
                $content = [Net.Http.StringContent]::new($requestText, [Text.Encoding]::UTF8, 'application/json')
                try { $response = $client.PostAsync("http://127.0.0.1:$listenPort/", $content).Result }
                finally { $content.Dispose() }
                try {
                    $body = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
                    if (-not $response.IsSuccessStatusCode -or [int]$body.payloadBytes -ne 0) {
                        throw "Daemon session lifecycle failed: status=$([int]$response.StatusCode) body=$($body | ConvertTo-Json -Compress)"
                    }
                } finally { $response.Dispose() }
            }
        } finally { $client.Dispose() }
        $stored = Get-Content -Raw -LiteralPath $sessionFile | ConvertFrom-Json
        if ([string]$stored.sessionId -ne 'fixture-session-2') { throw 'Daemon did not persist its recovered second session.' }
        return [pscustomobject]@{ Name='daemon_owned_session_stale_recovery_once'; ExitCode=0 }
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit(2000) | Out-Null
        }
    }
}

function Invoke-DaemonDiscoveryCacheProbe([int]$McpPort) {
    $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
    $listenPort = Get-FreePort
    $sessionFile = Join-Path $testRoot 'daemon-discovery-session.json'
    $cacheFile = Join-Path $testRoot 'daemon-discovery-schema.json'
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemon,
        '-ListenPort', [string]$listenPort,
        '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
        '-SessionFile', $sessionFile,
        '-TimeoutSec', '10',
        '-IdleTtlSec', '60'
    ) -PassThru -WindowStyle Hidden
    try {
        Wait-LoopbackPort $listenPort 5000
        $request = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('{"action":"tools.list"}'))
        $arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $gateway,
            '-RequestBase64', $request,
            '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
            '-SessionFile', $sessionFile,
            '-SchemaCacheFile', $cacheFile,
            '-DaemonUrl', "http://127.0.0.1:$listenPort/"
        )
        & powershell.exe @arguments | Out-Null
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $cacheFile)) {
            throw 'Minimal Base64 daemon discovery did not write the routed schema cache.'
        }
        & powershell.exe @arguments | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Cached daemon discovery failed.' }
        return [pscustomobject]@{ Name='daemon_base64_discovery_cache'; ExitCode=0 }
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit(2000) | Out-Null
        }
    }
}

function Invoke-DaemonTargetBindingProbe {
    $serverA = $null
    $serverB = $null
    $process = $null
    try {
        $serverA = Start-Fixture 'json_success' 16
        $serverB = Start-Fixture 'json_success' 32
        $endpointA = "http://127.0.0.1:$($serverA.Port)/mcp"
        $endpointB = "http://127.0.0.1:$($serverB.Port)/mcp"
        $listenPort = Get-FreePort
        $daemonUrl = "http://127.0.0.1:$listenPort/"
        $sessionA = Join-Path $testRoot 'binding-A-session.json'
        $sessionB = Join-Path $testRoot 'binding-B-session.json'
        $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemon,
            '-ListenPort', [string]$listenPort, '-Endpoint', $endpointA,
            '-SessionFile', $sessionA, '-TimeoutSec', '10', '-IdleTtlSec', '60'
        ) -PassThru -WindowStyle Hidden
        Wait-LoopbackPort $listenPort 5000

        $requestJson = @{ tool = 'ueagent_state'; arguments = @{} } | ConvertTo-Json -Compress
        $requestBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($requestJson))
        $invoke = {
            param($TargetEndpoint, $TargetSession, [string[]]$Extra)
            $arguments = @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $gateway,
                '-RequestBase64', $requestBase64, '-Endpoint', $TargetEndpoint,
                '-SessionFile', $TargetSession, '-TimeoutSec', '10'
            ) + $Extra
            $raw = & powershell.exe @arguments
            $exitCode = $LASTEXITCODE
            [pscustomobject]@{ ExitCode = $exitCode; Body = ($raw | ConvertFrom-Json) }
        }
        $direct = & $invoke $endpointB $sessionB @()
        if ($direct.ExitCode -ne 0 -or $direct.Body.payloadBytes -ne 32) { throw 'Binding control did not reach fixture B.' }
        $matching = & $invoke $endpointA $sessionA @('-DaemonUrl', $daemonUrl)
        if ($matching.ExitCode -ne 0 -or $matching.Body.payloadBytes -ne 16) { throw 'Matching daemon target failed.' }
        $callsBefore = @(Select-String -LiteralPath $serverA.Stdout -Pattern '^REQUEST tools/call ').Count

        $wrongEndpoint = & $invoke $endpointB $sessionB @('-DaemonUrl', $daemonUrl)
        if ($wrongEndpoint.ExitCode -eq 0 -or $wrongEndpoint.Body.code -ne 'endpoint_mismatch') {
            throw 'An explicit daemon accepted another endpoint.'
        }
        $wrongSession = & $invoke $endpointA $sessionB @('-DaemonUrl', $daemonUrl)
        if ($wrongSession.ExitCode -eq 0 -or $wrongSession.Body.code -ne 'session_mismatch') {
            throw 'An explicit daemon accepted another project session.'
        }
        $automatic = & $invoke $endpointB $sessionB @('-AutoDaemon', '-DaemonPort', [string]$listenPort)
        if ($automatic.ExitCode -ne 0 -or $automatic.Body.payloadBytes -ne 32) {
            throw 'AutoDaemon did not keep the requested target when its port belonged to another target.'
        }

        # Check the receiving boundary too: a daemon can be replaced between discovery and submit.
        $client = [Net.Http.HttpClient]::new()
        try {
            foreach ($case in @(
                @{ endpoint = $endpointB; sessionFile = $sessionA; expectedCode = 'endpoint_mismatch' },
                @{ endpoint = $endpointA; sessionFile = $sessionB; expectedCode = 'session_mismatch' }
            )) {
                $body = @{ tool = 'ueagent_state'; arguments = @{}; endpoint = $case.endpoint; sessionFile = $case.sessionFile } | ConvertTo-Json -Compress
                $content = [Net.Http.StringContent]::new($body, [Text.Encoding]::UTF8, 'application/json')
                try { $response = $client.PostAsync($daemonUrl, $content).Result }
                finally { $content.Dispose() }
                try {
                    $rejected = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
                    if ([int]$response.StatusCode -ne 400 -or $rejected.code -ne $case.expectedCode) {
                        throw "Daemon receiving boundary missed $($case.expectedCode)."
                    }
                } finally { $response.Dispose() }
            }
        } finally { $client.Dispose() }
        $callsAfter = @(Select-String -LiteralPath $serverA.Stdout -Pattern '^REQUEST tools/call ').Count
        if ($callsAfter -ne $callsBefore) { throw 'A rejected target-binding request reached fixture A.' }
        return [pscustomobject]@{ Name = 'daemon_endpoint_and_project_binding'; ExitCode = 0 }
    } finally {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit(2000) | Out-Null
        }
        Stop-Fixture $serverA
        Stop-Fixture $serverB
    }
}

function Test-SemanticValueShapes([int]$McpPort, [bool]$UseDaemon) {
    $sessionFile = Join-Path $testRoot 'value-shapes-session.json'
    $daemonProcess = $null
    $modeName = if ($UseDaemon) { 'daemon' } else { 'direct' }
    $extra = @()
    if ($UseDaemon) {
        $listenPort = Get-FreePort
        $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/mcp_gateway_daemon.ps1'
        $daemonProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemon,
            '-ListenPort', [string]$listenPort, '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
            '-SessionFile', $sessionFile, '-IdleTtlSec', '60'
        ) -PassThru -WindowStyle Hidden
        Wait-LoopbackPort $listenPort
        $extra = @('-DaemonUrl', "http://127.0.0.1:$listenPort/")
    }
    try {
        foreach ($case in @(
            @{ shape='empty'; expected='[]' },
            @{ shape='single'; expected='["one"]' },
            @{ shape='null'; expected='null' },
            @{ shape='false'; expected='false' },
            @{ shape='nested'; expected='{"values":[],"single":[1]}' },
            @{ shape='receipt'; expected='{"state":"terminal","result":[]}' }
        )) {
            $targetTool = 'ueagent_state' # Mock control isolates wire/value-shape behavior from task execution.
            $request = @{ action='direct.call'; tool=$targetTool; arguments=@{shape=$case.shape} } | ConvertTo-Json -Compress
            $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($request))
            $output = Join-Path $testRoot ("$modeName-$($case.shape).json")
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gateway -RequestBase64 $encoded `
                -Endpoint "http://127.0.0.1:$McpPort/mcp" -SessionFile $sessionFile -OutFile $output @extra
            if ($LASTEXITCODE -ne 0) { throw "$modeName $($case.shape) failed" }
            $actual = (Get-Content -Raw -LiteralPath $output).Trim()
            if ($actual -cne $case.expected) { throw "$modeName $($case.shape) changed JSON shape: $actual" }
        }
        return [pscustomobject]@{ Name=($modeName + '_semantic_value_shapes'); ExitCode=0 }
    } finally {
        if ($daemonProcess -and -not $daemonProcess.HasExited) {
            Stop-Process -Id $daemonProcess.Id -Force
            $daemonProcess.WaitForExit(2000) | Out-Null
        }
    }
}

$results = [Collections.Generic.List[object]]::new()
try {
    $server = Start-Fixture 'value_shapes' 0
    try {
        $results.Add((Test-SemanticValueShapes $server.Port $false))
        $results.Add((Test-SemanticValueShapes $server.Port $true))
    } finally {
        Stop-Fixture $server
    }
    $results.Add((Invoke-DaemonTargetBindingProbe))
    $invalidSession = Join-Path $testRoot 'request-invalid-session.json'
    $sessionMarker = 'preserve-local-parse-failure'
    [IO.File]::WriteAllText($invalidSession, $sessionMarker, [Text.UTF8Encoding]::new($false))
    $invalidJson = '{"action":"direct.call","arguments":'
    $invalidBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($invalidJson))
    $invalidOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gateway `
        -RequestBase64 $invalidBase64 -SessionFile $invalidSession 2>$null
    $invalidExitCode = $LASTEXITCODE
    if ($invalidExitCode -eq 0) { throw 'Malformed local request unexpectedly succeeded.' }
    $invalidResult = $invalidOutput | ConvertFrom-Json
    if ([string]$invalidResult.code -ne 'request_invalid') {
        throw "Malformed local request returned '$($invalidResult.code)' instead of request_invalid."
    }
    if (-not (Test-Path -LiteralPath $invalidSession) -or
        [IO.File]::ReadAllText($invalidSession) -ne $sessionMarker -or
        (Test-Path -LiteralPath (Join-Path $testRoot 'doctor.invalidate.json'))) {
        throw 'A local request parse failure invalidated the MCP session or doctor receipt.'
    }
    $results.Add([pscustomobject]@{ Name='request_invalid_no_session_reset'; ExitCode=$invalidExitCode })

    $daemonScript = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
    $daemonPort = Get-FreePort
    $daemonSession = Join-Path $testRoot 'daemon-invalid-session.json'
    $daemonMarker = '{"marker":"keep-daemon"}'
    [IO.File]::WriteAllText($daemonSession, $daemonMarker, [Text.UTF8Encoding]::new($false))
    $daemonProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $daemonScript,
        '-ListenPort', [string]$daemonPort,
        '-Endpoint', 'http://127.0.0.1:65534/mcp',
        '-SessionFile', $daemonSession,
        '-IdleTtlSec', '60'
    ) -PassThru -WindowStyle Hidden
    try {
        Wait-LoopbackPort $daemonPort 5000
        $http = [Net.Http.HttpClient]::new()
        try {
            $content = [Net.Http.StringContent]::new('{"tool":', [Text.Encoding]::UTF8, 'application/json')
            try { $response = $http.PostAsync("http://127.0.0.1:$daemonPort/", $content).Result }
            finally { $content.Dispose() }
            try {
                $daemonInvalid = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
                if ([int]$response.StatusCode -ne 400 -or [string]$daemonInvalid.code -ne 'request_invalid') {
                    throw "Daemon malformed request returned status=$([int]$response.StatusCode) code=$($daemonInvalid.code)."
                }
            } finally { $response.Dispose() }
        } finally { $http.Dispose() }
        if ($daemonProcess.HasExited -or [IO.File]::ReadAllText($daemonSession) -ne $daemonMarker -or
            (Test-Path -LiteralPath (Join-Path $testRoot 'doctor.invalidate.json'))) {
            throw 'A daemon-local parse failure stopped the daemon or invalidated live state.'
        }
        $results.Add([pscustomobject]@{ Name='daemon_request_invalid_no_session_reset'; ExitCode=0 })
    } finally {
        if (-not $daemonProcess.HasExited) {
            Stop-Process -Id $daemonProcess.Id -Force
            $daemonProcess.WaitForExit(2000) | Out-Null
        }
    }

    $legacyJson = @{ action='toolset.describe'; toolset='fixture'; detail='full' } | ConvertTo-Json -Compress
    $legacyBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($legacyJson))
    $legacyOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gateway -RequestBase64 $legacyBase64 2>$null
    if ($LASTEXITCODE -eq 0) { throw 'Legacy Gateway field detail unexpectedly remained accepted.' }
    $legacyResult = $legacyOutput | ConvertFrom-Json
    if ([string]$legacyResult.code -ne 'unsupported_request_field') {
        throw "Legacy Gateway field returned '$($legacyResult.code)' instead of unsupported_request_field."
    }

    $server = Start-Fixture 'success' 0
    try {
        $sessionFile = Join-Path $testRoot 'reused-session.json'
        $createdAt = [DateTime]::UtcNow.AddMinutes(-2)
        Write-TestSession $sessionFile $server.Port 'fixture-session' $createdAt ([DateTime]::UtcNow.AddMinutes(10))
        $before = [IO.File]::ReadAllText($sessionFile)
        $probe = Invoke-GatewayProbe 'reused_without_probe' $server.Port 10 15000 'direct.call' 'ueagent_state' $sessionFile
        if ($probe.ExitCode -ne 0) { throw "Direct cached-session call exited $($probe.ExitCode)." }
        $after = [IO.File]::ReadAllText($sessionFile)
        if ($after -ne $before) { throw 'A fresh reusable session was unnecessarily rewritten.' }
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ($requests -match 'REQUEST tools/list' -or $requests -match 'REQUEST initialize') {
            throw "A fresh reusable session was probed or reinitialized: $requests"
        }
        $results.Add([pscustomobject]@{ Name='reused_without_probe_or_write'; ExitCode=$probe.ExitCode })
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'stale_session' 0
    try {
        $sessionFile = Join-Path $testRoot 'stale-session.json'
        Write-TestSession $sessionFile $server.Port 'stale-session' ([DateTime]::UtcNow.AddMinutes(-2)) ([DateTime]::UtcNow.AddMinutes(10))
        $probe = Invoke-GatewayProbe 'stale_session_recovery' $server.Port 10 15000 'direct.call' 'ueagent_state' $sessionFile
        if ($probe.ExitCode -ne 0) { throw "Stale-session recovery exited $($probe.ExitCode)." }
        $stored = Get-Content -Raw -LiteralPath $sessionFile | ConvertFrom-Json
        if ([string]$stored.sessionId -ne 'fixture-session') { throw 'Recovered session was not persisted.' }
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ([Regex]::Matches($requests, 'REQUEST initialize').Count -ne 1 -or
            [Regex]::Matches($requests, 'REQUEST tools/call').Count -ne 2 -or
            $requests -match 'REQUEST tools/list') {
            throw "Stale session did not recover exactly once before dispatch: $requests"
        }
        $results.Add([pscustomobject]@{ Name='stale_session_recovery_once'; ExitCode=$probe.ExitCode })
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'stale_session' 0
    try {
        $probe = Invoke-DaemonSessionProbe $server.Port 15000
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ([Regex]::Matches($requests, 'REQUEST initialize').Count -ne 1 -or
            [Regex]::Matches($requests, 'REQUEST tools/list').Count -ne 2 -or
            $requests -match 'REQUEST tools/call') {
            throw "Daemon preflight stale session did not recover exactly once: $requests"
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'session_lifecycle' 0
    try {
        $probe = Invoke-DaemonLifecycleProbe $server.Port
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ([Regex]::Matches($requests, 'REQUEST initialize').Count -ne 2 -or
            [Regex]::Matches($requests, 'REQUEST tools/call').Count -ne 3 -or
            $requests -match 'REQUEST tools/list') {
            throw "Daemon did not recover its own expired session exactly once: $requests"
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'session_init_stale' 0
    try {
        $sessionFile = Join-Path $testRoot 'new-session-stale-before-call.json'
        $probe = Invoke-GatewayProbe 'new_session_stale_before_call' $server.Port 10 15000 'direct.call' 'ueagent_state' $sessionFile
        if ($probe.ExitCode -ne 0) { throw "New-session stale recovery exited $($probe.ExitCode)." }
        $stored = Get-Content -Raw -LiteralPath $sessionFile | ConvertFrom-Json
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ([string]$stored.sessionId -ne 'fixture-session-2' -or
            [Regex]::Matches($requests, 'REQUEST initialize').Count -ne 2 -or
            [Regex]::Matches($requests, 'REQUEST tools/call').Count -ne 2 -or
            $requests -match 'REQUEST tools/list') {
            throw "One-shot did not recover a newly initialized session before dispatch: $requests"
        }
        $results.Add([pscustomobject]@{ Name='new_session_stale_recovery_once'; ExitCode=$probe.ExitCode })
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'success' 0
    try {
        $probe = Invoke-DaemonDiscoveryCacheProbe $server.Port
        $requests = Get-Content -Raw -LiteralPath $server.Stdout
        if ([Regex]::Matches($requests, 'REQUEST tools/list').Count -ne 1) {
            throw "Second minimal daemon discovery did not hit schema cache: $requests"
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    foreach ($mode in @('success', 'json_success')) {
        $server = Start-Fixture $mode $SuccessPayloadBytes
        try {
            $probe = Invoke-GatewayProbe $mode $server.Port 20 30000
            if ($null -eq $probe.ExitCode -or $probe.ExitCode -ne 0) {
                $stdoutText = if (Test-Path -LiteralPath $probe.Stdout) { Get-Content -Raw -LiteralPath $probe.Stdout } else { '' }
                $stderrText = if (Test-Path -LiteralPath $probe.Stderr) { Get-Content -Raw -LiteralPath $probe.Stderr } else { '' }
                throw "$mode probe exited $($probe.ExitCode). stdout=$stdoutText stderr=$stderrText artifacts=$testRoot"
            }
            if (-not (Test-Path -LiteralPath $probe.Output)) { throw "$mode probe wrote no result file." }
            $data = Get-Content -Raw -LiteralPath $probe.Output | ConvertFrom-Json
            if ([int]$data.payloadBytes -ne $SuccessPayloadBytes -or $data.payload.Length -ne $SuccessPayloadBytes) {
                throw "$mode probe payload did not round-trip exactly."
            }
            if ($probe.PeakPrivateMB -ge 1024) {
                throw "$mode probe exceeded the 1 GiB regression ceiling: $($probe.PeakPrivateMB) MiB."
            }
            $results.Add($probe)
        } finally {
            Stop-Fixture $server
        }
    }

    $server = Start-Fixture 'echo' 0
    try {
        foreach ($removedAction in @('python.execute', 'script.execute', 'level.current')) {
            $probe = Invoke-GatewayProbe "removed_$($removedAction.Replace('.', '_'))" $server.Port 10 15000 $removedAction
            if ($probe.ExitCode -eq 0) { throw "$removedAction unexpectedly remained callable." }
            if (-not (Test-Path -LiteralPath $probe.Output)) { throw "$removedAction wrote no rejection result." }
            $data = Get-Content -Raw -LiteralPath $probe.Output | ConvertFrom-Json
            if ([string]$data.code -ne 'unknown_action') {
                throw "$removedAction returned '$($data.code)' instead of unknown_action."
            }
            $results.Add($probe)
        }
        $serverRequests = if (Test-Path -LiteralPath $server.Stdout) { Get-Content -Raw -LiteralPath $server.Stdout } else { '' }
        if ($serverRequests -match 'REQUEST tools/call') {
            throw 'A removed Gateway action reached tools/call before rejection.'
        }
    } finally {
        Stop-Fixture $server
    }

    [pscustomobject]@{
        Passed=$true
        SuccessPayloadBytes=$SuccessPayloadBytes
        Results=@($results)
        LeftoverGatewayProcesses=0
    } | ConvertTo-Json -Depth 6
} finally {
    if (-not $KeepArtifacts -and (Test-Path -LiteralPath $testRoot)) {
        $resolvedRoot = [IO.Path]::GetFullPath($testRoot)
        $resolvedBase = [IO.Path]::GetFullPath($tempBase + '\')
        if (-not $resolvedRoot.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase) -or
            -not ([IO.Path]::GetFileName($resolvedRoot)).StartsWith('ueagent-gateway-test-', [StringComparison]::Ordinal)) {
            throw "Refusing to remove unexpected test path: $resolvedRoot"
        }
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }
}
