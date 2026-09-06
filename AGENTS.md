# Iris agent bootstrap

Use the repository root as truth; this file is the workspace bootstrap.

## Always on

- End natural-language responses with `唔呣。` on a separate final line; tool-only, pure-code
  and pure-data responses are exempt.
- Use English file and directory names; see `rules/naming.md`.
- UE source branches use `Aether/` unless the user specifies otherwise.
- Preserve unrelated dirty work and existing safety controls.
- Read `USAGE.ankoha.md` only when explicitly requested.
- Disposable environments, evidence, screenshots, runs and one-off scripts belong under
  `tmp/<project-or-task>/`, not `work/`.

## Task routing

Read relevant instructions once; revisit them when changed or needed to resolve uncertainty.

- Slash commands: `rules/commands.md`. `/checkpoint` records verified progress for touched
  projects; it does not commit, archive or clean files.
- Governance: `rules/maintainer/README.md` and references applicable to the change.
- Projects: `work/<project>/AI-BRIEF.md` for context and constraints; relevant `BACKLOG.md`
  entries for task selection or continuation; `LOG.md` when history matters.
- Implementation, architecture and lifecycle decisions follow `notes/project-progress-methodology.md`.
- Navigation when needed: `rules/README.md` and root `README.md`.

## Completion

Carry implementation through execution, observation, fixes and relevant verification within
the user's scope. An explicit proposal or review request ends with the reviewable result.
Resolve routine reversible choices from context; retain existing authorization. When a local
instruction requires a pause, cite its file and requirement and continue independent authorized work.

## Unreal

Use `work/UEAgent/AGENTS.md` -> HOTPATH -> target route -> Gateway. HOTPATH defines request
encoding, execution and save boundaries. Offline source/config/cache/log analysis needs no
live call. Doctor is diagnostic only; do not add project-specific MCP gates or drive Unreal UI
with Computer Use. Ordinary reversible work needs no renewed confirmation.
UE project briefs link to UEAgent before execution instructions. Use `/project-init <name> --ue`
for new UE projects and retain the UE kind marker.
