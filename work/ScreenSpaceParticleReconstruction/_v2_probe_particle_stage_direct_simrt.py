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


def require(result, context):
    if not result.success:
        raise RuntimeError(context + ": " + str(result.message))


def node_by_type(module, node_type):
    return next(
        str(node.node_id)
        for node in SERVICE.list_nodes(SYSTEM, EMITTER, module)
        if str(node.node_type) == node_type
    )


def pins(module, node_id):
    return {
        (str(pin.direction), str(pin.pin_name))
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, module, node_id
        )
    }


raster_nodes = list(SERVICE.list_nodes(SYSTEM, EMITTER, RASTER_MODULE))
map_get = next(
    str(node.node_id)
    for node in raster_nodes
    if str(node.node_type) == "MapGet"
    and any(
        str(pin.pin_name) == "User.SSPR_DensityRaster"
        for pin in SERVICE.get_node_pins(
            SYSTEM, EMITTER, RASTER_MODULE, str(node.node_id)
        )
    )
)
raster_hlsl = node_by_type(RASTER_MODULE, "CustomHlsl")

if ("Output", "User.SSPR_SimRT") not in pins(RASTER_MODULE, map_get):
    require(
        SERVICE.add_pin(
            SYSTEM, EMITTER, RASTER_MODULE, map_get,
            "Output", "RenderTarget2D", "User.SSPR_SimRT"
        ),
        "Add SimRT map-get pin",
    )
if ("Input", "SimRT") not in pins(RASTER_MODULE, raster_hlsl):
    require(
        SERVICE.add_pin(
            SYSTEM, EMITTER, RASTER_MODULE, raster_hlsl,
            "Input", "RenderTarget2D", "SimRT"
        ),
        "Add SimRT HLSL pin",
    )

connections = {
    (
        str(item.from_node_id), str(item.from_pin),
        str(item.to_node_id), str(item.to_pin),
    )
    for item in SERVICE.list_connections(
        SYSTEM, EMITTER, RASTER_MODULE
    )
}
edge = (
    map_get, "User.SSPR_SimRT", raster_hlsl, "SimRT"
)
if edge not in connections:
    if not SERVICE.connect_pins(
        SYSTEM, EMITTER, RASTER_MODULE,
        map_get, "User.SSPR_SimRT", raster_hlsl, "SimRT"
    ):
        raise RuntimeError("Connect SimRT to raster HLSL failed")

writer = r"""int W = 1;
int H = 1;
SimRT.GetRenderTargetSize(W, H);
int I = ExecIndex();
int X = W > 0 ? I % W : 0;
int Y = W > 0 ? I / W : 0;
bool Valid = W > 0 && H > 0 && Y >= 0 && Y < H;
SimRT.SetRenderTargetValue(
    Valid, X, Y, float4(1.0f, 1.0f, 1.0f, 1.0f));
OutMark = Valid ? 1.0f : 0.0f;"""
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RASTER_MODULE, raster_hlsl, writer
):
    raise RuntimeError("Install direct SimRT writer failed")

resolve_hlsl = node_by_type(RESOLVE_MODULE, "CustomHlsl")
if not SERVICE.set_custom_hlsl_code(
    SYSTEM, EMITTER, RESOLVE_MODULE, resolve_hlsl,
    "OutMark = 0.0f;"
):
    raise RuntimeError("Disable resolve writer failed")

applied = bool(SERVICE.apply_changes(SYSTEM))
messages = [str(item) for item in SERVICE.get_compile_messages(SYSTEM, False)]
actors = unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors()
actor = next(
    item for item in actors
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(unreal.NiagaraComponent)[0]
component.reinitialize_system()
component.activate(True)
component.set_force_solo(True)
component.advance_simulation(60, 1.0 / 60.0)
saved = bool(unreal.EditorAssetLibrary.save_asset(PACKAGE, False))
print("V2_PARTICLE_DIRECT_SIMRT=" + json.dumps({
    "applied": applied,
    "compileMessages": messages,
    "active": bool(component.is_active()),
    "saved": saved,
}, sort_keys=True))
if not applied or messages or not saved:
    raise RuntimeError("Particle direct SimRT probe failed")
