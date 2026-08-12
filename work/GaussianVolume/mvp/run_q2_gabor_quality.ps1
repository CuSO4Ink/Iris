[CmdletBinding()]
param(
    [string]$GFieldsRoot = "D:\Work\AI\Iris\tmp\gabor_fields",
    [string]$GridPath = "D:\Work\AI\Iris\tmp\gabor_fields\data\volumes\grids\smoke2_vdb.npy",
    [string]$AbyssRoot = "D:\Work\Personal\Project\Abyss",
    [ValidateRange(1, 32)]
    [int]$CamerasPerStep = 4,
    [ValidateRange(0, 1200)]
    [int]$ResumeIterations = 0
)

$ErrorActionPreference = "Stop"
$expectedRevision = "009816f8dac566f343c292caddb231cab6a6099a"
$python = Join-Path $GFieldsRoot ".venv\Scripts\python.exe"
$base = Join-Path $GFieldsRoot "results\checkpoints\smoke2_q2_gaussian_10k\optimized_asset_pyr0\npy_data"
$checkpoint = Join-Path $GFieldsRoot "results\checkpoints\smoke2_q2_gabor_10k_4k"
$asset = Join-Path $checkpoint "optimized_asset_pyr1"
$completionMarker = Join-Path $checkpoint "optimized_pyr1.exr"
$exporter = Join-Path $PSScriptRoot "export_volprim_ply.py"
$json = Join-Path $AbyssRoot "Plugins\GaussianVolume\Content\Data\Smoke2_GFields_Q2_Gabor_10K_4K.json"

foreach ($path in @($GFieldsRoot, $GridPath, $AbyssRoot, $python, $base, $exporter)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required path does not exist: $path" }
}
$revision = (& git -C $GFieldsRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne $expectedRevision) {
    throw "Expected gabor_fields revision $expectedRevision, found $revision"
}

if (-not (Test-Path -LiteralPath $completionMarker)) {
    $iterations = 1200
    $trainArgs = @(
        "-m", "gfields.train", $GridPath,
        "--opacity_scale", "10", "--init_albedo", "0",
        "--output", $checkpoint,
        "--gauss_count", "10000", "--gabor_count", "4096",
        "--skip_gaussian_optim", "--from_gaussian_checkpoint", $base,
        "--iterations_gabor", "$iterations",
        "--gauss_target_level", "0", "--gabor_target_level", "0",
        "--cam_count", "32", "--cam_res_x", "512", "--cam_res_y", "512",
        "--ref_spp", "8192", "--ref_spp_chunk", "128",
        "--opt_spp", "2", "--grad_spp", "1", "--opt_cam_batch", "1", "--cam_subsample", "$CamerasPerStep",
        "--relocate_until", "0",
        "--write_image_every", "60", "--log_every", "20", "--checkpoint_every", "20"
    )
    if (Test-Path -LiteralPath (Join-Path $asset "data\root.primitives_pyr1.ply")) {
        if ($ResumeIterations -eq 0) {
            throw "Incomplete Gabor checkpoint exists; pass -ResumeIterations with the remaining step count"
        }
        $trainArgs[$trainArgs.IndexOf("$iterations")] = "$ResumeIterations"
        $trainArgs += @(
            "--from_gabor_checkpoint", (Join-Path $asset "npy_data"),
            "--epoch_start", "$(1200 - $ResumeIterations)",
            "--no_save_best"
        )
    }
    Push-Location $GFieldsRoot
    try {
        & $python @trainArgs
        if ($LASTEXITCODE -ne 0) { throw "Q2 Gabor training failed" }
    }
    finally { Pop-Location }
}

& python $exporter $asset $json --world-scale 500 --density-multiplier 1 --albedo 0.9 0.9 0.9
if ($LASTEXITCODE -ne 0) { throw "Q2 Gabor export failed" }
$payload = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($payload.gabor_count -le 0 -or $payload.primitive_count -ne $payload.gaussians.Count) {
    throw "Exported Q2 Gabor payload is incomplete"
}

[pscustomobject]@{
    GaussianBudget = 10000
    GaborBudget = 4096
    PrimitiveCount = $payload.primitive_count
    GaborCount = $payload.gabor_count
    Checkpoint = $checkpoint
    Json = $json
}
