# Rules · L0 — 工作区通用规则索引

> ⚡ 最高优先级：先读 [00-canary.ankoha](00-canary.ankoha.md)。

## 分层

| 层 | 位置 | 读者 |
|---|---|---|
| **L0** | 本目录根 | 所有 AI |
| **L1** | [maintainer/](maintainer/README.md) | 维护者 AI |
| **L2** | `work/<项目>/AI-BRIEF.md` | 项目 AI |

## L0 规则清单

| 文件 | 适用 | 摘要 |
|---|---|---|
| [00-canary.ankoha](00-canary.ankoha.md) | 所有回复 | 末尾单独一行 `唔呣。` |
| [commands](commands.md) | 用户发斜杠命令时 | `/general` `/maintainer` `/project` `/check` `/canary` `/help` |
| [annotation](annotation.md) | 所有文档协作 | `[!Q] / [!NOTE] / [!TODO] / [!FIX]` callout 格式 |
| [naming](naming.md) | 新建文件/文件夹时 | 文件名/文件夹名不出现中文，一律用英文命名 |

## 维护

- 新增 L0 规则 → 本表登记
- 规则文件保持小而聚焦（50~150 行）
- 废弃规则 → `archive/rules/<topic>.md`
