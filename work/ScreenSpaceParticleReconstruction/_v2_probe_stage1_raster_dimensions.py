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
RASTER_MODULE = "SSPR_RasterizeWhiteParticles"
RESOLVE_MODULE = "SSPR_ResolveGridToSimRT"
SERVICE = unreal.NiagaraScratchPadService


def hlsl_node(module):
    return next(
        str(node.node_id)
        for node in SERVICE.list_nodes(SYSTEM, EMITTER, module)
        if str(node.node_type) == "CustomHlsl"
    )


writer = r"""int W = 0;
int H = 0;
int D = 0;
DensityRaster.GetNumCells(W, H, D);
int RTW = 1;
int RTH = 1;
SimRT.GetRenderTargetSize(RTW, RTH);
int I = ExecIndex();
int X = RTW > 0 ? I % RTW : 0;
int Y = RTW > 0 ? I / RTW : 0;
bool ValidRT = RTW > 0 && RTH > 0 && Y >= 0 && Y < RTH;
float IsConfigured = (W == 2048 && H == 2048 && D == 1) ? 1.0f : 0.0f;
float IsAllocated = (W > 0 && H > 0 && D > 0) ? 1.0f : 0.0f;
int Ignore = 0;
if (IsAllocated > 0.5f)
{
    DensityRaster.InterlockedAddIntGridValue(0, 0, 0, 0, 0, Ignore);
}
SimRT.SetRenderTargetValue(
    ValidRT, X, Y, float4(IsConfigured, IsAllocated, 0.0f, 1.0f));
OutMark = (float)W;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RASTER_MODULE, hlsl_node(RASTER_MODULE), writer
):
    raise RuntimeError("Install Stage 1 dimension probe failed")
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RESOLVE_MODULE, hlsl_node(RESOLVE_MODULE),
    "OutMark = 0.0f;"
):
    raise RuntimeError("Disable resolve failed")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_STAGE1_RASTER_DIMENSIONS=" + json.dumps({
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Stage 1 Raster dimension probe failed")
