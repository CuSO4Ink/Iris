import json
import unreal


SYSTEM_PREFIX = (
    "/Game/SSPR_Validation/M2/NewNiagaraSystem."
    "NewNiagaraSystem:Grid2D_Gas_SmokeFire_Emitter_0"
)

rows = []
for stage in unreal.ObjectIterator(unreal.NiagaraSimulationStageBase):
    path = stage.get_path_name()
    if not path.startswith(SYSTEM_PREFIX):
        continue
    property_names = []
    for name in dir(stage):
        lower = name.lower()
        if any(
            token in lower
            for token in (
                "enable",
                "disable",
                "iteration",
                "script",
                "stage",
                "source",
                "spawn",
                "execute",
            )
        ):
            property_names.append(name)
    rows.append(
        {
            "path": path,
            "class": stage.get_class().get_path_name(),
            "name": str(stage.get_editor_property("simulation_stage_name")),
            "candidates": sorted(property_names),
        }
    )

print("GRID_STAGE_PROPERTIES=" + json.dumps(rows, sort_keys=True))
