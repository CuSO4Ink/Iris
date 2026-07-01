# WorkBuddy — ankoha 的 AI 协作工作区

Obsidian / Markdown，PARA 结构。面向技术方案、调研、项目跟踪。

## 目录地图

| 路径 | 职责 |
|---|---|
| `inbox/` | 未整理投递区 |
| `notes/` | 已整理长期笔记 |
| `research/` | 专题调研 |
| `work/` | 活跃项目（每个项目一个子目录） |
| `archive/` | 已结束 / 废弃项目，与 `work/` 对称 |
| `assets/` | 全局共享资源 |
| `rules/` | 工作区规则 |
| `templates/` | Obsidian 模板 + AI 接入模板 |
| `USAGE.ankoha.md` | 🔒 vault 所有者私人速查卡，**AI 非必要不读** |

## AI 入口（按角色分诊）

⚡ 所有 AI 都必须先读 `rules/00-canary.ankoha.md`。然后按角色：

| 角色 | 入口 |
|---|---|
| 通用协作 | `rules/README.md` |
| 工作区维护者 | `rules/maintainer/README.md` |
| 项目专属 | `work/<项目名>/AI-BRIEF.md` |

一键接入模板见 `templates/Onboarding-*.md`。

## 维护约定

- 新项目进 `work/<项目名>/`，结项整体 `mv` 到 `archive/<项目名>/`
- 目录结构变动 → 同步上表
- 空目录保留 `README.md` 说明用途
