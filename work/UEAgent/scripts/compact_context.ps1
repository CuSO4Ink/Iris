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

    [string]$ReceiptFile,
    [int]$ReceiptMaxAgeSec = 300,
    [string]$OutFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')

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
$projectName = [IO.Path]::GetFileNameWithoutExtension([string]$route.uProject)
$pluginFingerprint = Get-PluginFingerprint $projectRoot ([string]$route.engineRoot) $projectName
$kernelStatePath = Join-Path $projectRoot 'Saved\UEAgent\state.json'
$kernelState = $null
$kernelStateStatus = 'MISSING'
if (Test-Path -LiteralPath $kernelStatePath) {
    try {
        $kernelState = Read-JsonFile $kernelStatePath 'UEAgent reliable state'
        $kernelStateStatus = 'STALE'
    } catch {
        $kernelStateStatus = 'INVALID'
    }
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
$receiptPath = if ($ReceiptFile) {
    (Resolve-Path -LiteralPath $ReceiptFile -ErrorAction SilentlyContinue).Path
} else {
    Join-Path $projectRoot 'Saved\UEAgent\doctor.json'
}

$receiptState = 'MISSING'
$receipt = $null
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
        $hashMatch = [Regex]::Match($text, '(?m)^graph_sha1:\s*(\S+)')
        if ($formatMatch.Success) { $assetInfo.format = $formatMatch.Groups[1].Value }
        if ($hashMatch.Success) { $assetInfo.graphSha1 = $hashMatch.Groups[1].Value }
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
        if ($receiptIdentityReason -eq 'plugin_changed') { $assetInfo.invalidation = 'plugin_changed' }
        $assetInfo.current = $assetInfo.state -eq 'FRESH' -and $receiptIdentityReason -ne 'plugin_changed'
    }
}

if ($assetInfo.state -eq 'MISSING' -and $packagePath) { $assetInfo.invalidation = 'sidecar_missing' }
$receiptFresh = $receiptState -eq 'FRESH'
$receiptEditorEpoch = if ($receipt -and $receipt.identity) { [string]$receipt.identity.editorEpoch } else { '' }
$kernelEditorEpoch = if ($kernelState) { [string]$kernelState.editor_epoch } else { '' }
$receiptEditorPid = if ($receipt -and @($receipt.identity.listenerPids).Count) { [int]@($receipt.identity.listenerPids)[0] } else { 0 }
$kernelEditorPid = if ($kernelState -and [int]$kernelState.editor_pid -gt 0) { [int]$kernelState.editor_pid } else { $receiptEditorPid }
$kernelCurrent = $receiptFresh -and $receiptEditorEpoch -and
    $kernelEditorEpoch -eq $receiptEditorEpoch -and
    [string]$kernelState.protocol_version -eq [string]$route.reliableProtocol
if ($kernelCurrent) { $kernelStateStatus = 'CURRENT' }
$healthy = $receiptFresh -and $receiptStatus -eq 'HEALTHY' -and $kernelCurrent
$readOnlyRoute = $receiptFresh -and $receiptStatus -in @('HEALTHY', 'DEGRADED') -and $kernelCurrent
$needsDoctor = -not $assetInfo.current -and (
    $receiptState -in @('MISSING', 'STALE', 'INVALID', 'INVALIDATED') -or
    -not $kernelCurrent
)
$next = switch ($Operation) {
    'read' { if ($assetInfo.current) { 'CACHE_READ' } elseif ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($readOnlyRoute) { 'LIVE_READ' } else { 'BLOCKED' } }
    'mutate' { if ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($healthy) { 'LIVE_MUTATE_RELIABLE_QUEUE' } else { 'BLOCKED' } }
    'save' { if ($needsDoctor) { 'NEEDS_DOCTOR' } elseif ($healthy) { 'LIVE_SAVE_CAPABILITY_REQUIRED' } else { 'BLOCKED' } }
}
$kernelBusy = $kernelCurrent -and (
    [bool]$kernelState.performance_frozen -or [string]$kernelState.active_command_id
)
if ($kernelBusy -and $next -ne 'CACHE_READ' -and $Operation -in @('read', 'save')) {
    $next = 'WAIT_RELIABLE_JOB'
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
        receipt = [ordered]@{
            file = $receiptPath
            state = $receiptState
            status = $receiptStatus
            ageSec = $receiptAgeSec
            checkedAtUtc = $receiptCheckedAt
            maxAgeSec = $ReceiptMaxAgeSec
            identity = $receiptIdentityReason
        }
        reliable = [ordered]@{
            file = $kernelStatePath
            state = $kernelStateStatus
            protocolVersion = if ($kernelState) { [string]$kernelState.protocol_version } else { $null }
            editorEpoch = $kernelEditorEpoch
            editorPid = if ($kernelEditorPid -gt 0) { $kernelEditorPid } else { $null }
            activeCommandId = if ($kernelState) { [string]$kernelState.active_command_id } else { $null }
            lastReceiptId = if ($kernelState) { [string]$kernelState.last_receipt_id } else { $null }
            queuedCommandIds = if ($kernelState) { @($kernelState.queued_command_ids) } else { @() }
            performanceFrozen = if ($kernelState) { [bool]$kernelState.performance_frozen } else { $false }
            dirtyPackageCount = if ($kernelState) { [int]$kernelState.dirty_package_count } else { $null }
        }
        task = [ordered]@{ asset = $AssetPath; domain = $Domain; operation = $Operation }
        asset = $assetInfo
    }
} elseif ($next -eq 'CACHE_READ') {
    [ordered]@{ next = $next; sidecar = $assetInfo.sidecar }
} elseif ($next -eq 'NEEDS_DOCTOR') {
    [ordered]@{ next = $next; receipt = $receiptState; reliable = $kernelStateStatus; reason = $receiptIdentityReason }
} elseif ($next -eq 'WAIT_RELIABLE_JOB') {
    $compact = [ordered]@{ next = $next }
    if ([string]$kernelState.active_command_id) { $compact.commandId = [string]$kernelState.active_command_id }
    if (@($kernelState.queued_command_ids).Count) { $compact.queued = @($kernelState.queued_command_ids).Count }
    if ([bool]$kernelState.performance_frozen) { $compact.performanceFrozen = $true }
    $compact
} elseif ($next -in @('LIVE_READ', 'LIVE_MUTATE_RELIABLE_QUEUE', 'LIVE_SAVE_CAPABILITY_REQUIRED')) {
    [ordered]@{ next = $next }
} else {
    $compact = [ordered]@{ next = $next; receipt = $receiptState; reliable = $kernelStateStatus }
    if ($receiptStatus) { $compact.status = $receiptStatus }
    if ($receiptIdentityReason) { $compact.reason = $receiptIdentityReason }
    $compact
}
$json = if ($Pretty) { $output | ConvertTo-Json -Depth 12 } else { $output | ConvertTo-Json -Depth 12 -Compress }
if ($OutFile) {
    $parent = Split-Path $OutFile -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
    [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
} else {
    $json
}
