# UEAgent backlog

Only unresolved work lives here. Completed decisions belong in `LOG.md`.

## P0 — portable capability baseline

- [ ] Abyss target: cold-start the rebuilt editor and smoke-test the reflected Niagara authoring
      surface on the current VibeUE `bf96d6b` baseline; do not mark the route active until that
      live check passes.
- [ ] Run bootstrap + doctor on a clean UE 5.8 machine and record one native-MCP read and one
      authorised reversible mutation with independent readback.
- [ ] Decouple or explicitly parameterize hidden saves in Niagara `ApplyChanges` and VibeUE
      Blueprint property mutation.

## P1 — finish proven read models

- [ ] Validate the packaged save hook on disposable assets for all five cache types, including
      no-op, failure-path, and format-version checks.
- [ ] Add external Niagara script caches only when a real edit needs their internal logic.

## P2 — add only after evidence

- [ ] Add another AI-client rule adapter only when that client is used.
- [ ] Add timing/queue observability only when a concrete performance investigation needs it.
- [ ] Replace packaged source patches with upstream commits only when they are accepted upstream.
