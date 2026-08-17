# codexup · LOG

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.

### 2026-08-14 18:09 — [发现] 短等待会放大长上下文 token 消耗
7 天本机样本中，纯等待占总 token 6.44%，确定无信息的空轮询占 2.72%，单 session 可达 31.14%；
等待输入 98.64% 命中缓存，因此 token 降幅与账单降幅必须分开评估。

### 2026-08-14 18:37 — [决策] 默认改为功能优先
全局 Codex 与 Iris 默认先交付最小可用功能，仅为巨大且难恢复的具体损害设置特殊控制；
普通问题在观察到或可复现后修根因，不再强制 contract、baseline、Gate 或匹配 A/B。
