---
name: ue-mcp-workflows
description: Gate and operate Unreal Engine through UE 5.8 MCP with cache-first reads, live capability discovery, one-writer mutations, independent verification, and explicit save boundaries. Use before any AI task that depends on live UE state or modifies UE content.
---

# UE MCP Workflows

UEAgent is the policy source. A client or target project may contain only a thin route to this
Skill; do not maintain a second copy.

For the token-saving contract and rollback map, use [UEAgent/PROGRESSIVE-DISCLOSURE.md](../../PROGRESSIVE-DISCLOSURE.md).

## Mandatory gate

1. Read [HOTPATH.md](HOTPATH.md) and the target project's `Saved/UEAgent/route.json`.
2. Run `../../scripts/compact_context.ps1 -RouteFile <route> -AssetPath <asset> -Operation <op>`
   (default compact view; add `-View detail` only when required).
3. If the envelope returns `CACHE_READ`, read the sidecar with the progressive views and stop
   before MCP.
4. If it returns `NEEDS_DOCTOR`, run `../../scripts/doctor.ps1 -RouteFile <route>` once and use
   that receipt directly; do not run `compact_context.ps1` again for the same task.
5. Reuse a healthy receipt while the Editor listener PID and MCP session ID stay unchanged. A
   timeout, transport failure, explicit session close, plugin reload, or editor restart requires
   a new doctor; the receipt TTL is only a fallback when identity cannot be checked.
6. Follow the receipt:
   - `HEALTHY`: live reads are available; mutation still needs task capability and authority.
   - `DEGRADED`: cache plus only proven live reads; no mutation or save.
   - `OFFLINE`: local source/cache/config/log analysis only.
   - `BLOCKED`: repair the route/configuration before MCP work.
7. A timeout after a possible mutation is `RESULT_UNKNOWN`: read back before retrying.

For installation or recovery, read `../../SETUP.md`. After the mandatory gate, Gateway is the
default live transport: use `../../scripts/mcp_gateway.ps1` (and `-AutoDaemon` for repeated calls).
The platform/native MCP client is the fallback when the Gateway client/daemon is unavailable,
times out before an operation starts, or lacks a required client-only feature while the receipt is
still healthy. If the endpoint/Editor is unhealthy, repair or remain offline. Both routes use the
same endpoint, schema, authority, one-writer rule, and independent readback; switching transport
never bypasses the receipt or turns a mutation timeout into permission to retry.

On hosts with a trusted native MCP client, direct native transport is an optional performance
override for ordinary calls that do not need Gateway projection/session/debug shaping. Keep the
same receipt, schema, one-writer, and readback rules; do not treat this override as a new backend.

When using Gateway, pass `-SchemaCacheFile <project>\Saved\UEAgent\schema-cache.json`
for discovery-only actions. With a valid project MCP session, entries are session-scoped and are
discarded on session change; TTL remains the fallback when no session identity is available. The
cache never stores tool calls or mutations. For
repeated Gateway calls, also pass `-SessionFile <project>\Saved\UEAgent\mcp-session.json`
`-ReuseSession`; the gateway probes the session before use and rebuilds it after an editor restart.
Keep that file project-local and uncommitted. Use `-CloseSession` only for explicit shutdown.
The sibling `doctor.invalidate.json` is also machine-local and should remain uncommitted.

Use `-Action intent.list -DataOnly` only when the domain or entry tool is unknown. If the project
brief/domain card already identifies the candidate toolset and tool, go straight to a single-tool
`describe_toolset` call; skip `intent.list` and `toolsets.list`. `intent.list` never replaces
`describe_toolset`; verify the selected tool and arguments against the running schema. For saved
sidecars use `summary -> refs -> detail -> full`, and use `reflect_cache.ps1 -Action receipt` after
a save to summarize the cache delta before the independent live readback.

Use `-ProjectionJson`/`-ProjectionFile` on `tool.call`. Gateway/daemon `toolset.describe` defaults
to the structured-only `detail=call` view; use `-DescribeDetail summary` for names/descriptions and
`-DescribeDetail full` only to validate exact JSON Schema. If a host needs warm-call latency close
to a native MCP client,
run the optional `scripts/mcp_gateway_daemon.ps1` on loopback and POST the same request envelope;
the daemon is serialized and must be explicitly shut down. `mcp_gateway.ps1 -AutoDaemon` can warm
that daemon in the background while the first action remains one-shot; later gateway actions use
the warm route automatically. Use `-ProjectionProfile refs|compact` when the caller is feeding
the result directly into model context.
Model-facing success responses are data-only by default. Use `-Envelope` for legacy `{ok, action,
data}` consumers and `-Diagnostics` only for transport/session details. Errors keep a compact
envelope; raw server payloads require diagnostics.

## Load only the relevant rules

For `LIVE_READ`, load only the relevant domain reference after the receipt. For mutation, save,
or an unfamiliar/high-risk operation, also load [references/core.md](references/core.md) and the
target brief:

- Materials, functions, instances, Custom HLSL: [references/materials.md](references/materials.md)
- Blueprints: [references/blueprints.md](references/blueprints.md)
- Niagara: [references/niagara.md](references/niagara.md)
- Actors, components, levels, lighting, viewport: [references/scene-editing.md](references/scene-editing.md)
- Sidecar implementation/freshness/save hooks: [ReflectCache](../../projects/ReflectCache/AI-BRIEF.md)

Do not load the full ReflectCache protocol for an ordinary asset read.

## Execute the routed task

1. For Material, MaterialFunction, MaterialInstance, Blueprint, or Niagara saved-state reads,
   try `<Asset>.uasset.ai.md` first. Stop before MCP when a current recognized cache answers.
2. Read the target project's brief/task documents.
3. Discover the active tool/toolset schema; never guess a tool, UObject property, or graph pin.
4. Read exact asset/object/subobject/level paths and a cheap precondition.
5. Classify the action: read, reversible mutation, or high-risk save/delete/move/merge.
6. Probe an unverified capability outside production assets.
7. Apply one logical mutation with one writer. Prefer direct typed tools. Batch through
   `ProgrammaticToolset` only after that call shape is known safe for the domain.
8. Verify through an independent readback, compile/log result, invariant, runtime result, or
   user-visible check.
9. Clean Probe state and verify `exists=false`.
10. Save only inside the user's explicit boundary; report saved and still-dirty objects.

## Evidence discipline

- **Verified**: isolated or controlled reproduction with postconditions and cleanup.
- **Observed**: real incident without isolated reproduction.
- **Hypothesis**: possible cause; never an SOP.

Record material friction in `../../notes/mcp-pitfalls.md` with provenance. Promote it only
after verification. Structural evidence belongs to AI; aesthetic approval belongs to the user.

Never control Unreal UI through Computer Use. When an editor gesture or visual decision is
required, stop and give the user exact manual steps.

## Bundled tools

- `scripts/probe_custom_inputs.py`: isolated Material Custom-input array verification through
  `ProgrammaticToolset`.
- `../../bp_clipboard_to_ai.py`: compact parser for Blueprint text copied by the user.
