# Kinesis · BACKLOG

## Doing

- [ ] 修复衣摆形变基础：优先在 DCC 将下摆权重分配给现有 `CoatSkirt` 链，并以 Kinesis 自有 Mesh
  重新导入；若改用 Chaos Cloth，则先拆出明确服装 section 再建立碰撞与权重蒙版。
- [ ] 先人工验收 `/Game/Neow/Kinesis/Animation/Preview/PostureMVP/A_Kinesis_PostureMVP_Idle_Anim` 的
  五倍总量与整臂前移版本（Spine/Chest/UpperChest/Neck 本地 Roll 总增量为 `+10/+15/+20/-35` 度，
  左右 Shoulder 本地 Roll 为 `-75/-75` 度、UpperArm 本地 Yaw 为 `+20/-20` 度）；通过后再同步到 Walk_F/Run_F，并将同一上身体态校正扩展到
  所需 Locomotion 子集，再把合格动画接入 `ABP_Kinesis` 的空 `Locomotion` State Machine，保持 AnimBP
  只读 Snapshot。

## Next

- [ ] 冻结目标 PC、主 DCC、必要 UE 插件、Root Motion、Capsule、Movement 参数与 Source Manifest；
  决定是否把 `PHYS_AvatarSample_A` 绑定给主 Mesh。
- [ ] 建立 Preview Map（平地、坡面、台阶、墙角、门、Vault、目标假人）与自动回放骨架，
  输出首份 Trace/回放证据。
- [ ] 为已接通的 Snapshot 增加最小 Debug 输出，只读显示 Movement、Action、Interaction、Target、
  FrameId 和 StateRevision；随后冻结源码管理/LFS 策略并建立首个正式回退提交。

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
