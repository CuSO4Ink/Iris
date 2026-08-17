"""Log the imported smoke2 SVT metadata used by the UE baseline."""

import unreal


for name in ("U8", "F16"):
    asset = unreal.load_asset(
        f"/Game/GaussianVolume/Baselines/SVT_Smoke2_Density_{name}"
    )
    if not asset:
        raise RuntimeError(f"missing SVT {name}")
    unreal.log(
        "SVT_INSPECT "
        f"name={name} resolution={asset.get_editor_property('volume_resolution')} "
        f"format={asset.get_editor_property('format_a')} "
        f"frames={asset.get_editor_property('num_frames')} "
        f"mips={asset.get_editor_property('num_mip_levels')} "
        f"frame_transform={asset.get_frame_transform()}"
    )
