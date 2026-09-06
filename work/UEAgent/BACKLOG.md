# UEAgent backlog

Only unresolved work lives here. Completed decisions belong in `LOG.md`.

## P1 — finish proven read models

- [ ] Re-bootstrap Abyss. The rebuilt Niagara authoring composite is packaged but not installed on
      the only live target, so the four new ops, `RefreshModuleCallNodes`/`RemoveScratchPin` and K02
      are not in its editor. Its `route.json` is stale four ways and `-CheckOnly` now fails on the
      first; two of those drifted before this rebuild, from other sessions' uncommitted edits to
      `ue58-niagara-toolsets.patch` and the engine authoring patch. The VibeUE checkout is 32 files
      dirty, so this needs `-PreserveExistingVibeUE` and an explicit `-Endpoint`, then an
      AbyssEditor rebuild.
- [ ] Validate the packaged save hook on disposable assets for all five cache types, including
      no-op, failure-path, and format-version checks.
- [ ] Add external Niagara script caches only when a real edit needs their internal logic.

## P2 — add only after evidence

- [ ] Decide whether the `niagara-toolsets` capability profile still earns its place. Its
      non-self-sufficiency is now code-enforced (`requires: ["niagara-authoring"]`, so
      `-ApplyEngineNiagaraPatch` alone throws instead of relying on a `warning` string nothing
      read), but that leaves it a no-op alias: its one patch already ships in the niagara-authoring
      apply list, and no target declares the capability. Deleting it would also remove the
      `-ApplyEngineNiagaraPatch` switch and the only consumer of the `requires` mechanism.
- [ ] Decide whether to list `NiagaraToolsets` getters in `[UEAgent.Reliable] ReadOnlyTools` so pure
      reads skip the mutation queue. Config-only and no rebuild, but needs an editor restart, and it
      relaxes a gate - only do it for reads verified free of `Modify`/transaction/dirtying.
- [ ] Add another AI-client rule adapter only when that client is used.
- [ ] Add timing/queue observability only when a concrete performance investigation needs it.
- [ ] Replace packaged source patches with upstream commits only when they are accepted upstream.
