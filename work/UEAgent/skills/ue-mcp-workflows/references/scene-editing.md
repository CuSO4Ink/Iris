# Scene Editing SOP

## Establish scope

1. Query the current level and viewport/editor context.
2. Identify exact actor/component refs; never rely on labels alone.
3. For generated batches, choose one batch tag, semantic tags, and a root Outliner folder.
4. Define cleanup before generation.
5. Confirm whether the task authorizes asset saves, level saves, or neither.

Default to the currently open level. Do not assume blank-level creation exists.

## Mutate actors and components

- Use ActorTools for actor transform, label, tags, bounds, hierarchy, and component discovery.
- Use ObjectTools for component properties after `list_properties` or a known schema.
- Distinguish actor transform from component relative transform.
- After mutation, read back transforms, properties, folder, tags, and components.
- Use full level-object `refPath` values for actors and components.

For repeated operations, use one `ProgrammaticToolset` script and return a compact summary. Do not issue concurrent writers against the active level.

## Generate reversible content

Every generated actor batch must have:

```text
batch tag + semantic tags + root Outliner folder + cleanup query
```

Before deletion, query the tag/folder and report the exact count and scope. Delete only that scoped set.

## Validate scene behavior

- Use deterministic camera transforms for comparisons.
- Change one parameter or scene variable at a time.
- Let shaders and temporal effects settle before visual comparison.
- Keep a known control actor/material/lighting state for A/B.
- Verify technical facts separately from aesthetic approval.

Ask the user before any viewport screenshot or capture. If the user is in the editor, prefer direct viewport confirmation.

## Save deliberately

- Saving an asset does not authorize saving its level.
- Saving a level can capture unrelated user changes; inspect current scope first.
- Keep preview assignments in Dirty state until reviewed.
- Report which assets and levels were formally saved and which remain in memory or Autosave.
