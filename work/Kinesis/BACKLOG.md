# Kinesis · BACKLOG

## Doing

- [ ] 修复衣摆形变基础：优先在 DCC 将下摆权重分配给现有 `CoatSkirt` 链，并以 Kinesis 自有 Mesh
  重新导入；若改用 Chaos Cloth，则先拆出明确服装 section 再建立碰撞与权重蒙版。
- [ ] 人工并排验收 `/Game/Neow/Kinesis/Animation/Preview/PostureMVP` 下已同步的 Idle、Walk_F、Run_F：
  Spine/Chest/UpperChest/Neck 本地 Roll 总增量为 `+10/+15/+20/-35` 度，左右 Shoulder 本地 Roll 为
  `-25/-25` 度，UpperArm 本地 Yaw 为 `+20/-20` 度。重点检查 Run 后摆峰值与脚底接触；若仅 Run 有问题，
  只修其动态摆臂。通过后扩展到所需 Locomotion 子集，再将合格动画接入 `ABP_Kinesis` 的空
  `Locomotion` State Machine，保持 AnimBP 只读 Snapshot。

## Next

- [ ] 冻结目标 PC、主 DCC、必要 UE 插件、Root Motion、Capsule、Movement 参数与 Source Manifest；
  决定是否把 `PHYS_AvatarSample_A` 绑定给主 Mesh。
- [ ] 建立 Preview Map（平地、坡面、台阶、墙角、门、Vault、目标假人）与自动回放骨架，
  输出首份 Trace/回放证据。
- [ ] 为已接通的 Snapshot 增加最小 Debug 输出，只读显示 Movement、Action、Interaction、Target、
  FrameId 和 StateRevision；随后冻结源码管理/LFS 策略并建立首个正式回退提交。

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
