[CmdletBinding()]
param([string]$VibeUEPath,[string]$EngineRoot,[switch]$RequireAbyssProfile)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$manifest=Get-Content -Raw (Join-Path $root 'STACK-MANIFEST.json') | ConvertFrom-Json
if($manifest.runtime.reliable_protocol -ne '3.0.0'){throw 'Package does not describe protocol 3.0.'}
$patches=@($manifest.profiles.PSObject.Properties | ForEach-Object {$_.Value.apply} | Sort-Object -Unique)
foreach($relative in $patches){
    $path=Join-Path $root $relative
    if(-not (Test-Path -LiteralPath $path)){throw "Missing patch: $relative"}
    & git apply --numstat $path | Out-Null
    if($LASTEXITCODE -ne 0){throw "Unparseable patch: $relative"}
}
foreach($script in Get-ChildItem (Join-Path $root 'scripts') -Filter '*.ps1'){
    $tokens=$null;$errors=$null
    [Management.Automation.Language.Parser]::ParseFile($script.FullName,[ref]$tokens,[ref]$errors) | Out-Null
    if($errors.Count){throw "$($script.Name): $($errors.Message -join '; ')"}
}
& (Join-Path $PSScriptRoot 'test_task_gateway.ps1') | Out-Null
if($EngineRoot){
    & (Join-Path $root 'scripts/install_engine.ps1') -EngineRoot $EngineRoot -Profile niagara-authoring -CheckOnly | Out-Null
}
$fixture=Join-Path ([IO.Path]::GetFullPath((Join-Path $root '../../tmp/UEAgent'))) ('cache-fixture-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$source=Join-Path $fixture 'Probe.uasset';$sidecar=$source+'.ai.md'
[IO.File]::WriteAllText($source,'saved',[Text.UTF8Encoding]::new($false))
$stamp=(Get-Item $source).LastWriteTimeUtc.ToString('o')
[IO.File]::WriteAllText($sidecar,('```yaml'+"`nformat: vibeue-material-cache-v2`nsrc: /Game/Probe`nfile: $source`nmtime: $stamp`nsize: 5`n"+'```'+"`n`n## Logic`nOut.BaseColor = Const(1)`n"),[Text.UTF8Encoding]::new($false))
$cache=Join-Path $root 'scripts/reflect_cache.ps1'
$fresh=(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $cache -Sidecar $sidecar -View summary) | ConvertFrom-Json
if($LASTEXITCODE -ne 0 -or $fresh.cache.state -notin @('FRESH','fresh')){throw 'Fresh cache was not readable.'}
[IO.File]::WriteAllText($source,'changed saved asset',[Text.UTF8Encoding]::new($false))
$stale=(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $cache -Sidecar $sidecar -View summary) | ConvertFrom-Json
if($LASTEXITCODE -ne 0 -or $stale.cache.state -notin @('STALE','stale')){throw 'Changed source did not invalidate cache.'}
[pscustomobject]@{passed=$true;protocol='3.0.0';patches=$patches.Count;checks=@('package_parse','script_parse','task_gateway','cache_freshness');fixture=$fixture}|ConvertTo-Json -Compress
