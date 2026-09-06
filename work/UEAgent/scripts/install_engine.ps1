[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$EngineRoot,
    [ValidateSet('base', 'niagara-authoring')]
    [string]$Profile = 'base',
    [switch]$EngineExtensions,
    [switch]$CheckOnly,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')
$ueAgentRoot = Split-Path $PSScriptRoot -Parent
$manifest = Read-UeAgentStackManifest $ueAgentRoot
$EngineRoot = Resolve-RequiredPath $EngineRoot 'Engine root'

function Invoke-InstallGit($Repository, [string[]]$Arguments, [switch]$Check) {
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & git -C $Repository @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousErrorAction }
    if ($Check) { return $code -eq 0 }
    if ($code -ne 0) { throw "Git $($Arguments -join ' ') failed in ${Repository}: $($output -join [Environment]::NewLine)" }
}

function Set-EngineIniSettings($Path, $Section, $Settings) {
    $text = if (Test-Path -LiteralPath $Path) { [IO.File]::ReadAllText($Path) } else { '' }
    $pattern = "(?ms)^\[$([Regex]::Escape($Section))\]\r?\n(?<body>.*?)(?=^\[|\z)"
    $match = [Regex]::Match($text, $pattern)
    $body = if ($match.Success) { $match.Groups['body'].Value } else { '' }
    foreach ($name in $Settings.Keys) {
        $line = "$name=$($Settings[$name])"
        $linePattern = "(?m)^$([Regex]::Escape($name))=.*\r?$"
        if ($body -match $linePattern) {
            $body = [Regex]::Replace($body, $linePattern, [Text.RegularExpressions.MatchEvaluator]{ param($unusedMatch) $line })
        } else {
            $body = $body.TrimEnd("`r", "`n") + "`n$line`n"
        }
    }
    $sectionText = "[$Section]`n" + $body.TrimStart("`r", "`n")
    $updated = if ($match.Success) {
        $text.Substring(0, $match.Index) + $sectionText + $text.Substring($match.Index + $match.Length)
    } else { $text.TrimEnd("`r", "`n") + "`n`n" + $sectionText }
    $updated = $updated.TrimStart("`r", "`n")
    if ($updated -cne $text) { Write-Utf8NoBom $Path $updated }
}

function Test-InstallPatchSequence($Repository, [string[]]$Patches, [switch]$Reverse) {
    if (-not $Patches.Count) { return $true }
    # Git's temporary index replays dependent patches without touching either working tree/index.
    $temporaryRoot = [IO.Path]::GetFullPath((Join-Path $ueAgentRoot '..\..\tmp\UEAgent'))
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    $temporaryIndex = Join-Path $temporaryRoot ('install-index-' + [Guid]::NewGuid().ToString('N'))
    $previousIndex = $env:GIT_INDEX_FILE
    try {
        $paths = @(& git -C $Repository apply --numstat @Patches | ForEach-Object { ($_ -split "`t", 3)[2] } | Select-Object -Unique)
        if ($LASTEXITCODE -ne 0) { return $false }
        $existing = @($paths | Where-Object { Test-Path -LiteralPath (Join-Path $Repository $_) })
        $env:GIT_INDEX_FILE = $temporaryIndex
        Invoke-InstallGit $Repository @('read-tree', '--empty')
        if ($existing.Count) { Invoke-InstallGit $Repository (@('add', '-f', '--') + $existing) }
        $ordered = @($Patches)
        if ($Reverse) { [array]::Reverse($ordered) }
        foreach ($patch in $ordered) {
            $arguments = @('apply', '--cached', '--whitespace=nowarn')
            if ($Reverse) { $arguments += '--reverse' }
            if (-not (Invoke-InstallGit $Repository ($arguments + $patch) -Check)) { return $false }
        }
        return $true
    } finally {
        $env:GIT_INDEX_FILE = $previousIndex
        Remove-Item -LiteralPath $temporaryIndex -Force -ErrorAction SilentlyContinue
    }
}

function Get-PendingPatchSequence($Repository, [string[]]$Patches) {
    # Resume an installed prefix, including an optional capability appended on a later run.
    for ($count = $Patches.Count; $count -ge 0; --$count) {
        if ($count -gt 0 -and -not (Test-InstallPatchSequence $Repository @($Patches[0..($count - 1)]) -Reverse)) { continue }
        if ($count -eq $Patches.Count) { return }
        $pending = @($Patches[$count..($Patches.Count - 1)])
        if (Test-InstallPatchSequence $Repository $pending) { return $pending }
    }
    throw "Selected patches neither match an installed prefix nor apply cleanly in $Repository. Existing changes are preserved; merge the previous profile or local source edits before rerunning."
}

$buildVersion = Get-Descriptor (Join-Path $EngineRoot 'Engine\Build\Build.version') 'UE Build.version'
foreach ($pair in @(@('MajorVersion', 'major'), @('MinorVersion', 'minor'), @('PatchVersion', 'patch'), @('CompatibleChangelist', 'compatible_changelist'))) {
    if ($buildVersion.($pair[0]) -ne $manifest.engine.($pair[1])) {
        throw "Engine version mismatch for $($pair[0]): expected $($manifest.engine.($pair[1])), found $($buildVersion.($pair[0]))."
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
    throw 'Engine installation requires a source-engine Git checkout.'
}
$buildScript = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
if (-not $CheckOnly -and -not $SkipBuild -and -not (Test-Path -LiteralPath $buildScript)) {
    throw "Engine build entry not found: $buildScript"
}

$selectedProfiles = @('default', $Profile)
if ($EngineExtensions) { $selectedProfiles += 'engine-extensions' }
$relativePatches = @($selectedProfiles | ForEach-Object { @($manifest.profiles.$_.apply) } | Select-Object -Unique)
if (-not $relativePatches.Count) { throw 'The selected engine profiles contain no patches.' }
$enginePatches = @()
$vibePatches = @()
foreach ($relative in $relativePatches) {
    $path = Join-Path $ueAgentRoot ([string]$relative).Replace('/', '\')
    if (-not (Test-Path -LiteralPath $path)) { throw "Selected patch is missing: $relative" }
    if ([IO.File]::ReadAllText($path).Contains("`r")) { throw "Packaged patch must use LF line endings: $relative" }
    if ($relative -like 'patches/vibeue-*' -or $relative -like 'patches/niagara-mcp-authoring/vibeue/*') {
        $vibePatches += $path
    } else { $enginePatches += $path }
}

$vibePath = Join-Path $EngineRoot ([string]$manifest.runtime.vibeue_engine_path).Replace('/', '\')
if (-not (Test-Path -LiteralPath $vibePath)) {
    if ($CheckOnly) { throw "Engine VibeUE checkout is missing: $vibePath" }
    New-Item -ItemType Directory -Path (Split-Path $vibePath -Parent) -Force | Out-Null
    Invoke-InstallGit $EngineRoot @('clone', '--quiet', '--no-checkout', '-c', 'core.autocrlf=false', 'https://github.com/kevinpbuckley/VibeUE.git', $vibePath)
    Invoke-InstallGit $vibePath @('fetch', '--quiet', 'origin', [string]$manifest.profiles.base.vibeue_merge_base_ref)
    Invoke-InstallGit $vibePath @('fetch', '--quiet', 'origin', [string]$manifest.profiles.base.vibeue_ref)
    Invoke-InstallGit $vibePath @('checkout', '--quiet', '-b', 'Aether/ueagent', [string]$manifest.profiles.base.vibeue_merge_base_ref)
    Invoke-InstallGit $vibePath @('-c', 'user.name=ueagent-installer', '-c', 'user.email=ueagent-installer@localhost',
        'merge', '--quiet', '--no-ff', '--no-edit', [string]$manifest.profiles.base.vibeue_ref)
}
if (-not (Test-Path -LiteralPath (Join-Path $vibePath '.git'))) {
    throw "Existing VibeUE directory is not a Git checkout; it has been preserved: $vibePath"
}

$pluginPaths = Get-EnginePluginPaths $EngineRoot
if ($Profile -eq 'niagara-authoring') {
    $pluginPaths.NiagaraToolsets = Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\NiagaraToolsets\NiagaraToolsets.uplugin'
}
foreach ($name in $pluginPaths.Keys) { $null = Get-Descriptor $pluginPaths[$name] $name }
$plans = @(
    [pscustomobject]@{ repository = $EngineRoot; patches = $enginePatches; pending = @() },
    [pscustomobject]@{ repository = $vibePath; patches = $vibePatches; pending = @() }
)
foreach ($plan in $plans) {
    if ($CheckOnly) {
        if (-not (Test-InstallPatchSequence $plan.repository $plan.patches -Reverse)) { throw "Selected patch sequence is not installed in $($plan.repository)." }
    } else {
        $plan.pending = @(Get-PendingPatchSequence $plan.repository $plan.patches)
    }
}

if (-not $CheckOnly) {
    foreach ($plan in $plans) {
        foreach ($patch in $plan.pending) { Invoke-InstallGit $plan.repository @('apply', '--whitespace=nowarn', $patch) }
    }
    foreach ($name in $pluginPaths.Keys) {
        $descriptor = Get-Descriptor $pluginPaths[$name] $name
        if ($descriptor.EnabledByDefault -ne $true) {
            $null = Set-JsonProperty $descriptor 'EnabledByDefault' $true
            Write-Utf8NoBom $pluginPaths[$name] (($descriptor | ConvertTo-Json -Depth 30) + "`n")
        }
    }
    $endpoint = [Uri]$manifest.runtime.endpoint
    Set-EngineIniSettings (Join-Path $EngineRoot ([string]$manifest.runtime.mcp_engine_config).Replace('/', '\')) '/Script/ModelContextProtocolEngine.ModelContextProtocolSettings' ([ordered]@{
        ServerUrlPath = $endpoint.AbsolutePath; ServerPortNumber = $endpoint.Port; bAutoStartServer = 'True'; bEnableToolSearch = 'True'
    })
    Set-EngineIniSettings (Join-Path $EngineRoot 'Engine\Config\BaseEditor.ini') 'UEAgent.Reliable' ([ordered]@{
        Enabled = 'True'
    })
}

$null = Assert-EngineInstallation $EngineRoot $manifest
foreach ($name in $pluginPaths.Keys) { $null = Assert-DefaultEnginePlugin $pluginPaths[$name] $name }
foreach ($plan in $plans) {
    if (-not (Test-InstallPatchSequence $plan.repository $plan.patches -Reverse)) { throw "Patch verification failed in $($plan.repository)." }
}
$built = $false
if (-not $CheckOnly -and -not $SkipBuild) {
    & $buildScript UnrealEditor Win64 Development -WaitMutex -FromMsBuild | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Engine editor build failed (exit $LASTEXITCODE). Installed source changes are retained for diagnosis." }
    $built = $true
}
[ordered]@{
    ok = $true; engineRoot = $EngineRoot; profiles = $selectedProfiles; patchCount = $relativePatches.Count
    sourceAndDefaultsVerified = $true; built = $built; liveVerified = $false
} | ConvertTo-Json -Compress
