[CmdletBinding()]
param(
    [string]$GFieldsRoot = "D:\Work\AI\Iris\tmp\gabor_fields",
    [string]$VdbPath = "D:\Work\AI\Iris\tmp\openvdb_samples\smoke2.vdb",
    [string]$BlenderPython = "D:\_thm\rez_local_cache\ext\blender\4.0.2-thm.2\platform-windows\bin\4.0\python\bin\python.exe",
    [string]$AbyssRoot = "D:\Work\Personal\Project\Abyss"
)

$ErrorActionPreference = "Stop"
$expectedRevision = "009816f8dac566f343c292caddb231cab6a6099a"
$scriptRoot = $PSScriptRoot
$exporter = Join-Path $scriptRoot "export_volprim_ply.py"
$exporterTest = Join-Path $scriptRoot "test_export_volprim_ply.py"
$gfieldsPython = Join-Path $GFieldsRoot ".venv\Scripts\python.exe"
$vdbConverter = Join-Path $GFieldsRoot "gfields\references\vdb.py"
$gridDirectory = Join-Path $GFieldsRoot "data\volumes\grids"
$gridPath = Join-Path $gridDirectory "smoke2_vdb.npy"
$conversionDirectory = Join-Path $gridDirectory "_smoke2_vdb_import"
$checkpoint = Join-Path $GFieldsRoot "results\checkpoints\smoke2_vdb_chain_probe_padded"
$plyPath = Join-Path $checkpoint "optimized_asset_pyr0\data\root.primitives_pyr0.ply"
$jsonPath = Join-Path $AbyssRoot "Plugins\GaussianVolume\Content\Data\Smoke2_GFields_ChainProbe64_Absorption.json"

foreach ($requiredPath in @($GFieldsRoot, $VdbPath, $BlenderPython, $AbyssRoot, $exporter, $exporterTest, $gfieldsPython, $vdbConverter)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path does not exist: $requiredPath"
    }
}

$revision = (& git -C $GFieldsRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne $expectedRevision) {
    throw "Expected gabor_fields revision $expectedRevision, found $revision"
}
if (-not (Select-String -LiteralPath (Join-Path $GFieldsRoot "gfields\optimizers.py") -SimpleMatch "upper == lower" -Quiet)) {
    throw "Apply patches/gabor_fields-gaussian-pipeline-009816f.patch before running the probe"
}
if (-not (Test-Path -LiteralPath $gridPath)) {
    New-Item -ItemType Directory -Force -Path $conversionDirectory | Out-Null
    & $BlenderPython $vdbConverter --input $VdbPath --output $conversionDirectory --grid density
    if ($LASTEXITCODE -ne 0) { throw "OpenVDB conversion failed" }
    $convertedPath = Join-Path $conversionDirectory "$([IO.Path]::GetFileNameWithoutExtension($VdbPath)).npy"
    if (-not (Test-Path -LiteralPath $convertedPath)) { throw "Converter did not create $convertedPath" }
    Move-Item -LiteralPath $convertedPath -Destination $gridPath
}

if (-not (Test-Path -LiteralPath $plyPath)) {
    Push-Location $GFieldsRoot
    try {
        & $gfieldsPython -m gfields.train $gridPath `
            --gaussian --opacity_scale 10 --init_albedo 0 --regen_pyramid `
            --output $checkpoint --gauss_count 64 --iterations_gaussian 2 `
            --cam_count 2 --cam_res_x 32 --cam_res_y 32 `
            --ref_spp 4 --ref_spp_chunk 4 --opt_spp 1 --grad_spp 1 `
            --write_image_every 1 --log_every 1 --checkpoint_every 1
        if ($LASTEXITCODE -ne 0) { throw "GFields chain probe failed" }
    }
    finally {
        Pop-Location
    }
}

& python $exporterTest
if ($LASTEXITCODE -ne 0) { throw "Exporter regression tests failed" }

& python $exporter $plyPath $jsonPath `
    --world-scale 500 --density-multiplier 1 --albedo 0.9 0.9 0.9
if ($LASTEXITCODE -ne 0) { throw "PLY to UE JSON export failed" }

$payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
if ($payload.schema -ne "GaussianVolume.Primitives.v1") { throw "Unexpected JSON schema" }
if ($payload.primitive_count -ne 64 -or $payload.gaussians.Count -ne 64) { throw "Expected 64 primitives" }
if ($payload.density_property -ne "opacities_0") { throw "Unexpected density property" }
if ($payload.albedo_source -ne "override") { throw "Expected UE albedo override" }
foreach ($gaussian in $payload.gaussians) {
    foreach ($value in @($gaussian.center) + @($gaussian.scale) + @($gaussian.rotation) + @($gaussian.albedo) + @($gaussian.sigma_t) + @($gaussian.emission)) {
        $number = [double]$value
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            throw "Non-finite exported primitive value"
        }
    }
    if ($gaussian.sigma_t -lt 0 -or ($gaussian.scale | Where-Object { $_ -le 0 })) {
        throw "Invalid exported density or scale"
    }
}

[pscustomobject]@{
    Vdb = $VdbPath
    Grid = $gridPath
    Checkpoint = $checkpoint
    Ply = $plyPath
    Json = $jsonPath
    PrimitiveCount = $payload.primitive_count
    AspectHandling = "official --pad_grid cube padding"
    DensityFit = "absorption-only"
    UEAlbedo = "0.9,0.9,0.9"
}
