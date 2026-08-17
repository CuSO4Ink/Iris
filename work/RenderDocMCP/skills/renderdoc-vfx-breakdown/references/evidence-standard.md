# Evidence standard

## Evidence levels

### Confirmed

Use only when directly supported by one or more of:

- capture/executable metadata;
- pipeline state;
- Shader disassembly or register data flow;
- buffer contents and decoded layout;
- raw texture data;
- before/after target difference;
- pixel history;
- action timings or hardware counters;
- validated round-trip asset counts.

State the event/resource IDs.

### Inferred

Use when several facts support one interpretation but alternatives remain. State the evidence and the strongest alternative.

Example: a 6-index instanced quad with per-instance transforms and a foam-like packed texture is consistent with splash billboards, but the exact artistic label may remain inferred without a named resource or isolated visual result.

### Unconfirmed

Use when the frame cannot distinguish alternatives. Convert the uncertainty into a concrete next test.

## Claim format

Write important conclusions in this shape:

```text
Claim: Event 1234 is the visible splash batch.
Level: confirmed.
Evidence: DrawIndexedInstanced(6, 7); shared billboard VS; GBuffer difference of N pixels; output region matches the splash.
Limits: does not prove the engine-side emitter name.
```

## Common invalid shortcuts

- Resource format alone does not prove semantic meaning.
- Reflection names can be stale or misleading; verify slots and operations.
- A draw with no visible output is not proof that no shader work ran.
- A large instance count is not proof that the batch is visible.
- Event ID order is not necessarily global execution order across command lists.
- A blue-looking texture is not automatically a normal map.
- `discard` plus depth writes is not ordinary alpha transparency.
- A GBuffer writer is not the final-lighting Shader.
- Blender opening an FBX does not guarantee every DCC importer accepts it.

## Visibility terminology

Use these terms precisely:

- `submitted`: command exists in the capture;
- `rasterized candidate`: geometry reached rasterization based on pipeline evidence;
- `shader evaluated`: supported by counters/debug/timing, not assumed from submission;
- `visible output`: verified target/depth pixels changed;
- `zero visible output`: tested targets did not change;
- `not tested`: no valid difference/pixel-history test was performed.

## Performance terminology

Call a draw “potential overhead” when it is submitted but produces zero visible output. Call it “measured waste” only when GPU timing/counters quantify a non-trivial cost and the work is not required for another output or side effect.

## Raw versus presentation evidence

Keep both:

- raw: disassembly, JSON, binary/CSV, raw textures;
- presentation: annotated screenshots, channel sheets, semantic HLSL, tables.

Never overwrite raw evidence with a contrast-stretched or annotated version.
