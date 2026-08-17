# Maintainer Rules — L1 维护者准则

> **读者**：执行 vault 治理的 AI；普通项目任务无需读取本目录。
> **关系**：叠加在 L0 之上，不替代 L0。

> ⚡ **动手前必读**：[backup-before-edit](backup-before-edit.md) — 改结构性文件前先备份到 `.workbuddy/backups/<日期>/`

## 职责范围

- 规则治理：`rules/` 下文件的增删改
- 模板治理：维护 `templates/`，分类规则见 [templates/README.md](../../templates/README.md)
- 归档操作：`work/<项目>/` → `archive/<项目>/`，补归档三件套（日期 / 原因 / 后续方案），**格式见 [archive/README.md](../../archive/README.md)**
- 目录地图维护：根 `README.md` 的目录表与实际结构同步

## 不做什么

- 不替项目做技术决策或实施，除非用户在当前请求中明确把项目改动纳入范围
- 治理检查可读项目入口、文档地图和当前状态；与问题无关的技术正文不展开
- 不主动优化项目技术内容，只治理结构、入口和规则

## 与项目实施的边界

- 单一项目技术任务默认走 `/project <名>`
- 用户明确要求跨项目或规则联动时，可在其给定范围内直接执行，无需再次切换角色
- 未明确授权的项目技术改动只报告，不落地

## L1 规则清单

| 文件 | 适用场景 | 摘要 |
|---|---|---|
| [backup-before-edit](backup-before-edit.md) | 改结构性文件前 | 按仓库相对路径备份到 `.workbuddy/backups/<日期>/`，再动手 |
| [progressive-disclosure](progressive-disclosure.md) | 改任何 AI 可见文档前 | 按需暴露、单一真相源、入口从瘦到胖 |

## 维护

- 新增 L1 规则 → 本表登记一行
- 替换 L1 规则 → 同一改动内更新全部有效引用并删除旧规则；历史由 Git 保存
