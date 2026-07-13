# Portfolio

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

TA 个人作品集的**总纲枢纽项目**——只负责跨项目编排（叙事主线、呈现模板、收录验收、发布排期），不重做技术。三段内容由三颗"卫星项目"执行，本项目引用并裁决一致性。

## 当前状态

活跃（2026-06-18 启动）。从 `research/TA-Portfolio/portfolio-plan.md` 转正而来。

## 当前焦点

落地"枢纽 + 三卫星"结构：先统一首页 slogan 与"封面→breakdown→性能→一句话总结"四要素呈现模板，再排三段的展示优先级与发布节奏。

## 核心定位（第一性原理）

- **本项目是枢纽，不是执行体**：技术执行在三颗卫星项目里完成，Portfolio 只做编排、裁决、验收、发布。
- **三段递进叙事**：Part 1 立信（硬功底）→ Part 2 立魂（审美内核）→ Part 3 立异（AI 前瞻）。
- 首页 slogan：「我能做出效果（P1）、能解释为什么好看（P2）、还能用 AI 让团队做得更快更新（P3）。」
- **统一呈现四要素**：每个收录项目 = 成品封面 → breakdown 拆解 → 性能数据 → 一句话技术总结。无 breakdown 不收录。
- **工作产出不进个人作品集**：DyeSplashBaker / AirWall 是工作项目，仅作"技术思路来源"，收录项须个人独立重做。

## 枢纽 ↔ 卫星映射

| 作品集段 | 卫星项目（执行体，保持现状） | 本项目对它做什么 |
|---|---|---|
| Part 1 引擎效果功底 | `work/AIEffectFoundry/`（Frontier Effects Lab 线） | 收录验收 + 展示层归类为 P1 |
| Part 2 美术审美 | `archive/AestheticGym/`（07-09 归档暂停，重启见该目录说明） | 从 90 天计划挑 3~4 个代表复刻收录 |
| Part 3 AI×TA | `work/AIEffectFoundry/`（MCP Pipeline 线）+ `work/UEAgent/`（能力背书） | 收录验收 + 展示层归类为 P3 |
| **Part 1 + Part 3 垂直代表作** | **`work/Bifrost/`**（AIEffectFoundry 方向的首个落地实例）| **作 P1+P3 交汇代表作收录**：前沿内核(P1) + 我调教的 UE5.8 MCP 量产流程(P3) 在同一场景里一体落地，是当前唯一真正在产出的可交付物 |

> **边界决策（v2026-06-18，用户选 a）**：`AIEffectFoundry` 一个项目跨 P1+P3 不拆分——其"前沿内核 + AI pipeline"本是一体两面。拆分只在 Portfolio 的**展示层**完成，不动卫星项目的工程边界。

> **Bifrost 升格（v2026-07-06，用户拍板）**：Bifrost 从"方向3的一个小样本"提升为**跨 P1+P3 的垂直代表作**——它把 AIEffectFoundry 的前沿内核(P1) 与 MCP 量产流程(P3) 拧成一个可展示闭环。**Part 3 的收录载体直接指向 Bifrost 的搭建过程**（我调教的 UE5.8 MCP，自有版权可收录），替掉 portfolio-plan 里原先悬空的抽象"个人 AI×DCC 工具 demo"。UEAgent 仍仅作能力背书（工作项目、UE5.7.3、不可收录）。

## 技术栈与硬约束

- 本项目**不写引擎代码 / 不做 shader**，只产出 Markdown 编排文档与发布物料清单。
- 收录前置硬门槛：必须具备 breakdown，否则不收。
- 工作项目（DyeSplashBaker / AirWall / UEAgent 工作部分）只能作技术经验轻引用，不能作主线收录项。
- 发布平台：ArtStation（主）+ 个人站 + 关键项目录屏（B站 / YouTube）。

## 术语表

| 术语 | 含义 |
|---|---|
| **枢纽** | 本 Portfolio 项目，管编排不管执行 |
| **卫星** | AIEffectFoundry / AestheticGym / UEAgent，承载实际技术执行 |
| **Bifrost** | AIEffectFoundry 方向3 的落地实例，作 P1+P3 收录载体；不是新卫星，是方向落地的垂直切片 |
| **四要素** | 封面 → breakdown → 性能 → 一句话总结，收录项统一结构 |
| **收录验收** | 判定某卫星产出是否达到可进作品集的标准 |

## 文档地图

- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水（`/log` 维护）
- `BACKLOG.md` — 待办与三段展示排期
- `portfolio-plan.md` — 三段式叙事详细规划（从 research/ 迁入）

## 协作约定

- 文件改动限定在 `work/Portfolio/` 内；要改卫星项目去对应项目目录。
- 本项目**不复制卫星项目内容**，只引用其相对路径，避免双份维护。
- 跨项目裁决（归类 / 收录 / 优先级）记入本项目 LOG，不污染卫星 LOG。

---

## 维护

- 阶段切换 / 收录项变化 / 发布节奏调整 → 更新本文件
- ≤ 100 行，超了拆到 notes/ 或新文件
- 项目归档时本文件随迁，保留
