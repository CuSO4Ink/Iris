# Iris

Markdown-based AI collaboration workspace for research, project execution, and durable knowledge.

## Directory map

| Path | Responsibility |
|---|---|
| `AGENTS.md` | Single AI bootstrap and UE live-work gate |
| `inbox/` | Unsorted input; no retention guarantee |
| `notes/` | Durable cross-project knowledge |
| `research/` | Scoped research reports |
| `work/` | Active projects |
| `archive/` | Closed or rejected projects |
| `tmp/` | Local disposable environments and process artifacts |
| `assets/` | Shared durable assets |
| `rules/` | Task-specific rules |
| `templates/` | External onboarding and project templates |

AI starts at `AGENTS.md`; role-specific files are loaded only when routed there. External AI tools
that do not auto-load `AGENTS.md` may use `templates/Onboarding.md`.

New projects enter `work/<project>/`; closed projects move to `archive/<project>/`. Project process
artifacts stay in ignored `tmp/<project-or-task>/` and are deleted when no longer needed.
