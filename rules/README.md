# Rules

`AGENTS.md` is the only bootstrap. Load these rules only when the task needs them.

| Layer | Location | Purpose |
|---|---|---|
| L0 | `rules/` | Shared command, naming, and annotation rules |
| L1 | `rules/maintainer/` | Workspace governance |
| L2 | `work/<project>/AI-BRIEF.md` | Project goal and current state |

## L0 rules

| File | Use when |
|---|---|
| [commands](commands.md) | A registered slash command is invoked |
| [annotation](annotation.md) | Editing collaborative Markdown callouts |
| [naming](naming.md) | Creating or renaming files and directories |

Add a rule only when an existing source cannot own the behavior. When a rule is replaced, update
all active references in the same change and delete the obsolete rule; Git owns its history.
