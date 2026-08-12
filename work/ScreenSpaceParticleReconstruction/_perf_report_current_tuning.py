import json
import unreal

SYSTEM_PATH = "/Game/SSPR_Validation/Recovery/DenseG5_20260730/NS_SSPR_AnisotropicSplat_Main"
EMITTER_NAME = "Fountain"

system = unreal.load_asset(SYSTEM_PATH)
if system is None:
    raise RuntimeError("Recovery Dense G5 system is missing")

component = None
for actor in unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem
).get_all_level_actors():
    for candidate in actor.get_components_by_class(unreal.NiagaraComponent):
        asset = candidate.get_asset()
        if asset is not None and asset.get_path_name() == system.get_path_name():
            component = candidate
            break
    if component is not None:
        break
if component is None:
    raise RuntimeError("Active recovery Dense G5 component is missing")


def editor_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


float_names = [
    "User.SSPR_DensityPerParticle",
    "User.SSPR_DepthFarUU",
    "User.SSPR_DepthNearUU",
    "User.SSPR_FrontDepthWeightThreshold",
    "User.SSPR_GaussianCutoffSigma",
    "User.SSPR_MaxLengthPx",
    "User.SSPR_MinDirectionSpeedPx",
    "User.SSPR_MinLengthPx",
    "User.SSPR_VelocityLengthScale",
    "User.SSPR_WidthPx",
]
float_values = {}
for name in float_names:
    try:
        raw_value = component.get_variable_float(name)
        if isinstance(raw_value, tuple):
            float_values[name] = list(raw_value)
        else:
            float_values[name] = raw_value
    except Exception as exc:
        float_values[name] = {"error": str(exc)}

rapid_iteration = []
for item in unreal.NiagaraService.list_rapid_iteration_params(
    SYSTEM_PATH, EMITTER_NAME
):
    rapid_iteration.append(
        {
            "name": item.get_editor_property("parameter_name"),
            "type": item.get_editor_property("parameter_type"),
            "value": item.get_editor_property("value"),
            "script": item.get_editor_property("script_type"),
        }
    )

interfaces = []
for obj in unreal.ObjectIterator(unreal.NiagaraDataInterface):
    outer = obj.get_outer()
    if outer is None or outer.get_path_name() != component.get_path_name():
        continue
    row = {"class": obj.get_class().get_name(), "path": obj.get_path_name()}
    class_name = obj.get_class().get_name()
    if class_name == "NiagaraDataInterfaceRasterizationGrid3D":
        cells = obj.get_editor_property("num_cells")
        row.update(
            {
                "numCells": [int(cells.x), int(cells.y), int(cells.z)],
                "precision": float(obj.get_editor_property("precision")),
                "clear": bool(
                    obj.get_editor_property("clear_before_non_iteration_stage")
                ),
            }
        )
    elif class_name == "NiagaraDataInterfaceRenderTarget2D":
        size = obj.get_editor_property("size")
        row.update(
            {
                "size": [int(size.x), int(size.y)],
                "format": str(
                    obj.get_editor_property("override_render_target_format")
                ),
                "filter": str(
                    obj.get_editor_property("override_render_target_filter")
                ),
                "mips": str(obj.get_editor_property("mip_map_generation")),
                "inheritUserSettings": bool(
                    editor_property(
                        obj, "inherit_user_parameter_settings", False
                    )
                ),
            }
        )
    interfaces.append(row)

print(
    "PERF_CURRENT_TUNING="
    + json.dumps(
        {
            "system": system.get_path_name(),
            "component": component.get_path_name(),
            "active": bool(component.is_active()),
            "fixedTick": bool(system.get_editor_property("fixed_tick_delta")),
            "fixedTickSeconds": float(
                system.get_editor_property("fixed_tick_delta_time")
            ),
            "userFloatsEffective": float_values,
            "rapidIteration": rapid_iteration,
            "componentInterfaces": interfaces,
        },
        sort_keys=True,
    )
)
