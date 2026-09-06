[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RouteFile,

    [string]$AssetPath,

    [ValidateSet('', 'material', 'material-function', 'material-instance', 'blueprint', 'niagara', 'scene')]
    [string]$Domain = '',

    [ValidateSet('read', 'mutate', 'save')]
    [string]$Operation = 'read',

    [ValidateSet('compact', 'detail')]
    [string]$View = 'compact',

    [string]$OutFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'

$KnownCacheFormats = @(
    'vibeue-material-cache-v2',
    'vibeue-material-function-cache-v1',
    'vibeue-material-instance-cache-v1',
    'vibeue-blueprint-cache-v1',
    'vibeue-niagara-system-cache-v1'
)

function Read-JsonFile($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "$Label not found: $Path" }
    try { return (Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json) }
    catch { throw "Invalid $Label`: $($_.Exception.Message)" }
}

function Get-AssetPackagePath($Path) {
    if (-not $Path -or -not $Path.StartsWith('/Game/', [StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }
    $slash = $Path.LastIndexOf('/')
    $dot = $Path.IndexOf('.', $slash)
    if ($dot -gt $slash) { return $Path.Substring(0, $dot) }
    return $Path
}

function Read-SidecarHeader($Path) {
    $reader = [IO.File]::OpenText($Path)
    try {
        $lines = [Collections.Generic.List[string]]::new()
        $fences = 0
        while (-not $reader.EndOfStream -and $lines.Count -lt 64) {
            $line = $reader.ReadLine()
            $lines.Add($line)
            if ($line.TrimStart().StartsWith('```')) {
                $fences++
                if ($fences -eq 2) { break }
            }
        }
        return ($lines -join "`n")
    } finally {
        $reader.Dispose()
    }
}

$RouteFile = (Resolve-Path -LiteralPath $RouteFile).Path
$route = Read-JsonFile $RouteFile 'route file'
if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported route schema: $($route.schema)" }

$projectRoot = Split-Path ([string]$route.uProject) -Parent
$packagePath = Get-AssetPackagePath $AssetPath
$assetInfo = [ordered]@{
    package = $packagePath
    file = $null
    sidecar = $null
    sourceBytes = $null
    sourceMtimeUtc = $null
    sidecarBytes = $null
    sidecarMtimeUtc = $null
    format = $null
    state = 'MISSING'
    formatKnown = $false
    invalidation = $null
    hasLogic = $false
    current = $false
}

if ($packagePath) {
    $relative = $packagePath.Substring('/Game/'.Length).Replace('/', '\')
    $sourceFile = Join-Path $projectRoot (Join-Path 'Content' ($relative + '.uasset'))
    $sidecarFile = $sourceFile + '.ai.md'
    $assetInfo.file = $sourceFile
    $assetInfo.sidecar = $sidecarFile
    if (Test-Path -LiteralPath $sourceFile) {
        $source = Get-Item -LiteralPath $sourceFile
        $assetInfo.sourceBytes = [int64]$source.Length
        $assetInfo.sourceMtimeUtc = $source.LastWriteTimeUtc.ToString('o')
    }
    if (Test-Path -LiteralPath $sidecarFile) {
        $sidecar = Get-Item -LiteralPath $sidecarFile
        $text = if ($View -eq 'detail') {
            Get-Content -Raw -LiteralPath $sidecarFile
        } else {
            Read-SidecarHeader $sidecarFile
        }
        $assetInfo.sidecarBytes = [int64]$sidecar.Length
        $assetInfo.sidecarMtimeUtc = $sidecar.LastWriteTimeUtc.ToString('o')
        $formatMatch = [Regex]::Match($text, '(?m)^format:\s*(\S+)')
        $sizeMatch = [Regex]::Match($text, '(?m)^size:\s*(\d+)')
        if ($formatMatch.Success) { $assetInfo.format = $formatMatch.Groups[1].Value }
        $assetInfo.formatKnown = $assetInfo.format -and $KnownCacheFormats -contains $assetInfo.format
        $declaredSizeMatches = -not $sizeMatch.Success -or
            ([int64]$sizeMatch.Groups[1].Value -eq [int64]$assetInfo.sourceBytes)
        if ($View -eq 'detail') { $assetInfo.hasLogic = $text -match '(?m)^## Logic\s*$' }
        $sourceMatches = [bool]$assetInfo.sourceBytes -and
            $sidecar.LastWriteTimeUtc -ge (Get-Item -LiteralPath $sourceFile).LastWriteTimeUtc -and
            $declaredSizeMatches
        $assetInfo.state = if (-not $assetInfo.sourceBytes) { 'ORPHAN' }
            elseif (-not $assetInfo.formatKnown) { 'UNSUPPORTED_FORMAT' }
            elseif (-not $sourceMatches) { 'STALE' }
            else { 'FRESH' }
        $assetInfo.current = $assetInfo.state -eq 'FRESH'
    }
}

if ($assetInfo.state -eq 'MISSING' -and $packagePath) { $assetInfo.invalidation = 'sidecar_missing' }
$next = switch ($Operation) {
    'read' { if ($assetInfo.current) { 'CACHE_READ' } else { 'LIVE_CALL' } }
    'mutate' { 'LIVE_CALL' }
    'save' { 'LIVE_CALL' }
}

$output = if ($View -eq 'detail') {
    [ordered]@{
        schema = 'ueagent-context-v1'
        next = $next
        route = [ordered]@{
            endpoint = [string]$route.endpoint
            project = [string]$route.uProject
            engine = [string]$route.engineRoot
            ueAgent = [string]$route.ueAgentRoot
        }
        task = [ordered]@{ asset = $AssetPath; domain = $Domain; operation = $Operation }
        asset = $assetInfo
    }
} elseif ($next -eq 'CACHE_READ') {
    [ordered]@{ next = $next; sidecar = $assetInfo.sidecar }
} else {
    [ordered]@{ next = $next }
}
$json = if ($Pretty) { $output | ConvertTo-Json -Depth 12 } else { $output | ConvertTo-Json -Depth 12 -Compress }
if ($OutFile) {
    $parent = Split-Path $OutFile -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
    [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
} else {
    $json
}
