import collections
import json
import unreal

SYSTEM = (
    "/Game/SSPR_Validation/Performance/DenseG5SparseV2/"
    "NS_SSPR_AnisotropicSplat_Main."
    "NS_SSPR_AnisotropicSplat_Main"
)

system = unreal.load_asset(SYSTEM)
if system is None:
    raise RuntimeError("Sparse V2 System is missing")
actor = next(
    item
    for item in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if item.get_actor_label() == "SSPR_ParticleTrails_Main"
)
component = actor.get_components_by_class(
    unreal.NiagaraComponent
)[0]

groups = {"systemExactOuter": [], "componentExactOuter": []}
for data_interface in unreal.ObjectIterator(
    unreal.NiagaraDataInterface
):
    outer = data_interface.get_outer()
    if outer is None:
        continue
    row = {
        "class": data_interface.get_class().get_name(),
        "path": data_interface.get_path_name(),
    }
    if outer.get_path_name() == system.get_path_name():
        groups["systemExactOuter"].append(row)
    if outer.get_path_name() == component.get_path_name():
        groups["componentExactOuter"].append(row)

result = {}
for name, rows in groups.items():
    result[name] = {
        "counts": dict(
            collections.Counter(row["class"] for row in rows)
        ),
        "rows": rows,
    }
print(
    "PERF_SPARSE_V2_DI_OUTERS="
    + json.dumps(result, sort_keys=True)
)
