import json
import unreal


SYSTEM_TOKEN = "NS_SSPR_ParticleTrails_Main"


def main():
    targets = []
    for target in unreal.ObjectIterator(unreal.TextureRenderTarget2D):
        try:
            sx = int(target.get_editor_property("size_x"))
            sy = int(target.get_editor_property("size_y"))
            fmt = str(target.get_editor_property("render_target_format"))
        except Exception:
            continue
        if sx < 128 or sy < 128:
            continue
        outer = target.get_outer()
        targets.append(
            {
                "path": target.get_path_name(),
                "size": [sx, sy],
                "format": fmt,
                "outer": outer.get_path_name() if outer else None,
            }
        )

    data_interfaces = []
    for di in unreal.ObjectIterator(unreal.NiagaraDataInterfaceRenderTarget2D):
        path = di.get_path_name()
        if SYSTEM_TOKEN not in path and "NiagaraComponent" not in path:
            continue
        try:
            size = di.get_editor_property("size")
            size_row = [int(size.x), int(size.y)]
        except Exception:
            size_row = None
        data_interfaces.append(
            {
                "path": path,
                "size": size_row,
                "inherit": bool(
                    di.get_editor_property("inherit_user_parameter_settings")
                ),
            }
        )

    print(
        "PARTICLE_INTERNAL_TARGETS="
        + json.dumps(
            {"targets": targets, "dataInterfaces": data_interfaces},
            sort_keys=True,
        )
    )


main()
