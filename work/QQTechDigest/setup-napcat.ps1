param(
    [ValidatePattern('^$|^\d{5,12}$')]
    [string]$QQ = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$runtimeRoot = Join-Path $workspaceRoot 'tmp\QQTechDigest\napcat'
$archivePath = Join-Path $runtimeRoot 'NapCat.Shell.zip'
$shellRoot = Join-Path $runtimeRoot 'shell'
$downloadUrl = 'https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip'
$pythonCommand = Get-Command python -ErrorAction Stop

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
if (-not (Test-Path -LiteralPath $archivePath)) {
    Write-Host 'Downloading the official NapCat Shell package...'
    $partialArchive = $archivePath + '.partial'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $partialArchive
    Move-Item -LiteralPath $partialArchive -Destination $archivePath
}
if (-not (Test-Path -LiteralPath $shellRoot)) {
    New-Item -ItemType Directory -Path $shellRoot | Out-Null
    Expand-Archive -LiteralPath $archivePath -DestinationPath $shellRoot
}

$launcher = Get-ChildItem -LiteralPath $shellRoot -Recurse -Filter 'launcher.bat' -File | Select-Object -First 1
if (-not $launcher) {
    throw 'launcher.bat was not found in NapCat.Shell.zip.'
}

Push-Location $projectRoot
try {
    & $pythonCommand.Source '.\qq_tech_digest.py' init --config '.\config.json'
    if ($LASTEXITCODE -ne 0) { throw 'QQTechDigest initialization failed.' }

    $napcatConfigDir = Join-Path $launcher.DirectoryName 'config'
    New-Item -ItemType Directory -Force -Path $napcatConfigDir | Out-Null
    $napcatConfig = Join-Path $napcatConfigDir 'onebot11.json'
    & $pythonCommand.Source '.\qq_tech_digest.py' napcat-config --config '.\config.json' --output $napcatConfig
    if ($LASTEXITCODE -ne 0) { throw 'NapCat OneBot configuration failed.' }
}
finally {
    Pop-Location
}

Write-Host "NapCat is ready at $($launcher.DirectoryName)"
if ($QQ) {
    Write-Host 'Opening NapCat. Scan the QR code or approve the login in mobile QQ.'
    Start-Process -FilePath $launcher.FullName -ArgumentList '-q', $QQ -WorkingDirectory $launcher.DirectoryName -WindowStyle Normal
}
else {
    Write-Host 'When the account is available, run: .\setup-napcat.ps1 -QQ 123456789'
}
