import json
import unreal


FOLDER = "/Game/SSPR_Validation/M2"
RT_NAMES = (
    "RT_SSPR_Current",
    "RT_SSPR_HistoryA",
    "RT_SSPR_HistoryB",
    "RT_SSPR_Core",
    "RT_SSPR_BlurSmall",
    "RT_SSPR_BlurLarge",
    "RT_SSPR_Density",
    "RT_SSPR_Smoke",
)

SMALL_CODE = r"""
float invRes = max(InvResolution, 1.0e-6f);
float2 halfTexel = float2(0.5f * invRes, 0.5f * invRes);
float2 upper = 1.0f - halfTexel;
float2 d = float2(
    max(RadiusPx, 0.0f) * invRes,
    max(RadiusPx, 0.0f) * invRes);
#define SSPR_SAMPLE(OFFSET) ((all((UV + (OFFSET)) >= halfTexel) && all((UV + (OFFSET)) <= upper)) ? Texture2DSampleLevel(SourceTexture, SourceTextureSampler, clamp(UV + (OFFSET), halfTexel, upper), 0).r : 0.0f)
float result = SSPR_SAMPLE(float2(0, 0)) * 0.25f;
result += SSPR_SAMPLE(float2( d.x, 0)) * 0.125f;
result += SSPR_SAMPLE(float2(-d.x, 0)) * 0.125f;
result += SSPR_SAMPLE(float2(0,  d.y)) * 0.125f;
result += SSPR_SAMPLE(float2(0, -d.y)) * 0.125f;
result += SSPR_SAMPLE(float2( d.x,  d.y) * 0.7071f) * 0.0625f;
result += SSPR_SAMPLE(float2(-d.x,  d.y) * 0.7071f) * 0.0625f;
result += SSPR_SAMPLE(float2( d.x, -d.y) * 0.7071f) * 0.0625f;
result += SSPR_SAMPLE(float2(-d.x, -d.y) * 0.7071f) * 0.0625f;
#undef SSPR_SAMPLE
return float3(saturate(result), 0.0f, 0.0f);
""".strip()

LARGE_CODE = r"""
float invRes = max(InvResolution, 1.0e-6f);
float2 halfTexel = float2(0.5f * invRes, 0.5f * invRes);
float2 upper = 1.0f - halfTexel;
float2 d = float2(
    max(RadiusPx, 0.0f) * invRes,
    max(RadiusPx, 0.0f) * invRes);
float2 h = d * 0.5f;
#define SSPR_SAMPLE(OFFSET) ((all((UV + (OFFSET)) >= halfTexel) && all((UV + (OFFSET)) <= upper)) ? Texture2DSampleLevel(SourceTexture, SourceTextureSampler, clamp(UV + (OFFSET), halfTexel, upper), 0).r : 0.0f)
float result = SSPR_SAMPLE(float2(0, 0)) * 0.16f;
result += SSPR_SAMPLE(float2( d.x, 0)) * 0.10f;
result += SSPR_SAMPLE(float2(-d.x, 0)) * 0.10f;
result += SSPR_SAMPLE(float2(0,  d.y)) * 0.10f;
result += SSPR_SAMPLE(float2(0, -d.y)) * 0.10f;
result += SSPR_SAMPLE(float2( d.x,  d.y) * 0.7071f) * 0.07f;
result += SSPR_SAMPLE(float2(-d.x,  d.y) * 0.7071f) * 0.07f;
result += SSPR_SAMPLE(float2( d.x, -d.y) * 0.7071f) * 0.07f;
result += SSPR_SAMPLE(float2(-d.x, -d.y) * 0.7071f) * 0.07f;
result += SSPR_SAMPLE(float2( h.x, 0)) * 0.04f;
result += SSPR_SAMPLE(float2(-h.x, 0)) * 0.04f;
result += SSPR_SAMPLE(float2(0,  h.y)) * 0.04f;
result += SSPR_SAMPLE(float2(0, -h.y)) * 0.04f;
#undef SSPR_SAMPLE
return float3(saturate(result), 0.0f, 0.0f);
""".strip()

CARD_COLOR_CODE = r"""
float2 halfTexel = float2(0.5f / 256.0f, 0.5f / 256.0f);
float2 safeUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, safeUV, 0).r;
float edgeDistance = min(
    min(UV.x, 1.0f - UV.x),
    min(UV.y, 1.0f - UV.y));
float edgeMask = smoothstep(0.0f, 2.0f / 256.0f, edgeDistance);
density *= edgeMask;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
float3 color = max(SmokeColor.rgb, 0.0f);
return color * alpha * max(EmissiveStrength, 0.0f);
""".strip()

CARD_OPACITY_CODE = r"""
float2 halfTexel = float2(0.5f / 256.0f, 0.5f / 256.0f);
float2 safeUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float density = Texture2DSampleLevel(
    DensityTexture, DensityTextureSampler, safeUV, 0).r;
float edgeDistance = min(
    min(UV.x, 1.0f - UV.x),
    min(UV.y, 1.0f - UV.y));
float edgeMask = smoothstep(0.0f, 2.0f / 256.0f, edgeDistance);
density *= edgeMask;
density = max(density - max(BlackPoint, 0.0f), 0.0f);
float alpha = 1.0f - exp(
    -max(Extinction, 0.0f) *
    max(DensityScale, 0.0f) *
    density);
return saturate(alpha * max(OpacityScale, 0.0f));
""".strip()


rt_results = {}
for name in RT_NAMES:
    path = FOLDER + "/" + name
    texture = unreal.load_asset(path)
    if not isinstance(texture, unreal.TextureRenderTarget2D):
        raise RuntimeError("Missing M2 RT: " + path)
    properties = {}
    for property_name in ("address_x", "address_y"):
        try:
            texture.set_editor_property(
                property_name,
                unreal.TextureAddress.TA_CLAMP,
            )
            properties[property_name] = str(
                texture.get_editor_property(property_name)
            )
        except Exception as exc:
            properties[property_name] = "unsupported: " + str(exc)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save RT: " + path)
    rt_results[name] = properties

material_updates = {
    "M_SSPR_BlurSmall": {
        "SSPR M2-B fixed 9 tap small blur": SMALL_CODE,
    },
    "M_SSPR_BlurLarge": {
        "SSPR M2-B fixed 13 tap large blur": LARGE_CODE,
    },
    "M_SSPR_SmokeCard": {
        "SSPR M2-C smoke color": CARD_COLOR_CODE,
        "SSPR M2-C smoke opacity": CARD_OPACITY_CODE,
    },
}

lib = unreal.MaterialEditingLibrary
material_results = {}
for material_name, custom_specs in material_updates.items():
    path = FOLDER + "/" + material_name
    material = unreal.load_asset(path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing M2 material: " + path)
    found = {}
    for expression in lib.get_material_expressions(material):
        if not isinstance(expression, unreal.MaterialExpressionCustom):
            continue
        description = str(expression.get_editor_property("description"))
        if description in custom_specs:
            expression.set_editor_property("code", custom_specs[description])
            found[description] = True
    missing = sorted(set(custom_specs) - set(found))
    if missing:
        raise RuntimeError(
            material_name + " missing Custom nodes: " + repr(missing)
        )
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(path, False):
        raise RuntimeError("Failed to save material: " + path)
    material_results[material_name] = sorted(found)

result = {
    "renderTargets": rt_results,
    "materials": material_results,
    "edgeFadePixels": 2.0,
}
print("M2_EDGE_FIX=" + json.dumps(result, sort_keys=True))
