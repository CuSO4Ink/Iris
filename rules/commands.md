# Commands

A command triggers only at the start of a standalone, non-code-block line. Run multiple command
lines in order. Unknown commands return `未注册指令 /<name>，发 /help 查看可用指令`.

## Routing

| Command | Argument | Behavior |
|---|---|---|
| `/general` | — | Use `rules/README.md` and the root `README.md` |
| `/maintainer` | — | Read and follow `rules/maintainer/README.md` |
| `/project` | `<name>` | Enter `work/<name>/`; execute a UEAgent-first block before reading project content |

## Project lifecycle

Except `/project-init`, these commands require an active project. Arguments containing spaces use
underscores or camel case; quoted arguments are unsupported.

| Command | Argument | Behavior |
|---|---|---|
| `/project-init` | `<name> [--ue]` | Copy the three project-kit Markdown templates to `work/<name>/`; `--ue` adds the canonical UE marker and UEAgent-first block |
| `/checkpoint` | — | Flush verified progress from the current session into every project actually touched |
| `/push` | `[message]` | Run `iris-sync.ps1` for the active project plus explicitly touched shared paths; never stage the repository root |

### `/checkpoint`

Treat it as an in-flight sync point, not a completion review: when invoked, update immediately from
the evidence available at that moment, then continue the original task. Do not wait for project
completion.

Use the current conversation, tool results, actual workspace state, and existing project documents
as sources. For each project actually touched:

1. Update `AI-BRIEF.md` with the current state, focus, and verified facts.
2. Update `BACKLOG.md` so it contains only unresolved, executable work.
3. Append only durable decisions, discoveries, rejections, and rollbacks to `LOG.md`.
4. Report what changed; write nothing when there is no material progress.

It does not commit or push Git, archive a project, delete process files, modify technical assets,
or grant user acceptance.

### `/push`

Invoke `iris-sync.ps1 -Paths <active-project>[,<explicit-shared-path>...]`. The script validates
the scoped project boundary, refuses an empty or repository-wide scope, and aborts on any Git
failure. `/push` synchronizes existing scoped work; it does not edit project documents.

## Help

| Command | Argument | Behavior |
|---|---|---|
| `/help` | — | Reproduce all command tables from this file |
