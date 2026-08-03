# UEAgent backlog

Only unresolved work lives here. Completed decisions belong in `LOG.md`.

## P0 — portable capability baseline

- [x] Harden the long-lived Gateway daemon for daemon-first use: cancel timed-out HTTP reads,
      dispose request/context streams, cap request/response bytes, bind lifetime to the UE session,
      and recycle on a memory/request budget. One-shot/native MCP remain failure fallbacks. Verified
      with temporary guarded daemons; details in `LOG.md`.
- [ ] Rebuild and live-probe the packaged advanced Niagara authoring profile; until then,
      `RequestNewTypedPin`/SimulationStage mutation remains task-gated and unverified.
- [x] Rebuild the UE v2+v3 MCP tool-search patches and live-probe `detail=call`; v3 is loaded in
      Abyss and the raw response is structured-only. The effect classifier was corrected to use
      the tool leaf name, so `get_expressions` reports `read` instead of matching `editor`.
- [ ] Run bootstrap + doctor on a clean UE 5.8 machine and record one native-MCP read and one
      authorised reversible mutation with independent readback.
- [ ] Decouple or explicitly parameterize hidden saves in Niagara `ApplyChanges` and VibeUE
      Blueprint property mutation.

## P1 — finish proven read models

- [ ] Validate the packaged save hook on disposable assets for all five cache types, including
      no-op, failure-path, and format-version checks.
- [ ] Handle asset rename/delete orphan sidecars.
- [ ] Add external Niagara script caches only when a real edit needs their internal logic.

## P2 — add only after evidence

- [ ] Add another AI-client rule adapter only when that client is used.
- [ ] Add timing/queue observability only when a concrete performance investigation needs it.
- [ ] Replace packaged source patches with upstream commits only when they are accepted upstream.
