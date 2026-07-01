# AIEffectFoundry · EffectSpec v0

## 目的

定义 AI/MCP 生成普通材质、蓝图、Actor、参数面板和测试场景时的输入格式。

EffectSpec 不是给 AI 自由发挥的 prompt，而是给 AI/MCP 的生产规格。

## 基本结构

字段：name / intent / art_direction(mood, style_keywords, color_palette, material_keywords, avoid) / assets(materials, blueprints, actors, niagara) / parameters(exposed, hidden) / constraints(performance_budget, platform, rendering_path, forbidden_features) / verification(screenshots, checklist) / human_review(required_decisions, rejection_criteria)。

## 字段说明

- name：资产组名称，可读、不绑过窄题材，可作 UE 目录/资源前缀。
- intent：一句话说明这个 spec 要解决什么问题。
- art_direction：记录人的 Art Direction，不是让 AI 决定美术。包含 mood、风格关键词、色板、材质关键词、avoid 列表。
- assets：AI/MCP 需要创建的普通资产（第一版只做常规脚手架，不实现复杂 kernel）。
- parameters：暴露给 LookDev 的参数，命名稳定、范围明确，避免 AI 随机加无意义参数。
- constraints：性能预算、平台、渲染路径、禁用特性（如不允许复杂多层透明排序、无意义 texture sample 堆叠）。
- verification：Verifier 检查项（截图角度、命名、参数、测试 Actor、截图记录）。
- human_review：必须人判断的部分（色彩是否符合 moodboard、是否廉价塑料感、是否保留该变体）与 rejection_criteria（风格漂移、参数不可控、视觉噪声过高、性能失控）。

## 第一版 MCP 生成边界

AI/MCP 可做：创建基础材质图、材质实例、暴露参数、普通 Blueprint/Actor、测试场景、控制面板、截图与日志。

AI/MCP 不负责：高级效果内核实现、最终 Art Direction、最终 LookDev、性能/质量最终判断、自定义引擎渲染路径设计。

## 作品集展示方式

每个 EffectSpec 保留三张证据：Spec 输入、AI/MCP 初版输出、Human LookDev 后版本。证明 AI 是生产助手，人负责方向和质量。
