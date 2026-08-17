# codexup

<!-- /project-init --ue inserts the UE marker and UEAgent-first block above this title. -->

## State

`active`

## Goal

- **Problem**: Codex 的长时异步工具默认短等待会反复唤醒模型、重放大上下文并消耗 token。
- **Outcome**: 用短小的全局规则消除已观察到的 Codex 浪费或开发阻力，优先交付可用功能。
- **Smallest working feature**: 一次只上线一条已确认有现实作用的默认规则。

## Implementation

- **Canonical path**: 本目录保存证据与决策；获准的跨项目规则写入 `C:\Users\violinapeng\.codex\AGENTS.md`。
- **Reused foundation**: Codex 原生 `AGENTS.md`、session JSONL 的 `last_token_usage` 与 Python 标准库流式统计。

## Truth

- **Implementation truth**: 全局 `AGENTS.md` 已启用功能优先策略；长时等待规则尚未应用。
- **Runtime / external truth**: 本机 7 天数据确认约 10 秒的外层提前 yield 与短 `functions.wait` 会形成空轮询；官方公开文档未规定这些工具参数的内部默认行为。

## Optimization 001 — Long-running waits

候选全局规则：

```md
## Long-running asynchronous work

For non-interactive long-running work:
- Empty `write_stdin` polls and `functions.wait` MUST use `yield_time_ms >= 180000`; prefer `300000` when intermediate output is unnecessary.
- `functions.exec` MUST set its outer `@exec yield_time_ms` at least `30000` ms beyond the longest nested wait.
- Do not use long waits for non-empty interactive stdin; waits return early on completion.
- Do not wake merely to report unchanged running state.
```

### 2026-08-14 measured evidence

- 范围：排除审计所在当前 session；35 个 session、6.233 GiB JSONL；Codex `0.145.0-alpha.30` 至 `0.147.0-alpha.6.6`。
- `functions.exec`：14,066 次；13,985 次（99.42%）未设置外层 yield。646 次返回 running，其中 589 次（91.18%）无外层设置；返回中位数 11.028 秒。
- `functions.wait`：1,224 次，全部低于 180 秒；yield 中位数 27.5 秒。579 次没有新输出、仅返回仍在运行；最长连续 27 次。
- Token：18,294 个计数轮次共 2,370,491,803；纯等待轮次 152,755,365（6.44%）；确定无信息的空轮询 64,524,595（2.72%）；单 session 最高 31.14%。
- 成本边界：等待输入的 98.64% 为 cached input，原始 token 降幅不能直接等同于账单降幅。
- 兼容边界：本样本没有 `write_stdin`；该条仅为其他 Codex 版本或执行路径保留。

### Source boundary

- [OpenAI Docs — AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：全局文件在 Codex home 中加载，指令链按 run/session 构建；可靠验证应使用新 session，compact 重载没有公开保证。
- [OpenAI Docs — Model guidance](https://developers.openai.com/api/docs/guides/latest-model)：保持提示精简，并用代表性工作负载比较最终质量、token、成本、延迟、调用数和重试数。
- `yield_time_ms` 数值与节约区间是本机实测，不是 OpenAI 官方承诺。

## Optimization 002 — Feature-first development

2026-08-14 已写入全局 `AGENTS.md`，并同步到 Iris 的
[Project Progress Methodology](../../notes/project-progress-methodology.md)：默认先交付最小可用功能，
只修复已观察到或可复现的 bug；只有巨大且难恢复的具体损害才新增特殊控制。项目模板不再
强制 contract、冻结 baseline、Gate 或匹配 A/B。现有安全措施和 UE live-work gate 保留。

## Current Focus

应用 Optimization 001 的候选规则；后续只在正常使用暴露问题时补测或修正。

## Constraints

- 全局提示只保留跨项目、已测量、不可由平台默认可靠覆盖的规则。
- 长等待只用于非交互式异步工作；不得延迟非空 stdin 或用户所需的中间反馈。
- 系统与开发者指令优先于全局 `AGENTS.md`。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/codexup/`.

## Document Map

- `AI-BRIEF.md`: goal and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
