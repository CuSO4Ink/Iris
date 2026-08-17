# NPR_rendering BACKLOG

## Doing

- [ ] 重新打开 AbyssEditor 并通过 UEAgent gate，读取
  `T_AvatarSampleA_Shoes_N_Micro_V8_2` 的 GPU 资产预览。若资源异常，修复导入/重建；若资源正常，
  检查并修复已编译的 Micro 采样/合成分支。用同一灯光与机位对比
  `PartNormalStrength=1, MicroNormalStrength=0/1`，修复前保持 Micro 为 0，不修改灯光或 PBR 参数。
- [ ] Micro 分支修复后再验收鞋子 V8.2.1，重点确认前掌、灰色护边和黑色鞋底的连续性，
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
- [ ] 首轮材质通过后创建 `TP_NPR_Clean2Band`、`TP_NPR_GradientSoft`、
  `TP_NPR_HybridPBR`，并逐套静态绑定、编译和回读。
- [ ] 创建只引用、不修改原角色的 `L_NPR_Validation`，完成 Default Lit 两机位、四灯光基线。
- [ ] 按 `SPEC.md` G4–G5 完成匹配 A/B、用户视觉 Gate、GPU/Shader/PSO/纹理审计并决策；
  只有原生路径出现有证据的硬阻塞时才更新规格。

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
