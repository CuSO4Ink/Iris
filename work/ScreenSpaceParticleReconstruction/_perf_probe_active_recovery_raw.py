import re


source_path = (
    r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"
    r"\_perf_fast_active_raw_gate.py"
)
with open(source_path, encoding="utf-8") as source_file:
    source_code = source_file.read()

source_code = re.sub(
    r"SYSTEM = \(\n.*?\n\)\n",
    "SYSTEM = (\n"
    '    "/Game/SSPR_Validation/Recovery/DenseG5_20260730/"\n'
    '    "NS_SSPR_AnisotropicSplat_Main.'
    'NS_SSPR_AnisotropicSplat_Main"\n'
    ")\n",
    source_code,
    count=1,
    flags=re.DOTALL,
)
source_code = source_code.replace(
    "PERF_FAST_ACTIVE_RAW_GATE",
    "PERF_ACTIVE_RECOVERY_RAW_GATE",
)
source_code = source_code.replace(
    "Fast active raw gate failed",
    "Active recovery raw gate failed",
)
exec(
    compile(
        source_code,
        source_path + ":RECOVERY",
        "exec",
    )
)
