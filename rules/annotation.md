# Annotation callouts

Use native Obsidian callouts when a user and AI collaborate inside Markdown.

| Tag | Meaning | Response |
|---|---|---|
| `[!Q]` | User question | Keep it and append `[!A]` immediately below |
| `[!NOTE]` | User fact or constraint | Apply where relevant; no reply block required |
| `[!TODO]` | User-owned action by default | Track it; execute only when delegated |
| `[!FIX]` | Correction | Fix the document and append `[!FIXED]` immediately below |

```markdown
> [!Q] Question
> — v YYYY-MM-DD

> [!A] Answer
> — ai YYYY-MM-DD
```

Every callout line starts with `>`. Keep a blank line around each block. Never delete the original
`Q` or `FIX`; state changes are append-only. Initial unresolved-item scans may search
`\[!Q\]|\[!FIX\]` and then verify that the next non-empty callout is `A` or `FIXED`.

The four user-side insertion templates remain under `templates/Annotation-*.md`.
