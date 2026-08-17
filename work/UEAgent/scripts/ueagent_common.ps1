function Get-NormalizedFileSha256($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $text = [IO.File]::ReadAllText($Path) -replace "`r`n", "`n" -replace "`r", "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($text))
        )).Replace('-', '')
    } finally {
        $sha.Dispose()
    }
}

function Test-GitPatchesApplied($Repository, [string[]]$Patches) {
    if (-not $Patches -or $Patches.Count -eq 0) { return $true }
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & git -C $Repository apply --reverse --check @Patches 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
        & git -C $Repository apply --reverse --check --ignore-space-change --ignore-whitespace @Patches 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Test-GitPatchApplied($Repository, $Patch) {
    Test-GitPatchesApplied $Repository @($Patch)
}

function Test-VibeUEProfileApplied($Repository, $Patch, $Profile) {
    if (Test-GitPatchApplied $Repository $Patch) { return $true }
    # Later patches overlap the composite profile; these markers verify its public surface.
    $modulePath = Join-Path $Repository 'Source\VibeUE\Private\Module.cpp'
    $scratchHeaderPath = Join-Path $Repository 'Source\VibeUE\Public\PythonAPI\UNiagaraScratchPadService.h'
    $scratchSourcePath = Join-Path $Repository 'Source\VibeUE\Private\PythonAPI\UNiagaraScratchPadService.cpp'
    if (-not (Test-Path -LiteralPath $modulePath) -or -not (Test-Path -LiteralPath $scratchHeaderPath) -or
        -not (Test-Path -LiteralPath $scratchSourcePath)) { return $false }
    $module = Get-Content -Raw -LiteralPath $modulePath
    $header = Get-Content -Raw -LiteralPath $scratchHeaderPath
    $source = Get-Content -Raw -LiteralPath $scratchSourcePath
    foreach ($marker in @('vibeue-material-cache-v2', 'vibeue-blueprint-cache-v1', 'vibeue-niagara-system-cache-v1', 'VibeUE.MaterialAICache.Rebuild')) {
        if (-not $module.Contains($marker)) { return $false }
    }
    if (-not $header.Contains('GetCustomHlslCode')) { return $false }
    if ($Profile -eq 'niagara-authoring') {
        foreach ($marker in @('CreateSimulationStage', 'ConfigureGrid2DSimulationStage', 'CreateInternalRenderTarget2DUserParameter', 'CreateRasterizationGrid3DUserParameter')) {
            if (-not $header.Contains($marker)) { return $false }
        }
        if (-not $source.Contains('RequestNewTypedPin')) { return $false }
    }
    return $true
}

function Get-IniSectionBody($Path, $Section) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $match = [Regex]::Match(
        (Get-Content -Raw -LiteralPath $Path),
        "(?ms)^\[$([Regex]::Escape($Section))\]\r?\n(?<body>.*?)(?=^\[|\z)"
    )
    if ($match.Success) { return $match.Groups['body'].Value }
    return $null
}

function Read-UeAgentStackManifest($UeAgentRoot) {
    $path = Join-Path $UeAgentRoot 'STACK-MANIFEST.json'
    if (-not (Test-Path -LiteralPath $path)) { throw "UEAgent stack manifest not found: $path" }
    $manifest = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ($manifest.schema -ne 'ueagent-stack-v1') { throw "Unsupported UEAgent stack manifest: $($manifest.schema)" }
    return $manifest
}

function Get-UeAgentManifestPatchErrors($UeAgentRoot, $Manifest) {
    @($Manifest.patches.PSObject.Properties | ForEach-Object {
        $path = Join-Path $UeAgentRoot ([string]$_.Name).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) {
            "Manifest patch is missing: $($_.Name)"
        } elseif ((Get-NormalizedFileSha256 $path) -ne [string]$_.Value) {
            "Manifest patch hash differs: $($_.Name)"
        }
    })
}

function Get-EnabledExternalPluginInventory($Project, $ProjectRoot) {
    $pluginRoot = Join-Path $ProjectRoot 'Plugins'
    if (-not [IO.Directory]::Exists($pluginRoot)) { return @() }
    $descriptors = @{}
    foreach ($path in [IO.Directory]::EnumerateFiles($pluginRoot, '*.uplugin', [IO.SearchOption]::AllDirectories)) {
        $name = [IO.Path]::GetFileNameWithoutExtension($path)
        if ($descriptors.ContainsKey($name)) { throw "Duplicate project plugin descriptor: $name" }
        $descriptors[$name] = $path
    }
    @($Project.Plugins | Where-Object { $_.Enabled -and $_.Name -ne 'VibeUE' } | ForEach-Object {
        $name = [string]$_.Name
        if ($descriptors.ContainsKey($name)) {
            $path = [string]$descriptors[$name]
            $descriptor = [IO.File]::ReadAllText($path) | ConvertFrom-Json
            [pscustomobject][ordered]@{
                name = $name
                descriptor = $path.Substring($ProjectRoot.TrimEnd('\').Length + 1).Replace('\', '/')
                version = [int]$descriptor.Version
                versionName = [string]$descriptor.VersionName
                descriptorSha256 = Get-NormalizedFileSha256 $path
            }
        }
    } | Sort-Object name)
}

function Get-PluginFingerprint($ProjectRoot, $EngineRoot, $ProjectName) {
    $patterns = @()
    if ($ProjectRoot) {
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\VibeUE\*.uplugin')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\Binaries\Win64\*.dll')
        $patterns += (Join-Path $ProjectRoot 'Plugins\NiagaraToolsets\*.uplugin')
        if ($ProjectName) {
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-VibeUE*.dll")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-VibeUE.patch_*.exe")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-NiagaraToolsets*.dll")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-NiagaraToolsets.patch_*.exe")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-ModelContextProtocol*.dll")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-ModelContextProtocol*.patch_*.exe")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-EditorToolset*.dll")
            $patterns += (Join-Path $ProjectRoot "Binaries\Win64\${ProjectName}Editor-EditorToolset*.patch_*.exe")
        }
    }
    if ($EngineRoot) {
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\*.uplugin')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\Binaries\Win64\*.dll')
        $patterns += (Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\*.uplugin')
    }
    $paths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($pattern in $patterns) {
        $directory = [IO.Path]::GetDirectoryName($pattern)
        if (-not [IO.Directory]::Exists($directory)) { continue }
        try {
            foreach ($path in [IO.Directory]::EnumerateFiles($directory, [IO.Path]::GetFileName($pattern), [IO.SearchOption]::TopDirectoryOnly)) {
                $null = $paths.Add($path)
            }
        } catch {
            # A concurrently replaced plugin directory simply contributes no fingerprint entries.
        }
    }
    if ($paths.Count -eq 0) { return $null }
    $orderedPaths = [string[]]::new($paths.Count)
    $paths.CopyTo($orderedPaths)
    [Array]::Sort($orderedPaths, [StringComparer]::OrdinalIgnoreCase)
    $stampLines = [string[]]::new($orderedPaths.Length)
    for ($index = 0; $index -lt $orderedPaths.Length; $index++) {
        $file = [IO.FileInfo]::new($orderedPaths[$index])
        $stampLines[$index] = "$($file.FullName)|$($file.Length)|$($file.LastWriteTimeUtc.ToString('o'))"
    }
    $stamp = [string]::Join("`n", $stampLines)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($stamp)))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}
