[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [string]$VibeUERef,
    [string]$Endpoint,
    [switch]$PreserveExistingVibeUE,
    [string]$TargetProfile,
    [switch]$ApplyNiagaraAuthoringProfile,
    [switch]$ApplyEngineNiagaraPatch,
    [switch]$ApplyMcpToolSearchPatch,
    [string]$ExternalPluginSourceRoot,
    [switch]$CheckOnly,
    [switch]$SkipBuild,
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')
$VibeUERepository = 'https://github.com/kevinpbuckley/VibeUE.git'

function Resolve-RequiredPath($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "$Label not found: $Path" }
    (Resolve-Path -LiteralPath $Path).Path
}

function Assert-LastExitCode($Message) {
    if ($LASTEXITCODE -ne 0) { throw "$Message (exit $LASTEXITCODE)" }
}

function Invoke-GitQuiet {
    # Run git in a child scope so stderr records cannot surface as terminating errors under
    # ErrorActionPreference=Stop; the caller judges the result through $LASTEXITCODE.
    param([string]$Repository, [string[]]$GitArguments)
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git -C $Repository @GitArguments 2>$null
    } catch {
        # stderr noise must never abort bootstrap; exit code is the only verdict.
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Ensure-GitPatchApplied($Repository, $Patch, $Label) {
    if (Test-GitPatchApplied $Repository $Patch) { return }
    Invoke-GitQuiet $Repository @('apply', '--check', $Patch)
    if ($LASTEXITCODE -ne 0) {
        # Packaged patches were generated against a locally merged VibeUE baseline; relaxed
        # context is the verified fallback, bounded afterwards by Test-VibeUEProfileApplied.
        Invoke-GitQuiet $Repository @('apply', '--check', '-C1', '--ignore-space-change', '--ignore-whitespace', $Patch)
        Assert-LastExitCode "$Label does not apply cleanly"
        Invoke-GitQuiet $Repository @('apply', '-C1', '--ignore-space-change', '--ignore-whitespace', $Patch)
        Assert-LastExitCode "$Label application failed"
        return
    }
    Invoke-GitQuiet $Repository @('apply', $Patch)
    Assert-LastExitCode "$Label application failed"
}

function Enable-UProjectPlugin($Project, $Name) {
    if (-not ($Project.PSObject.Properties.Name -contains 'Plugins')) {
        $Project | Add-Member -NotePropertyName Plugins -NotePropertyValue @()
    }
    $existing = @($Project.Plugins | Where-Object Name -eq $Name)
    if ($existing) {
        $existing[0].Enabled = $true
        return
    }
    $Project.Plugins = @($Project.Plugins) + [pscustomobject]@{ Name = $Name; Enabled = $true }
}

function Set-JsonProperty($Object, $Name, $Value) {
    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Write-Utf8NoBom($Path, $Text) {
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Assert-UeAgentReliableConfig($ProjectRoot) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEditor.ini'
    $body = Get-IniSectionBody $path 'UEAgent.Reliable'
    if ($null -eq $body) { throw "UEAgent reliable config section is missing: $path" }
    foreach ($expected in @('Enabled=True', 'SaveTokenLifetimeSeconds=300', 'EnableFaultInjection=False')) {
        if ($body -notmatch "(?m)^$([Regex]::Escape($expected))\r?$") {
            throw "UEAgent reliable config setting is missing: $expected"
        }
    }
}

function Set-UeAgentReliableConfig($ProjectRoot) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEditor.ini'
    $block = @'
[UEAgent.Reliable]
Enabled=True
SaveTokenLifetimeSeconds=300
EnableFaultInjection=False
'@
    $existing = if (Test-Path -LiteralPath $path) { (Get-Content -Raw -LiteralPath $path) + '' } else { '' }
    $pattern = '(?ms)^\[UEAgent\.Reliable\]\r?\n.*?(?=^\[|\z)'
    $updated = if ($existing -match $pattern) {
        [Regex]::Replace($existing, $pattern, $block.Trim() + [Environment]::NewLine)
    } else {
        $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine +
            $block.Trim() + [Environment]::NewLine
    }
    Write-Utf8NoBom $path $updated.TrimStart()
}

function Get-TargetProfile($Manifest, $Name, $ProjectName) {
    if ($null -eq $Manifest.targets) {
        throw 'UEAgent stack manifest declares no targets; -TargetProfile is not supported.'
    }
    $profile = $Manifest.targets.$Name
    if ($null -eq $profile) { throw "UEAgent stack manifest has no declared target: $Name" }
    if ([string]$profile.project_name -ne $ProjectName) {
        throw "Target '$Name' is declared for project '$($profile.project_name)'; found $ProjectName.uproject."
    }
    return $profile
}

function Get-TargetCapabilities($Profile, $CapabilitySwitches) {
    @($Profile.capabilities | ForEach-Object {
        $capability = [string]$_
        if (-not $CapabilitySwitches.Contains($capability)) {
            throw "Target '$($Profile.project_name)' declares an unknown capability: $capability"
        }
        $capability
    })
}

function Get-RoutedCapabilities($Manifest, $UeAgentRoot, $Route) {
    @($Manifest.profiles.PSObject.Properties | Where-Object {
        if ([string]$_.Value.kind -eq 'core') { return $false }
        $fields = @(Get-UeAgentPatchPlan $Manifest $UeAgentRoot @($_.Name) $null |
            Where-Object { $_.routeField } | ForEach-Object { $_.routeField })
        $fields.Count -gt 0 -and -not @($fields | Where-Object {
            -not ($Route.PSObject.Properties.Name -contains $_)
        }).Count
    } | ForEach-Object { [string]$_.Value.capability })
}

function Assert-ProjectSettings($ProjectRoot, $EngineRoot, $Profile) {
    if ($null -eq $Profile.project_settings) { return }
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $knownSections = Get-EngineIniSectionNames $EngineRoot
    foreach ($section in $Profile.project_settings.PSObject.Properties) {
        Assert-KnownIniSection $knownSections $section.Name $Profile
        $body = Get-IniSectionBody $path $section.Name
        foreach ($setting in $section.Value.PSObject.Properties) {
            $expected = "$($setting.Name)=$($setting.Value)"
            if ($null -eq $body -or $body -notmatch "(?m)^$([Regex]::Escape($expected))\r?$") {
                throw "Target '$($Profile.project_name)' setting is missing: [$($section.Name)] $expected"
            }
        }
    }
}

# Writing and reading back use the same manifest name, so only the engine config hierarchy can
# catch a section name that is consistently wrong.
function Assert-KnownIniSection($KnownSections, $Section, $Profile) {
    if ($KnownSections.Contains($Section)) { return }
    throw "Target '$($Profile.project_name)' declares a project_settings section the engine config hierarchy does not define: [$($Section)]"
}

function Set-IniSectionSettings($Path, $Section, $Settings) {
    $existing = if (Test-Path -LiteralPath $Path) { (Get-Content -Raw -LiteralPath $Path) + '' } else { '' }
    foreach ($setting in $Settings.PSObject.Properties) {
        $line = "$($setting.Name)=$($setting.Value)"
        $linePattern = "(?m)^$([Regex]::Escape([string]$setting.Name))=.*\r?$"
        if ($existing -match $linePattern) {
            $existing = [Regex]::Replace($existing, $linePattern, $line)
        } elseif ($existing -match "(?m)^\[$([Regex]::Escape($Section))\]\r?$") {
            $existing = [Regex]::Replace($existing, "(?m)^\[$([Regex]::Escape($Section))\]\r?$", "[$Section]$([Environment]::NewLine)$line")
        } else {
            $existing = $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine +
                "[$Section]$([Environment]::NewLine)$line$([Environment]::NewLine)"
        }
    }
    Write-Utf8NoBom $Path $existing.TrimStart()
}

function Set-ProjectSettings($ProjectRoot, $EngineRoot, $Profile) {
    if ($null -eq $Profile.project_settings) { return }
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $knownSections = Get-EngineIniSectionNames $EngineRoot
    foreach ($section in $Profile.project_settings.PSObject.Properties) {
        Assert-KnownIniSection $knownSections $section.Name $Profile
        Set-IniSectionSettings $path $section.Name $section.Value
    }
}

function Assert-ExternalPlugins($Project, $ProjectRoot, $Profile) {
    $expected = @($Profile.external_plugins)
    $actual = @(Get-EnabledExternalPluginInventory $Project $ProjectRoot)
    if ((ConvertTo-Json -InputObject $actual -Depth 5 -Compress) -ne
        (ConvertTo-Json -InputObject $expected -Depth 5 -Compress)) {
        throw "Target '$($Profile.project_name)' external plugins are missing or differ from the pinned bootstrap inventory."
    }
    return $actual
}

function Ensure-ExternalPlugins($Project, $ProjectRoot, $Profile, $SourceRoot) {
    $expected = @($Profile.external_plugins)
    $resolvedSourceRoot = if ($SourceRoot) { Resolve-RequiredPath $SourceRoot 'External plugin source root' } else { $null }
    if ($resolvedSourceRoot) {
        foreach ($plugin in $expected) {
            $relativeDescriptor = ([string]$plugin.descriptor).Replace('/', '\')
            $relativeDirectory = Split-Path $relativeDescriptor -Parent
            $destinationDirectory = Join-Path $ProjectRoot $relativeDirectory
            if (Test-Path -LiteralPath (Join-Path $destinationDirectory (Split-Path $relativeDescriptor -Leaf))) {
                continue
            }
            if (Test-Path -LiteralPath $destinationDirectory) {
                throw "External plugin directory is incomplete; refusing to merge: $destinationDirectory"
            }
            $sourceDirectory = Join-Path $resolvedSourceRoot $relativeDirectory
            if (-not (Test-Path -LiteralPath $sourceDirectory)) {
                throw "External plugin source is missing: $sourceDirectory"
            }
            New-Item -ItemType Directory -Path (Split-Path $destinationDirectory -Parent) -Force | Out-Null
            Copy-Item -LiteralPath $sourceDirectory -Destination (Split-Path $destinationDirectory -Parent) -Recurse
        }
    }
    Assert-ExternalPlugins $Project $ProjectRoot $Profile | Out-Null
}

function Set-McpSettingsFile($Path, $Uri) {
    $settings = @"
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=$($uri.AbsolutePath)
ServerPortNumber=$($uri.Port)
bAutoStartServer=True
bEnableToolSearch=True
"@
    $existingSettings = if (Test-Path -LiteralPath $Path) { (Get-Content -Raw -LiteralPath $Path) + '' } else { '' }
    $sectionPattern = '(?ms)^\[/Script/ModelContextProtocolEngine\.ModelContextProtocolSettings\]\r?\n.*?(?=^\[|\z)'
    $newSettings = if ($existingSettings -match $sectionPattern) {
        [regex]::Replace($existingSettings, $sectionPattern, $settings.Trim() + [Environment]::NewLine)
    } else {
        $existingSettings.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $settings.Trim() + [Environment]::NewLine
    }
    Write-Utf8NoBom $Path $newSettings.TrimStart()
}

function Set-UeAgentGate($ProjectRoot) {
    $agentsPath = Join-Path $ProjectRoot 'AGENTS.md'
    $start = '<!-- UEAGENT_GATE_START -->'
    $end = '<!-- UEAGENT_GATE_END -->'
    $block = @'
<!-- UEAGENT_GATE_START -->
## UEAgent live-Unreal gate

Before any work that reads live Unreal state or mutates UE:

1. Read `ueAgentRoot/skills/ue-mcp-workflows/HOTPATH.md`.
2. Locate `Saved/UEAgent/route.json` and pass it to `ueAgentRoot/scripts/compact_context.ps1` for the
   target. Read the route or wrapper source only to diagnose a failure.
3. If it returns `CACHE_READ`, do not call MCP. Otherwise run
   `ueAgentRoot/scripts/doctor.ps1 -RouteFile Saved/UEAgent/route.json`. For a live read, load only
   the relevant domain card; add the Skill and Core before mutation or save.
4. Follow the receipt. Writable work must use `ueagent_snapshot` -> `ueagent_submit` -> terminal
   receipt -> independent snapshot; save only with the receipt-issued exact `ueagent_save` capability.
5. For Gateway calls crossing child PowerShell, serialize the complete request and use UTF-8
   `-RequestBase64` (or `-RequestFile`); never pass hand-escaped raw JSON command-line arguments.
6. Hash-guarded mutations must use one complete manifest from one named asset version; never mix
   historical baselines, and resolve a mismatch before the first mutation.

Offline source/cache/config/log analysis may proceed, but must not claim live editor state.
<!-- UEAGENT_GATE_END -->
'@
    $existing = if (Test-Path -LiteralPath $agentsPath) {
        (Get-Content -Raw -LiteralPath $agentsPath) + ''
    } else {
        ''
    }
    $pattern = "(?ms)^$([regex]::Escape($start)).*?^$([regex]::Escape($end))\r?\n?"
    $updated = if ($existing -match $pattern) {
        [regex]::Replace($existing, $pattern, $block.Trim() + [Environment]::NewLine)
    } else {
        $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine +
            $block.Trim() + [Environment]::NewLine
    }
    Write-Utf8NoBom $agentsPath $updated.TrimStart()
}

$UProject = Resolve-RequiredPath $UProject 'UProject'
$EngineRoot = Resolve-RequiredPath $EngineRoot 'Engine root'
$ueAgentRoot = Split-Path $PSScriptRoot -Parent
$stackManifest = Read-UeAgentStackManifest $ueAgentRoot
$manifestErrors = @(Get-UeAgentManifestPatchErrors $ueAgentRoot $stackManifest)
if ($manifestErrors.Count) { throw ($manifestErrors -join '; ') }
if (-not $PSBoundParameters.ContainsKey('VibeUERef')) { $VibeUERef = [string]$stackManifest.profiles.base.vibeue_ref }
$vibeUEFetchRef = if ($PSBoundParameters.ContainsKey('VibeUERef')) {
    $VibeUERef
} else {
    [string]$stackManifest.profiles.base.vibeue_fetch_ref
}
if (-not $vibeUEFetchRef) { $vibeUEFetchRef = $VibeUERef }
$vibeUEMergeBaseRef = [string]$stackManifest.profiles.base.vibeue_merge_base_ref
$vibeUEMergedTree = [string]$stackManifest.profiles.base.vibeue_merged_tree
if (-not $PSBoundParameters.ContainsKey('Endpoint')) { $Endpoint = [string]$stackManifest.runtime.endpoint }
$projectRoot = Split-Path $UProject -Parent
$projectName = [IO.Path]::GetFileNameWithoutExtension($UProject)
$capabilitySwitches = Get-UeAgentCapabilitySwitches $stackManifest
$coreCapabilities = @(Get-UeAgentCoreCapabilities $stackManifest)
$coreFallback = Get-UeAgentCoreFallback $stackManifest
$explicitCapabilities = @($capabilitySwitches.Keys | Where-Object {
    $PSBoundParameters.ContainsKey($capabilitySwitches[$_])
})
$target = $null
if ($TargetProfile) {
    $target = Get-TargetProfile $stackManifest $TargetProfile $projectName
    $declaredCapabilities = @(Get-TargetCapabilities $target $capabilitySwitches)
    $undeclared = @($explicitCapabilities | Where-Object { $declaredCapabilities -notcontains $_ })
    if ($undeclared.Count) {
        throw "Target '$($target.project_name)' does not declare the explicitly requested capabilities: $($undeclared -join ', ')."
    }
    $explicitCapabilities = $declaredCapabilities
}
$explicitCores = @($explicitCapabilities | Where-Object { $coreCapabilities -contains $_ })
if ($explicitCores.Count -gt 1) {
    throw "Conflicting core VibeUE profiles were requested: $($explicitCores -join ', ')."
}
$explicitCoreCapability = if ($explicitCores.Count -eq 1) { $explicitCores[0] } else { '' }
$coreCapability = if ($explicitCoreCapability) { $explicitCoreCapability } else { $coreFallback }
$additiveCapabilities = @($explicitCapabilities | Where-Object { $coreCapabilities -notcontains $_ })
$selectedProfiles = @(Get-UeAgentSelectedProfiles $stackManifest $coreCapability $additiveCapabilities)
Assert-UeAgentProfileRequirements $stackManifest $selectedProfiles
$patchPlan = @(Get-UeAgentPatchPlan $stackManifest $ueAgentRoot $selectedProfiles $target)
foreach ($entry in $patchPlan) {
    Resolve-RequiredPath $entry.path "UEAgent patch '$($entry.relative)'" | Out-Null
}
$vibePatchPlan = @($patchPlan | Where-Object { $_.repo -eq 'vibeue' })
$enginePatchPlan = @($patchPlan | Where-Object { $_.repo -eq 'engine' })
if (-not $vibePatchPlan.Count) { throw 'The selected UEAgent profiles resolve no VibeUE patch.' }
if (-not $enginePatchPlan.Count) { throw 'The selected UEAgent profiles resolve no engine patch.' }
$profilePlugins = @(Get-UeAgentProfilePlugins $stackManifest $selectedProfiles)
$reliableProtocolVersion = [string]$stackManifest.runtime.reliable_protocol
$mutationTransport = [string]$stackManifest.runtime.mutation_transport

$vibeProfile = $coreCapability
$vibePatchPath = $vibePatchPlan[0].path
$buildScript = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$projectEditor = Join-Path $projectRoot "Binaries\Win64\$($projectName)Editor.exe"
$nativeMcp = Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\ModelContextProtocol.uplugin'
$editorToolset = Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\EditorToolset.uplugin'
$buildVersionPath = Join-Path $EngineRoot 'Engine\Build\Build.version'
$vibePath = Join-Path $projectRoot 'Plugins\VibeUE'
$vibeManifest = Join-Path $vibePath 'VibeUE.uplugin'

foreach ($required in @($buildScript, $editor, $nativeMcp, $editorToolset, $buildVersionPath)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "UE 5.8 MCP prerequisite not found: $required" }
}
$buildVersion = Get-Content -Raw -LiteralPath $buildVersionPath | ConvertFrom-Json
if ($buildVersion.MajorVersion -ne $stackManifest.engine.major -or
    $buildVersion.MinorVersion -ne $stackManifest.engine.minor -or
    $buildVersion.PatchVersion -ne $stackManifest.engine.patch -or
    $buildVersion.CompatibleChangelist -ne $stackManifest.engine.compatible_changelist) {
    throw "UE $($stackManifest.engine.major).$($stackManifest.engine.minor).$($stackManifest.engine.patch) changelist $($stackManifest.engine.compatible_changelist) is required; found $($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion) changelist $($buildVersion.CompatibleChangelist)."
}
$plannedRelatives = @($patchPlan | ForEach-Object { $_.relative })
$foreignEnginePatches = @()
if (Test-Path -LiteralPath (Join-Path $EngineRoot '.git')) {
    $foreignEnginePatches = @($stackManifest.patches.PSObject.Properties |
        ForEach-Object { Get-UeAgentPatchEntry $stackManifest $ueAgentRoot $_.Name } |
        Where-Object {
            $_.repo -eq 'engine' -and $plannedRelatives -notcontains $_.relative -and
            (Test-Path -LiteralPath $_.path) -and (Test-GitPatchApplied $EngineRoot $_.path)
        })
}
if (-not $CheckOnly -and $foreignEnginePatches.Count) {
    throw "The engine carries patches outside the selected profile: $(($foreignEnginePatches | ForEach-Object { $_.relative }) -join ', '). Rerun with the matching capability switches."
}

if ($CheckOnly) {
    $mcpPath = Join-Path $projectRoot '.mcp.json'
    $settingsPath = Join-Path $projectRoot 'Config\DefaultEditorPerProjectUserSettings.ini'
    $defaultEditorPath = Join-Path $projectRoot 'Config\DefaultEditor.ini'
    $routePath = Join-Path $projectRoot 'Saved\UEAgent\route.json'
    $agentsPath = Join-Path $projectRoot 'AGENTS.md'
    foreach ($required in @($vibeManifest, $mcpPath, $settingsPath, $defaultEditorPath, $routePath, $agentsPath)) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Configured file not found: $required" }
    }
    $project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
    $route = Get-Content -Raw -LiteralPath $routePath | ConvertFrom-Json
    if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported UEAgent route schema: $($route.schema)" }
    $routedTargetProfile = $null
    if ($route.PSObject.Properties.Name -contains 'targetProfile') {
        $routedTargetProfile = Get-TargetProfile $stackManifest ([string]$route.targetProfile) $projectName
    }
    $externalPlugins = @(Get-EnabledExternalPluginInventory $project $projectRoot)
    if ($routedTargetProfile) {
        Assert-ExternalPlugins $project $projectRoot $routedTargetProfile | Out-Null
    } elseif ((ConvertTo-Json -InputObject $externalPlugins -Depth 5 -Compress) -ne
        (ConvertTo-Json -InputObject @($route.externalPlugins) -Depth 5 -Compress)) {
        throw 'Enabled external plugins differ from the routed bootstrap inventory; rerun bootstrap.'
    }
    if ($target) {
        $routedTargetName = if ($routedTargetProfile) { [string]$routedTargetProfile.project_name } else { '' }
        if ($routedTargetName -ne [string]$target.project_name) {
            throw "The route was not bootstrapped with -TargetProfile $($target.project_name)."
        }
    }
    if (-not $PSBoundParameters.ContainsKey('Endpoint')) { $Endpoint = [string]$route.endpoint }
    $actualRef = (& git -C $vibePath rev-parse HEAD 2>$null).Trim()
    Assert-LastExitCode 'Could not read VibeUE revision'
    if ($route.PSObject.Properties.Name -contains 'vibeUEMergedTree') {
        $expectedTree = [string]$route.vibeUEMergedTree
        $actualTree = (& git -C $vibePath rev-parse 'HEAD^{tree}' 2>$null).Trim()
        Assert-LastExitCode 'Could not read VibeUE tree revision'
        if ($actualTree -ne $expectedTree) { throw "VibeUE tree is $actualTree; expected $expectedTree" }
    } elseif ($actualRef -ne $VibeUERef) {
        throw "VibeUE revision is $actualRef; expected $VibeUERef"
    }
    $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    if ($mcp.mcpServers.'ue-editor'.url -ne $Endpoint) { throw "MCP endpoint is not configured as $Endpoint." }
    $settings = Get-Content -Raw -LiteralPath $settingsPath
    foreach ($expected in @("ServerUrlPath=$(([Uri]$Endpoint).AbsolutePath)", "ServerPortNumber=$(([Uri]$Endpoint).Port)", 'bAutoStartServer=True', 'bEnableToolSearch=True')) {
        if ($settings -notmatch "(?m)^$([regex]::Escape($expected))`r?$") { throw "MCP project setting missing: $expected" }
    }
    $userSettingsPath = Join-Path $projectRoot 'Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini'
    if ((Test-Path -LiteralPath $userSettingsPath) -and
        (Get-Content -Raw -LiteralPath $userSettingsPath) -match '(?m)^bAutoStartServer=False\r?$') {
        throw "User-layer settings override MCP auto-start in $userSettingsPath; rerun bootstrap to repair."
    }
    $routeVibeProfile = if ($route.PSObject.Properties.Name -contains 'vibeUEProfile') {
        [string]$route.vibeUEProfile
    } else { $coreFallback }
    if ($routeVibeProfile -notin $coreCapabilities) {
        throw "Unsupported UEAgent VibeUE profile: $routeVibeProfile"
    }
    if ($explicitCoreCapability -and $explicitCoreCapability -ne $routeVibeProfile) {
        throw "The route was bootstrapped with the '$routeVibeProfile' core profile; the requested one is '$explicitCoreCapability'."
    }
    $routedCapabilities = @(Get-RoutedCapabilities $stackManifest $ueAgentRoot $route)
    foreach ($capability in $additiveCapabilities) {
        if ($routedCapabilities -notcontains $capability) {
            throw "The route carries no fingerprint for the requested capability: $capability"
        }
    }
    $selectedProfiles = @(Get-UeAgentSelectedProfiles $stackManifest $routeVibeProfile $routedCapabilities)
    Assert-UeAgentProfileRequirements $stackManifest $selectedProfiles
    $patchPlan = @(Get-UeAgentPatchPlan $stackManifest $ueAgentRoot $selectedProfiles $routedTargetProfile)
    foreach ($entry in $patchPlan) {
        Resolve-RequiredPath $entry.path "UEAgent patch '$($entry.relative)'" | Out-Null
    }
    $vibePatchPlan = @($patchPlan | Where-Object { $_.repo -eq 'vibeue' })
    $enginePatchPlan = @($patchPlan | Where-Object { $_.repo -eq 'engine' })
    $profilePlugins = @(Get-UeAgentProfilePlugins $stackManifest $selectedProfiles)
    $vibeProfile = $routeVibeProfile
    $vibePatchPath = $vibePatchPlan[0].path
    foreach ($plugin in @('ModelContextProtocol', 'EditorToolset', 'VibeUE') + $profilePlugins) {
        if (-not @($project.Plugins | Where-Object { $_.Name -eq $plugin -and $_.Enabled }).Count) {
            throw "Plugin is not enabled in $UProject`: $plugin"
        }
    }
    foreach ($pair in @(
        @('ueAgentRoot', $ueAgentRoot),
        @('uProject', $UProject),
        @('engineRoot', $EngineRoot),
        @('endpoint', $Endpoint),
        @('transport', 'native-http'),
        @('access', 'task-gated-write'),
        @('reliableProtocol', $reliableProtocolVersion),
        @('mutationTransport', $mutationTransport)
    )) {
        if ([string]$route.($pair[0]) -ne [string]$pair[1]) {
            throw "UEAgent route mismatch for $($pair[0]): $($route.($pair[0]))"
        }
    }
    $agents = Get-Content -Raw -LiteralPath $agentsPath
    if ($agents -notmatch '(?m)^<!-- UEAGENT_GATE_START -->\r?$') {
        throw "UEAgent gate is missing from $agentsPath"
    }
    foreach ($requiredGateRule in @('`-RequestBase64`', 'Hash-guarded mutations')) {
        if (-not $agents.Contains($requiredGateRule)) {
            throw "UEAgent gate is stale or incomplete in $agentsPath`: missing $requiredGateRule"
        }
    }
    $vibeBatchApplied = Test-GitPatchesApplied $vibePath @($vibePatchPlan | ForEach-Object { $_.path })
    $engineBatchApplied = Test-GitPatchesApplied $EngineRoot @($enginePatchPlan | ForEach-Object { $_.path })
    foreach ($entry in $patchPlan) {
        if ($entry.routeField) {
            if ([string]$route.($entry.routeField) -ne $entry.sha256) {
                throw "UEAgent route mismatch for $($entry.routeField): routed $($route.($entry.routeField)), manifest $($entry.sha256) ($($entry.relative))"
            }
        } else {
            if (-not ($route.PSObject.Properties.Name -contains 'targetPatchSha256')) {
                throw 'The routed target profile has no targetPatchSha256 fingerprint table; rerun bootstrap.'
            }
            $routedSha = [string]$route.targetPatchSha256.PSObject.Properties[$entry.relative].Value
            if ($routedSha -ne $entry.sha256) {
                throw "The routed target patch fingerprint differs: $($entry.relative)"
            }
        }
    }
    if (-not (Test-VibeUEProfileApplied $vibePath $vibePatchPath $routeVibeProfile)) {
        throw "The routed UEAgent VibeUE profile is not applied: $routeVibeProfile"
    }
    Assert-UeAgentReliableConfig $projectRoot
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'The routed UEAgent profile requires a source-engine Git checkout.'
    }
    foreach ($entry in $patchPlan) {
        $repository = if ($entry.repo -eq 'engine') { $EngineRoot } else { $vibePath }
        $batchApplied = if ($entry.repo -eq 'engine') { $engineBatchApplied } else { $vibeBatchApplied }
        if (-not $batchApplied -and -not (Test-GitPatchApplied $repository $entry.path)) {
            throw "The routed $($entry.repo) patch is not applied: $($entry.relative)"
        }
    }
    if ($routedTargetProfile) {
        Assert-ProjectSettings $projectRoot $EngineRoot $routedTargetProfile
    }
    Write-Host "UEAgent static check passed for $projectName." -ForegroundColor Green
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to install VibeUE.' }
if (-not (Test-Path -LiteralPath $vibePath)) {
    New-Item -ItemType Directory -Path (Split-Path $vibePath -Parent) -Force | Out-Null
    & git clone --quiet -c core.autocrlf=false $VibeUERepository $vibePath 2>$null
    Assert-LastExitCode 'VibeUE clone failed'
}
if (-not (Test-Path -LiteralPath (Join-Path $vibePath '.git'))) { throw "Existing VibeUE directory is not a Git checkout: $vibePath" }
$origin = (& git -C $vibePath remote get-url origin 2>$null).Trim()
Assert-LastExitCode 'Could not read VibeUE origin'
if ($origin -notin @($VibeUERepository, 'git@github.com:kevinpbuckley/VibeUE.git')) {
    throw "Unexpected VibeUE origin: $origin"
}
$dirty = & git -C $vibePath status --porcelain 2>$null
Assert-LastExitCode 'Could not inspect VibeUE checkout'
if (-not $dirty) {
    # Packaged patches are LF; normalize a machine-level core.autocrlf=true checkout before patching.
    & git -C $vibePath config core.autocrlf false 2>$null
    Assert-LastExitCode 'Could not pin VibeUE line endings'
    & git -C $vibePath checkout --quiet --force HEAD 2>$null
    Assert-LastExitCode 'Could not normalize VibeUE line endings'
}
if ($dirty) {
    if (-not $PreserveExistingVibeUE) {
        throw "VibeUE checkout has local changes; use -PreserveExistingVibeUE only after verifying them: $vibePath"
    }
    $actualRef = (& git -C $vibePath rev-parse HEAD 2>$null).Trim()
    Assert-LastExitCode 'Could not read VibeUE revision'
    if ($vibeUEMergedTree) {
        $actualTree = (& git -C $vibePath rev-parse 'HEAD^{tree}' 2>$null).Trim()
        Assert-LastExitCode 'Could not read VibeUE tree revision'
        if ($actualTree -ne $vibeUEMergedTree -and -not (Test-VibeUEProfileApplied $vibePath $vibePatchPath $vibeProfile)) {
            throw "Dirty VibeUE tree is $actualTree and lacks the verified UEAgent profile; expected the merged baseline tree $vibeUEMergedTree. Refusing an ambiguous baseline."
        }
    } elseif ($actualRef -ne $VibeUERef) {
        throw "Dirty VibeUE revision is $actualRef; expected $VibeUERef. Refusing an ambiguous baseline."
    }
    if (-not (Test-VibeUEProfileApplied $vibePath $vibePatchPath $vibeProfile)) {
        throw 'Dirty VibeUE checkout does not contain the packaged UEAgent patch.'
    }
    Write-Warning "Preserving local VibeUE changes on baseline $VibeUERef."
} else {
    & git -C $vibePath fetch --quiet origin $vibeUEMergeBaseRef 2>$null
    Assert-LastExitCode "Could not fetch VibeUE merge base $vibeUEMergeBaseRef"
    & git -C $vibePath fetch --quiet origin $vibeUEFetchRef 2>$null
    Assert-LastExitCode "Could not fetch VibeUE $vibeUEFetchRef"
    # The packaged VibeUE patches were generated on the verified merge of two pinned public
    # commits, so a fresh checkout replays that exact merge; upstream branch movement cannot
    # shift the baseline because both parents are pinned SHAs.
    $mergeSource = if ($vibeUEFetchRef -match '^refs/heads/') {
        "origin/$($vibeUEFetchRef -replace '^refs/heads/', '')"
    } else { 'FETCH_HEAD' }
    & git -C $vibePath checkout --quiet --detach $vibeUEMergeBaseRef 2>$null
    Assert-LastExitCode "Could not checkout VibeUE merge base $vibeUEMergeBaseRef"
    & git -C $vibePath -c user.name=ueagent-bootstrap -c user.email=ueagent-bootstrap@localhost merge --quiet --no-ff --no-edit $mergeSource 2>$null
    Assert-LastExitCode "Could not reproduce the verified VibeUE merged baseline from $vibeUEFetchRef"
    $mergedTree = (& git -C $vibePath rev-parse 'HEAD^{tree}' 2>$null).Trim()
    Assert-LastExitCode 'Could not read VibeUE merged tree'
    if ($vibeUEMergedTree -and $mergedTree -ne $vibeUEMergedTree) {
        throw "Reproduced VibeUE merged tree is $mergedTree; expected the verified $vibeUEMergedTree."
    }
}
if (-not (Test-GitPatchesApplied $vibePath @($vibePatchPlan | ForEach-Object { $_.path }))) {
    foreach ($entry in $vibePatchPlan) {
        Ensure-GitPatchApplied $vibePath $entry.path $entry.relative
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
    throw 'The UEAgent patch plan requires a source-engine Git checkout.'
}
if (-not (Test-GitPatchesApplied $EngineRoot @($enginePatchPlan | ForEach-Object { $_.path }))) {
    foreach ($entry in $enginePatchPlan) {
        Ensure-GitPatchApplied $EngineRoot $entry.path $entry.relative
    }
}

$project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
if ($target) {
    Ensure-ExternalPlugins $project $projectRoot $target $ExternalPluginSourceRoot
}
$projectChanged = $false
$requiredPlugins = @('ModelContextProtocol', 'EditorToolset', 'VibeUE') + $profilePlugins
foreach ($plugin in $requiredPlugins) {
    if (-not @($project.Plugins | Where-Object { $_.Name -eq $plugin -and $_.Enabled }).Count) {
        Enable-UProjectPlugin $project $plugin
        $projectChanged = $true
    }
}
if ($projectChanged) {
    Write-Utf8NoBom $UProject (($project | ConvertTo-Json -Depth 50) + [Environment]::NewLine)
}

$uri = [Uri]$Endpoint
if ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    throw 'The UE MCP endpoint must remain unauthenticated loopback HTTP.'
}
$configDir = Join-Path $projectRoot 'Config'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
Set-UeAgentReliableConfig $projectRoot
if ($target) { Set-ProjectSettings $projectRoot $EngineRoot $target }
$settingsPath = Join-Path $configDir 'DefaultEditorPerProjectUserSettings.ini'
Set-McpSettingsFile $settingsPath $uri
# The per-user layer outranks the Default ini; a stale bAutoStartServer=False there silently
# disables the MCP server on every startup, so bootstrap repairs both layers.
$userSettingsDir = Join-Path $projectRoot 'Saved\Config\WindowsEditor'
New-Item -ItemType Directory -Path $userSettingsDir -Force | Out-Null
Set-McpSettingsFile (Join-Path $userSettingsDir 'EditorPerProjectUserSettings.ini') $uri

$mcpPath = Join-Path $projectRoot '.mcp.json'
$mcp = if (Test-Path -LiteralPath $mcpPath) { Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $mcp) { $mcp = [pscustomobject]@{} }
if (-not ($mcp.PSObject.Properties.Name -contains 'mcpServers')) {
    $mcp | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}
Set-JsonProperty $mcp.mcpServers 'ue-editor' ([pscustomobject]@{ type = 'streamable-http'; url = $Endpoint })
Write-Utf8NoBom $mcpPath (($mcp | ConvertTo-Json -Depth 20) + [Environment]::NewLine)

$routeDir = Join-Path $projectRoot 'Saved\UEAgent'
New-Item -ItemType Directory -Path $routeDir -Force | Out-Null
$routePath = Join-Path $routeDir 'route.json'
$externalPlugins = @(Get-EnabledExternalPluginInventory $project $projectRoot)
$route = [ordered]@{
    schema = 'ueagent-route-v1'
    transport = 'native-http'
    access = 'task-gated-write'
    ueAgentRoot = $ueAgentRoot
    uProject = $UProject
    engineRoot = $EngineRoot
    endpoint = $Endpoint
    reliableProtocol = $reliableProtocolVersion
    mutationTransport = $mutationTransport
    vibeUERef = $VibeUERef
    vibeUEMergedTree = $vibeUEMergedTree
    vibeUEProfile = $vibeProfile
}
foreach ($entry in $patchPlan) {
    if ($entry.routeField) { $route[$entry.routeField] = $entry.sha256 }
}
$route['externalPlugins'] = $externalPlugins
if ($target) {
    $route['targetProfile'] = [string]$target.project_name
    $targetPatchSha256 = [ordered]@{}
    foreach ($entry in @($patchPlan | Where-Object { -not $_.routeField })) {
        $targetPatchSha256[$entry.relative] = $entry.sha256
    }
    if ($targetPatchSha256.Count) { $route['targetPatchSha256'] = $targetPatchSha256 }
}
Write-Utf8NoBom $routePath (($route | ConvertTo-Json -Depth 10) + [Environment]::NewLine)
Set-UeAgentGate $projectRoot

if (-not $SkipBuild) {
    & $buildScript "$($projectName)Editor" Win64 Development "-Project=$UProject" -WaitMutex -FromMsBuild
    Assert-LastExitCode "$projectName editor build failed"
}
if ($Launch) {
    $launchEditor = if (Test-Path -LiteralPath $projectEditor) { $projectEditor } else { $editor }
    Start-Process -FilePath $launchEditor -ArgumentList "`"$UProject`""
}

Write-Host "UEAgent configured $projectName. Run doctor.ps1 with $routePath before live work." -ForegroundColor Green
