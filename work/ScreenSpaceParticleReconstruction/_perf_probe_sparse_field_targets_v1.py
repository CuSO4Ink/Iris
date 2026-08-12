import re


source_path = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_g5_probe_field_targets.py"
)
with open(source_path, "r", encoding="utf-8") as source_file:
    source_code = source_file.read()

source_code = re.sub(
    r"SYSTEM = \(\n.*?\n\)\n",
    "SYSTEM = (\n"
    '    "/Game/SSPR_Validation/M2/AnisotropicSplat_V2/'
    'Performance/"\n'
    '    "NS_SSPR_AnisotropicSplat_PerfSparseV1.'
    'NS_SSPR_AnisotropicSplat_PerfSparseV1"\n'
    ")\n",
    source_code,
    count=1,
    flags=re.DOTALL,
)
source_code = source_code.replace(
    "G5_FIELD_TARGETS", "PERF_SPARSE_FIELD_TARGETS_V1"
)
source_code = source_code.replace(
    "Validation actor is not using the V2 system",
    "Validation actor is not using PerfSparseV1",
)
source_code = source_code.replace(
    "G5 raw field target gate failed",
    "PerfSparseV1 raw field target gate failed",
)
exec(compile(source_code, source_path + ":PerfSparseV1", "exec"))
