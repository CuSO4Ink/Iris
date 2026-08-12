[CmdletBinding()]
param(
    [string]$Sidecar,
    [string]$AssetPath,
    [string]$ProjectRoot,
    [string]$RouteFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
$reader = Join-Path $PSScriptRoot 'reflect_cache.ps1'
if (-not (Test-Path -LiteralPath $reader)) { throw "Reflect cache reader not found: $reader" }

function Invoke-View($Name) {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $reader, '-Action', 'read', '-View', $Name)
    if ($Sidecar) { $args += @('-Sidecar', $Sidecar) }
    if ($AssetPath) { $args += @('-AssetPath', $AssetPath) }
    if ($ProjectRoot) { $args += @('-ProjectRoot', $ProjectRoot) }
    if ($RouteFile) { $args += @('-RouteFile', $RouteFile) }
    $hostExe = (Get-Command powershell.exe -ErrorAction Stop).Source
    $lines = & $hostExe @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "reflect_cache failed for view '$Name': $(@($lines) -join [Environment]::NewLine)" }
    $text = (@($lines) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    $null = $text | ConvertFrom-Json
    $bytes = [Text.Encoding]::UTF8.GetByteCount($text)
    return [ordered]@{
        view = $Name
        bytes = $bytes
        estimatedTokens = [int][Math]::Ceiling($bytes / 4.0)
    }
}

$rows = @('summary', 'refs', 'detail', 'full') | ForEach-Object { Invoke-View $_ }
$fullRow = @($rows | Where-Object { $_['view'] -eq 'full' }) | Select-Object -First 1
$fullBytes = if ($fullRow) { [int]$fullRow['bytes'] } else { 0 }
foreach ($row in $rows) {
    $row['reductionVsFullPct'] = if ($fullBytes) {
        [Math]::Round((1 - ($row.bytes / [double]$fullBytes)) * 100, 1)
    } else { 0 }
}

$result = [ordered]@{
    schema = 'ueagent-progressive-audit-v1'
    defaultView = 'summary'
    sidecar = $Sidecar
    views = $rows
    rule = 'summary -> refs -> detail -> full; expand only when the preceding view cannot answer the task'
}
$json = if ($Pretty) { $result | ConvertTo-Json -Depth 10 } else { $result | ConvertTo-Json -Depth 10 -Compress }
$json
