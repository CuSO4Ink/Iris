import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
PACKAGE = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
MODULE = "SSPR_RasterizeWhiteParticles"
SERVICE = unreal.NiagaraScratchPadService

node_id = next(
    str(node.node_id)
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, MODULE)
    if str(node.node_type) == "CustomHlsl"
)
writer = r"""int W = 1;
int H = 1;
int D = 1;
DensityRaster.GetNumCells(W, H, D);
float4 Clip = mul(float4(WorldPos, 1.0f), View.WorldToClip);
bool InFront = Clip.w > 0.0001f;
float2 Ndc = InFront ? Clip.xy / Clip.w : float2(0.0f, 0.0f);
float2 CurrentUV = Ndc * float2(0.5f, -0.5f) + 0.5f;
int2 Pixel = int2(floor(CurrentUV * float2(W, H)));
bool Valid =
    W > 0 && H > 0 && D > 0 && InFront &&
    CurrentUV.x >= 0.0f && CurrentUV.x < 1.0f &&
    CurrentUV.y >= 0.0f && CurrentUV.y < 1.0f &&
    Pixel.x >= 0 && Pixel.x < W && Pixel.y >= 0 && Pixel.y < H;
int PreviousValue = 0;
if (Valid)
{
    DensityRaster.InterlockedAddIntGridValue(
        Pixel.x, Pixel.y, 0, 0, 1024, PreviousValue);
}
OutMark = Valid ? 1.0f : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, MODULE, node_id, writer
):
    raise RuntimeError("Install Stage 1 projection point writer failed")
applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_STAGE1_PROJECTION_RASTER_POINTS=" + json.dumps({
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Stage 1 projection point probe failed")
