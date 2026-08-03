# Scene Editing SOP

## Establish scope

1. Read current level and editor context.
2. Resolve exact actor/component refs; labels are not identities.
3. For generated content, choose one batch tag, semantic tags, and root Outliner folder.
4. Define the cleanup query before generation.
5. Confirm whether asset save, level save, both, or neither is authorised.

Do not assume blank-level creation exists.

## Mutate actors and components

- Use `ActorTools` for transforms, labels, tags, bounds, hierarchy, and components.
- Use `ObjectTools` for component properties after schema discovery.
- Distinguish actor world transform from component relative transform.
- Read back transform, properties, folder, tags, and components after mutation.
- Use full level-object `refPath` values.

Prefer direct typed actor creation. A real nested
`ProgrammaticToolset → SceneTools.add_to_scene_from_class` call stalled while the direct call
succeeded; batch that path only after an isolated Probe verifies the active build.

For otherwise verified deterministic repetition, one `ProgrammaticToolset` call may return a
compact summary. Never issue concurrent writers against the active level.

## Generate reversible content

Every generated batch needs:

```text
batch tag + semantic tags + root Outliner folder + cleanup query
```

Before deletion, query and report the exact tag/folder scope. Zero Asset Registry referencers is
not sufficient proof that an asset is safe to delete.

## Validate and save

- Change one scene variable at a time and keep a known control for A/B.
- Let shaders and temporal effects settle before comparison.
- Verify technical facts separately from aesthetic approval.
- Asset save never authorises level save; a level save may capture unrelated user changes.
- Report formal saves, Dirty objects, and Autosaves separately.

Do not use Computer Use or mouse automation for Unreal. For selection, editor panels, screenshots,
or aesthetic review, stop and give the user exact manual steps. Prefer the user's live viewport.
