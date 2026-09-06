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
        if ($LASTEXITCODE -eq 0) { return $true }
        # Relaxed-application fallback: patches applied with reduced context still reverse-check
        # when the context requirement is lowered to match.
        & git -C $Repository apply --reverse --check -C1 --ignore-space-change --ignore-whitespace @Patches 2>$null
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
        foreach ($marker in @(
            'CreateSimulationStage', 'ConfigureGrid2DSimulationStage',
            'CreateInternalRenderTarget2DUserParameter', 'CreateRasterizationGrid3DUserParameter',
            'AddParameterInputNode', 'AddParticleReadNode', 'CreateEmitterAsset',
            'RegisterScratchModuleForEmitter', 'RefreshModuleCallNodes', 'RemoveScratchPin'
        )) {
            if (-not $header.Contains($marker)) { return $false }
        }
        if (-not $source.Contains('RequestNewTypedPin')) { return $false }
    }
    return $true
}

function Get-EngineIniSectionNames($EngineRoot) {
    $names = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $configRoot = Join-Path $EngineRoot 'Engine\Config'
    if (-not (Test-Path -LiteralPath $configRoot)) { return $names }
    foreach ($file in [IO.Directory]::EnumerateFiles($configRoot, '*.ini', [IO.SearchOption]::AllDirectories)) {
        foreach ($match in [Regex]::Matches((Get-Content -Raw -LiteralPath $file) + '', '(?m)^\[([^\]]+)\]')) {
            $null = $names.Add($match.Groups[1].Value.Trim())
        }
    }
    return $names
}

function Get-IniSectionBody($Path, $Section) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $match = [Regex]::Match(
        (Get-Content -Raw -LiteralPath $Path) + '',
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
    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($property in $Manifest.patches.PSObject.Properties) {
        $relative = [string]$property.Name
        $path = Join-Path $UeAgentRoot $relative.Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) {
            $errors.Add("Manifest patch is missing: $relative")
        } elseif ((Get-NormalizedFileSha256 $path) -ne [string]$property.Value.sha256) {
            $errors.Add("Manifest patch hash differs: $relative")
        }
        if ([string]$property.Value.repo -notin @('engine', 'vibeue')) {
            $errors.Add("Manifest patch declares an unknown repo: $relative")
        }
    }
    $referenced = [System.Collections.Generic.List[string]]::new()
    foreach ($property in $Manifest.profiles.PSObject.Properties) {
        foreach ($relative in @($property.Value.apply) | Where-Object { $_ }) { $referenced.Add([string]$relative) }
    }
    if ($Manifest.targets) {
        foreach ($property in $Manifest.targets.PSObject.Properties) {
            foreach ($group in @('engine', 'vibeue')) {
                foreach ($relative in @($property.Value.extra_patches.$group) | Where-Object { $_ }) {
                    $referenced.Add([string]$relative)
                }
            }
        }
    }
    foreach ($relative in @($referenced | Select-Object -Unique)) {
        if (-not ($Manifest.patches.PSObject.Properties.Name -contains $relative)) {
            $errors.Add("Manifest apply list names an unpinned patch: $relative")
        }
    }
    return @($errors)
}

function Get-UeAgentCapabilitySwitches($Manifest) {
    $switches = [ordered]@{}
    foreach ($property in $Manifest.profiles.PSObject.Properties) {
        $profile = $property.Value
        if (-not ($profile.PSObject.Properties.Name -contains 'bootstrap_switch')) { continue }
        $switches[[string]$profile.capability] = ([string]$profile.bootstrap_switch).TrimStart('-')
    }
    return $switches
}

function Get-UeAgentCoreCapabilities($Manifest) {
    @($Manifest.profiles.PSObject.Properties |
        Where-Object { [string]$_.Value.kind -eq 'core' } |
        ForEach-Object { [string]$_.Value.capability })
}

function Get-UeAgentCoreFallback($Manifest) {
    $switchless = @($Manifest.profiles.PSObject.Properties | Where-Object {
        [string]$_.Value.kind -eq 'core' -and
        -not ($_.Value.PSObject.Properties.Name -contains 'bootstrap_switch')
    } | ForEach-Object { [string]$_.Value.capability })
    if ($switchless.Count -ne 1) {
        throw "UEAgent stack manifest must declare exactly one switchless core profile; found $($switchless.Count)."
    }
    return $switchless[0]
}

function Get-UeAgentPatchEntry($Manifest, $UeAgentRoot, [string]$Relative) {
    $record = $Manifest.patches.PSObject.Properties[$Relative]
    if ($null -eq $record) { throw "UEAgent stack manifest has no pinned patch: $Relative" }
    $repo = [string]$record.Value.repo
    if ($repo -notin @('engine', 'vibeue')) {
        throw "UEAgent stack manifest patch '$Relative' declares an unknown repo: $repo"
    }
    [pscustomobject]@{
        relative   = $Relative
        path       = (Join-Path $UeAgentRoot $Relative.Replace('/', '\'))
        sha256     = [string]$record.Value.sha256
        repo       = $repo
        routeField = if ($record.Value.PSObject.Properties.Name -contains 'route_field') {
            [string]$record.Value.route_field
        } else { '' }
    }
}

function Get-UeAgentSelectedProfiles($Manifest, [string]$CoreCapability, [string[]]$Capabilities) {
    $core = @()
    $additive = @()
    foreach ($property in $Manifest.profiles.PSObject.Properties) {
        $capability = [string]$property.Value.capability
        if (-not $capability) { throw "UEAgent profile '$($property.Name)' declares no capability name." }
        if ([string]$property.Value.kind -eq 'core') {
            if ($capability -eq $CoreCapability) { $core += $property.Name }
        } elseif ($Capabilities -contains $capability) {
            $additive += $property.Name
        }
    }
    if ($core.Count -ne 1) {
        throw "UEAgent stack manifest resolved $($core.Count) core profiles for capability '$CoreCapability'; exactly one is required."
    }
    return @($core + $additive)
}

function Assert-UeAgentProfileRequirements($Manifest, [string[]]$ProfileNames) {
    $provided = @($ProfileNames | ForEach-Object { [string]$Manifest.profiles.$_.capability })
    foreach ($name in $ProfileNames) {
        $profile = $Manifest.profiles.$name
        if (-not ($profile.PSObject.Properties.Name -contains 'requires')) { continue }
        foreach ($required in @($profile.requires) | Where-Object { $_ }) {
            if ($provided -notcontains [string]$required) {
                throw "UEAgent profile '$name' is not self-sufficient: it requires capability '$required', which is not selected."
            }
        }
    }
}

function Get-UeAgentProfilePlugins($Manifest, [string[]]$ProfileNames) {
    @($ProfileNames | ForEach-Object {
        $profile = $Manifest.profiles.$_
        if ($profile.PSObject.Properties.Name -contains 'required_plugins') { @($profile.required_plugins) }
    } | Where-Object { $_ } | Select-Object -Unique)
}

function Get-UeAgentPatchPlan($Manifest, $UeAgentRoot, [string[]]$ProfileNames, $Target) {
    $entries = [ordered]@{}
    $append = {
        param($Relative)
        $Relative = [string]$Relative
        if (-not $Relative -or $entries.Contains($Relative)) { return }
        $entries[$Relative] = Get-UeAgentPatchEntry $Manifest $UeAgentRoot $Relative
    }
    foreach ($name in $ProfileNames) {
        $profile = $Manifest.profiles.$name
        if ($null -eq $profile) { throw "UEAgent stack manifest has no declared profile: $name" }
        foreach ($relative in @($profile.apply)) { & $append $relative }
    }
    if ($Target -and $Target.extra_patches) {
        foreach ($group in @('engine', 'vibeue')) {
            foreach ($relative in @($Target.extra_patches.$group)) { & $append $relative }
        }
    }
    return @($entries.Values)
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
