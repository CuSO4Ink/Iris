[CmdletBinding()]
param(
    [ValidateSet("Q1", "Q2", "Q3")]
    [string]$Stage = "Q1",
    [string]$GFieldsRoot = "D:\Work\AI\Iris\tmp\gabor_fields",
    [string]$GridPath = "D:\Work\AI\Iris\tmp\gabor_fields\data\volumes\grids\smoke2_vdb.npy",
    [string]$AbyssRoot = "D:\Work\Personal\Project\Abyss",
    [ValidateRange(0, 240)]
    [int]$ResumeIterations = 0
)

$ErrorActionPreference = "Stop"
$expectedRevision = "009816f8dac566f343c292caddb231cab6a6099a"
$stages = @{
    Q1 = @{ Count = 4096;  Slug = "q1_gaussian_4k";  Asset = "Q1_4K" }
    Q2 = @{ Count = 10000; Slug = "q2_gaussian_10k"; Asset = "Q2_10K" }
    Q3 = @{ Count = 24576; Slug = "q3_gaussian_24k"; Asset = "Q3_24K" }
}
$config = $stages[$Stage]
$python = Join-Path $GFieldsRoot ".venv\Scripts\python.exe"
$checkpoint = Join-Path $GFieldsRoot "results\checkpoints\smoke2_$($config.Slug)"
$plyPath = Join-Path $checkpoint "optimized_asset_pyr0\data\root.primitives_pyr0.ply"
$completionMarker = Join-Path $checkpoint "optimized_pyr0.exr"
$exporter = Join-Path $PSScriptRoot "export_volprim_ply.py"
$jsonPath = Join-Path $AbyssRoot "Plugins\GaussianVolume\Content\Data\Smoke2_GFields_$($config.Asset).json"

foreach ($requiredPath in @($GFieldsRoot, $GridPath, $AbyssRoot, $python, $exporter)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path does not exist: $requiredPath"
    }
}

$revision = (& git -C $GFieldsRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne $expectedRevision) {
    throw "Expected gabor_fields revision $expectedRevision, found $revision"
}
if (-not (Select-String -LiteralPath (Join-Path $GFieldsRoot "gfields\optimizers.py") -SimpleMatch "upper == lower" -Quiet)) {
    throw "Apply patches/gabor_fields-gaussian-pipeline-009816f.patch before training"
}

if (-not (Test-Path -LiteralPath $completionMarker)) {
    $trainArgs = @(
        "-m", "gfields.train", $GridPath,
        "--gaussian", "--opacity_scale", "10", "--init_albedo", "0",
        "--output", $checkpoint, "--gauss_count", $config.Count,
        "--iterations_gaussian", "240",
        "--cam_count", "32", "--cam_res_x", "512", "--cam_res_y", "512",
        "--ref_spp", "8192", "--ref_spp_chunk", "128",
        "--opt_spp", "2", "--grad_spp", "1", "--opt_cam_batch", "1",
        "--relocate_until", "210",
        "--write_image_every", "60", "--log_every", "20", "--checkpoint_every", "60"
    )
    if (Test-Path -LiteralPath $plyPath) {
        if ($ResumeIterations -eq 0) {
            throw "Incomplete checkpoint exists at $checkpoint; pass -ResumeIterations with the remaining iteration count"
        }
        $resumePath = Join-Path $checkpoint "optimized_asset_pyr0\npy_data"
        $trainArgs += @("--from_gaussian_checkpoint", $resumePath)
        $trainArgs[($trainArgs.IndexOf("--iterations_gaussian") + 1)] = "$ResumeIterations"
        $trainArgs[($trainArgs.IndexOf("--relocate_until") + 1)] = "0"
    }
    Push-Location $GFieldsRoot
    try {
        & $python @trainArgs
        if ($LASTEXITCODE -ne 0) { throw "$Stage training failed" }
    }
    finally {
        Pop-Location
    }
}
if (-not (Test-Path -LiteralPath $plyPath)) { throw "$Stage did not produce $plyPath" }

& python $exporter $plyPath $jsonPath `
    --world-scale 500 --density-multiplier 1 --albedo 0.9 0.9 0.9
if ($LASTEXITCODE -ne 0) { throw "$Stage export failed" }

$payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
if ($payload.schema -ne "GaussianVolume.Primitives.v1") { throw "Unexpected JSON schema" }
if ($payload.primitive_count -ne $payload.gaussians.Count -or $payload.primitive_count -gt $config.Count) {
    throw "Invalid primitive count $($payload.primitive_count) for budget $($config.Count)"
}

[pscustomobject]@{
    Stage = $Stage
    PrimitiveBudget = $config.Count
    PrimitiveCount = $payload.primitive_count
    Checkpoint = $checkpoint
    Json = $jsonPath
    Reference = "32 cameras, 512x512, 8192 spp (shared content-addressed cache)"
    Fit = "absorption-only; official Gaussian-only recipe"
}
