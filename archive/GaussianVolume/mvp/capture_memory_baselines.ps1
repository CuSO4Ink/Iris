param(
    [string]$OutputDirectory = "",
    [int]$WarmupSeconds = 5,
    [int]$Samples = 10,
    [int]$SampleIntervalMs = 250,
    [ValidateSet("Legacy", "G37")]
    [string]$Suite = "Legacy",
    [int]$Repeats = 1,
    [switch]$AllowConcurrentGpuWork
)

$ErrorActionPreference = "Stop"

$editor = "D:\Work\Personal\Project\Abyss\Binaries\Win64\AbyssEditor-Cmd.exe"
$project = "D:\Work\Personal\Project\Abyss\Abyss.uproject"

if (-not $OutputDirectory) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDirectory = Join-Path $PSScriptRoot "..\evidence\memory-$stamp-$($Suite.ToLower())"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

foreach ($required in @($editor, $project)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing required file: $required"
    }
}

if (-not $AllowConcurrentGpuWork) {
    $pythonProcesses = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue
    if ($pythonProcesses) {
        $ids = ($pythonProcesses.Id -join ", ")
        throw "Python work is active (PID $ids). Re-run after it exits so the GPU-memory evidence is uncontaminated, or pass -AllowConcurrentGpuWork deliberately."
    }
    $editorProcesses = Get-Process -Name "AbyssEditor", "AbyssEditor-Cmd" -ErrorAction SilentlyContinue
    if ($editorProcesses) {
        $ids = ($editorProcesses.Id -join ", ")
        throw "Abyss editor work is active (PID $ids). Close it before the cold-process capture, or pass -AllowConcurrentGpuWork deliberately."
    }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$cases = if ($Suite -eq "G37") {
    [ordered]@{
        Empty = "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_Empty"
        SVT = "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_SVT"
        GS = "/Game/GaussianVolume/Benchmarks/VRAM_20260731/L_G37_GS"
    }
} else {
    [ordered]@{
        Empty = "/Game/GaussianVolume/Maps/L_GaussianVolume_EmptyBaseline"
        GaussianQ2 = "/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab"
        SVT_U8 = "/Game/GaussianVolume/Maps/L_GaussianVolume_SVT_U8"
        SVT_F16 = "/Game/GaussianVolume/Maps/L_GaussianVolume_SVT_F16"
        NanoVDB_Fp8 = "/Game/GaussianVolume/Maps/L_GaussianVolume_NanoVDB_Fp8"
        NanoVDB_FpN = "/Game/GaussianVolume/Maps/L_GaussianVolume_NanoVDB_FpN"
    }
}

function Get-Median([double[]]$Values) {
    $ordered = @($Values | Sort-Object)
    $middle = [int][math]::Floor($ordered.Count / 2)
    if (($ordered.Count % 2) -eq 1) {
        return $ordered[$middle]
    }
    return ($ordered[$middle - 1] + $ordered[$middle]) / 2.0
}

function Get-ProcessGpuMemory([int]$ProcessId) {
    $samples = Get-Counter `
        "\GPU Process Memory(*)\Local Usage", `
        "\GPU Process Memory(*)\Non Local Usage" |
        Select-Object -ExpandProperty CounterSamples |
        Where-Object { $_.InstanceName -like "pid_${ProcessId}_*" }

    $local = ($samples |
        Where-Object { $_.Path.EndsWith("\local usage") } |
        Measure-Object -Property CookedValue -Sum).Sum
    $nonLocal = ($samples |
        Where-Object { $_.Path.EndsWith("\non local usage") } |
        Measure-Object -Property CookedValue -Sum).Sum
    [pscustomobject]@{
        LocalBytes = [double]$local
        NonLocalBytes = [double]$nonLocal
    }
}

$results = @()
foreach ($entry in $cases.GetEnumerator()) {
    $label = $entry.Key
    $map = $entry.Value
    for ($run = 1; $run -le $Repeats; ++$run) {
    $log = Join-Path $OutputDirectory "$label.run$run.log"
    $execCommands = "r.GaussianVolume.LogCandidateStats 1,r.SparseVolumeTexture.Streaming.PrintMemoryStats 1,GaussianVolume.ScheduleMemoryDump 300"
    $arguments = @(
        $project,
        $map,
        "-game",
        "-Multiprocess",
        "-Unattended",
        "-NoSplash",
        "-NoSound",
        "-NoP4",
        "-NoLiveCoding",
        "-RenderOffscreen",
        "-Windowed",
        "-ForceRes",
        "-ResX=1920",
        "-ResY=1080",
        "-dx12",
        "-NoVSync",
        "-benchmark",
        "-seconds=600",
        "-ExecCmds=`"$execCommands`"",
        "-AbsLog=$log"
    )

    Write-Host "Starting live capture: $label run $run/$Repeats"
    $process = Start-Process -FilePath $editor -ArgumentList $arguments `
        -PassThru -WindowStyle Hidden
    try {
        $deadline = (Get-Date).AddSeconds(45)
        do {
            Start-Sleep -Milliseconds 250
            if ($process.HasExited) {
                throw "$label exited before its map reached play. See $log"
            }
            $loaded = (Test-Path -LiteralPath $log) -and
                (Select-String -LiteralPath $log -Pattern "Load map complete $map" -Quiet)
        } until ($loaded -or (Get-Date) -ge $deadline)

        if (-not $loaded) {
            throw "$label did not reach play within 45 seconds. See $log"
        }

        Start-Sleep -Seconds $WarmupSeconds
        $memorySamples = for ($index = 0; $index -lt $Samples; ++$index) {
            if ($process.HasExited) {
                throw "$label exited during GPU-memory sampling. See $log"
            }
            $memory = Get-ProcessGpuMemory $process.Id
            if ($memory.LocalBytes -le 0) {
                throw "No dedicated GPU-memory counter was found for $label PID $($process.Id)."
            }
            [pscustomobject]@{
                Sample = $index
                LocalMiB = $memory.LocalBytes / 1MB
                NonLocalMiB = $memory.NonLocalBytes / 1MB
            }
            Start-Sleep -Milliseconds $SampleIntervalMs
        }

        $localValues = [double[]]@($memorySamples.LocalMiB)
        $nonLocalValues = [double[]]@($memorySamples.NonLocalMiB)
        $row = [pscustomobject]@{
            Label = $label
            Run = $run
            Map = $map
            ProcessId = $process.Id
            Resolution = "1920x1080"
            WarmupSeconds = $WarmupSeconds
            SampleCount = $Samples
            DedicatedMedianMiB = [math]::Round((Get-Median $localValues), 3)
            DedicatedMinMiB = [math]::Round(($localValues | Measure-Object -Minimum).Minimum, 3)
            DedicatedMaxMiB = [math]::Round(($localValues | Measure-Object -Maximum).Maximum, 3)
            SharedMedianMiB = [math]::Round((Get-Median $nonLocalValues), 3)
        }
        $results += $row
        $memorySamples | ConvertTo-Json -Depth 3 |
            Set-Content -LiteralPath (Join-Path $OutputDirectory "$label.run$run.samples.json")
        Write-Host ("{0} run {1}: dedicated median {2:N3} MiB" -f
            $label, $run, $row.DedicatedMedianMiB)
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id
            $process.WaitForExit()
        }
    }

    if (Select-String -LiteralPath $log `
        -Pattern "Fatal error:|GPU Crashed or D3D Device Removed|Shader compilation failures are Fatal" `
        -Quiet) {
        throw "$label logged a fatal render failure. See $log"
    }
    }
}

$empty = Get-Median ([double[]]@(
    ($results | Where-Object Label -eq "Empty").DedicatedMedianMiB
))
$resultsWithDelta = foreach ($row in $results) {
    $row | Add-Member -NotePropertyName DedicatedDeltaVsEmptyMiB `
        -NotePropertyValue ([math]::Round($row.DedicatedMedianMiB - $empty, 3)) `
        -PassThru
}
$resultsWithDelta | Export-Csv -LiteralPath (Join-Path $OutputDirectory "results.csv") -NoTypeInformation
$resultsWithDelta | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $OutputDirectory "results.json")

$summary = foreach ($group in ($resultsWithDelta | Group-Object Label)) {
    $rows = @($group.Group)
    [pscustomobject]@{
        Label = $group.Name
        Repeats = $rows.Count
        DedicatedMedianMiB = [math]::Round((Get-Median ([double[]]@($rows.DedicatedMedianMiB))), 3)
        DedicatedStablePeakMiB = [math]::Round(($rows.DedicatedMaxMiB | Measure-Object -Maximum).Maximum, 3)
        SharedMedianMiB = [math]::Round((Get-Median ([double[]]@($rows.SharedMedianMiB))), 3)
        DedicatedDeltaVsEmptyMiB = [math]::Round((Get-Median ([double[]]@($rows.DedicatedDeltaVsEmptyMiB))), 3)
    }
}
$summary | Export-Csv -LiteralPath (Join-Path $OutputDirectory "summary.csv") -NoTypeInformation
$summary | ConvertTo-Json -Depth 3 |
    Set-Content -LiteralPath (Join-Path $OutputDirectory "summary.json")

Write-Host "Live cold-process GPU-memory evidence: $OutputDirectory"
$resultsWithDelta | Format-Table Label,DedicatedMedianMiB,DedicatedDeltaVsEmptyMiB,SharedMedianMiB
$summary | Format-Table Label,Repeats,DedicatedMedianMiB,DedicatedStablePeakMiB,DedicatedDeltaVsEmptyMiB
