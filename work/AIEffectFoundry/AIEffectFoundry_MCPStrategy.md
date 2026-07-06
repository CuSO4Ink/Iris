# AIEffectFoundry · MCP Strategy

## 核心结论

不绑定任何单一 MCP 实现。走 Spec-first + Adapter 架构：先定义自己的 TA 生产协议，第三方 MCP 先验证流程，UE 官方 MCP 稳定后替换执行层。

## 背景矛盾

出图主线基线为 UE5.8 自定义渲染引擎（v2026-07-06 更新，随 Bifrost 落地确认）。但 UE 官方 MCP 仍不稳定；第三方 MCP 可用但有 API 变动、版本适配、功能覆盖、链路稳定性等风险。所以「引擎基线定在 5.8」与「MCP 执行层不 all-in 任何一家」是两件独立的事——基线已定，MCP 仍走 Spec-first + Adapter 解耦。

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

## UE5.8 基线与 MCP 的角色

引擎基线：UE5.8 自定义渲染即当前出图主线（v2026-07-06 起，作废早期「UE5.5 主线 / UE5.8 仅 preview 观察」的旧决策）。

MCP 执行层仍解耦：官方 MCP 尚不稳定，短期用第三方 MCP / 可控 UE 自动化跑通最小闭环；官方稳定后按 adapter 无痛替换。基线版本与 MCP 供应商是正交的两条决策线，互不绑定。

## 本质澄清

MCP 是可替换执行层；EffectSpec / Action Plan / Verifier / Human Review 才是作品集核心。这不是提示词工程，prompt 只是输入界面。
