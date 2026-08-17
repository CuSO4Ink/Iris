param(
    [ValidateSet('serve', 'digest', 'init')]
    [string]$Command = 'serve'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command python -ErrorAction Stop

Push-Location $projectRoot
try {
    & $pythonCommand.Source '.\qq_tech_digest.py' $Command --config '.\config.json'
    if ($LASTEXITCODE -ne 0) {
        throw "QQTechDigest exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
