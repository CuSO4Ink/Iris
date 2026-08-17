# Project Progress Methodology

Default lifecycle for research, visual, and UE projects.

## Durable record

- `AI-BRIEF.md`: goal, project state, current truth, focus, and real constraints.
- `BACKLOG.md`: unresolved executable work only; delete it when empty.
- `LOG.md`: durable decisions, rejections, discoveries, and rollbacks; never an operation stream.

`/checkpoint` is the in-flight sync defined in [Commands](../rules/commands.md). Use it at meaningful
milestones instead of waiting for project close.

## Project states

- `candidate`: a goal exists; execution has not started.
- `active`: the current feature is being built.
- `waiting`: awaiting an external dependency or user decision.
- `blocked`: no useful in-scope progress is currently possible.
- `archived`: no current work.

## Implementation policy

Build the smallest working end-to-end feature from a real entry to an observable outcome, run the
smallest relevant check, then continue. Planning, research, preflight, and documentation must not
displace code execution, simulation, or measurement.

Keep one current path. When replacing an interface, path, rule, or implementation, update its active
callers, checks, and documents in the same change, then delete the superseded path. Do not keep
speculative compatibility layers, aliases, duplicate implementations, or runtime fallbacks. Stop
only if a clean cutover could cross a high-impact boundary such as destroying user-owned data.

Briefly check the repository, standard library, native platform, installed dependencies, and
existing patterns before custom work. Create a module only for a distinct current responsibility;
do not add an interface, factory, adapter, configuration layer, or extension point for one current
implementation or fixed value.

## Delivery loop

1. Choose the next observable piece of functionality.
2. Implement it on the current path.
3. Run one smallest relevant check or direct measurement.
4. Continue; fix observed or reproducible bugs at the root cause.

Do not add speculative hashes, frozen contracts, baselines, gates, or preflight systems. Add a
special control only for a concrete failure that could cause severe, hard-to-recover harm and is
not already covered by Git, versioning, database constraints, types, or ordinary tests. Typical
boundaries are irreversible data loss, serious security or privacy breaches, and uncontrolled
production or external effects. Preserve existing safety controls.

## Artifact boundary

Disposable environments, runs, screenshots, generated evidence, and one-off scripts live under
`tmp/<project-or-task>/`, which Git and Syncthing ignore. Promote only source or final evidence that
the Brief names; delete the rest after use.

## Reuse rule

Do not build a platform before a real task repeats. Extract shared code or an SOP only when the
repeated use makes the shared form smaller than keeping the cases local.
