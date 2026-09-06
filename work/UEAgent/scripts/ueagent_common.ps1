function Test-GitPatchesApplied($Repository, [string[]]$Patches) {
    if (-not $Patches -or $Patches.Count -eq 0) { return $true }
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & git -C $Repository apply --reverse --check @Patches 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
        & git -C $Repository apply --reverse --check --ignore-space-change --ignore-whitespace @Patches 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
        # Match patches installed with reduced context after surrounding source changes.
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

function Get-EnginePluginPaths($EngineRoot) {
    [ordered]@{
        ModelContextProtocol = Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\ModelContextProtocol.uplugin'
        EditorToolset = Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\EditorToolset.uplugin'
        VibeUE = Join-Path $EngineRoot 'Engine\Plugins\AI\VibeUE\VibeUE.uplugin'
    }
}

function Resolve-RequiredPath($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
    (Resolve-Path -LiteralPath $Path).Path
}

function Write-Utf8NoBom($Path, $Text) {
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Set-JsonProperty($Object, $Name, $Value) {
    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Get-GitRevision($Repository, $Label, $Fallback) {
    $gitDir = Join-Path $Repository '.git'
    if (Test-Path -LiteralPath $gitDir) {
        $revision = (& git -C $Repository rev-parse HEAD 2>$null).Trim()
        if ($LASTEXITCODE -eq 0 -and $revision) {
            return $revision
        }
    }
    if ($Fallback) {
        return $Fallback
    }
    throw "Could not identify $Label revision: $Repository"
}

function Get-Descriptor($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label descriptor not found: $Path"
    }
    try {
        return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    } catch {
        throw "$Label descriptor is invalid JSON: $Path"
    }
}

function Assert-DefaultEnginePlugin($Path, $Name) {
    $descriptor = Get-Descriptor $Path $Name
    if ($descriptor.EnabledByDefault -ne $true) {
        throw "Engine plugin $Name is not EnabledByDefault: $Path"
    }
    return $descriptor
}

function Assert-IniSettings($Path, $Section, $Expected) {
    $body = Get-IniSectionBody $Path $Section
    if ($null -eq $body) {
        throw "Engine configuration section is missing: [$Section] in $Path"
    }
    foreach ($line in $Expected) {
        if ($body -notmatch "(?m)^$([Regex]::Escape($line))\r?$") {
            throw "Engine configuration setting is missing: $line in [$Section]"
        }
    }
}

function Assert-EngineInstallation($EngineRoot, $StackManifest) {
    $buildVersionPath = Join-Path $EngineRoot 'Engine\Build\Build.version'
    $buildVersion = Get-Content -Raw -LiteralPath $buildVersionPath | ConvertFrom-Json
    if ($buildVersion.MajorVersion -ne $StackManifest.engine.major -or
        $buildVersion.MinorVersion -ne $StackManifest.engine.minor -or
        $buildVersion.PatchVersion -ne $StackManifest.engine.patch -or
        $buildVersion.CompatibleChangelist -ne $StackManifest.engine.compatible_changelist) {
        throw "UE $($StackManifest.engine.major).$($StackManifest.engine.minor).$($StackManifest.engine.patch) changelist $($StackManifest.engine.compatible_changelist) is required; found $($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion) changelist $($buildVersion.CompatibleChangelist)."
    }

    $pluginPaths = Get-EnginePluginPaths $EngineRoot
    $descriptors = [ordered]@{}
    foreach ($name in $pluginPaths.Keys) {
        $descriptors[$name] = Assert-DefaultEnginePlugin $pluginPaths[$name] $name
    }

    $mcpSettings = Join-Path $EngineRoot 'Engine\Config\BaseEditorPerProjectUserSettings.ini'
    Assert-IniSettings $mcpSettings '/Script/ModelContextProtocolEngine.ModelContextProtocolSettings' @(
        'ServerUrlPath=/mcp',
        'ServerPortNumber=8000',
        'bAutoStartServer=True',
        'bEnableToolSearch=True'
    )
    $reliableSettings = Join-Path $EngineRoot 'Engine\Config\BaseEditor.ini'
    Assert-IniSettings $reliableSettings 'UEAgent.Reliable' @(
        'Enabled=True'
    )

    $vibePath = Split-Path $pluginPaths.VibeUE -Parent
    $vibeRevisionFallback = "descriptor:$($descriptors.VibeUE.Version)-$($descriptors.VibeUE.VersionName)"
    [pscustomobject]@{
        BuildVersion = $buildVersion
        ModelContextProtocol = $descriptors.ModelContextProtocol
        EditorToolset = $descriptors.EditorToolset
        VibeUE = $descriptors.VibeUE
        VibeUEPath = $vibePath
        VibeUERevision = Get-GitRevision $vibePath 'VibeUE' $vibeRevisionFallback
        EngineRevision = Get-GitRevision $EngineRoot 'UE 5.8 engine' ("cl-$($buildVersion.CompatibleChangelist)")
    }
}
