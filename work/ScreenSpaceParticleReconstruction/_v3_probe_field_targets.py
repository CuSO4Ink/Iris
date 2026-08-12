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
    '    "/Game/SSPR_Validation/Versions/'
    'V3_AnisotropicSplat_20260730/"\n'
    '    "NS_SSPR_AnisotropicSplat_V3.'
    'NS_SSPR_AnisotropicSplat_V3"\n'
    ")\n",
    source_code,
    count=1,
    flags=re.DOTALL,
)
source_code = source_code.replace(
    "G5_FIELD_TARGETS", "V3_FIELD_TARGETS"
)
source_code = source_code.replace(
    "Validation actor is not using the V2 system",
    "Validation actor is not using the V3 snapshot system",
)
source_code = source_code.replace(
    "G5 raw field target gate failed",
    "V3 raw field target gate failed",
)
source_code = re.sub(
    r"    main_signature = \(\n.*?\n    \)\n"
    r"    aux_signature = \(\n.*?\n    \)\n",
    """    main_signature = (
        channels["r"]["max"] > 1.0
        and channels["r"]["nonzero"] > 0
        and channels["a"]["nonzero"] > 0
        and channels["r"]["nonzero"] < pixel_count
        and sum(
            channel["nonfinite"] for channel in channels.values()
        ) == 0
    )
    aux_signature = (
        channels["r"]["max"] > 1.0e-6
        and channels["r"]["max"] <= 1.01
        and channels["g"]["max"] > 1.0e-5
        and channels["g"]["max"] <= 1.01
        and channels["b"]["nonzero"] == 0
        and channels["a"]["max"] > 0.5
        and channels["a"]["nonzero"] < pixel_count
        and sum(
            channel["nonfinite"] for channel in channels.values()
        ) == 0
    )
""",
    source_code,
    count=1,
    flags=re.DOTALL,
)
exec(compile(source_code, source_path + ":V3", "exec"))
