[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [string]$VibeUERef = '271f48771d077179fb597dc285ab5b898c5e8038',
    [string]$Endpoint = 'http://127.0.0.1:8000/mcp',
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

$UProject = Resolve-RequiredPath $UProject 'UProject'
$EngineRoot = Resolve-RequiredPath $EngineRoot 'Engine root'
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
    foreach ($required in @($vibeManifest, $mcpPath, $settingsPath)) {
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
    $mcp = Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json
    if ($mcp.mcpServers.'ue-editor'.url -ne $Endpoint) { throw "MCP endpoint is not configured as $Endpoint." }
    $settings = Get-Content -Raw -LiteralPath $settingsPath
    foreach ($expected in @("ServerUrlPath=$(([Uri]$Endpoint).AbsolutePath)", "ServerPortNumber=$(([Uri]$Endpoint).Port)", 'bAutoStartServer=True', 'bEnableToolSearch=True')) {
        if ($settings -notmatch "(?m)^$([regex]::Escape($expected))`r?$") { throw "MCP project setting missing: $expected" }
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
if ($dirty) { throw "VibeUE checkout has local changes; refusing to replace them: $vibePath" }
& git -C $vibePath fetch origin $VibeUERef
Assert-LastExitCode "Could not fetch VibeUE $VibeUERef"
& git -C $vibePath checkout --detach $VibeUERef
Assert-LastExitCode "Could not checkout VibeUE $VibeUERef"

$project = Get-Content -Raw -LiteralPath $UProject | ConvertFrom-Json
foreach ($plugin in @('ModelContextProtocol', 'EditorToolset', 'VibeUE')) { Enable-UProjectPlugin $project $plugin }
[IO.File]::WriteAllText($UProject, ($project | ConvertTo-Json -Depth 50) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

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
[IO.File]::WriteAllText($settingsPath, $newSettings.TrimStart(), [Text.UTF8Encoding]::new($false))

$mcpPath = Join-Path $projectRoot '.mcp.json'
$mcp = if (Test-Path -LiteralPath $mcpPath) { Get-Content -Raw -LiteralPath $mcpPath | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not ($mcp.PSObject.Properties.Name -contains 'mcpServers')) {
    $mcp | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}
Set-JsonProperty $mcp.mcpServers 'ue-editor' ([pscustomobject]@{ type = 'streamable-http'; url = $Endpoint })
[IO.File]::WriteAllText($mcpPath, ($mcp | ConvertTo-Json -Depth 20) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

if (-not $SkipBuild) {
    & $buildScript "$($projectName)Editor" Win64 Development "-Project=$UProject" -WaitMutex -FromMsBuild
    Assert-LastExitCode "$projectName editor build failed"
}
if ($Launch) {
    Start-Process -FilePath $editor -ArgumentList "`"$UProject`""
}

Write-Host "UEAgent configured $projectName. Run this script with -CheckOnly, then mcp_gateway.ps1 -Action ping." -ForegroundColor Green
