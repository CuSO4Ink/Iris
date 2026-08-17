# AI Effect Foundry · Direction Notes

> **L2 项目方向索引**。配合 AI-BRIEF.md 一起读。

## 当前路线

走「系统 + 一个代表场景」（方案 B）：先建 AI-native TA 系统，再选一个代表场景证明系统能落地。

核心原则：能力服务表达，不让单个技术 demo（如史莱姆）决定整体美术基调。

## 三层结构

- AI/MCP 常规生产层：普通材质、蓝图、Actor、参数面板、测试场景、截图记录。
- 高级效果内核库：动态表面重建、NNE、3D Gaussian、自定义 NPR、Simulation/Field。
- Art Direction / LookDev 层：主题、风格、审美判断、构图、灯光、色彩、最终表达。

## 文档索引

- `EXECUTION-PLAN.md`：分阶段执行流程（Phase 0-5）。
- `AIEffectFoundry_CapabilityMap.md`：现有资源拆成可复用能力。
- `AIEffectFoundry_KernelBrief_DynamicSurfaceReconstruction.md`：首个高级效果内核 brief（流体+Marching Cubes 抽象成动态表面重建，不绑史莱姆）。
- `AIEffectFoundry_EffectSpec_v0.md`：AI/MCP 常规生成输入规范。
- `AIEffectFoundry_ExpressionCandidates.md`：代表场景候选（东方灵液 / 科幻液态金属 / 梦境动态雕塑）。**⚠️ 已归档，被 `work/Bifrost/` 取代（v2026-07-06）**，仅作历史备选记录。
- `AIEffectFoundry_MCPStrategy.md`：MCP-agnostic 策略，第三方先验证、官方稳定后替换。

## 关键决策记录

- **已决策：出图主线基线为 UE5.8 自定义渲染引擎。** （v2026-07-06 更新）随 Bifrost 落地实践确认真实主线已切到 UE5.8——用户调教的 UE5.8 MCP 即在此基线跑通，故基线随之上移。
- 历史：早期（≤2026-07-01）曾以 UE5.5 为短期稳定出图基线、UE5.8 仅作 preview 观察分支；自 2026-07-02 Bifrost 立项起，UE5.8 已成实际出图与 MCP 主线，旧的「UE5.5 主线 / UE5.8 观察」决策作废。
- MCP 不绑单一实现，走 Spec-first + Adapter，第三方先跑通流程。
- 本质是 AI-native TA pipeline 设计，不是提示词工程；技术含量在规格化、执行适配、验证、高级内核、审美决策。
- 旧作品集资源（NPR 渲染、流体/表面重建、海洋、角色材质）拆成能力库，不原样搬运。

## 下一步最小行动

1. 对三个代表场景候选做 moodboard 关键词与画面焦点拆解。
2. 基于 EffectSpec v0 设计第一个 AI/MCP 生成任务。
3. 为 Dynamic Surface Reconstruction Kernel 画一张数据流图。
4. 已完成：出图主线基线已统一为 UE5.8 自定义渲染（v2026-07-06，随 Bifrost 落地切换，作废旧的 UE5.5 主线决策）。

