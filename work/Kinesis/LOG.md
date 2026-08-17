# Kinesis · LOG

### 2026-08-13 15:33 — [决策] 按 UE 5.8 单主角动画平台立项
以蓝图 v2.0 为当前合同来源；先建立状态安全、连续性和可观察性，再扩战斗深度与少数英雄演出。

### 2026-08-13 15:33 — [决策] 传统 Locomotion 与单一动作权威先行
首期不做完整 Motion Matching；C++ ActionCoordinator 保持唯一真相，MM 只在传统基线后做隔离 A/B。

### 2026-08-13 15:33 — [决策] 初始模块保持一个插件三个边界
只建 `HeroAnimation` 的 `Runtime`、`Editor`、`Tests`；约 20–30 个核心类或职责真正分离后再拆。

### 2026-08-13 16:47 — [决策] 绑定 Abyss 与 Kinesis 资产根
目标工程固定为 Abyss，资产根为 `/Game/Neow/Kinesis`；运行时代码仍进入单一 `HeroAnimation` 插件。

### 2026-08-13 16:47 — [发现] P0 尚无源码回退点
Abyss 当前为无 commit 的 `master`，且 `.uproject` 未跟踪；先建立可回退基线，再进入模块与资产制作。

### 2026-08-13 20:36 — [决策] 首切片不建立空模块
HeroAnimation 当前只建一个 Runtime 模块，开发期测试同置 `Private/Tests`；第一段 Editor-only 代码出现时再拆 Editor 模块。

### 2026-08-13 20:36 — [发现] HeroAnimation 隔离构建与测试通过
Win64 Editor Development、Game Development/Shipping 均成功，快照不变量测试 1/1 通过；实际 Abyss 整目标重链待运行中的编辑器安全关闭。

### 2026-08-13 21:50 — [决策] Kinesis 与 Third Person 模板隔离
运行入口改为独立的 BP_KinesisCharacter、ABP_Kinesis 与 BP_KinesisGameMode；Third Person 模板不承载 HeroAnimation 组件。

### 2026-08-13 21:50 — [否决] 不直接复用 Bifrost 的 SKEL_1 动画
现有测试动画骨架与 AvatarSampleA 不同；女性 Reference/Retarget Pose 通过视觉 Gate 前，Locomotion 保持空骨架而不硬接低质量动画。

### 2026-08-13 22:16 — [决策] 表现系统只保留语义 Cue 接口
连续状态继续由 Snapshot 提供；瞬时表现由 Coordinator 广播 `FHeroPresentationCue`，首版只携带
GameplayTag、Magnitude、SequenceId 与 StateRevision。当前不创建 Presentation Component、Profile、
Niagara/材质/音效依赖或动画到表现的闭环；第一个真实消费者出现时再按需求扩充数据包。

### 2026-08-13 23:20 — [决策] 首批动画复用 UE 原生 IK Retarget 批量导出
`HeroAnimationEditor` 只向 UEAgent 暴露原生 `RunBatchRetarget` 的窄入口，不自建采样或导出管线；
首批仅产出 Idle/Walk/Run/Jump Loop 供女性体态视觉 Gate，验收前不接入 Locomotion。

### 2026-08-13 23:55 — [发现] 首轮视觉 Gate 失败源于错误的重定向基准
女性资产自带 IK Rig 将 Pelvis 指向 `root`，Kinesis Retargeter 又继承了 Manny 源姿势旋转偏移；
首批四条输出作废。修正为从女性 Mesh 原生 Characterize、清空旧 Op/Pose 并自动对齐目标姿势。

### 2026-08-14 15:49 — [决策] 二级运动使用实例级 Post Process override
保留导入 Mesh；Kinesis 自有 Meta/Post AnimBP，角色 Construction Script 调用
`SetOverridePostProcessAnimBP`。直改原生继承组件 CDO 导致的编译/保存循环已撤销，重启后状态为 clean。

### 2026-08-14 17:29 — [发现] 源 VRM 可见衣摆未蒙皮到 CoatSkirt 链
源文件有 80 根 `CoatSkirt` 骨，但衣服 section 对其权重接近零，下装主要由 Hips/UpperLeg 驱动；
Spring 与 Collider 调参不能产生分离，下一修复层级是 DCC 蒙皮或明确切换 Chaos Cloth。

### 2026-08-17 20:18 — [回滚] 统一 Shoulder 基线恢复为 -25 度
用户澄清此前画面的问题来自 Run 而非 Idle；撤销 Idle 的 `-75/-45` 试调，并将 Idle、Walk、Run 统一到
Shoulder `-25/-25`。若 Run 仍过度后摆，只修其动态摆臂，不再改变共享静态体态。

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.
