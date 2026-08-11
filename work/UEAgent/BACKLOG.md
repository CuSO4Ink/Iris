# UEAgent backlog

Only unresolved work lives here. Completed decisions belong in `LOG.md`.

## P0 — portable capability baseline

- [x] Harden the long-lived Gateway daemon for daemon-first use: cancel timed-out HTTP reads,
      dispose request/context streams, cap request/response bytes, bind lifetime to the UE session,
      and recycle on a memory/request budget. One-shot/native MCP remain failure fallbacks. Verified
      with temporary guarded daemons; details in `LOG.md`.
- [x] Rebuild and live-probe the packaged advanced Niagara authoring profile. Bootstrap now
      applies it with `-ApplyNiagaraAuthoringProfile`; the route and doctor gate the matching
      `RequestNewTypedPin`/SimulationStage authoring surface.
- [ ] Abyss target: cold-start the rebuilt editor and smoke-test the reflected Niagara authoring
      surface on the current VibeUE `bf96d6b` baseline; do not mark the route active until that
      live check passes.
- [x] Rebuild the UE v2+v3 MCP tool-search patches and live-probe `detail=call`; v3 is loaded in
      Abyss and the raw response is structured-only. The effect classifier was corrected to use
      the tool leaf name, so `get_expressions` reports `read` instead of matching `editor`.
- [ ] Run bootstrap + doctor on a clean UE 5.8 machine and record one native-MCP read and one
      authorised reversible mutation with independent readback.
- [ ] On one compatible prebuilt UnrealMCP project, run the `project-unrealmcp-readonly` bootstrap
      and live doctor path, record the exact six-tool allow-list plus one `get_project_info` read,
      and confirm the receipt remains `DEGRADED` with mutation/save blocked.
- [ ] Decouple or explicitly parameterize hidden saves in Niagara `ApplyChanges` and VibeUE
      Blueprint property mutation.

## P1 — finish proven read models

- [ ] Validate the packaged save hook on disposable assets for all five cache types, including
      no-op, failure-path, and format-version checks.
- [x] Add bounded live intent projections (`identity`, `topology`, `logic`, `runtime`, `hlsl`,
      `changed`) with Material/Blueprint/Niagara aliases; explicit projections remain available.
- [x] Add cache lifecycle reconciliation: recognized-format checks, source-hash rename repair,
      orphan quarantine, and a project-local cache manifest. Dirty Editor state remains live-only.
- [ ] Add external Niagara script caches only when a real edit needs their internal logic.

## P2 — add only after evidence

- [ ] Add another AI-client rule adapter only when that client is used.
- [ ] Add timing/queue observability only when a concrete performance investigation needs it.
- [ ] Replace packaged source patches with upstream commits only when they are accepted upstream.
