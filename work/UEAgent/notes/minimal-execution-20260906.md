# Five-boundary execution cutover — 2026-09-06

The user explicitly approved K1–K5 and R01–R25. Protocol 3.0.0 is implemented in the installed
UE 5.8.1 source and portable base/authoring patch sequences. No commits were made; all three
existing Git indexes are byte-equivalent at the staged-entry level to the prior recorded state.
Unrelated dirty work was retained. The test target was UEAgentProbe, not Abyss.

## Final behavior

K1 binds project and editor epoch once per MCP session and checks them at task dispatch.
K2 retains one active mutation until the actual callback finishes. Caller-declared reads can
overlap. K3 compares the canonical actual request, without a digest, and checks writes of the
accepted and terminal records. Generated IDs remain stable across session recovery. K4 performs
one explicit typed readback against the requested expected result. K5 saves the verified task's
exact dirty package set by command ID, preserving pre-existing-dirty opt-in and save generations.
A checked save-start record prevents automatic repetition when a save result is uncertain.

Normal Gateway calls use the task executor. Gateway waits/polls locally and returns the terminal
result. Direct native capabilities remain trusted local APIs; this is not a hostile-client sandbox.

| Approved cuts | Implementation |
|---|---|
| R01–R05 | No automatic pre/post/save snapshots or generic OCC/diff verification. Explicit diagnostic snapshots remain; metadata-only snapshots skip property reflection. One typed readback replaces the separate model verification round. |
| R06–R10 | One execution card and thin navigation. Doctor and unknown-schema discovery are on demand. The model no longer polls each stage. Broad copies/identity/extreme tests apply to structural or difficult-to-reverse work. |
| R11–R13 | No HMAC/nonce/expiry/token table, command/payload/attachment hashes. Exact task records carry save eligibility; ordinary UTF-8/path/size handling remains. |
| R14–R17 | No generated cache/HLSL/file/result hashes or automatic source-hash rename tracking. Cache reconcile reports applicability. Accepted/terminal records replace per-transition journaling; evidence writes are checked. |
| R18–R20 | Removed generic dirty/save auditing, the 46-tool policy and the optional engine authorization delegate. Gateway calls share one executor; caller-declared reads do not wait for the writer. |
| R21–R25 | Removed global profiling freeze and the dedicated profile job. Use normal monitor tools with task-selected warmup/samples. Removed session/schema TTL and per-call daemon ping. Installation checks stay at installation; no extra confirmation for already-authorized reversible tasks. |

Ordinary parsing, resource bounds, loopback/Inbox paths, necessary synchronization, native
compilation, typed pins, same-package scratch ownership and shutdown fixes remain. Save
generations detect intervening saves, not every concurrent manual unsaved edit. Whole-asset
change detection, out-of-scope effect detection and detailed crash-stage reconstruction are
intentionally reduced; no automatic rollback or unconditional exactly-once claim is made.

## Measured and exercised

- Real editor build: `tmp/UEAgent/minimal-execution/build-10.log`, succeeded.
- Native regressions: 3 succeeded, 0 failed (ScratchOwnership, SnapshotIdentity,
  TargetedVerification), `native-report-final/index.json`.
- Transport: 16 groups passed, including bounded JSON/SSE responses, session recovery,
  daemon mismatch/fallback, malformed pre-dispatch requests and exact value shapes.
- Task Gateway: 6 checks passed for value shapes, one identity binding, wrong-project rejection,
  local waiting, save intent and stable generated command IDs.
- Installer: 11 checks passed. Real installed source/default check succeeded. Base and authoring
  packages strictly apply; all 12 repository patches parse with LF endings.
- Blueprint InitialLifeSpan was changed, read back and saved at 12.75. Niagara Spawn Count was
  changed, compiled, read back and saved at 40. Both survived a cold Editor restart.
- Same-ID replay returned the original saved result; different content with that ID failed.
  Wrong readback prevented save; a wrong package assertion failed. An obstructed accepted-record
  path rejected the mutation before dispatch, and the property remained unchanged.
- Final live state had zero dirty packages. Test-owned Editor/daemon processes were closed after
  verification; production project assets were not changed.

A final cache check exposed a pre-existing serialization limitation: FJsonObjectConverter
serialized Niagara instanced input wrappers as empty objects. The existing converter now exports
their concrete struct and value, including nested instanced values. The saved sidecar was checked
for the exact DirectionalBurst / SpawnBurst_Instantaneous / Spawn Count value 40 without hashes.

| Measurement | Result |
|---|---:|
| Kernel lines | 2301 → 1253 |
| Previous four entry documents | 24,525 UTF-8 bytes |
| Current execution card | 2647 UTF-8 bytes |
| Current mandatory card plus navigation | 3101 UTF-8 bytes |
| Automatic mutation snapshots | 0 |
| Targeted readback per verified mutation | 1 |
| Example Blueprint terminal response | 478 bytes |
| Example Niagara terminal response | 548 bytes |

One warm Blueprint mutate/readback/save sample completed in about 0.9 seconds. These are measured
bytes and examples, not billing tokens or a controlled before/after throughput benchmark. Full
artifacts are under `tmp/UEAgent/minimal-execution/`, especially `audit.json`, `final-live.log`,
`cache-values.log`, `transport-tests-final.json`, `install-tests-final.log` and the strict package
results. Abyss still lacks VRM4U and has not been live-verified by this cutover.
