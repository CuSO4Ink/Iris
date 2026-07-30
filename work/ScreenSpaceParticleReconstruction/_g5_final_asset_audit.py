import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
)
EMITTER = "Fountain"
RASTER_MODULE = "SSPR_RasterizeWhiteParticles"
RESOLVE_MODULE = "SSPR_ResolveGridToSimRT"
DEBUG_MATERIAL = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "M_SSPR_G5_FieldDebugV2"
)
HQ_MATERIAL = (
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/"
    "M_SSPR_AnisotropicSplat_Display"
)
SERVICE = unreal.NiagaraScratchPadService


def property_value(obj, names):
    for name in names:
        try:
            value = obj.get_editor_property(name)
            if hasattr(value, "get_path_name"):
                return value.get_path_name()
            return str(value)
        except Exception:
            pass
    return None


def custom_code(module):
    for node in SERVICE.list_nodes(SYSTEM, EMITTER, module):
        if str(node.node_type) == "CustomHlsl":
            return SERVICE.get_custom_hlsl_code(
                SYSTEM, EMITTER, module, str(node.node_id)
            )
    raise RuntimeError("Missing Custom HLSL in " + module)


system = unreal.load_asset(SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("V2 Niagara System is missing")

stages = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    stages.append(
        {
            "path": path,
            "name": property_value(
                stage, ("simulation_stage_name",)
            ),
            "iterationSource": property_value(
                stage, ("iteration_source",)
            ),
            "writesParticles": property_value(
                stage,
                (
                    "writes_particles",
                    "b_writes_particles",
                ),
            ),
            "disablePartialParticleUpdate": property_value(
                stage,
                (
                    "disable_partial_particle_update",
                    "b_disable_partial_particle_update",
                ),
            ),
        }
    )

raster_code = custom_code(RASTER_MODULE)
resolve_code = custom_code(RESOLVE_MODULE)
debug_diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    DEBUG_MATERIAL
)
hq_diagnostics = unreal.MaterialNodeService.get_material_diagnostics(
    HQ_MATERIAL
)

authored_aux = []
authored_raster = []
for data_interface in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    path = data_interface.get_path_name()
    if not path.startswith(SYSTEM + ":"):
        continue
    class_name = data_interface.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRenderTarget2D" and (
        "SSPR_AuxRT" in path
    ):
        size = data_interface.get_editor_property("size")
        authored_aux.append(
            {
                "path": path,
                "size": [int(size.x), int(size.y)],
                "format": property_value(
                    data_interface,
                    ("override_render_target_format",),
                ),
                "filter": property_value(
                    data_interface,
                    ("override_render_target_filter",),
                ),
                "mips": property_value(
                    data_interface, ("mip_map_generation",)
                ),
            }
        )
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        cells = data_interface.get_editor_property("num_cells")
        if [int(cells.x), int(cells.y), int(cells.z)] == [
            2048,
            2048,
            1,
        ]:
            authored_raster.append(
                {
                    "path": path,
                    "cells": [
                        int(cells.x),
                        int(cells.y),
                        int(cells.z),
                    ],
                    "precision": property_value(
                        data_interface, ("precision",)
                    ),
                    "clear": property_value(
                        data_interface,
                        ("clear_before_non_iteration_stage",),
                    ),
                }
            )

result = {
    "compileMessages": [
        str(item)
        for item in SERVICE.get_compile_messages(SYSTEM, False)
    ],
    "fixedTick": bool(
        system.get_editor_property("fixed_tick_delta")
    ),
    "fixedTickDeltaTime": float(
        system.get_editor_property("fixed_tick_delta_time")
    ),
    "stages": stages,
    "rasterCodeGate": {
        "sixAttributesReferenced": all(
            "0, {}, ".format(index) in raster_code
            or "0, {},\n".format(index) in raster_code
            for index in range(6)
        ),
        "frontDepthAtomicMax": (
            "InterlockedMaxFloatGridValue" in raster_code
        ),
        "noHistoryToken": "History" not in raster_code,
    },
    "resolveCodeGate": {
        "sixAttributesRead": all(
            "0, {}, ".format(index) in resolve_code
            or "0, {},\n".format(index) in resolve_code
            for index in range(6)
        ),
        "mainWrite": "SimRT.SetRenderTargetValue" in resolve_code,
        "auxWrite": "AuxRT.SetRenderTargetValue" in resolve_code,
        "noHistoryToken": "History" not in resolve_code,
    },
    "authoredRaster": authored_raster,
    "authoredAux": authored_aux,
    "debugMaterial": {
        "compiled": bool(debug_diagnostics.is_compiled_ok),
        "errors": [
            str(item) for item in debug_diagnostics.compile_errors
        ],
    },
    "hqMaterial": {
        "compiled": bool(hq_diagnostics.is_compiled_ok),
        "errors": [
            str(item) for item in hq_diagnostics.compile_errors
        ],
    },
}
print("G5_FINAL_ASSET_AUDIT=" + json.dumps(result, sort_keys=True))
if (
    result["compileMessages"]
    or not result["fixedTick"]
    or not result["rasterCodeGate"]["sixAttributesReferenced"]
    or not result["rasterCodeGate"]["frontDepthAtomicMax"]
    or not result["resolveCodeGate"]["sixAttributesRead"]
    or not result["resolveCodeGate"]["mainWrite"]
    or not result["resolveCodeGate"]["auxWrite"]
    or not result["authoredRaster"]
    or not result["authoredAux"]
    or not result["debugMaterial"]["compiled"]
    or result["debugMaterial"]["errors"]
    or not result["hqMaterial"]["compiled"]
    or result["hqMaterial"]["errors"]
):
    raise RuntimeError("G5 final asset audit failed: " + repr(result))
