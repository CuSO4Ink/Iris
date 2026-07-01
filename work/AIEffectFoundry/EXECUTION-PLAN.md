# AIEffectFoundry 执行流程草案

## 当前决策

采用「系统 + 一个代表场景」路线。

不是围绕某一个具体效果定美术基调，而是先建立一套 AI-native TA 系统，再选择一个代表场景证明系统能落地。

核心结构：

- AI/MCP 常规生产层：负责普通材质、蓝图、Actor、参数面板、测试场景、截图记录。
- 高级效果内核库：负责不可替代的技术深度，如动态表面重建、NNE、3D Gaussian、自定义 NPR、Simulation/Field。
- Art Direction / LookDev 层：负责主题、风格、审美判断、构图、灯光、色彩、最终表达。
- 代表场景：把以上三层组合成一件可展示作品。

## 已有资源

### 1. UE5.5 自定义渲染引擎

- 自定义 Toon / NPR Shading Model、lighting、shadow、rim、outline、tone mapping 等渲染路径改造。
- **已决策：短期作品集出图基线固定为 UE5.5 自定义渲染。** 当前阶段所有可见画面、LookDev、代表场景验证优先在 UE5.5 上完成。
- UE5.8 仍视为 preview / 后续验证分支：只用于观察官方 MCP、新特性与核心能力迁移，不作为当前主线，不阻塞出图。

### 2. 旧版技术拆解素材

- PBF / SPH 软体/流体模拟、Neighbor Grid 3D、SDF 场、Marching Cubes、RDG Compute、ProceduralMesh、海洋/水体、NPR 角色渲染经验。
- 不作为固定美术主题，拆成高级效果内核能力。

### 3. AIEffectFoundry 项目方向

- MCP/AI 负责常规 TA 执行层；用户负责底层效果、验证、Art Direction 与最终表达。
- 走 Human-in-the-loop，而非 AI 自动替代人完成作品。

## 执行流程

### Phase 0：资产盘点与方向锁定

产出文档：

- `AIEffectFoundry_CapabilityMap.md`
- `AIEffectFoundry_KernelBrief_DynamicSurfaceReconstruction.md`
- `AIEffectFoundry_EffectSpec_v0.md`
- `AIEffectFoundry_ExpressionCandidates.md`
- `AIEffectFoundry_MCPStrategy.md`

判断标准：能否服务多个美术主题、是否有作品集展示价值、是否能和 AI/MCP 流程形成对照、是否代表个人不可替代能力。

### Phase 1：建立 AI/MCP 常规生产层

先支持有限范围，不做通用大平台。

优先能力：按 EffectSpec 生成基础材质、材质实例与参数、普通 Blueprint/Actor 脚手架、控制面板/Debug 开关、摆放测试对象、自动截图与日志。

验收：输出可重复、命名目录规范一致、参数接口清晰、有截图日志、人可审核回滚。

### Phase 2：整理高级效果内核库

首批内核：

1. Dynamic Surface Reconstruction Kernel（粒子/场、邻域查询、SDF/密度场、Marching Cubes，可转译多种视觉对象）。
2. NNE Runtime Effect Kernel（多输入状态 → 效果参数/状态输出）。
3. Gaussian / Neural Volume Kernel（体积雾、能量云、扫描残影，先作为前沿视觉模块）。
4. Stylized Rendering Stack（自定义 NPR/Toon/Outline/Light，UE5.5 出图基线，UE5.8 做核心迁移）。

每个 Kernel 记录：解决什么视觉问题、输入输出、可转译对象、Debug view、性能/限制、是否适合第一版代表场景。

### Phase 3：选择代表场景，而不是被技术倒推主题

从 Art Direction 出发筛选。当前重点候选：

- 东方幻想材料工坊 / 灵液场景。
- 科幻生物实验 / 液态金属场景。
- 梦境动态雕塑 / 抽象展厅。

注意：动态表面重建内核服务这些方向，不反过来决定方向。

### Phase 4：做一条垂直闭环 MVP

闭环：Art Direction Spec → AI/MCP Build → Verifier Review → Kernel Integration → Human LookDev → Portfolio Breakdown。

成功标准：有最终画面、有 AI 初版与人工调整对比、有至少一个高级效果内核、有清晰 Human-in-the-loop 流程、有可复用 spec/recipe/checklist。

### Phase 5：作品集包装

页面结构：Final Scene → System Overview → AI/MCP Workflow → Advanced Kernels → Art Direction/LookDev → Human vs AI Responsibility → Future Expansion。

核心叙事：

> 这不是 AI 替我做作品，而是一套 Human-in-the-loop 的未来 TA 工作流。AI/MCP 做可规格化生产，我做底层效果、质量验证和最终美术表达。

## 下一步最小行动

1. 对三个代表场景候选做 moodboard 关键词与画面焦点拆解。
2. 基于 EffectSpec v0 设计第一个 AI/MCP 生成任务。
3. 为 Dynamic Surface Reconstruction Kernel 画一张数据流图。
4. 已完成：短期出图基线已定为 UE5.5 自定义渲染；UE5.8 只做后续核心迁移验证。

