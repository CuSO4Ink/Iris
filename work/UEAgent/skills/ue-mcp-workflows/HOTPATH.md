# UEAgent task entry

Locate `<Project>/Saved/UEAgent/route.json`. Saved-state questions may use a current sidecar;
`compact_context.ps1` returns CACHE_READ or LIVE_CALL. For live work pass the route directly to
`scripts/mcp_gateway.ps1`. Gateway binds project/Editor identity once per MCP session, executes
and waits locally. Doctor is an on-demand diagnostic, not a normal task prerequisite.

Build JSON from objects. Across child PowerShell use UTF-8 RequestBase64 or RequestFile.
Never hand-escape JSON. A local parse failure did not contact UE.

Normal requests: `toolset`, `tool`, `arguments`, and explicit `readOnly=true` for queries.
Mutations use a stable `commandId`, exact `scopes`, optional `readback`, and `save=true` when
authorized. A readback is one typed target (`target_type`, `toolset_name`, `tool_name`,
`arguments`) plus `expect`: object fields match a subset, arrays exactly, numbers within 1e-6.
Save requires a passing readback. Discover unknown schemas only when needed. Ordinary reads are
caller-declared trusted operations, not a security sandbox.

Five execution responsibilities: project/epoch binding; one writer; command-ID replay with
canonical request comparison and checked accepted/terminal records; one targeted readback;
exact task-owned save packages. There are no automatic mutation snapshots, OCC, payload hashes,
HMAC save tokens, or out-of-scope event auditing. Explicit diagnostic snapshots remain available.

Default calls wait locally and return a terminal result. `wait=false` returns a task ID for long
work. On an ambiguous transport failure query that same command ID; never automatically resend.
`ueagent_save` accepts `command_id`, not a token. Pre-existing dirty packages need explicit
`allowPreexistingDirtySave=true`. A failed verification cannot save. A previous Editor epoch
cannot authorize a new save. No automatic rollback is promised; concurrent manual edits in the
same package can escape detection after the removal of whole-object snapshot comparisons.

Read only the relevant domain card for unfamiliar work. Compilation and targeted runtime
readback are actual task work. Broad duplication/identity/extreme testing is for structural or
hard-to-reverse changes, not mandatory for every scalar edit. Keep known Niagara ownership,
typed-pin, compilation and shutdown fixes. Use real frames for GPU/runtime observation.

No Computer Use driving Unreal UI. User authorization persists; do not add confirmation for
ordinary reversible edits. Saved caches never represent dirty Editor state. Installation checks
belong to installation/upgrade; preserve unrelated source and index changes.
