# AIEffectFoundry · MCP Strategy

## 核心结论

不绑定任何单一 MCP 实现。走 Spec-first + Adapter 架构：先定义自己的 TA 生产协议，第三方 MCP 先验证流程，UE 官方 MCP 稳定后替换执行层。

## 背景矛盾

UE5.8 仍是 preview，官方 MCP 不稳定；第三方 MCP 可用但有 API 变动、版本适配、功能覆盖、链路稳定性等风险。两边都不能 all-in。

## 策略

- 短期：用第三方 MCP / 可控 UE 自动化跑通最小闭环。
- 中期：观察 UE 官方 MCP，稳定后做官方 adapter。
- 长期：作品集叙事不写“依赖某 MCP”，而写“我设计了一套 AI-native TA pipeline，MCP 只是执行适配层”。

## 架构分层

EffectSpec / Art Direction Spec → TA Action Plan → MCP Adapter Layer → 执行后端（第三方 MCP / UE 官方 MCP / Python·Editor Utility fallback）→ UE Assets → Verifier / Screenshot / Human Review。

护城河是中间层：TA Action Plan + MCP Adapter Layer。系统不直接对某个 MCP 说话，而是先生成抽象动作，再由 adapter 决定实际怎么执行。

## 第一版最小动作集

CreateMaterial、CreateMaterialInstance、SetMaterialParameter、CreateBlueprintActor、AddComponent、ExposeParameter、PlaceActor、CreateTestMap、TakeScreenshot、ExportLog。

跑通这 10 个动作，AI/MCP 常规生产层即有雏形。

## 可记录性要求

每次 MCP 执行都留：输入 spec、action plan、执行日志、生成资产清单、截图、verifier 结果、人类审查意见。这样从第三方换到官方 MCP 时能复现流程。

## UE5.8 preview 的角色

不作为主线。preview 适合：官方 MCP 观察、新特性探索、小型验证、adapter 兼容性测试。不适合：最终出图主线、长周期场景、深度引擎魔改、唯一依赖。主线短期用稳定环境（UE5.5 自定义渲染）出图。

## 本质澄清

MCP 是可替换执行层；EffectSpec / Action Plan / Verifier / Human Review 才是作品集核心。这不是提示词工程，prompt 只是输入界面。
