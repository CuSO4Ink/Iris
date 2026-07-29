import json
import unreal


SYSTEM = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main"
)
MATERIAL = (
    "/Game/SSPR_Validation/M2/ParticleTrails/"
    "M_SSPR_ParticleTrails_Display.M_SSPR_ParticleTrails_Display"
)
EMITTER = "Fountain"
MODULES = {
    "SSPR_DisplayCardSetup",
    "SSPR_Projection",
    "SSPR_RasterizeTrails",
    "SSPR Resolve Grid To Material",
    "SSPR_ResolveGridToSimRT",
}


def main():
    service = unreal.NiagaraScratchPadService
    scratch = {}
    for module_name_value in service.list_scratch_modules(SYSTEM, EMITTER):
        module_name = str(module_name_value)
        if module_name not in MODULES:
            continue
        nodes = list(service.list_nodes(SYSTEM, EMITTER, module_name))
        custom_nodes = [
            node for node in nodes if str(node.node_type) == "CustomHlsl"
        ]
        scratch[module_name] = {
            "hlsl": [
                str(
                    service.get_custom_hlsl_code(
                        SYSTEM, EMITTER, module_name, str(node.node_id)
                    )
                )
                for node in custom_nodes
            ],
            "pins": [
                {
                    "name": str(pin.pin_name),
                    "direction": str(pin.direction),
                    "type": str(pin.type_name),
                    "connected": bool(pin.is_connected),
                    "default": str(pin.default_value),
                }
                for node in nodes
                for pin in service.get_node_pins(
                    SYSTEM, EMITTER, module_name, str(node.node_id)
                )
                if str(pin.pin_name)
                in {
                    "Engine.Owner.Position",
                    "Emitter.Position",
                    "Emitter.SpriteSize",
                    "Particles.SSPR_ScreenUV",
                    "Particles.Position",
                    "WorldPos",
                    "OutUV",
                    "ScreenUV",
                    "OutSize",
                }
            ],
        }

    material = unreal.load_object(None, MATERIAL)
    if material is None:
        raise RuntimeError("Display material is missing")
    lib = unreal.MaterialEditingLibrary
    expressions = list(lib.get_material_expressions(material))
    material_nodes = []
    for expression in expressions:
        inputs = list(lib.get_inputs_for_material_expression(material, expression))
        material_nodes.append(
            {
                "class": expression.get_class().get_name(),
                "path": expression.get_path_name(),
                "inputNames": [
                    str(name)
                    for name in lib.get_material_expression_input_names(
                        expression
                    )
                ],
                "connectedInputs": [
                    input_expression.get_class().get_name()
                    for input_expression in inputs
                    if input_expression is not None
                ],
            }
        )

    actor = next(
        (
            item
            for item in unreal.get_editor_subsystem(
                unreal.EditorActorSubsystem
            ).get_all_level_actors()
            if item.get_actor_label() == "SSPR_ParticleTrails_Main"
        ),
        None,
    )
    actor_row = None
    if actor is not None:
        location = actor.get_actor_location()
        actor_row = {
            "path": actor.get_path_name(),
            "location": [location.x, location.y, location.z],
        }

    view = unreal.ViewportService.get_viewport_info()
    view_row = None
    if view is not None:
        view_row = {
            "location": [view.location.x, view.location.y, view.location.z],
            "rotation": [
                view.rotation.pitch,
                view.rotation.yaw,
                view.rotation.roll,
            ],
            "fov": float(view.fov),
        }

    print(
        "PARTICLE_ALIGNMENT_STATE="
        + json.dumps(
            {
                "scratch": scratch,
                "materialNodes": material_nodes,
                "actor": actor_row,
                "view": view_row,
            },
            sort_keys=True,
        )
    )


main()
