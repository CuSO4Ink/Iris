import json
import unreal


ROOT = "/Game/SSPR_Validation/M2/AnisotropicSplat_V2"
FUNCTION_PATH = ROOT + "/Functions/M3_HQFluidV2/MF_SSPR_MipPyramidDensity"
MATERIAL_PATH = ROOT + "/M_SSPR_AnisotropicSplat_Display"
SYSTEM_PATH = ROOT + "/NS_SSPR_AnisotropicSplat_Main.NS_SSPR_AnisotropicSplat_Main"
SYSTEM_PACKAGE = ROOT + "/NS_SSPR_AnisotropicSplat_Main"
SIMRT_DI_PATH = SYSTEM_PATH + ":NiagaraDataInterfaceRenderTarget2D_0"


STABLE_LOD0_CODE = r"""
// Stable high-quality reconstruction for a Niagara-owned render target.
// All taps explicitly read mip 0. This avoids consuming a mip chain while
// Niagara is regenerating it in the same frame as the sprite renderer.
float2 safeTexel = max(abs(TexelSize), float2(1.0e-7f, 1.0e-7f));
float2 halfTexel = safeTexel * 0.5f;
float2 centerUV = clamp(UV, halfTexel, 1.0f - halfTexel);
float core = max(Texture2DSampleLevel(
    SourceTexture, SourceTextureSampler, centerUV, 0.0f).r, 0.0f);

float smallRadius = max(SmallRadiusPx, 1.0f);
float largeRadius = max(LargeRadiusPx, smallRadius);

// Seven-tap binomial kernel in each axis. The radius parameter denotes the
// complete center-to-edge footprint in source pixels.
float w7[7] = {1.0f, 6.0f, 15.0f, 20.0f, 15.0f, 6.0f, 1.0f};
float smallSum = 0.0f;
float smallWeight = 0.0f;
float2 smallStep = safeTexel * (smallRadius / 3.0f);
[unroll]
for (int sy = 0; sy < 7; ++sy)
{
    [unroll]
    for (int sx = 0; sx < 7; ++sx)
    {
        float2 tapUV = centerUV + float2(sx - 3, sy - 3) * smallStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w7[sx] * w7[sy] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), 0.0f).r;
        smallSum += max(value, 0.0f) * weight;
        smallWeight += weight;
    }
}
float small = smallSum / max(smallWeight, 1.0e-5f);

// Thirteen-tap binomial kernel in each axis for the continuous smoke body.
float w13[13] = {
    1.0f, 12.0f, 66.0f, 220.0f, 495.0f, 792.0f, 924.0f,
    792.0f, 495.0f, 220.0f, 66.0f, 12.0f, 1.0f
};
float largeSum = 0.0f;
float largeWeight = 0.0f;
float2 largeStep = safeTexel * (largeRadius / 6.0f);
[unroll]
for (int ly = 0; ly < 13; ++ly)
{
    [unroll]
    for (int lx = 0; lx < 13; ++lx)
    {
        float2 tapUV = centerUV + float2(lx - 6, ly - 6) * largeStep;
        float valid = step(halfTexel.x, tapUV.x) * step(tapUV.x, 1.0f - halfTexel.x)
                    * step(halfTexel.y, tapUV.y) * step(tapUV.y, 1.0f - halfTexel.y);
        float weight = w13[lx] * w13[ly] * valid;
        float value = Texture2DSampleLevel(
            SourceTexture, SourceTextureSampler,
            clamp(tapUV, halfTexel, 1.0f - halfTexel), 0.0f).r;
        largeSum += max(value, 0.0f) * weight;
        largeWeight += weight;
    }
}
float large = largeSum / max(largeWeight, 1.0e-5f);
return float3(core, small, large);
"""


def find_exact_object(object_class, path):
    for value in unreal.ObjectIterator(object_class):
        if value.get_path_name() == path:
            return value
    return None


def main():
    play_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if play_subsystem.is_in_play_in_editor():
        raise RuntimeError("Refusing to modify published assets while PIE is active")

    function = unreal.load_asset(FUNCTION_PATH)
    material = unreal.load_asset(MATERIAL_PATH)
    system = unreal.load_asset(SYSTEM_PATH)
    if not isinstance(function, unreal.MaterialFunction):
        raise RuntimeError("Missing V2 pyramid-density function")
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Missing V2 display material")
    if not isinstance(system, unreal.NiagaraSystem):
        raise RuntimeError("Missing V2 Niagara system")

    custom_nodes = [
        expression
        for expression in unreal.MaterialEditingLibrary.get_material_function_expressions(function)
        if isinstance(expression, unreal.MaterialExpressionCustom)
    ]
    if len(custom_nodes) != 1:
        raise RuntimeError("Expected exactly one Custom node, found {}".format(len(custom_nodes)))

    function.modify()
    custom_nodes[0].modify()
    custom_nodes[0].set_editor_property("code", STABLE_LOD0_CODE.strip())
    custom_nodes[0].set_editor_property(
        "description", "SSPR stable LOD0 spatial density reconstruction"
    )
    function.set_editor_property(
        "description",
        "SSPR V2: stable high-quality LOD0 spatial reconstruction; mip-bias inputs retained for interface compatibility.",
    )
    unreal.MaterialEditingLibrary.update_material_function(function)
    function_saved = bool(unreal.EditorAssetLibrary.save_loaded_asset(function, False))
    if not function_saved:
        function_saved = bool(unreal.EditorAssetLibrary.save_asset(FUNCTION_PATH, False))

    simrt_di = find_exact_object(
        unreal.NiagaraDataInterfaceRenderTarget2D, SIMRT_DI_PATH
    )
    if simrt_di is None:
        raise RuntimeError("Missing authored SimRT DI: " + SIMRT_DI_PATH)
    simrt_di.modify()
    simrt_di.set_editor_property(
        "mip_map_generation", unreal.NiagaraMipMapGeneration.DISABLED
    )
    simrt_di.set_editor_property(
        "mip_map_generation_type", unreal.NiagaraMipMapGenerationType.LINEAR
    )
    simrt_di.set_editor_property(
        "override_render_target_filter", unreal.TextureFilter.TF_BILINEAR
    )

    applied = bool(unreal.NiagaraScratchPadService.apply_changes(SYSTEM_PATH))
    compile_messages = [
        str(value)
        for value in unreal.NiagaraScratchPadService.get_compile_messages(
            SYSTEM_PATH, False
        )
    ]
    system_saved = bool(unreal.EditorAssetLibrary.save_loaded_asset(system, False))
    if not system_saved:
        system_saved = bool(unreal.EditorAssetLibrary.save_asset(SYSTEM_PACKAGE, False))

    unreal.MaterialEditingLibrary.recompile_material(material)
    material_saved = bool(unreal.EditorAssetLibrary.save_loaded_asset(material, False))
    if not material_saved:
        material_saved = bool(unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False))
    diagnostics = unreal.MaterialNodeService.get_material_diagnostics(MATERIAL_PATH)

    result = {
        "function": function.get_path_name(),
        "functionSaved": function_saved,
        "customCodeLength": len(STABLE_LOD0_CODE.strip()),
        "simRT": {
            "path": simrt_di.get_path_name(),
            "mipGeneration": str(simrt_di.get_editor_property("mip_map_generation")),
            "mipType": str(simrt_di.get_editor_property("mip_map_generation_type")),
            "filter": str(simrt_di.get_editor_property("override_render_target_filter")),
        },
        "niagaraApplied": applied,
        "niagaraCompileMessages": compile_messages,
        "systemSaved": system_saved,
        "materialSaved": material_saved,
        "materialCompiled": bool(diagnostics.is_compiled_ok),
        "materialCompileErrors": [str(value) for value in diagnostics.compile_errors],
    }
    print("V2_STABLE_LOD0_RECONSTRUCTION=" + json.dumps(result, sort_keys=True))
    if (
        not function_saved
        or not applied
        or compile_messages
        or not system_saved
        or not material_saved
        or not diagnostics.is_compiled_ok
        or diagnostics.compile_errors
    ):
        raise RuntimeError("Stable LOD0 installation validation failed: " + repr(result))


main()
