import json
import unreal

service = unreal.NiagaraScratchPadService
names = [
    name
    for name in dir(service)
    if any(token in name.lower() for token in ("raster", "render_target", "user_parameter"))
]
print("V2_RASTER_API=" + json.dumps({"methods": names}, sort_keys=True))
