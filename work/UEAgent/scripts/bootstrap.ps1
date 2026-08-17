[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [string]$VibeUERef,
    [string]$Endpoint,
    [switch]$PreserveExistingVibeUE,
    [switch]$ApplyAbyssProfile,
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

function Ensure-GitPatchApplied($Repository, $Patch, $Label) {
    if (Test-GitPatchApplied $Repository $Patch) { return }
    & git -C $Repository apply --check $Patch
    Assert-LastExitCode "$Label does not apply cleanly"
    & git -C $Repository apply $Patch
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
    $existing = if (Test-Path -LiteralPath $path) { Get-Content -Raw -LiteralPath $path } else { '' }
    $pattern = '(?ms)^\[UEAgent\.Reliable\]\r?\n.*?(?=^\[|\z)'
    $updated = if ($existing -match $pattern) {
        [Regex]::Replace($existing, $pattern, $block.Trim() + [Environment]::NewLine)
    } else {
        $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine +
            $block.Trim() + [Environment]::NewLine
    }
    Write-Utf8NoBom $path $updated.TrimStart()
}

function Assert-AbyssProjectSettings($ProjectRoot) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $body = Get-IniSectionBody $path 'SystemSettings'
    if ($null -eq $body -or $body -notmatch '(?m)^r\.VolumetricCloud\.ConservativeDensity\.SDFMaxStep=32\r?$') {
        throw "Abyss volumetric-cloud setting is missing: $path"
    }
}

function Set-AbyssProjectSettings($ProjectRoot) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $line = 'r.VolumetricCloud.ConservativeDensity.SDFMaxStep=32'
    $existing = if (Test-Path -LiteralPath $path) { Get-Content -Raw -LiteralPath $path } else { '' }
    $linePattern = '(?m)^r\.VolumetricCloud\.ConservativeDensity\.SDFMaxStep=.*\r?$'
    if ($existing -match $linePattern) {
        $updated = [Regex]::Replace($existing, $linePattern, $line)
    } elseif ($existing -match '(?m)^\[SystemSettings\]\r?$') {
        $updated = [Regex]::Replace($existing, '(?m)^\[SystemSettings\]\r?$', "[SystemSettings]$([Environment]::NewLine)$line")
    } else {
        $updated = $existing.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine +
            "[SystemSettings]$([Environment]::NewLine)$line$([Environment]::NewLine)"
    }
    Write-Utf8NoBom $path $updated.TrimStart()
}

function Get-AbyssProfile($Manifest) {
    $profile = $Manifest.profiles.abyss
    if ($null -eq $profile -or [string]$profile.project_name -ne 'Abyss') {
        throw 'UEAgent stack manifest is missing the verified Abyss profile.'
    }
    return $profile
}

function Assert-AbyssExternalPlugins($Project, $ProjectRoot, $Manifest) {
    $profile = Get-AbyssProfile $Manifest
    $expected = @($profile.external_plugins)
    $actual = @(Get-EnabledExternalPluginInventory $Project $ProjectRoot)
    if ((ConvertTo-Json -InputObject $actual -Depth 5 -Compress) -ne
        (ConvertTo-Json -InputObject $expected -Depth 5 -Compress)) {
        throw 'Abyss external plugins are missing or differ from the pinned bootstrap inventory.'
    }
    return $actual
}

function Ensure-AbyssExternalPlugins($Project, $ProjectRoot, $Manifest, $SourceRoot) {
    $profile = Get-AbyssProfile $Manifest
    $expected = @($profile.external_plugins)
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
    Assert-AbyssExternalPlugins $Project $ProjectRoot $Manifest | Out-Null
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

Offline source/cache/config/log analysis may proceed, but must not claim live editor state.
<!-- UEAGENT_GATE_END -->
'@
    $existing = if (Test-Path -LiteralPath $agentsPath) {
        Get-Content -Raw -LiteralPath $agentsPath
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
if (-not $PSBoundParameters.ContainsKey('Endpoint')) { $Endpoint = [string]$stackManifest.runtime.endpoint }
$projectRoot = Split-Path $UProject -Parent
$projectName = [IO.Path]::GetFileNameWithoutExtension($UProject)
if ($ApplyAbyssProfile) {
    if ($projectName -ne 'Abyss') { throw "-ApplyAbyssProfile requires Abyss.uproject; found $projectName." }
    $ApplyNiagaraAuthoringProfile = $true
    $ApplyEngineNiagaraPatch = $true
    $ApplyMcpToolSearchPatch = $true
}
if ($ApplyNiagaraAuthoringProfile) { $ApplyEngineNiagaraPatch = $true }
$reliableProtocolVersion = [string]$stackManifest.runtime.reliable_protocol
$mutationTransport = [string]$stackManifest.runtime.mutation_transport

$coreVibePatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-ueagent.patch') 'UEAgent VibeUE patch'
$authoringVibePatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\niagara-mcp-authoring\vibeue\vibeue-ueagent-authoring.patch') 'UEAgent Niagara authoring VibeUE patch'
$vibePerformancePatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-performance-monitor.patch') 'VibeUE performance monitor patch'
$vibeShutdownGuardPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-mcp-shutdown-guard.patch') 'VibeUE MCP shutdown guard patch'
$vibeReliablePatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-reliable-kernel.patch') 'VibeUE reliable execution kernel patch'
$vibeMaterialDiagnosticDocPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-material-diagnostic-doc.patch') 'VibeUE material diagnostic patch'
$vibeAbyssCompatibilityPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-abyss-compatibility.patch') 'VibeUE Abyss compatibility patch'
$engineMcpAuthorizationPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-mcp-authorization-gate.patch') 'UE 5.8 MCP authorization gate patch'
$engineNiagaraPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-niagara-toolsets.patch') 'UEAgent Niagara Toolsets patch'
$engineNiagaraAuthoringPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\niagara-mcp-authoring\ue-5.8\niagaraeditor-export-authoring-apis-current.patch') 'UEAgent Niagara authoring engine patch'
$mcpToolSearchPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-mcp-tool-search.patch') 'UEAgent MCP tool-search patch'
$abyssEngineExtensionsPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-abyss-engine-extensions.patch') 'Abyss engine extensions patch'
$vibeProfile = if ($ApplyNiagaraAuthoringProfile) { 'niagara-authoring' } else { 'base' }
$vibePatchPath = if ($ApplyNiagaraAuthoringProfile) { $authoringVibePatchPath } else { $coreVibePatchPath }
$vibePatchManifestPath = if ($ApplyNiagaraAuthoringProfile) {
    'patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch'
} else { 'patches/vibeue-ueagent.patch' }
$vibePatchSha256 = [string]$stackManifest.patches.($vibePatchManifestPath)
$vibePerformancePatchSha256 = [string]$stackManifest.patches.'patches/vibeue-performance-monitor.patch'
$vibeShutdownGuardPatchSha256 = [string]$stackManifest.patches.'patches/vibeue-mcp-shutdown-guard.patch'
$vibeReliablePatchSha256 = [string]$stackManifest.patches.'patches/vibeue-reliable-kernel.patch'
$vibeMaterialDiagnosticDocPatchSha256 = [string]$stackManifest.patches.'patches/vibeue-material-diagnostic-doc.patch'
$vibeAbyssCompatibilityPatchSha256 = [string]$stackManifest.patches.'patches/vibeue-abyss-compatibility.patch'
$engineMcpAuthorizationPatchSha256 = [string]$stackManifest.patches.'patches/ue58-mcp-authorization-gate.patch'
$engineNiagaraPatchSha256 = [string]$stackManifest.patches.'patches/ue58-niagara-toolsets.patch'
$engineNiagaraAuthoringPatchSha256 = [string]$stackManifest.patches.'patches/niagara-mcp-authoring/ue-5.8/niagaraeditor-export-authoring-apis-current.patch'
$mcpToolSearchPatchSha256 = [string]$stackManifest.patches.'patches/ue58-mcp-tool-search.patch'
$abyssEngineExtensionsPatchSha256 = [string]$stackManifest.patches.'patches/ue58-abyss-engine-extensions.patch'
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
$engineNiagaraAuthoringPatchApplied = Test-GitPatchApplied $EngineRoot $engineNiagaraAuthoringPatchPath
if (-not $CheckOnly -and -not $ApplyNiagaraAuthoringProfile -and $engineNiagaraAuthoringPatchApplied) {
    throw 'The engine has the Niagara authoring patch; rerun with -ApplyNiagaraAuthoringProfile so VibeUE uses the matching composite.'
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
    foreach ($plugin in @('ModelContextProtocol', 'EditorToolset', 'VibeUE')) {
        if (-not @($project.Plugins | Where-Object { $_.Name -eq $plugin -and $_.Enabled }).Count) {
            throw "Plugin is not enabled in $UProject`: $plugin"
        }
    }
    $route = Get-Content -Raw -LiteralPath $routePath | ConvertFrom-Json
    if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported UEAgent route schema: $($route.schema)" }
    $externalPlugins = @(Get-EnabledExternalPluginInventory $project $projectRoot)
    if ($route.environmentProfile -eq 'abyss-full') {
        Assert-AbyssExternalPlugins $project $projectRoot $stackManifest | Out-Null
    } elseif ((ConvertTo-Json -InputObject $externalPlugins -Depth 5 -Compress) -ne
        (ConvertTo-Json -InputObject @($route.externalPlugins) -Depth 5 -Compress)) {
        throw 'Enabled external plugins differ from the routed bootstrap inventory; rerun bootstrap.'
    }
    if ($ApplyAbyssProfile -and $route.environmentProfile -ne 'abyss-full') {
        throw 'The route was not bootstrapped with -ApplyAbyssProfile.'
    }
    if (-not $PSBoundParameters.ContainsKey('Endpoint')) { $Endpoint = [string]$route.endpoint }
    $actualRef = (& git -C $vibePath rev-parse HEAD).Trim()
    Assert-LastExitCode 'Could not read VibeUE revision'
    if ($actualRef -ne $VibeUERef) { throw "VibeUE revision is $actualRef; expected $VibeUERef" }
    $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    if ($mcp.mcpServers.'ue-editor'.url -ne $Endpoint) { throw "MCP endpoint is not configured as $Endpoint." }
    $settings = Get-Content -Raw -LiteralPath $settingsPath
    foreach ($expected in @("ServerUrlPath=$(([Uri]$Endpoint).AbsolutePath)", "ServerPortNumber=$(([Uri]$Endpoint).Port)", 'bAutoStartServer=True', 'bEnableToolSearch=True')) {
        if ($settings -notmatch "(?m)^$([regex]::Escape($expected))`r?$") { throw "MCP project setting missing: $expected" }
    }
    $routeVibeProfile = if ($route.PSObject.Properties.Name -contains 'vibeUEProfile') {
        [string]$route.vibeUEProfile
    } else {
        'base'
    }
    if ($routeVibeProfile -notin @('base', 'niagara-authoring')) {
        throw "Unsupported UEAgent VibeUE profile: $routeVibeProfile"
    }
    if ($ApplyNiagaraAuthoringProfile -and $routeVibeProfile -ne 'niagara-authoring') {
        throw 'The route was not bootstrapped with -ApplyNiagaraAuthoringProfile.'
    }
    $expectedVibePatchPath = if ($routeVibeProfile -eq 'niagara-authoring') {
        $authoringVibePatchPath
    } else {
        $coreVibePatchPath
    }
    $expectedVibePatchSha256 = if ($routeVibeProfile -eq 'niagara-authoring') {
        [string]$stackManifest.patches.'patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch'
    } else { [string]$stackManifest.patches.'patches/vibeue-ueagent.patch' }
    foreach ($pair in @(
        @('ueAgentRoot', $ueAgentRoot),
        @('uProject', $UProject),
        @('engineRoot', $EngineRoot),
        @('endpoint', $Endpoint),
        @('transport', 'native-http'),
        @('access', 'task-gated-write'),
        @('reliableProtocol', $reliableProtocolVersion),
        @('mutationTransport', $mutationTransport),
        @('vibeUEPatchSha256', $expectedVibePatchSha256),
        @('vibeUEPerformancePatchSha256', $vibePerformancePatchSha256),
        @('vibeUEMcpShutdownGuardPatchSha256', $vibeShutdownGuardPatchSha256),
        @('vibeUEReliablePatchSha256', $vibeReliablePatchSha256),
        @('vibeUEMaterialDiagnosticDocPatchSha256', $vibeMaterialDiagnosticDocPatchSha256),
        @('engineMcpAuthorizationPatchSha256', $engineMcpAuthorizationPatchSha256)
    )) {
        if ([string]$route.($pair[0]) -ne [string]$pair[1]) {
            throw "UEAgent route mismatch for $($pair[0]): $($route.($pair[0]))"
        }
    }
    $agents = Get-Content -Raw -LiteralPath $agentsPath
    if ($agents -notmatch '(?m)^<!-- UEAGENT_GATE_START -->\r?$') {
        throw "UEAgent gate is missing from $agentsPath"
    }
    $vibeRuntimeBatchApplied = Test-GitPatchesApplied $vibePath @(
        $vibePerformancePatchPath, $vibeShutdownGuardPatchPath, $vibeReliablePatchPath
    )
    $engineBatchPatches = @($engineMcpAuthorizationPatchPath)
    if ($route.engineNiagaraPatchSha256) { $engineBatchPatches += $engineNiagaraPatchPath }
    if ($routeVibeProfile -eq 'niagara-authoring') { $engineBatchPatches += $engineNiagaraAuthoringPatchPath }
    if ($route.mcpToolSearchPatchSha256) { $engineBatchPatches += $mcpToolSearchPatchPath }
    if ($route.environmentProfile -eq 'abyss-full') { $engineBatchPatches += $abyssEngineExtensionsPatchPath }
    $engineBatchApplied = Test-GitPatchesApplied $EngineRoot $engineBatchPatches
    if (-not (Test-VibeUEProfileApplied $vibePath $expectedVibePatchPath $routeVibeProfile)) {
        throw "The routed UEAgent VibeUE profile is not applied: $routeVibeProfile"
    }
    if (-not $vibeRuntimeBatchApplied -and -not (Test-GitPatchApplied $vibePath $vibePerformancePatchPath)) {
        throw 'The routed VibeUE performance monitor patch is not applied.'
    }
    if (-not $vibeRuntimeBatchApplied -and -not (Test-GitPatchApplied $vibePath $vibeShutdownGuardPatchPath)) {
        throw 'The routed VibeUE MCP shutdown guard patch is not applied.'
    }
    if (-not $vibeRuntimeBatchApplied -and -not (Test-GitPatchApplied $vibePath $vibeReliablePatchPath)) {
        throw 'The routed VibeUE reliable execution kernel patch is not applied.'
    }
    if (-not (Test-GitPatchApplied $vibePath $vibeMaterialDiagnosticDocPatchPath)) {
        throw 'The routed VibeUE material diagnostic patch is not applied.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git')) -or
        (-not $engineBatchApplied -and -not (Test-GitPatchApplied $EngineRoot $engineMcpAuthorizationPatchPath))) {
        throw 'The routed UE 5.8 MCP authorization gate patch is not applied.'
    }
    Assert-UeAgentReliableConfig $projectRoot
    if ($routeVibeProfile -eq 'niagara-authoring') {
        if (-not $route.engineNiagaraAuthoringPatchSha256 -or
            [string]$route.engineNiagaraAuthoringPatchSha256 -ne $engineNiagaraAuthoringPatchSha256 -or
            (-not $engineBatchApplied -and -not (Test-GitPatchApplied $EngineRoot $engineNiagaraAuthoringPatchPath))) {
            throw 'The routed UE 5.8 Niagara authoring profile does not match the installed engine.'
        }
    }
    if ($route.engineNiagaraPatchSha256) {
        if ([string]$route.engineNiagaraPatchSha256 -ne $engineNiagaraPatchSha256 -or
            (-not $engineBatchApplied -and -not (Test-GitPatchApplied $EngineRoot $engineNiagaraPatchPath))) {
            throw 'The routed UE 5.8 Niagara Toolsets patch does not match the installed engine.'
        }
    }
    if ($ApplyMcpToolSearchPatch -and -not $route.mcpToolSearchPatchSha256) {
        throw 'The compact MCP tool-search profile is requested but the route has no patch fingerprint.'
    }
    if ($route.mcpToolSearchPatchSha256) {
        if ([string]$route.mcpToolSearchPatchSha256 -ne $mcpToolSearchPatchSha256 -or
            (-not $engineBatchApplied -and -not (Test-GitPatchApplied $EngineRoot $mcpToolSearchPatchPath))) {
            throw 'The routed UE 5.8 MCP tool-search patch does not match the installed engine.'
        }
    }
    if ($route.environmentProfile -eq 'abyss-full') {
        if ([string]$route.vibeUEAbyssCompatibilityPatchSha256 -ne $vibeAbyssCompatibilityPatchSha256 -or
            -not (Test-GitPatchApplied $vibePath $vibeAbyssCompatibilityPatchPath)) {
            throw 'The routed Abyss VibeUE compatibility patch is not applied.'
        }
        if ([string]$route.engineAbyssExtensionsPatchSha256 -ne $abyssEngineExtensionsPatchSha256 -or
            (-not $engineBatchApplied -and -not (Test-GitPatchApplied $EngineRoot $abyssEngineExtensionsPatchPath))) {
            throw 'The routed Abyss engine extensions do not match the installed engine.'
        }
        Assert-AbyssProjectSettings $projectRoot
    }
    Write-Host "UEAgent static check passed for $projectName." -ForegroundColor Green
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to install VibeUE.' }
if (-not (Test-Path -LiteralPath $vibePath)) {
    New-Item -ItemType Directory -Path (Split-Path $vibePath -Parent) -Force | Out-Null
    & git clone $VibeUERepository $vibePath
    Assert-LastExitCode 'VibeUE clone failed'
}
if (-not (Test-Path -LiteralPath (Join-Path $vibePath '.git'))) { throw "Existing VibeUE directory is not a Git checkout: $vibePath" }
$origin = (& git -C $vibePath remote get-url origin).Trim()
Assert-LastExitCode 'Could not read VibeUE origin'
if ($origin -notin @($VibeUERepository, 'git@github.com:kevinpbuckley/VibeUE.git')) {
    throw "Unexpected VibeUE origin: $origin"
}
$dirty = & git -C $vibePath status --porcelain
Assert-LastExitCode 'Could not inspect VibeUE checkout'
if ($dirty) {
    if (-not $PreserveExistingVibeUE) {
        throw "VibeUE checkout has local changes; use -PreserveExistingVibeUE only after verifying them: $vibePath"
    }
    $actualRef = (& git -C $vibePath rev-parse HEAD).Trim()
    Assert-LastExitCode 'Could not read VibeUE revision'
    if ($actualRef -ne $VibeUERef) {
        throw "Dirty VibeUE revision is $actualRef; expected $VibeUERef. Refusing an ambiguous baseline."
    }
    if (-not (Test-VibeUEProfileApplied $vibePath $vibePatchPath $vibeProfile)) {
        throw 'Dirty VibeUE checkout does not contain the packaged UEAgent patch.'
    }
    Write-Warning "Preserving local VibeUE changes on baseline $VibeUERef."
} else {
    & git -C $vibePath fetch origin $vibeUEFetchRef
    Assert-LastExitCode "Could not fetch VibeUE $vibeUEFetchRef"
    & git -C $vibePath checkout --detach $VibeUERef
    Assert-LastExitCode "Could not checkout VibeUE $VibeUERef"
    Ensure-GitPatchApplied $vibePath $vibePatchPath 'UEAgent VibeUE patch'
}
$vibeRuntimePatches = @($vibePerformancePatchPath, $vibeShutdownGuardPatchPath, $vibeReliablePatchPath)
if (-not (Test-GitPatchesApplied $vibePath $vibeRuntimePatches)) {
    Ensure-GitPatchApplied $vibePath $vibePerformancePatchPath 'VibeUE performance monitor patch'
    Ensure-GitPatchApplied $vibePath $vibeShutdownGuardPatchPath 'VibeUE MCP shutdown guard patch'
    Ensure-GitPatchApplied $vibePath $vibeReliablePatchPath 'VibeUE reliable execution kernel patch'
}
Ensure-GitPatchApplied $vibePath $vibeMaterialDiagnosticDocPatchPath 'VibeUE material diagnostic patch'
if ($ApplyAbyssProfile) {
    Ensure-GitPatchApplied $vibePath $vibeAbyssCompatibilityPatchPath 'VibeUE Abyss compatibility patch'
}

if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
    throw 'The reliable VibeUE profile requires a source-engine Git checkout for the MCP authorization gate.'
}
Ensure-GitPatchApplied $EngineRoot $engineMcpAuthorizationPatchPath 'UE 5.8 MCP authorization gate patch'

$engineNiagaraPatchApplied = Test-GitPatchApplied $EngineRoot $engineNiagaraPatchPath
if ($ApplyEngineNiagaraPatch -and -not $engineNiagaraPatchApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the Niagara Toolsets extension requires a source-engine Git checkout.'
    }
    Ensure-GitPatchApplied $EngineRoot $engineNiagaraPatchPath 'UE 5.8 Niagara Toolsets patch'
    $engineNiagaraPatchApplied = $true
}

if ($ApplyNiagaraAuthoringProfile -and -not $engineNiagaraAuthoringPatchApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the Niagara authoring profile requires a source-engine Git checkout.'
    }
    Ensure-GitPatchApplied $EngineRoot $engineNiagaraAuthoringPatchPath 'UE 5.8 Niagara authoring engine patch'
    $engineNiagaraAuthoringPatchApplied = $true
}

$mcpToolSearchPatchApplied = Test-GitPatchApplied $EngineRoot $mcpToolSearchPatchPath
if ($ApplyMcpToolSearchPatch -and -not $mcpToolSearchPatchApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the MCP tool-search profile requires a source-engine Git checkout.'
    }
    Ensure-GitPatchApplied $EngineRoot $mcpToolSearchPatchPath 'UE 5.8 MCP tool-search patch'
    $mcpToolSearchPatchApplied = $true
}
$abyssEngineExtensionsPatchApplied = Test-GitPatchApplied $EngineRoot $abyssEngineExtensionsPatchPath
if ($ApplyAbyssProfile -and -not $abyssEngineExtensionsPatchApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the Abyss engine extensions requires a source-engine Git checkout.'
    }
    Ensure-GitPatchApplied $EngineRoot $abyssEngineExtensionsPatchPath 'Abyss engine extensions patch'
    $abyssEngineExtensionsPatchApplied = $true
}

$project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
if ($ApplyAbyssProfile) {
    Ensure-AbyssExternalPlugins $project $projectRoot $stackManifest $ExternalPluginSourceRoot
}
$projectChanged = $false
foreach ($plugin in @('ModelContextProtocol', 'EditorToolset', 'VibeUE')) {
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
if ($ApplyAbyssProfile) { Set-AbyssProjectSettings $projectRoot }
$settingsPath = Join-Path $configDir 'DefaultEditorPerProjectUserSettings.ini'
$settings = @"
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=$($uri.AbsolutePath)
ServerPortNumber=$($uri.Port)
bAutoStartServer=True
bEnableToolSearch=True
"@
$existingSettings = if (Test-Path -LiteralPath $settingsPath) { Get-Content -Raw -LiteralPath $settingsPath } else { '' }
$sectionPattern = '(?ms)^\[/Script/ModelContextProtocolEngine\.ModelContextProtocolSettings\]\r?\n.*?(?=^\[|\z)'
$newSettings = if ($existingSettings -match $sectionPattern) {
    [regex]::Replace($existingSettings, $sectionPattern, $settings.Trim() + [Environment]::NewLine)
} else {
    $existingSettings.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $settings.Trim() + [Environment]::NewLine
}
Write-Utf8NoBom $settingsPath $newSettings.TrimStart()

$mcpPath = Join-Path $projectRoot '.mcp.json'
$mcp = if (Test-Path -LiteralPath $mcpPath) { Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json } else { [pscustomobject]@{} }
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
    vibeUEProfile = $vibeProfile
    vibeUEPatchSha256 = $vibePatchSha256
    vibeUEPerformancePatchSha256 = $vibePerformancePatchSha256
    vibeUEMcpShutdownGuardPatchSha256 = $vibeShutdownGuardPatchSha256
    vibeUEReliablePatchSha256 = $vibeReliablePatchSha256
    vibeUEMaterialDiagnosticDocPatchSha256 = $vibeMaterialDiagnosticDocPatchSha256
    engineMcpAuthorizationPatchSha256 = $engineMcpAuthorizationPatchSha256
    externalPlugins = $externalPlugins
}
if ($engineNiagaraPatchApplied) {
    $route['engineNiagaraPatchSha256'] = $engineNiagaraPatchSha256
}
if ($engineNiagaraAuthoringPatchApplied) {
    $route['engineNiagaraAuthoringPatchSha256'] = $engineNiagaraAuthoringPatchSha256
}
if ($mcpToolSearchPatchApplied) {
    $route['mcpToolSearchPatchSha256'] = $mcpToolSearchPatchSha256
}
if ($ApplyAbyssProfile) {
    $route['environmentProfile'] = 'abyss-full'
    $route['vibeUEAbyssCompatibilityPatchSha256'] = $vibeAbyssCompatibilityPatchSha256
    $route['engineAbyssExtensionsPatchSha256'] = $abyssEngineExtensionsPatchSha256
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
