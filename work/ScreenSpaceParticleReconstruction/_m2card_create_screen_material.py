import json
import unreal


FOLDER = "/Game/SSPR_Validation/M2"
SOURCE_MATERIAL_PATH = FOLDER + "/M_SSPR_SmokeResolve"
CARD_MATERIAL_PATH = FOLDER + "/M_SSPR_SmokeCard"
CARD_INSTANCE_PATH = FOLDER + "/MI_SSPR_SmokeCard_Default"

source_material = unreal.load_asset(SOURCE_MATERIAL_PATH)
if not isinstance(source_material, unreal.Material):
    raise RuntimeError("Smoke Resolve source material is missing")

material = unreal.load_asset(CARD_MATERIAL_PATH)
material_created = False
if material is None:
    if not unreal.EditorAssetLibrary.duplicate_asset(
        SOURCE_MATERIAL_PATH,
        CARD_MATERIAL_PATH,
    ):
        raise RuntimeError("Failed to duplicate Smoke Card material")
    material = unreal.load_asset(CARD_MATERIAL_PATH)
    material_created = True
if not isinstance(material, unreal.Material):
    raise RuntimeError("Smoke Card material is missing or invalid")

lib = unreal.MaterialEditingLibrary
expressions = list(lib.get_material_expressions(material))
custom_nodes = {
    str(item.get_editor_property("description")): item
    for item in expressions
    if isinstance(item, unreal.MaterialExpressionCustom)
}
required_custom = (
    "SSPR M2-C smoke color",
    "SSPR M2-C smoke opacity",
)
if any(name not in custom_nodes for name in required_custom):
    raise RuntimeError("Smoke Card material is missing Resolve custom nodes")

for expression in expressions:
    if isinstance(expression, unreal.MaterialExpressionTextureCoordinate):
        lib.delete_material_expression(material, expression)

screen_position = None
for expression in lib.get_material_expressions(material):
    if isinstance(expression, unreal.MaterialExpressionScreenPosition):
        screen_position = expression
        break
if screen_position is None:
    screen_position = lib.create_material_expression(
        material,
        unreal.MaterialExpressionScreenPosition,
        -1080,
        -100,
    )

for description in required_custom:
    if not lib.connect_material_expressions(
        screen_position,
        "ViewportUV",
        custom_nodes[description],
        "UV",
    ):
        raise RuntimeError("Failed to connect ViewportUV to " + description)

material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
try:
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_UNLIT,
    )
except Exception:
    pass
material.set_editor_property("two_sided", True)
material.set_editor_property("disable_depth_test", True)
lib.layout_material_expressions(material)
lib.recompile_material(material)
if not unreal.EditorAssetLibrary.save_asset(CARD_MATERIAL_PATH, False):
    raise RuntimeError("Failed to save Smoke Card material")

instance = unreal.load_asset(CARD_INSTANCE_PATH)
instance_created = False
if instance is None:
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_SSPR_SmokeCard_Default",
        FOLDER,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    instance_created = True
if not isinstance(instance, unreal.MaterialInstanceConstant):
    raise RuntimeError("Smoke Card material instance is missing or invalid")
instance.set_editor_property("parent", material)
for parameter_name, value in {
    "Extinction": 2.6,
    "DensityScale": 1.0,
    "OpacityScale": 0.82,
    "EmissiveStrength": 1.0,
    "BlackPoint": 0.015,
}.items():
    lib.set_material_instance_scalar_parameter_value(
        instance,
        parameter_name,
        float(value),
    )
lib.set_material_instance_vector_parameter_value(
    instance,
    "SmokeColor",
    unreal.LinearColor(0.62, 0.72, 0.82, 1.0),
)
if not unreal.EditorAssetLibrary.save_asset(CARD_INSTANCE_PATH, False):
    raise RuntimeError("Failed to save Smoke Card material instance")

result = {
    "material": {
        "path": material.get_path_name(),
        "created": material_created,
        "expressions": len(lib.get_material_expressions(material)),
        "disableDepthTest": bool(
            material.get_editor_property("disable_depth_test")
        ),
    },
    "instance": {
        "path": instance.get_path_name(),
        "created": instance_created,
        "parent": instance.get_editor_property("parent").get_path_name(),
    },
}
print("M2CARD_MATERIAL=" + json.dumps(result, sort_keys=True))
