[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RouteFile,

    [string]$AssetPath,

    [ValidateSet('', 'material', 'material-function', 'material-instance', 'blueprint', 'niagara', 'scene')]
    [string]$Domain = '',

    [ValidateSet('read', 'inspect', 'mutate', 'save')]
    [string]$Operation = 'read',

    [ValidateSet('compact', 'detail')]
    [string]$View = 'compact',

    [string]$ReceiptFile,
    [int]$ReceiptMaxAgeSec = 300,
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

function Test-ListenerProcesses($Pids) {
    $normalized = @($Pids | ForEach-Object { [int]$_ } | Sort-Object)
    if ($normalized.Count -eq 0) { return $null }
    try {
        foreach ($listenerPid in $normalized) {
            if (-not (Get-Process -Id $listenerPid -ErrorAction Stop)) { return $false }
        }
        return $true
    } catch {
        return $false
    }
}

function Read-McpSessionSnapshot($Path, $Endpoint) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $entry = Read-JsonFile $Path 'MCP session'
        if ($entry.schema -ne 'ueagent-mcp-session-v1' -or
            [string]$entry.endpoint -ne [string]$Endpoint -or -not $entry.sessionId) { return $null }
        $expires = [DateTime]::Parse([string]$entry.expiresAtUtc).ToUniversalTime()
        if ($expires -le [DateTime]::UtcNow) { return $null }
        return $entry
    } catch {
        return $null
    }
}

function Get-PluginFingerprint($ProjectRoot, $EngineRoot) {
    $patterns = @()
    if ($ProjectRoot) {
        $patterns += (Join-Path $ProjectRoot 'Plugins\UnrealMCP\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\UnrealMCP\*.uplugin')
        $patterns += (Join-Path $ProjectRoot 'Plugins\UnrealMCP\Python\unreal_mcp_server_advanced.py')
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\*.uplugin')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\*.uplugin')
    }
    if ($EngineRoot) {
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\*.uplugin')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\*.uplugin')
    }
    $files = @($patterns | ForEach-Object { Get-ChildItem -Path $_ -File -ErrorAction SilentlyContinue })
    if ($files.Count -eq 0) { return $null }
    $stamp = @($files | Sort-Object FullName | ForEach-Object {
        "$($_.FullName)|$($_.Length)|$($_.LastWriteTimeUtc.ToString('o'))"
    }) -join "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($stamp)))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-ReceiptInvalidationPath($ReceiptPath) {
    if (-not $ReceiptPath) { return $null }
    $parent = Split-Path -Parent $ReceiptPath
    if (-not $parent) { return $null }
    return Join-Path $parent 'doctor.invalidate.json'
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

$RouteFile = (Resolve-Path -LiteralPath $RouteFile).Path
$route = Read-JsonFile $RouteFile 'route file'
if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported route schema: $($route.schema)" }

$projectRoot = Split-Path ([string]$route.uProject) -Parent
$pluginFingerprint = Get-PluginFingerprint $projectRoot ([string]$route.engineRoot)
$receiptPath = if ($ReceiptFile) {
    (Resolve-Path -LiteralPath $ReceiptFile -ErrorAction SilentlyContinue).Path
} else {
    Join-Path $projectRoot 'Saved\UEAgent\doctor.json'
}

$receiptState = 'MISSING'
$receiptStatus = $null
$receiptAgeSec = $null
$receiptCheckedAt = $null
$receiptIdentityValid = $null
$receiptIdentityReason = 'missing'
if ($receiptPath -and (Test-Path -LiteralPath $receiptPath)) {
    try {
        $receipt = Read-JsonFile $receiptPath 'doctor receipt'
        $receiptStatus = [string]$receipt.status
        $receiptCheckedAt = [string]$receipt.checkedAtUtc
        $checkedAtUtc = [DateTime]::Parse($receiptCheckedAt).ToUniversalTime()
        $receiptAgeSec = [Math]::Max(0, [int]([DateTime]::UtcNow - $checkedAtUtc).TotalSeconds)
        $invalidationPath = Get-ReceiptInvalidationPath $receiptPath
        if ($invalidationPath -and (Test-Path -LiteralPath $invalidationPath)) {
            $receiptState = 'INVALIDATED'
            $receiptIdentityReason = 'transport_failure'
        } else {
            $storedPidsSource = if ($receipt.endpoint.listenerPids) {
                $receipt.endpoint.listenerPids
            } else {
                $receipt.identity.listenerPids
            }
            $storedPids = @($storedPidsSource | ForEach-Object { [int]$_ } | Sort-Object)
            $listenerAlive = Test-ListenerProcesses $storedPids
            $listenerKnown = $null -ne $listenerAlive -and $storedPids.Count -gt 0
            if ($listenerKnown) {
                $receiptIdentityValid = $listenerAlive
                $receiptIdentityReason = if ($receiptIdentityValid) { 'listener_unchanged' } else { 'editor_pid_changed' }
            }

            $sessionFile = Join-Path $projectRoot 'Saved\UEAgent\mcp-session.json'
            $session = Read-McpSessionSnapshot $sessionFile ([string]$route.endpoint)
            $storedSessionId = [string]$receipt.identity.mcpSessionId
            if ($storedSessionId) {
                if (-not $session) {
                    $receiptIdentityValid = $false
                    $receiptIdentityReason = 'mcp_session_missing_or_expired'
                } elseif ([string]$session.sessionId -ne $storedSessionId) {
                    $receiptIdentityValid = $false
                    $receiptIdentityReason = 'mcp_session_changed'
                } else {
                    $receiptIdentityValid = if ($null -eq $receiptIdentityValid) { $true } else { $receiptIdentityValid }
                    if ($receiptIdentityValid) { $receiptIdentityReason = 'session_unchanged' }
                }
            }

            $storedPluginFingerprint = [string]$receipt.identity.pluginFingerprint
            if ($storedPluginFingerprint -and $pluginFingerprint -and $storedPluginFingerprint -ne $pluginFingerprint) {
                $receiptIdentityValid = $false
                $receiptIdentityReason = 'plugin_changed'
            }

            $identityKnown = $null -ne $receiptIdentityValid
            $receiptState = if ($identityKnown -and -not $receiptIdentityValid) {
                'STALE'
            } elseif ($identityKnown -and $receiptIdentityValid) {
                'FRESH'
            } elseif ($receiptAgeSec -le $ReceiptMaxAgeSec) {
                $receiptIdentityReason = 'ttl_fallback'
                'FRESH'
            } else {
                $receiptIdentityReason = 'ttl_expired'
                'STALE'
            }
        }
    } catch {
        $receiptState = 'INVALID'
        $receiptIdentityReason = 'invalid_receipt'
    }
}

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
    graphSha1 = $null
    state = 'MISSING'
    formatKnown = $false
    liveDirtyCheck = $true
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
        $text = Get-Content -Raw -LiteralPath $sidecarFile
        $assetInfo.sidecarBytes = [int64]$sidecar.Length
        $assetInfo.sidecarMtimeUtc = $sidecar.LastWriteTimeUtc.ToString('o')
        $formatMatch = [Regex]::Match($text, '(?m)^format:\s*(\S+)')
        $sizeMatch = [Regex]::Match($text, '(?m)^size:\s*(\d+)')
        $hashMatch = [Regex]::Match($text, '(?m)^graph_sha1:\s*(\S+)')
        if ($formatMatch.Success) { $assetInfo.format = $formatMatch.Groups[1].Value }
        if ($hashMatch.Success) { $assetInfo.graphSha1 = $hashMatch.Groups[1].Value }
        $assetInfo.formatKnown = $assetInfo.format -and $KnownCacheFormats -contains $assetInfo.format
        $declaredSizeMatches = -not $sizeMatch.Success -or
            ([int64]$sizeMatch.Groups[1].Value -eq [int64]$assetInfo.sourceBytes)
        $assetInfo.hasLogic = $text -match '(?m)^## Logic\s*$'
        $sourceMatches = [bool]$assetInfo.sourceBytes -and
            $sidecar.LastWriteTimeUtc -ge (Get-Item -LiteralPath $sourceFile).LastWriteTimeUtc -and
            $declaredSizeMatches
        $assetInfo.state = if (-not $assetInfo.sourceBytes) { 'ORPHAN' }
            elseif (-not $assetInfo.formatKnown) { 'UNSUPPORTED_FORMAT' }
            elseif (-not $sourceMatches) { 'STALE' }
            else { 'FRESH' }
        if ($receiptIdentityReason -eq 'plugin_changed') { $assetInfo.invalidation = 'plugin_changed' }
        $assetInfo.current = $assetInfo.state -eq 'FRESH' -and $receiptIdentityReason -ne 'plugin_changed'
    }
}

if ($assetInfo.state -eq 'MISSING' -and $packagePath) { $assetInfo.invalidation = 'sidecar_missing' }
$assetInfo.liveDirtyCheck = $true

$receiptFresh = $receiptState -eq 'FRESH'
$healthy = $receiptFresh -and $receiptStatus -eq 'HEALTHY'
$readOnlyRoute = $receiptFresh -and $receiptStatus -in @('HEALTHY', 'DEGRADED')
$needsDoctor = -not $assetInfo.current -and (
    $receiptState -in @('MISSING', 'STALE', 'INVALID', 'INVALIDATED') -or
    $receiptStatus -eq 'READY'
)
$next = switch ($Operation) {
    'read' { if ($assetInfo.current) { 'CACHE_READ' } elseif ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($readOnlyRoute) { 'LIVE_READ' } else { 'BLOCKED' } }
    'inspect' { if ($assetInfo.current) { 'CACHE_READ' } elseif ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($readOnlyRoute) { 'LIVE_READ' } else { 'BLOCKED' } }
    'mutate' { if ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($healthy) { 'LIVE_MUTATE_TASK_GATED' } else { 'BLOCKED' } }
    'save' { if ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($healthy) { 'LIVE_SAVE_EXPLICIT' } else { 'BLOCKED' } }
}

$context = [ordered]@{
    schema = 'ueagent-context-v1'
    next = $next
    route = [ordered]@{
        endpoint = [string]$route.endpoint
        project = [string]$route.uProject
        engine = [string]$route.engineRoot
        ueAgent = [string]$route.ueAgentRoot
    }
    receipt = [ordered]@{
        file = $receiptPath
        state = $receiptState
        status = $receiptStatus
        ageSec = $receiptAgeSec
        checkedAtUtc = $receiptCheckedAt
        maxAgeSec = $ReceiptMaxAgeSec
        identity = $receiptIdentityReason
    }
    task = [ordered]@{
        asset = $AssetPath
        domain = $Domain
        operation = $Operation
    }
    asset = $assetInfo
}

$output = if ($View -eq 'compact') {
    [ordered]@{
        schema = 'ueagent-context-compact-v1'
        next = $next
        task = [ordered]@{ asset = $AssetPath; domain = $Domain; operation = $Operation }
        route = [ordered]@{ endpoint = [string]$route.endpoint; project = [string]$route.uProject }
        receipt = [ordered]@{ state = $receiptState; status = $receiptStatus; ageSec = $receiptAgeSec }
        asset = [ordered]@{
            package = $assetInfo.package
            current = $assetInfo.current
            state = $assetInfo.state
            sidecar = $assetInfo.sidecar
            format = $assetInfo.format
            formatKnown = $assetInfo.formatKnown
            graphSha1 = $assetInfo.graphSha1
            liveDirtyCheck = $assetInfo.liveDirtyCheck
            invalidation = $assetInfo.invalidation
        }
        expand = 'compact_context.ps1 -View detail'
    }
} else { $context }
$json = if ($Pretty) { $output | ConvertTo-Json -Depth 12 } else { $output | ConvertTo-Json -Depth 12 -Compress }
if ($OutFile) {
    $parent = Split-Path $OutFile -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
    [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
} else {
    $json
}
