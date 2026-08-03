[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [string]$VibeUERef = '271f48771d077179fb597dc285ab5b898c5e8038',
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp',
    [switch]$PreserveExistingVibeUE,
    [switch]$ApplyEngineNiagaraPatch,
    [switch]$ApplyMcpToolSearchPatches,
    [switch]$CheckOnly,
    [switch]$SkipBuild,
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
$VibeUERepository = 'https://github.com/kevinpbuckley/VibeUE.git'

function Resolve-RequiredPath($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "$Label not found: $Path" }
    (Resolve-Path -LiteralPath $Path).Path
}

function Assert-LastExitCode($Message) {
    if ($LASTEXITCODE -ne 0) { throw "$Message (exit $LASTEXITCODE)" }
}

function Test-GitPatchApplied($Repository, $Patch) {
    & git -C $Repository apply --reverse --check $Patch 2>$null
    $LASTEXITCODE -eq 0
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

function Set-UeAgentGate($ProjectRoot) {
    $agentsPath = Join-Path $ProjectRoot 'AGENTS.md'
    $start = '<!-- UEAGENT_GATE_START -->'
    $end = '<!-- UEAGENT_GATE_END -->'
    $block = @'
<!-- UEAGENT_GATE_START -->
## UEAgent live-Unreal gate

Before any work that reads live Unreal state or mutates UE:

1. Read `ueAgentRoot/skills/ue-mcp-workflows/HOTPATH.md`.
2. Read `Saved/UEAgent/route.json` and run `ueAgentRoot/scripts/compact_context.ps1` for the target.
3. If it returns `CACHE_READ`, do not call MCP. Otherwise run
   `ueAgentRoot/scripts/doctor.ps1 -RouteFile Saved/UEAgent/route.json`. For a live read, load only
   the relevant domain card; add the Skill and Core before mutation or save.
4. Follow the receipt; do not mutate or save unless its state and the task-specific rules permit it.

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
$vibePatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\vibeue-ueagent.patch') 'UEAgent VibeUE patch'
$engineNiagaraPatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-niagara-toolsets.patch') 'UEAgent Niagara Toolsets patch'
$mcpToolSearchV2PatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-mcp-tool-search-v2.patch') 'UEAgent MCP tool-search v2 patch'
$mcpToolSearchV3PatchPath = Resolve-RequiredPath (Join-Path $ueAgentRoot 'patches\ue58-mcp-tool-search-v3-call-view.patch') 'UEAgent MCP tool-search v3 patch'
$vibePatchSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $vibePatchPath).Hash
$engineNiagaraPatchSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $engineNiagaraPatchPath).Hash
$mcpToolSearchV2PatchSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $mcpToolSearchV2PatchPath).Hash
$mcpToolSearchV3PatchSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $mcpToolSearchV3PatchPath).Hash
$projectRoot = Split-Path $UProject -Parent
$projectName = [IO.Path]::GetFileNameWithoutExtension($UProject)
$buildScript = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$nativeMcp = Join-Path $EngineRoot 'Engine\Plugins\Experimental\ModelContextProtocol\ModelContextProtocol.uplugin'
$editorToolset = Join-Path $EngineRoot 'Engine\Plugins\Experimental\Toolsets\EditorToolset\EditorToolset.uplugin'
$buildVersionPath = Join-Path $EngineRoot 'Engine\Build\Build.version'
$vibePath = Join-Path $projectRoot 'Plugins\VibeUE'
$vibeManifest = Join-Path $vibePath 'VibeUE.uplugin'

foreach ($required in @($buildScript, $editor, $nativeMcp, $editorToolset, $buildVersionPath)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "UE 5.8 MCP prerequisite not found: $required" }
}
$buildVersion = Get-Content -Raw -LiteralPath $buildVersionPath | ConvertFrom-Json
if ($buildVersion.MajorVersion -ne 5 -or $buildVersion.MinorVersion -ne 8) {
    throw "UE 5.8 is required; found $($buildVersion.MajorVersion).$($buildVersion.MinorVersion)."
}

if ($CheckOnly) {
    $mcpPath = Join-Path $projectRoot '.mcp.json'
    $settingsPath = Join-Path $projectRoot 'Config\DefaultEditorPerProjectUserSettings.ini'
    $routePath = Join-Path $projectRoot 'Saved\UEAgent\route.json'
    $agentsPath = Join-Path $projectRoot 'AGENTS.md'
    foreach ($required in @($vibeManifest, $mcpPath, $settingsPath, $routePath, $agentsPath)) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Configured file not found: $required" }
    }
    $project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
    foreach ($plugin in @('ModelContextProtocol', 'EditorToolset', 'VibeUE')) {
        if (-not @($project.Plugins | Where-Object { $_.Name -eq $plugin -and $_.Enabled }).Count) {
            throw "Plugin is not enabled in $UProject`: $plugin"
        }
    }
    $actualRef = (& git -C $vibePath rev-parse HEAD).Trim()
    Assert-LastExitCode 'Could not read VibeUE revision'
    if ($actualRef -ne $VibeUERef) { throw "VibeUE revision is $actualRef; expected $VibeUERef" }
    if (-not (Test-GitPatchApplied $vibePath $vibePatchPath)) {
        throw 'The packaged UEAgent VibeUE patch is not applied.'
    }
    $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    if ($mcp.mcpServers.'ue-editor'.url -ne $Endpoint) { throw "MCP endpoint is not configured as $Endpoint." }
    $settings = Get-Content -Raw -LiteralPath $settingsPath
    foreach ($expected in @("ServerUrlPath=$(([Uri]$Endpoint).AbsolutePath)", "ServerPortNumber=$(([Uri]$Endpoint).Port)", 'bAutoStartServer=True', 'bEnableToolSearch=True')) {
        if ($settings -notmatch "(?m)^$([regex]::Escape($expected))`r?$") { throw "MCP project setting missing: $expected" }
    }
    $route = Get-Content -Raw -LiteralPath $routePath | ConvertFrom-Json
    if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported UEAgent route schema: $($route.schema)" }
    foreach ($pair in @(
        @('ueAgentRoot', $ueAgentRoot),
        @('uProject', $UProject),
        @('engineRoot', $EngineRoot),
        @('endpoint', $Endpoint),
        @('vibeUEPatchSha256', $vibePatchSha256)
    )) {
        if ([string]$route.($pair[0]) -ne [string]$pair[1]) {
            throw "UEAgent route mismatch for $($pair[0]): $($route.($pair[0]))"
        }
    }
    $agents = Get-Content -Raw -LiteralPath $agentsPath
    if ($agents -notmatch '(?m)^<!-- UEAGENT_GATE_START -->$') {
        throw "UEAgent gate is missing from $agentsPath"
    }
    if ($route.engineNiagaraPatchSha256) {
        if ([string]$route.engineNiagaraPatchSha256 -ne $engineNiagaraPatchSha256 -or
            -not (Test-GitPatchApplied $EngineRoot $engineNiagaraPatchPath)) {
            throw 'The routed UE 5.8 Niagara Toolsets patch does not match the installed engine.'
        }
    }
    if ($ApplyMcpToolSearchPatches -and (-not $route.mcpToolSearchV2PatchSha256 -or -not $route.mcpToolSearchV3PatchSha256)) {
        throw 'The compact MCP tool-search profile is requested but the route has no patch fingerprints.'
    }
    if ($route.mcpToolSearchV2PatchSha256 -or $route.mcpToolSearchV3PatchSha256) {
        if ([string]$route.mcpToolSearchV2PatchSha256 -ne $mcpToolSearchV2PatchSha256 -or
            [string]$route.mcpToolSearchV3PatchSha256 -ne $mcpToolSearchV3PatchSha256 -or
            -not (Test-GitPatchApplied $EngineRoot $mcpToolSearchV3PatchPath)) {
            throw 'The routed UE 5.8 MCP tool-search patches do not match the installed engine.'
        }
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
    if (-not (Test-GitPatchApplied $vibePath $vibePatchPath)) {
        throw 'Dirty VibeUE checkout does not contain the packaged UEAgent patch.'
    }
    Write-Warning "Preserving local VibeUE changes on baseline $VibeUERef."
} else {
    & git -C $vibePath fetch origin $VibeUERef
    Assert-LastExitCode "Could not fetch VibeUE $VibeUERef"
    & git -C $vibePath checkout --detach $VibeUERef
    Assert-LastExitCode "Could not checkout VibeUE $VibeUERef"
    Ensure-GitPatchApplied $vibePath $vibePatchPath 'UEAgent VibeUE patch'
}

$engineNiagaraPatchApplied = Test-GitPatchApplied $EngineRoot $engineNiagaraPatchPath
if ($ApplyEngineNiagaraPatch -and -not $engineNiagaraPatchApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the Niagara Toolsets extension requires a source-engine Git checkout.'
    }
    Ensure-GitPatchApplied $EngineRoot $engineNiagaraPatchPath 'UE 5.8 Niagara Toolsets patch'
    $engineNiagaraPatchApplied = $true
}

$mcpToolSearchV3Applied = Test-GitPatchApplied $EngineRoot $mcpToolSearchV3PatchPath
$mcpToolSearchV2Applied = Test-GitPatchApplied $EngineRoot $mcpToolSearchV2PatchPath
$mcpToolSearchPatchesApplied = $mcpToolSearchV3Applied
if ($ApplyMcpToolSearchPatches -and -not $mcpToolSearchPatchesApplied) {
    if (-not (Test-Path -LiteralPath (Join-Path $EngineRoot '.git'))) {
        throw 'Applying the MCP tool-search profile requires a source-engine Git checkout.'
    }
    if (-not $mcpToolSearchV2Applied) {
        Ensure-GitPatchApplied $EngineRoot $mcpToolSearchV2PatchPath 'UE 5.8 MCP tool-search v2 patch'
    }
    Ensure-GitPatchApplied $EngineRoot $mcpToolSearchV3PatchPath 'UE 5.8 MCP tool-search v3 patch'
    $mcpToolSearchPatchesApplied = $true
}

$project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
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
$route = [ordered]@{
    schema = 'ueagent-route-v1'
    ueAgentRoot = $ueAgentRoot
    uProject = $UProject
    engineRoot = $EngineRoot
    endpoint = $Endpoint
    vibeUERef = $VibeUERef
    vibeUEPatchSha256 = $vibePatchSha256
}
if ($engineNiagaraPatchApplied) {
    $route['engineNiagaraPatchSha256'] = $engineNiagaraPatchSha256
}
if ($mcpToolSearchPatchesApplied) {
    $route['mcpToolSearchV2PatchSha256'] = $mcpToolSearchV2PatchSha256
    $route['mcpToolSearchV3PatchSha256'] = $mcpToolSearchV3PatchSha256
}
Write-Utf8NoBom $routePath (($route | ConvertTo-Json -Depth 10) + [Environment]::NewLine)
Set-UeAgentGate $projectRoot

if (-not $SkipBuild) {
    & $buildScript "$($projectName)Editor" Win64 Development "-Project=$UProject" -WaitMutex -FromMsBuild
    Assert-LastExitCode "$projectName editor build failed"
}
if ($Launch) {
    Start-Process -FilePath $editor -ArgumentList "`"$UProject`""
}

Write-Host "UEAgent configured $projectName. Run doctor.ps1 with $routePath before live work." -ForegroundColor Green
