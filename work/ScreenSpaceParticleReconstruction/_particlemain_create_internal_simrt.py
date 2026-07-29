import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
DI_PATH = SYSTEM + ":SSPR_SimRTDI"


def find_by_path(object_class, path):
    for obj in unreal.ObjectIterator(object_class):
        if obj.get_path_name() == path:
            return obj
    return None


system = unreal.load_object(None, SYSTEM)
if not isinstance(system, unreal.NiagaraSystem):
    raise RuntimeError("ParticleTrails system is missing")

di = find_by_path(unreal.NiagaraDataInterfaceRenderTarget2D, DI_PATH)
created = False
if di is None:
    di = unreal.new_object(
        unreal.NiagaraDataInterfaceRenderTarget2D,
        outer=system,
        name="SSPR_SimRTDI",
    )
    created = True

di.set_editor_property("inherit_user_parameter_settings", False)
di.set_editor_property("size", unreal.IntPoint(2048, 2048))
di.set_editor_property("override_format", True)
di.set_editor_property(
    "override_render_target_format",
    unreal.TextureRenderTargetFormat.RTF_RGBA16F,
)
di.set_editor_property(
    "override_render_target_filter",
    unreal.TextureFilter.TF_BILINEAR,
)
try:
    di.set_editor_property("preview_render_target", True)
except Exception:
    pass

print(
    "PARTICLE_INTERNAL_SIMRT="
    + json.dumps(
        {
            "path": di.get_path_name(),
            "created": created,
            "size": [
                di.get_editor_property("size").x,
                di.get_editor_property("size").y,
            ],
            "inherit": bool(
                di.get_editor_property("inherit_user_parameter_settings")
            ),
            "format": str(
                di.get_editor_property("override_render_target_format")
            ),
            "filter": str(
                di.get_editor_property("override_render_target_filter")
            ),
        },
        sort_keys=True,
    )
)
