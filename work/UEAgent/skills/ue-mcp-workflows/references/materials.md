# Material Editing SOP

## Build from an audited baseline

1. Duplicate a known material or create a scratch material.
2. Record the original expression count and every material output root that matters.
3. Add and connect nodes using refs returned in the same script when possible.
4. Recompile once after the logical graph mutation.
5. Verify expression count, critical inputs, output roots, parameters, and logs.
6. Keep the production Material Instance or component on its previous material until the new graph passes identity testing.

Do not infer a volumetric or specialized material output from its UI label. Query the original graph's actual property root.

## Discover real pin names

Verified examples from the current UE MCP stack:

```text
VectorParameter full vector output: ""
TextureSampleParameter2D coordinates input: UVs
TextureSampleParameter2D outputs: RGB, R, G, B, A, RGBA
WorldPosition outputs: XYZ, XY, Z
ComponentMask input: None
Saturate input: None
OneMinus input: None
SmoothStep inputs: Min, Max, Value
CloudSampleAttribute output for normalized cloud height: NormAltitudeInLayer
```

Treat this list as version-specific evidence. Re-query when the UE/plugin version changes or a connection fails.

## Add Custom inputs with staged array edits

Verified behavior: `MaterialExpressionCustom` inputs are editable through MCP.

The node starts with one `None` input. Use this exact sequence:

1. Set `inputs` to one element named `A`; do not change array length.
2. Read the complete `inputs` value back.
3. Preserve the full first element, including its nested `input` struct.
4. Append a fully initialized second element named `B`.
5. Set the complete array in a second call.
6. Query `get_expression_input_names`; expect `A`, `B`.
7. Connect sources, set code/output type, recompile, and verify input wiring.

Do not append with only `inputName` fields after the first element has been renamed. The diff engine may interpret the old element as changed during expansion.

Run `../scripts/probe_custom_inputs.py` to revalidate this recipe in isolation.

## Treat semantic outputs separately

Do not mirror wiring into specialized outputs merely because types are compatible. For example, a volumetric conservative-density input represents a sampling bound, not ordinary display density. Audit its invariant and native consumers before modifying it.

## Validate with identities before looks

Use this order:

1. **Identity**: authoring mask or new branch fixed to its neutral value must match the original material.
2. **Single control**: vary only one parameter or channel.
3. **Extreme**: verify zero/one or bypass/on behavior.
4. **Composition**: combine channels only after each one is independently proven.
5. **LookDev**: hand visual controls to the user after structural behavior is trustworthy.

Do not use several extreme overrides at once to attribute a failure.

## Material Instance checks

- Reparent deliberately and verify the new parent.
- List or read parameters after the parent recompiles.
- Verify texture refs and scalar/vector values.
- Compare floats with tolerance.
- Avoid saving the instance or assigning it into a level until the parent material is valid.
