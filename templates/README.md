# templates — 模板目录

扁平放置单文件，成组模板用子目录。按文件名前缀分类。

## 三类

### Annotation-* — Obsidian Templates 插件用

| 文件 | 用途 |
|---|---|
| `Annotation-Q.md` | 问 callout |
| `Annotation-NOTE.md` | 补充 callout |
| `Annotation-TODO.md` | 待办 callout |
| `Annotation-FIX.md` | 纠错 callout |

`Ctrl+Shift+T` 插入，细则见 `rules/annotation.md`。

### Onboarding-* — 人类复制粘贴给 AI 用

| 文件 | 用途 |
|---|---|
| `Onboarding-General.md` | 通用接入 |
| `Onboarding-Maintainer.md` | 维护者接入 |
| `Onboarding-Project.md` | 项目接入（替换 `{项目名}`） |

**不**被 Obsidian Templates 插件加载。复制方框代码块内容即可用。

### project-kit/ — 项目工作台三件套

| 文件 | 复制到 |
|---|---|
| `project-kit/AI-BRIEF.md` | `work/<项目>/AI-BRIEF.md` |
| `project-kit/LOG.md` | `work/<项目>/LOG.md` |
| `project-kit/BACKLOG.md` | `work/<项目>/BACKLOG.md` |

详见 `project-kit/README.md`。通常用 `/project-init` 命令自动化。

## 新增约定

- 单文件模板：必须带类别前缀（`Annotation-` / `Onboarding-` / `Project-` / ...）
- 成组模板：开子目录放一起，带 `README.md` 说明
- 新类别出现 → 本 README 加一类
- 文件数超 15 再考虑拆子目录（Type 2 决策，延后）
