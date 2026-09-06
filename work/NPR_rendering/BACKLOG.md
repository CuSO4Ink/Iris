# NPR_rendering BACKLOG

## Doing

- [ ] 皮肤 SSS 单次 Probe（用户 2026-08-27 批准）：新建 `M_NPR_CharacterSkin`（Substrate Slab +
  复用 `SP_AvatarSample_A` SubsurfaceProfile），只切换 `MI_N00_000_00_Face_00_SKIN__Instance_`
  做同机位同灯光 A/B；通过用户视觉 Gate 后再推广到 Body，失败则删除 Probe 回退 Toon。
  Toon BSDF 无 SSS 输入（源码已确认），SSS 只有 Slab 路径，皮肤因此脱离 Toon 母材。
- [ ] 以 `MicroNormalStrength=0` 为接受状态验收鞋子 V8.2.1（用户已确认变黑不再出现，根因排查
  关闭，不再恢复 Micro），重点确认前掌、灰色护边和黑色鞋底的连续性，
  并覆盖 Close、Gameplay Medium、Full Body 三个距离。
- [ ] 为大 Guard、厚 Strap/锚点、Outsole/Heel 宏观层和改变轮廓的 Hardware 建立实例级轮廓，执行
  “细分/重拓扑 → 贴合 → Solidify/Bevel → Skin Weight Transfer”；当前环境未安装 Blender，
  不手写第二套重拓扑器。
- [ ] 补齐用户目标参考图，并冻结平台/RHI、输出设置和 Toon 增量 GPU 预算；确认源 VRM 无切线
  在目标动画和远近景下是否构成问题。

## Next

- [ ] 视觉 Gate 只允许在合理范围内微调四个强度；需要远高于 1 时退回修正贴图生成或导入设置，
  不以过强法线掩盖结构缺失。
- [ ] 用通过 Gate 的“多视角语义 → PartID → MaterialID → Meso → Micro → PBR”规则复核其余
  10 个服装槽；不恢复 NMR 或共享 Detail Normal。
- [ ] 正式 Cook 前重建鞋实例的 Material Texture Streaming Data，确认派生表只引用当前 V8_2 Meso、Micro、P，
  再完成纹理驻留与 mip 密度审计；当前不运行会波及全项目材质的无过滤重建。
- [ ] 首轮材质与 SSS Probe 通过后创建 `TP_NPR_Clean2Band`、`TP_NPR_GradientSoft`、
  `TP_NPR_HybridPBR`，并逐套静态绑定、编译和回读；Ramp 效果评估与 Profile 调优随该项进行。
- [ ] 创建只引用、不修改原角色的 `L_NPR_Validation`，完成 Default Lit 两机位、四灯光基线。
- [ ] 按 `SPEC.md` G4–G5 完成匹配 A/B、用户视觉 Gate、GPU/Shader/PSO/纹理审计并决策；
  只有原生路径出现有证据的硬阻塞时才更新规格。

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
