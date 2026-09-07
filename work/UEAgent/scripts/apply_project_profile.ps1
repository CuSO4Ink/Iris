[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UProject,

    [Parameter(Mandatory)]
    [string]$EngineRoot,

    [Parameter(Mandatory)]
    [string]$ProjectProfile,

    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ueagent_common.ps1')

function Get-ProjectProfile($StackManifest, $Name) {
    $entry = $StackManifest.project_profiles.$Name
    if ($null -eq $entry) {
        $declared = @($StackManifest.project_profiles.PSObject.Properties | ForEach-Object { $_.Name })
        $available = if ($declared.Count) { $declared -join ', ' } else { 'none' }
        throw "Unknown UEAgent project profile: $Name. Declared project profiles: $available."
    }
    return $entry
}

function Get-ProjectProfileLabel($Entry, $Name) {
    $projectName = [string]$Entry.project_name
    if ($projectName) { return "Project '$projectName' (profile '$Name')" }
    return "Project profile '$Name'"
}

function Assert-ProjectSettings($ProjectRoot, $EngineRoot, $ProjectSettings, $Label) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $knownSections = Get-EngineIniSectionNames $EngineRoot
    foreach ($section in $ProjectSettings.PSObject.Properties) {
        Assert-KnownIniSection $knownSections $section.Name $Label
        $expected = @($section.Value.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" })
        Assert-IniSettings $path $section.Name $expected
    }
}

function Set-ProjectSettings($ProjectRoot, $EngineRoot, $ProjectSettings, $Label) {
    $path = Join-Path $ProjectRoot 'Config\DefaultEngine.ini'
    $knownSections = Get-EngineIniSectionNames $EngineRoot
    foreach ($section in $ProjectSettings.PSObject.Properties) {
        Assert-KnownIniSection $knownSections $section.Name $Label
        $settings = [ordered]@{}
        foreach ($setting in $section.Value.PSObject.Properties) {
            $settings[[string]$setting.Name] = [string]$setting.Value
        }
        Set-IniSectionSettings $path $section.Name $settings
    }
    return $path
}

$UProject = Resolve-RequiredPath $UProject 'UProject'
$EngineRoot = Resolve-RequiredPath $EngineRoot 'Engine root'
$projectRoot = Split-Path $UProject -Parent
$projectName = [IO.Path]::GetFileNameWithoutExtension($UProject)

$stackManifest = Read-UeAgentStackManifest (Split-Path $PSScriptRoot -Parent)
$profileEntry = Get-ProjectProfile $stackManifest $ProjectProfile
$label = Get-ProjectProfileLabel $profileEntry $ProjectProfile
$projectSettings = $profileEntry.project_settings

if ($null -eq $projectSettings) {
    Write-Host "$label declares no project settings; nothing to apply." -ForegroundColor Green
    exit 0
}

if ($CheckOnly) {
    Assert-ProjectSettings $projectRoot $EngineRoot $projectSettings $label
    Write-Host "Project settings check passed for $projectName." -ForegroundColor Green
    exit 0
}

$iniPath = Set-ProjectSettings $projectRoot $EngineRoot $projectSettings $label
Assert-ProjectSettings $projectRoot $EngineRoot $projectSettings $label
Write-Host "Project settings applied for $projectName." -ForegroundColor Green
Write-Host "Project ini: $iniPath"
Write-Host "Project plugins and route binding are handled separately; see SETUP.md."
