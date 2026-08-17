# blender · BACKLOG

## Doing

- [ ] Run the disposable vertical slice through `blender-ai-mcp` `llm-guided`: status/goal -> create
  -> inspect/measure/assert -> capture -> save; record calls, latency, and exposed tool definitions.

## Next

- [ ] Try `glonorce/Blender_mcp` on the same slice only if the guided baseline lacks a required
  operation; compare behavior, not advertised feature count.
- [ ] Choose the reused baseline from live evidence, then define only the public contracts used by
  the slice. Treat the proposed 15 tools as a candidate inventory, not a v1 quota.
- [ ] Add a `--background` CLI job for the first real blocking workflow and verify its output artifact
  by reopening or inspecting it.
- [ ] Add `prepare_game_asset` only after the underlying asset-preparation sequence has run end to end
  and its postconditions are known.

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
