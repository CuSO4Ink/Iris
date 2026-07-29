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


writer = r"""int W = 1;
int H = 1;
SimRT.GetRenderTargetSize(W, H);
int X = (int)floor(ScreenUV.x * (float)W);
int Y = (int)floor(ScreenUV.y * (float)H);
bool Valid =
    W > 0 && H > 0 &&
    ScreenUV.x >= 0.0f && ScreenUV.x < 1.0f &&
    ScreenUV.y >= 0.0f && ScreenUV.y < 1.0f &&
    X >= 0 && X < W && Y >= 0 && Y < H;
SimRT.SetRenderTargetValue(
    Valid, X, Y, float4(1.0f, 1.0f, 1.0f, 1.0f));
OutMark = Valid ? 1.0f : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RASTER_MODULE, hlsl_node(RASTER_MODULE), writer
):
    raise RuntimeError("Install ScreenUV direct writer failed")
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RESOLVE_MODULE, hlsl_node(RESOLVE_MODULE),
    "OutMark = 0.0f;"
):
    raise RuntimeError("Disable resolve failed")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(120, 1.0 / 60.0)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_SCREEN_UV_DIRECT_SIMRT=" + json.dumps({
    "active": bool(component.is_active()),
    "applied": applied,
    "compileMessages": messages,
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("ScreenUV direct probe failed")
