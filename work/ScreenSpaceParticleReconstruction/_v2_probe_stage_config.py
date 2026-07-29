import json
import unreal

SYSTEMS = [
    "/Game/SSPR_Validation/M2/ParticleTrails/NS_SSPR_ParticleTrails_Main.NS_SSPR_ParticleTrails_Main",
    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main",
]
rows = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    owner = next((item for item in SYSTEMS if path.startswith(item + ":")), None)
    if owner is None:
        continue
    props = {}
    for name in (
        "simulation_stage_name", "b_enabled", "enabled", "iteration_source",
        "execute_behavior", "b_disable_partial_particle_update",
        "b_particle_iteration_state_enabled", "b_gpu_dispatch_force_linear",
        "direct_dispatch_type", "direct_dispatch_element_type", "data_interface",
        "num_iterations",
    ):
        try:
            props[name] = str(stage.get_editor_property(name))
        except Exception as error:
            props[name] = "ERROR:" + str(error)
    rows.append({
        "owner": owner,
        "path": path,
        "class": stage.get_class().get_name(),
        "properties": props,
    })
print("V2_STAGE_CONFIG=" + json.dumps(rows, sort_keys=True))
