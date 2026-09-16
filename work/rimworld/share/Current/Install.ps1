param(
 [Parameter(Mandatory=$true)][string]$GamePath,
 [string]$UserDataPath = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios'),
 [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$bundleRoot=$PSScriptRoot
$gameRoot=[IO.Path]::GetFullPath($GamePath)
$dataRoot=[IO.Path]::GetFullPath($UserDataPath)
if(-not (Test-Path -LiteralPath (Join-Path $gameRoot 'RimWorldWin64.exe'))){throw 'GamePath must point to the installed RimWorld directory.'}
[xml]$profile=Get-Content -LiteralPath (Join-Path $bundleRoot 'Config/ModsConfig.xml') -Raw
$manifest=Import-Csv -LiteralPath (Join-Path $bundleRoot 'Manifests/mods.tsv') -Delimiter "`t"
$active=@($profile.ModsConfigData.activeMods.li)
if($active.Count -ne $manifest.Count){throw 'Mod manifest/list mismatch.'}
$workshopRoot=Join-Path (Split-Path (Split-Path $gameRoot -Parent) -Parent) 'workshop/content/294100'
$missing=New-Object 'System.Collections.Generic.List[string]'
foreach($m in $manifest){
 $aboutPath=switch($m.kind){
  'workshop' {Join-Path $workshopRoot ($m.workshopId+'/About/About.xml')}
  'local' {Join-Path $bundleRoot ('Mods/'+$m.localFolder+'/About/About.xml')}
  'official' {
   $found=$null
   foreach($folder in Get-ChildItem -LiteralPath (Join-Path $gameRoot 'Data') -Directory){
    $candidate=Join-Path $folder.FullName 'About/About.xml'
    if(Test-Path -LiteralPath $candidate){[xml]$a=Get-Content -LiteralPath $candidate -Raw;if($a.ModMetaData.packageId -ieq $m.packageId){$found=$candidate;break}}
   }
   $found
  }
 }
 if(-not $aboutPath -or -not (Test-Path -LiteralPath $aboutPath)){$missing.Add($m.name+' ['+$m.packageId+'] '+$m.workshopId);continue}
 [xml]$a=Get-Content -LiteralPath $aboutPath -Raw
 if($a.ModMetaData.packageId -ine $m.packageId){$missing.Add('Package mismatch: '+$m.packageId)}
}
if($missing.Count){throw ('Missing/download incomplete mods or DLC. Complete Steam downloads first:'+ [Environment]::NewLine+($missing -join [Environment]::NewLine))}
Write-Output ('Validated '+$active.Count+' mod entries, required DLC and installed Workshop folders.')
if($ValidateOnly){return}
if(Get-Process -Name RimWorldWin64 -ErrorAction SilentlyContinue){throw 'Save and fully exit RimWorld before installation.'}
$backupRoot=Join-Path $dataRoot ('TransferBackups/'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$modsRoot=Join-Path $gameRoot 'Mods'
New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null
foreach($m in $manifest | Where-Object kind -eq 'local'){
 $source=Join-Path $bundleRoot ('Mods/'+$m.localFolder)
 $target=[IO.Path]::GetFullPath((Join-Path $modsRoot $m.localFolder))
 if(-not $target.StartsWith($modsRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid local mod destination.'}
 if(Test-Path -LiteralPath $target){
  if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw ('Resolve linked mod folder before install: '+$target)}
  $modBackup=Join-Path $backupRoot ('Mods/'+$m.localFolder)
  New-Item -ItemType Directory -Force -Path (Split-Path $modBackup -Parent) | Out-Null
  Move-Item -LiteralPath $target -Destination $modBackup
 }
 Copy-Item -LiteralPath $source -Destination $target -Recurse
}
function Copy-ProfileFile([string]$Source,[string]$RelativePath){
 $target=[IO.Path]::GetFullPath((Join-Path $dataRoot $RelativePath))
 if(-not $target.StartsWith($dataRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid settings destination.'}
 if(Test-Path -LiteralPath $target){
  $old=Join-Path $backupRoot ('UserData/'+$RelativePath)
  New-Item -ItemType Directory -Force -Path (Split-Path $old -Parent) | Out-Null
  Copy-Item -LiteralPath $target -Destination $old
 }
 New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
 Copy-Item -LiteralPath $Source -Destination $target -Force
}
foreach($section in 'Settings/ModSettings','Settings/Game'){
 foreach($file in Get-ChildItem -LiteralPath (Join-Path $bundleRoot $section) -File){Copy-ProfileFile $file.FullName ('Config/'+$file.Name)}
}
$extrasRoot=Join-Path $bundleRoot 'Settings/UserData'
foreach($file in Get-ChildItem -LiteralPath $extrasRoot -Recurse -File){Copy-ProfileFile $file.FullName $file.FullName.Substring($extrasRoot.Length+1)}
# Activate the complete list last, after its local mods and parameters are in place.
Copy-ProfileFile (Join-Path $bundleRoot 'Config/ModsConfig.xml') 'Config/ModsConfig.xml'
Write-Output ('Installed complete profile. Backup: '+$backupRoot)
Write-Output 'Fill in your AI-provider API keys locally. Saves were not copied or modified.'
