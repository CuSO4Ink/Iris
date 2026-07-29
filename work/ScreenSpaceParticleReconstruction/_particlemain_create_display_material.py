import json
import unreal

FOLDER = "/Game/SSPR_Validation/M2/ParticleTrails"
MATERIAL_PATH = FOLDER + "/M_SSPR_ParticleTrails_Display"

unreal.EditorAssetLibrary.make_directory(FOLDER)
material = unreal.load_asset(MATERIAL_PATH)
created = False
if material is None:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SSPR_ParticleTrails_Display",
        FOLDER,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    created = material is not None
if not isinstance(material, unreal.Material):
    raise RuntimeError("Failed to create particle trajectory material")

lib = unreal.MaterialEditingLibrary
for expression in list(lib.get_material_expressions(material)):
    lib.delete_material_expression(material, expression)

material.set_editor_property(
    "material_domain", unreal.MaterialDomain.MD_SURFACE
)
material.set_editor_property(
    "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT
)
try:
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_UNLIT,
    )
except Exception:
    pass
material.set_editor_property("two_sided", True)
material.set_editor_property("disable_depth_test", True)

default_texture = None
for candidate in (
    "/Engine/EngineResources/Black.Black",
    "/Engine/EngineResources/DefaultTexture.DefaultTexture",
):
    loaded = unreal.load_asset(candidate)
    if isinstance(loaded, unreal.Texture):
        default_texture = loaded
        break
if default_texture is None:
    raise RuntimeError("No engine default texture could be loaded")

texture = lib.create_material_expression(
    material,
    unreal.MaterialExpressionTextureSampleParameter2D,
    -700,
    -50,
)
texture.set_editor_property(
    "parameter_name", "TrajectoryTexture"
)
texture.set_editor_property("texture", default_texture)
try:
    texture.set_editor_property(
        "sampler_type",
        unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )
except Exception:
    pass

screen_position = lib.create_material_expression(
    material,
    unreal.MaterialExpressionScreenPosition,
    -920,
    -50,
)
if not lib.connect_material_expressions(
    screen_position, "ViewportUV", texture, "UVs"
):
    raise RuntimeError(
        "Failed to connect ViewportUV to trajectory texture UVs"
    )

gain = lib.create_material_expression(
    material,
    unreal.MaterialExpressionScalarParameter,
    -480,
    120,
)
gain.set_editor_property("parameter_name", "TrajectoryGain")
gain.set_editor_property("default_value", 1.0)

density = lib.create_material_expression(
    material,
    unreal.MaterialExpressionMultiply,
    -250,
    0,
)
lib.connect_material_expressions(texture, "R", density, "A")
lib.connect_material_expressions(gain, "", density, "B")

color = lib.create_material_expression(
    material,
    unreal.MaterialExpressionVectorParameter,
    -240,
    -190,
)
color.set_editor_property("parameter_name", "SmokeColor")
color.set_editor_property(
    "default_value",
    unreal.LinearColor(0.82, 0.88, 1.0, 1.0),
)

emissive = lib.create_material_expression(
    material,
    unreal.MaterialExpressionMultiply,
    20,
    -90,
)
lib.connect_material_expressions(density, "", emissive, "A")
lib.connect_material_expressions(color, "", emissive, "B")

if not lib.connect_material_property(
    emissive,
    "",
    unreal.MaterialProperty.MP_EMISSIVE_COLOR,
):
    raise RuntimeError("Failed to connect trajectory emissive output")
if not lib.connect_material_property(
    density,
    "",
    unreal.MaterialProperty.MP_OPACITY,
):
    raise RuntimeError("Failed to connect trajectory opacity output")

usage_enabled = False
try:
    usage_enabled = bool(
        lib.set_material_usage(
            material,
            unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES,
        )
    )
except Exception:
    try:
        material.set_editor_property(
            "used_with_niagara_sprites", True
        )
        usage_enabled = True
    except Exception:
        usage_enabled = False

lib.layout_material_expressions(material)
lib.recompile_material(material)
saved = bool(
    unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, False)
)
result = {
    "path": material.get_path_name(),
    "created": created,
    "expressions": len(
        lib.get_material_expressions(material)
    ),
    "usageEnabled": usage_enabled,
    "saved": saved,
}
print(
    "PARTICLE_DISPLAY_MATERIAL="
    + json.dumps(result, sort_keys=True)
)
if not saved or result["expressions"] < 6:
    raise RuntimeError(
        "Particle trajectory material build failed: "
        + repr(result)
    )
