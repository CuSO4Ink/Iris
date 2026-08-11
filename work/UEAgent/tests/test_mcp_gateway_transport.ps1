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
$tempBase = [IO.Path]::GetTempPath().TrimEnd('\')
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
    $stdout = Join-Path $testRoot "$Mode-server.stdout.txt"
    $stderr = Join-Path $testRoot "$Mode-server.stderr.txt"
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

function Invoke-GatewayProbe(
    [string]$Name,
    [int]$Port,
    [int]$TimeoutSec,
    [int]$GuardGraceSec,
    [int]$MaxPrivateMemoryMB,
    [int]$MaxWaitMs,
    [string]$Action = 'script.execute',
    [string]$Script = 'x'
) {
    $stdout = Join-Path $testRoot "$Name-gateway.stdout.txt"
    $stderr = Join-Path $testRoot "$Name-gateway.stderr.txt"
    $output = Join-Path $testRoot "$Name-result.json"
    $requestJson = @{ action=$Action; script=$Script } | ConvertTo-Json -Compress
    $requestBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($requestJson))
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $gateway,
        '-RequestBase64', $requestBase64,
        '-Endpoint', "http://127.0.0.1:$Port/mcp",
        '-TimeoutSec', [string]$TimeoutSec,
        '-ProcessGuardGraceSec', [string]$GuardGraceSec,
        '-ProcessGuardMaxPrivateMemoryMB', [string]$MaxPrivateMemoryMB,
        '-DataOnly',
        '-OutFile', $output
    ) -PassThru -WindowStyle Hidden

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

function Invoke-DaemonHangProbe([int]$McpPort, [int]$MaxWaitMs) {
    $daemon = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\mcp_gateway_daemon.ps1'
    $listenPort = Get-FreePort
    $sessionFile = Join-Path $testRoot 'daemon-session.json'
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $daemon,
        '-ListenPort', [string]$listenPort,
        '-Endpoint', "http://127.0.0.1:$McpPort/mcp",
        '-SessionFile', $sessionFile,
        '-TimeoutSec', '1',
        '-HardRequestGraceSec', '1',
        '-MaxPrivateMemoryMB', '2048',
        '-IdleTtlSec', '60'
    ) -PassThru -WindowStyle Hidden

    try {
        Wait-LoopbackPort $listenPort 5000
        $client = [Net.Http.HttpClient]::new()
        $client.Timeout = [TimeSpan]::FromSeconds(5)
        $clientResult = 'not_started'
        try {
            $body = '{"action":"script.execute","script":"x","dataOnly":true}'
            $content = [Net.Http.StringContent]::new($body, [Text.Encoding]::UTF8, 'application/json')
            try {
                $request = $client.PostAsync("http://127.0.0.1:$listenPort/", $content)
                try {
                    if ($request.Wait(5000)) {
                        if ($request.Status -eq [Threading.Tasks.TaskStatus]::RanToCompletion) {
                            $response = $request.Result
                            try {
                                $responseText = $response.Content.ReadAsStringAsync().Result
                                $clientResult = "status=$([int]$response.StatusCode) body=$responseText"
                            } finally {
                                $response.Dispose()
                            }
                        } else {
                            $clientResult = "task_status=$($request.Status)"
                        }
                    } else {
                        $clientResult = 'client_wait_timeout'
                    }
                } catch {
                    $clientResult = "client_exception=$($_.Exception.Message)"
                }
            } finally {
                $content.Dispose()
            }
        } finally {
            $client.Dispose()
        }

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
            throw "Daemon did not terminate within the ${MaxWaitMs}ms hard deadline. client=$clientResult"
        }
        $process.WaitForExit()
        $process.Refresh()
        return [pscustomobject]@{
            Name='daemon_initialize_hang'
            Pid=$process.Id
            ExitCode=[int]$process.ExitCode
            ElapsedMs=$watch.ElapsedMilliseconds
            PeakPrivateMB=[Math]::Round($peakPrivateBytes / 1MB, 2)
            ClientResult=$clientResult
        }
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit(2000) | Out-Null
        }
    }
}

$results = [Collections.Generic.List[object]]::new()
try {
    $server = Start-Fixture 'success' $SuccessPayloadBytes
    try {
        $probe = Invoke-GatewayProbe 'success' $server.Port 20 5 2048 30000
        if ($null -eq $probe.ExitCode -or $probe.ExitCode -ne 0) {
            $stdoutText = if (Test-Path -LiteralPath $probe.Stdout) { Get-Content -Raw -LiteralPath $probe.Stdout } else { '' }
            $stderrText = if (Test-Path -LiteralPath $probe.Stderr) { Get-Content -Raw -LiteralPath $probe.Stderr } else { '' }
            throw "Success probe exited $($probe.ExitCode). stdout=$stdoutText stderr=$stderrText artifacts=$testRoot"
        }
        if (-not (Test-Path -LiteralPath $probe.Output)) { throw 'Success probe wrote no result file.' }
        $data = Get-Content -Raw -LiteralPath $probe.Output | ConvertFrom-Json
        if ([int]$data.payloadBytes -ne $SuccessPayloadBytes -or $data.payload.Length -ne $SuccessPayloadBytes) {
            throw 'Success probe payload did not round-trip exactly.'
        }
        if ($probe.PeakPrivateMB -ge 1024) {
            throw "Success probe exceeded the 1 GiB regression ceiling: $($probe.PeakPrivateMB) MiB."
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'echo' 0
    try {
        $pythonPayload = "import unreal`nprint('isolated')"
        $probe = Invoke-GatewayProbe 'python_execute_route' $server.Port 10 2 1024 15000 'python.execute' $pythonPayload
        if ($null -eq $probe.ExitCode -or $probe.ExitCode -ne 0) {
            $stdoutText = if (Test-Path -LiteralPath $probe.Stdout) { Get-Content -Raw -LiteralPath $probe.Stdout } else { '' }
            $stderrText = if (Test-Path -LiteralPath $probe.Stderr) { Get-Content -Raw -LiteralPath $probe.Stderr } else { '' }
            throw "python.execute probe exited $($probe.ExitCode). stdout=$stdoutText stderr=$stderrText"
        }
        $data = Get-Content -Raw -LiteralPath $probe.Output | ConvertFrom-Json
        if ([string]$data.request.params.name -ne 'execute_python_code') {
            throw 'python.execute did not route to the top-level execute_python_code tool.'
        }
        $bootstrap = [string]$data.request.params.arguments.code
        $encodedPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonPayload))
        if (-not $bootstrap.Contains($encodedPayload) -or
            -not $bootstrap.Contains('_ueagent_scope.clear()') -or
            -not $bootstrap.Contains('_ueagent_gc.collect()')) {
            throw 'python.execute did not emit the isolated, collect-before-return bootstrap.'
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'echo' 0
    try {
        $wrongBackendPayload = "import unreal`nprint('wrong backend')"
        $probe = Invoke-GatewayProbe 'programmatic_unreal_rejected' $server.Port 10 2 1024 15000 'script.execute' $wrongBackendPayload
        if ($probe.ExitCode -eq 0) { throw 'script.execute unexpectedly accepted an Unreal Python payload.' }
        if (-not (Test-Path -LiteralPath $probe.Output)) { throw 'Wrong-backend probe wrote no result file.' }
        $data = Get-Content -Raw -LiteralPath $probe.Output | ConvertFrom-Json
        if ([string]$data.code -ne 'wrong_script_backend') {
            throw "Wrong-backend probe returned '$($data.code)' instead of wrong_script_backend."
        }
        $serverRequests = if (Test-Path -LiteralPath $server.Stdout) { Get-Content -Raw -LiteralPath $server.Stdout } else { '' }
        if ($serverRequests -match 'REQUEST tools/call') {
            throw 'Wrong-backend payload reached tools/call before rejection.'
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'call_hang' 0
    try {
        $probe = Invoke-GatewayProbe 'call_hang' $server.Port 1 1 2048 6000
        if ($probe.ExitCode -eq 0) { throw 'Call-hang probe unexpectedly succeeded.' }
        if ($probe.ElapsedMs -ge 6000) { throw 'Call-hang probe did not terminate within the hard deadline.' }
        if ($probe.PeakPrivateMB -ge 512) {
            throw "Call-hang probe exceeded 512 MiB: $($probe.PeakPrivateMB) MiB."
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'initialize_hang' 0
    try {
        $probe = Invoke-GatewayProbe 'initialize_hang' $server.Port 1 1 2048 6000
        if ($probe.ExitCode -eq 0) { throw 'Initialize-hang probe unexpectedly succeeded.' }
        if ($probe.ElapsedMs -ge 6000) { throw 'Initialize-hang probe did not terminate within the hard deadline.' }
        if ($probe.PeakPrivateMB -ge 512) {
            throw "Initialize-hang probe exceeded 512 MiB: $($probe.PeakPrivateMB) MiB."
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'call_hang' 0
    try {
        $probe = Invoke-GatewayProbe 'memory_guard' $server.Port 10 1 64 6000
        if ($probe.ExitCode -eq 0) { throw 'Memory-guard probe unexpectedly succeeded.' }
        if ($probe.ElapsedMs -ge 3000) { throw 'Memory guard did not terminate promptly.' }
        if ($probe.PeakPrivateMB -ge 256) {
            throw "Memory-guard probe exceeded 256 MiB: $($probe.PeakPrivateMB) MiB."
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $server = Start-Fixture 'initialize_hang' 0
    try {
        $probe = Invoke-DaemonHangProbe $server.Port 6000
        if ($probe.ExitCode -eq 0) { throw 'Daemon initialize-hang probe unexpectedly succeeded.' }
        if ($probe.ElapsedMs -ge 6000) { throw 'Daemon initialize-hang probe did not terminate within the hard deadline.' }
        if ($probe.PeakPrivateMB -ge 512) {
            throw "Daemon initialize-hang probe exceeded 512 MiB: $($probe.PeakPrivateMB) MiB."
        }
        $results.Add($probe)
    } finally {
        Stop-Fixture $server
    }

    $leftovers = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'powershell.exe' -and
        ($_.CommandLine -like "*$gateway*" -or $_.CommandLine -like '*mcp_gateway_daemon.ps1*')
    })
    if ($leftovers.Count -gt 0) {
        throw "Gateway regression test left PowerShell processes: $(@($leftovers.ProcessId) -join ', ')"
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
