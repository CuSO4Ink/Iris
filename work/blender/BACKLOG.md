# blender · BACKLOG

## Doing

- [ ] Define the first bounded mutation contracts on the bridge side — create, rename, transform,
  delete — each carrying its own readback, so the slice's create step stops needing `escapeHatch`.
  Grow the set from observed tasks, not from the 15-tool candidate inventory. The job side is already
  bounded; the interactive side is not.

## Next

- [ ] Batch the `convert` kind over the whole Kinesis BVH set and run the channel-matched parity job
  against every file in `tmp/Kinesis/batch-fbx/`. One file is proven equivalent (789/789 fcurves);
  the batch is the actual deliverable, and it is what retires `tmp/Kinesis/bvh2fbx.py`.
- [ ] Promote the bake stage to a bounded kind. `bpy.ops.object.bake` is verified present with all
  twelve bake types, and the car chain just exercised AO plus diffuse color end to end, so the
  postconditions are now known: map type, resolution, sample count and output paths. It currently
  runs as a script job, which is the escape route the kinds exist to replace.
- [ ] Add an animation-render kind only once a real task defines its postconditions. A frame sequence
  is not a single verifiable artifact — it needs frame count plus per-frame existence, which
  `verify_artifacts` cannot express today, so it needs a verifier change, not just a new template.
- [ ] Add progress reporting. Neither route has a progress channel; the job route is the tractable
  one, since a generated kind script can write a progress file the poll already has a place to read.
- [ ] Move the portable Blender out of `tmp/Kinesis/` to a stable home and repoint `BLENDER_PATH`;
  its current location belongs to another project's scratch space and can be cleaned at any time.
- [ ] Add session/epoch identity binding to `route.json`, the way UEAgent binds project and Editor
  identity per session, so a restarted Blender cannot authorise a save from a previous epoch.
- [ ] Write the Blender Skill/AGENTS execution card — the HOTPATH equivalent. It has to cover the
  bridge verbs, the job verbs, and `job_kinds` as the discovery entry, plus the rule for choosing
  between them. Today the gateway's module docstring is the only card, and nothing routes to it from
  `AI-BRIEF.md`.
- [ ] Add `prepare_game_asset` only after the underlying asset-preparation sequence has run end to end
  and its postconditions are known.

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
