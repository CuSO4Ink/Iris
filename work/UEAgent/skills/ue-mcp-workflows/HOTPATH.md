# UEAgent hot path

This is the default machine-facing card. Locate the route and execute `compact_context.ps1`; do
not load either file's contents unless that step fails. For `CACHE_READ`, load only this card and
the sidecar view needed for the answer. Do not preload AI-BRIEF, SETUP, LOG, BACKLOG, Core, or every
domain card. Full measurements and rollback are in
[PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

Budget before the MCP result: navigation <=1.5k estimated tokens, live read rules <=4k, mutation
rules <=8k. If a task exceeds the budget, unload on-demand prose before weakening a safety gate.

## Non-negotiable pre-dispatch rules

- Do not send raw JSON through a child `powershell.exe`. Build the complete request as a PowerShell
  object, serialize it with `ConvertTo-Json`, UTF-8/Base64 encode it, and call Gateway with
  `-RequestBase64`. Use `-RequestFile` for large/multiline requests and `-ScriptFile` only for
  Gateway actions that support it; otherwise keep Custom HLSL/code inside the encoded request.
  Never hand-escape `-RequestJson`, `-ArgumentsJson`, or `-ProjectionJson` across a process
  boundary, even for read-only calls.
- A parameter or `ConvertFrom-Json` failure before MCP dispatch is a known pre-dispatch failure.
  UE was not contacted: do not label it `RESULT_UNKNOWN`, claim asset access, or retry a mutation.
- A hash-guarded mutation must derive every expected HLSL/pass hash from one named asset version's
  complete manifest. Never mix historical baselines. On mismatch, stop before the first setter and
  confirm the expected version from recorded source/history; the current live hash alone is not
  authority to update the lock.

## Gate

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <ueAgentRoot>\scripts\compact_context.ps1 `
  -RouteFile <project>\Saved\UEAgent\route.json -AssetPath /Game/... `
  -Domain material -Operation read -ReceiptFile <project>\Saved\UEAgent\doctor.json
```

Default output is compact routing state, not live evidence. Use `-View detail` only for diagnosis.

| Result | Next step |
|---|---|
| `CACHE_READ` | `reflect_cache.ps1 -Action read -View summary`; expand `refs -> detail -> full` only as needed; no MCP if answered |
| `NEEDS_DOCTOR` | run `doctor.ps1 -OutFile <project>\Saved\UEAgent\doctor.json` once; use its receipt directly; no second compact pass |
| `LIVE_READ` | one bounded `ueagent_snapshot`/typed allow-listed live read |
| `LIVE_MUTATE_RELIABLE_QUEUE` | load Skill + Core + one domain card; snapshot, submit, poll receipt, verify |
| `LIVE_SAVE_CAPABILITY_REQUIRED` | call `ueagent_save` only with the verified receipt's exact one-use token/package set |
| `WAIT_RELIABLE_JOB` | poll `ueagent_state`/`ueagent_get_job`; do not bypass the read or performance barrier |
| `BLOCKED` | repair route or request the exact manual UE console step |

## Live call bounds

- Gateway is the only AI-facing client; add `-AutoDaemon` only for repeated calls on that same path.
  Native MCP is the server behind Gateway. If the fixed `ueagent_*` surface cannot express the
  operation, add the typed operation or stop. No alternate client or Python mutation route exists.
  On timeout, poll the same `command_id`; if the receipt is missing, run `ueagent_recover` and read
  back before any retry.
- Model-facing calls provide only `tool`, non-empty `arguments`, and an optional `toolset` or
  `projectionProfile`. Omit action, endpoint, response mode, session, and `structured=true`:
  Gateway infers reliable direct calls, registry calls, toolset describe, data-only output, and
  structured-only transport. Run from the target project root or pass its `-RouteFile`; Gateway
  binds endpoint/session/cache from that route. Discovery without a tool still names its action.
- Across a `powershell.exe` boundary, let the caller serialize that minimal object through
  `-RequestBase64`, `-RequestFile`, or the matching `*File` option; never pass raw JSON through
  command-line strings—the raw JSON switches are intentionally not exposed. A local
  `request_invalid` was not sent and does not invalidate the session or Doctor receipt.
- If the domain/tool is known, skip `toolsets.list`; describe one tool with
  `detail=call`. Use `summary` for routing and `full` only for exact schema validation/recovery.
- Request one projection: `identity`, `topology`, `logic`, `runtime`, `hlsl`, or `changed`.
  Domain aliases (`material.*`, `blueprint.*`, `niagara.*`) are accepted. HLSL/script is explicit.
- Default output removes JSON-RPC/MCP envelopes, duplicate text, positive success flags, a lone
  `returnValue`, empty/derived reliable fields, timings, and fixed-state diagnostic counters;
  nested receipt JSON becomes structured data.
  Safety identity, outcome/effect/verification/persistence, hashes, save tokens, errors, and
  semantic payload values remain exact. Use `-Diagnostics` only for a scoped transport incident;
  ordinary model-facing calls never request raw envelopes.
- Build OCC and protected-field hashes from one bounded live read in the current Editor epoch
  immediately before submit; never mix saved or historical-version hashes. For partial HLSL edits,
  read the target and protected siblings together, then re-read that same set after the receipt.
- Never cache calls or mutations. Discovery/schema cache is valid only for its current session and
  declared expiry.
  Use `ueagent_batch_read` for at most 64 bounded state/snapshot/job/receipt reads; large evidence is
  externalized with SHA-256. Combine only one logical mutation, then verify changed nodes/pins/
  properties plus compile/dirty state from a different signal.

## Invalidation

Discard a Doctor receipt after Editor PID/epoch change, plugin fingerprint change, explicit close,
or an ambiguous transport failure. A normal MCP session replacement does not invalidate a receipt
while that Editor identity still matches. Discard discovery/schema cache after session or toolset
change, or its declared expiry. A mutation timeout does not discard its command identity. A sidecar
describes saved state only; it never satisfies OCC and dirty Editor state always requires a live snapshot.
After rename/delete/cache-generator change:

```powershell
powershell -File <ueAgentRoot>\scripts\reflect_cache.ps1 -Action reconcile `
  -RouteFile <project>\Saved\UEAgent\route.json -Repair
```

The reconciler rehomes only a unique source-hash match and quarantines unresolved sidecars under
`Saved\UEAgent\cache-orphans`; it never deletes them.
