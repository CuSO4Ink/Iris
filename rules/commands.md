# Commands — 斜杠指令协议（L0）

> 用户通过斜杠命令触发固定流程。见到命令按表执行，不要反问。

## 协议

- 命令只在非代码块中的独立行行首触发，例如 `/project DyeSplashBaker`；正文、引用、路径或示例中的 `/xxx` 不触发
- 多个独立命令行按先后顺序执行
- 命令后可带参数，用空格分隔：`/project DyeSplashBaker`
- `/project-init` 支持可选 `--ue` 标记：`/project-init Bifrost --ue`
- `--ue` 只对 `/project-init` 生效；其他未注册参数按未注册指令处理，不猜测含义
- 参数本身含空格时用下划线或驼峰（如 `/project My_Project`），不支持引号
- 未注册的 `/xxx`：回复"未注册指令 `/xxx`，发 `/help` 查看可用指令"，不猜

## 接入与角色类

| 命令 | 参数 | 行为 |
|---|---|---|
| `/general` | — | 按 `templates/Onboarding-General.md` 方框内容执行 |
| `/maintainer` | — | 按 `templates/Onboarding-Maintainer.md` 方框内容执行 |
| `/project` | `<项目名>` | 按 `templates/Onboarding-Project.md` 方框执行，`{项目名}` 替换为参数 |

## 项目生产类

**前提**：除 `/project-init` 外，当前会话已通过 `/project <名>` 接入项目，AI 知道活跃项目。若未接入，其他命令报错"请先 `/project <项目名>` 接入项目"。

| 命令 | 参数 | 行为 |
|---|---|---|
| `/project-init` | `<项目名> [--ue]` | 把 `templates/project-kit/` 下三份模板复制到 `work/<项目名>/`，替换 `{项目名}` 占位符；带 `--ue` 时在 `AI-BRIEF.md` 顶部写入 `<!-- iris-project-kind: ue -->` 和 `work/UEAgent/AGENTS.md` 的标准 UEAgent-first 导航块，报告建成 |
| `/push` | `[一句话]` | git 同步(纯git,不改文档内容): ① 在仓库根 git add -A ② commit(有参数用作message,否则自动"sync: 时间戳") ③ git fetch + 检测落后 → pull --rebase ④ 冲突则停下报告冲突文件不强推 ⑤ 无冲突则 push ⑥ 报告最终状态 |
| `/checkpoint` | — | 收工快照：① 读当天 LOG 新增条目 → 提炼 1~3 条有长期价值的更新到 AI-BRIEF ② 把有长期价值的已完成普通任务提炼进 LOG 后移出 BACKLOG；项目约定保留的状态/验收记录不移动 ③ 报告摘要给用户确认 |

## 帮助

| 命令 | 参数 | 行为 |
|---|---|---|
| `/help` | — | 完整复述本文件所有指令表的三列（命令 / 参数 / 行为），不省略 |

## 扩展

- 新增命令 → 对应分组表加一行
- 保持"命令 → 现有流程"的映射，不在命令层定义新逻辑，逻辑放对应规则文件
- 废弃命令 → 直接从本表及专用文档删除
