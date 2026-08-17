<!-- iris-project-kind: ue -->
# Kinesis

> **UEAgent first.** Before reading or changing live Unreal state, read
> [UEAgent](../UEAgent/AGENTS.md) and the
> [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md), then locate the target project's
> `Saved/UEAgent/route.json` and run `compact_context.ps1` without loading either file unless it fails. Stop on `CACHE_READ`; on
> `NEEDS_DOCTOR`, run the routed `doctor.ps1` once and use its receipt. Offline
> source/cache/config/log analysis may skip MCP but must not claim live Editor state.

## State

`active`

## Contract

- **Problem**: 单主角动作 RPG 的移动、交互、战斗、受击和演出若各自维护状态与过渡，
  会产生脚滑、Root/Capsule 跳变、Montage 死锁、无限 Warping 和不可解释的中断。
- **Goal**: 基于 Unreal Engine 5.8，为唯一主角建立可长期扩展的动画“操作系统”，并最终交付
  15–25 分钟、目标 PC 单机 60 FPS 的商业级垂直切片；固定范围为 1 名主角、1 套主武器、
  6 类环境交互、30–50 个有效 Action、2 个普通敌人原型、1 个 Boss、至少 5 个英雄动作与
  2–4 分钟实时剧情。
- **Non-goals**: 首期完整 Motion Matching；运行时生成核心攻击；MimicKit/ProtoMotions 主线；
  多可玩角色、多独立武器、联机预测、跨平台最低规格、任意物体/高度自动交互、双 DCC 生产线，
  以及由 Notify、Montage、AnimBP 或 GAS 维护第二份动作真相。
- **Mature baseline / proven pattern**: UE 5.8 原生 Gameplay Tags/GAS、Motion Warping、IK Rig、
  Control Rig、FBIK、Smart Objects、Data Validation；ALS 只学问题拆解，Lyra 学线程安全数据与
  Linked Layers，GASP 学 Trajectory/Pose Search；第一版采用可控的传统 Locomotion。
- **Smallest end-to-end pass**: `Light_01` 从输入进入唯一 ActionCoordinator，经阶段、Root/Target、
  Hit、Reaction、Camera/VFX/SFX 与 Continuity Bridge 安全恢复控制，并留下 Debug、回放与测试证据。
- **Pass**: 垂直切片从探索、Traversal、战斗、Boss 到演出无隐藏状态重置；6 类交互共用协议；
  5 个英雄动作达到 Q5、普通动作/受击达到 Q3/Q4；命令行验证可运行；目标 PC 60 FPS 且降级可用。
- **Stop / rollback**: 任一月度 Gate 不通过就停止扩动作/交互/效果，回到最近已验证基线修复；
  两周无未经剪辑的可玩闭环即缩减范围。不得用兼容层保留失败路线。

## Implementation

- **Canonical path**: 目标工程为 `D:/Work/Personal/Project/Abyss/Abyss.uproject`；资产根为
  `/Game/Neow/Kinesis`，后续运行时代码以 `Plugins/HeroAnimation/` 为唯一实现入口；
  `work/Kinesis/` 只保存项目契约、未完成工作和耐久决策。
- **Character source assets**: 导入源区为 `/Game/Neow/NPRRendering`；当前主 Mesh 为
  `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Model/SK_AvatarSample_A`，Skeleton 为
  `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Rig/SKEL_AvatarSample_A`，Post Process
  AnimBP 为 `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Animation/ABP_Post_AvatarSample_A`。
  导入器生成的 IK Rig、Retargeter 与 Pose Asset 只作为候选源资产，不成为 Kinesis 的动作权威；
  Kinesis 自有资产仍进入 `/Game/Neow/Kinesis`。
- **Reused foundation**: UE 5.8 原生插件与 Lyra/GASP/ALS 的已证明局部模式；不迁移整套样例工程。
- **Module boundaries**: 首期保持一个 `HeroAnimation` 插件；运行时职责仍集中在 Runtime 模块，开发期
  测试放在同模块 `Private/Tests`。`HeroAnimationEditor` 仅封装 UE 原生 IK Retarget 批量导出并向
  UEAgent 注册可靠入口；职责或依赖真正分离后再拆独立 Tests 模块，不建立空模块。

## Current Gate

**P0 — 女性 Locomotion 质量 Gate（正确方向体态校正待验收）**：Abyss 整目标构建、HeroAnimation 加载、
独立 Character、AnimBP 与 GameMode 链路已完成。首批 Idle/Walk/Run/Jump Loop 已正式保存但人工判定表现
完全错误，属于已知坏产物。`FemaleMoveAnimSet` 的首版体态候选变化不明显，随后加强版因将 `Y Forward`
误判为反向而加重后仰，均已被人工视觉 Gate 否决。正确方向保守版随后确认幅度太小；当前仅将 Idle 原位
提高到五倍总量，并以 Shoulder 与 UpperArm 联合校正左右整臂，Walk_F/Run_F 暂保留一倍版本。Idle 视觉 Gate 通过前不批量同步、
不接入 AnimBP，也不扩展到整库。

### Secondary Motion Gate

Kinesis 当前自有二级运动资产为 `VM_Kinesis_SecondaryMotion` 与 `ABP_Kinesis_Post`。运行时角色继续使用
导入的 `SK_AvatarSample_A`，由 `BP_KinesisCharacter` 的 Construction Script 调用一次
`SetOverridePostProcessAnimBP(...ABP_Kinesis_Post_C, false)`；不修改源 Mesh，也不再直接写原生继承组件的
Generated CDO。首轮仅将 56 个非末端 `CoatSkirt` 关节调整为 stiffness `0.18`、gravity `0.25`、
drag `0.18`；头发与其他链保持不变。`SK_Kinesis_AvatarSample_A` 保留为 Kinesis 自有预览 Mesh，运行时
Pawn 不依赖它。正确预览路径下的视觉 Gate 仍失败；源 VRM 权重审计确认虽有 80 根 `CoatSkirt` 骨，
可见衣服对它们的权重实际接近零。下装相关 section 中 `Onepiece_00_CLOTH_01` 有 97.6% 顶点由
Hips/Leg 主导，`Onepiece_00_CLOTH_02` 为 95.3%，`Tops_01_CLOTH_04` 为 83.6%。因此 Spring 参数与
Collider 无法让当前衣摆脱离腿部；下一 Gate 是在 DCC 重做衣摆蒙皮，或明确改走 Chaos Cloth。

## Truth

- **Implementation truth**: Kinesis 资产根为 `/Game/Neow/Kinesis`。源 Mesh/Skeleton 位于
  `Characters/VRoid/AvatarSampleA` 的 `Model`/`Rig` 子目录；Mesh 为 `Y` Forward，保留导入器生成的
  `ABP_Post_AvatarSample_A` 作为 Post Process AnimBP；`PHYS_AvatarSample_A` 存在但 Mesh 的
  `PhysicsAsset` 仍为 `None`。骨架共 195 bones，结构 Root 为单位变换且唯一直接子骨为
  `J_Bip_C_Hips`；自动生成的 IK Rig、Retargeter 与 Retarget Pose 尚未通过质量 Gate。
  `Plugins/HeroAnimation` 提供纯值 `FHeroAnimStateSnapshot`、唯一生产端
  `UHeroActionCoordinatorComponent` 与只读复制边界 `UHeroAnimInstance`。Coordinator 在
  `CharacterMovement` 更新后采集本地速度/腾空状态，并维护 Action、Interaction、Target、FrameId 与
  StateRevision；AnimInstance 仅在 Game Thread 复制合法快照，不从动画工作线程读取 Actor/UObject。
  对未来材质、VFX、音效和镜头仅保留 `FHeroPresentationCue` 语义契约：Coordinator 可广播
  GameplayTag、Magnitude、SequenceId 与 StateRevision，当前没有 Presentation Component、资产映射或
  任何表现系统依赖，消费者不得反写动作状态。
  `ABP_Kinesis` 已保存，父类为 `UHeroAnimInstance`、目标骨架正确，并建立尚未填充动画的
  `Locomotion` State Machine；`BP_KinesisCharacter` 已隔离创建，含 Coordinator，绑定 VRoid Mesh 与
  `ABP_Kinesis`，初始 Mesh 变换为 `Z=-96`、`Yaw=-90`；`BP_KinesisGameMode` 已保存并将其设为默认
  Pawn。`DefaultEngine.ini` 已切到 Kinesis GameMode。2026-08-13 22:13 的保存缓存确认 Kinesis Character
  含 3 个本地组件（包括 Coordinator），原 Third Person Character 仅保留 CameraBoom 与 FollowCamera；
  Kinesis 自有 IK Retargeter `/Game/Neow/Kinesis/Animation/Retarget/RTG_Kinesis_Female` 已于
  2026-08-13 23:06 正式保存，并已配置女性 `IK_NewIKRig`、女性预览 Mesh、AvatarSampleA 目标 Mesh 与
  `POSE_A`。首批输出位于 `/Game/Neow/Kinesis/Animation/Locomotion`：`A_Kinesis_Idle_Anim`、
  `A_Kinesis_Walk_F_Anim`、`A_Kinesis_Run_F_Anim`、`A_Kinesis_Jump_Loop_Anim`；不修改 VRoid 导入目录
  中的原资产。该首批输出已于人工 Gate 判定无效，待原位覆盖；不得作为 Locomotion 输入。次轮候选位于
  `/Game/Neow/Kinesis/Animation/Preview/PostureMVP`，包含 `A_Kinesis_PostureMVP_Idle_Anim`、
  `A_Kinesis_PostureMVP_Walk_F_Anim` 与 `A_Kinesis_PostureMVP_Run_F_Anim`。Idle 在完整帧范围内为
  `J_Bip_C_Spine/Chest/UpperChest/Neck` 叠加本地 Roll `+10/+15/+20/-35` 度，并为
  `J_Bip_L/R_Shoulder` 叠加本地 Roll `-75/-75` 度、`J_Bip_L/R_UpperArm` 叠加本地 Yaw
  `+20/-20` 度以从肩根带动整条手臂前移；Walk_F/Run_F 仍为 `+2/+3/+4/-7` 度。Root、骨盆、腿、
  肘、手腕与源动画不变。
- **Verification truth**: 第二个源码切片已再次通过 `BuildPlugin` 的 Win64 `UnrealEditor Development`、
  `UnrealGame Development` 与 `UnrealGame Shipping` 编译；已有两个窄回归检查通过。实际
  `AbyssEditor Win64 Development` 整目标构建成功，运行中的编辑器已加载 HeroAnimation；
  `ABP_Kinesis`、`BP_KinesisCharacter` 与 `BP_KinesisGameMode` 均已通过 warnings-as-errors 编译；
  Presentation Cue 契约已通过 UHT 与 HeroAnimation 单模块 C++ 编译；Editor 关闭后，实际
  `AbyssEditor-HeroAnimation.dll` 已于 2026-08-13 22:19 重新链接。新增的 `HeroAnimationEditor` 已独立
  通过 UHT、Win64 `UnrealEditor Development`、`UnrealGame Development` 与 `UnrealGame Shipping`
  构建，并于 2026-08-13 通过实际 `AbyssEditor Win64 Development` 重链。首批导出可靠命令与精确保存
  均为 `succeeded/verified`；五个 Kinesis 包独立读回为 clean、`save_generation=1`。四条动画全部绑定
  `SKEL_AvatarSample_A`：Idle 3.333333 秒/201 帧，Walk 1.066667 秒/65 帧，Run 0.8 秒/49 帧，Jump Loop
  0.833333 秒/51 帧；Walk/Run 保留源资产的 Root Motion，Idle/Jump Loop 为非 Root Motion。首轮视觉
  Gate 失败后，修正版 Editor 工具已通过独立 BuildPlugin：它从女性 Mesh 原生生成 Kinesis 源 Rig，
  清空继承 Op/Pose，自动对齐目标姿势并关闭不稳定的 IK Pass；修正版已通过实际
  `AbyssEditor Win64 Development` 重链。负向加强版经并排侧视人工观察确认方向错误后，三条候选均已
  原位替换为正向保守版并精确保存；Idle/Walk/Run 分别与未校正 Locomotion 在第 0 帧独立读回比较，四根
  骨的总增量均精确为 `+2/+3/+4/-7` 度，三项资产均为 `clean`。该版本视觉确认方向正确但幅度太小后，
  Idle 随后继续提高到 `+10/+15/+20/-35` 度，并将左右 UpperArm 以本地 Yaw `+20/-20` 度镜像前移；
  第 0 帧相对未校正 Idle 的旋转矩阵独立读回误差小于 `0.000002`。该版人工观察仍显手臂靠后后，左右
  Shoulder 先以本地 Roll `-15/-15` 度从肩根前移整臂，再提高到 `-25/-25` 度；人工观察仍判定不足后，
  按用户指定将当前前摆总量放大三倍至 `-75/-75` 度。独立读回确认躯干与 UpperArm 参数未被覆盖，
  双手全局 Y 从三倍版约 `-25.7/-22.6` 最终前移到 `+30.3/+39.6`。资产正式保存、
  `save_generation=21`、package SHA-256 为
  `b22297518857c98ccf0e603f86ceb95237707df5a1c55d7dfa804d4430f1c802`，状态为 `clean`；未保存或修改
  Walk_F、Run_F 与其他任务包。最终审美结论仍由人工 Gate 决定。截图工具
  曾使参考演示地图发生一次非预期重存；Editor 关闭后已用任务前同尺寸、同时间戳的原始文件恢复，恢复后
  SHA-256 为 `86A8322C36919BA811A87588627EC1738D254253B6ED95B8E17AC0E52DEC12D1`。
- **Runtime / external truth**: `Saved/UEAgent/route.json` 已绑定；2026-08-14 当前 live receipt 为
  `HEALTHY`，Editor epoch 为 `057C7FF7-4483-6E26-10CA-CC94DC00328C`。三条正确方向体态候选均已独立
  读回并正式保存；本切片未保存或修改其他任务正在使用的关卡与材质包。当前日志确认 UE `5.8.1-0+UE5`。现有 Bifrost 测试动画绑定
  `/Game/Bifrost/Animation/TestVroid/SKEL_1`，不能直接作为 AvatarSampleA 动画使用；在女性体态
  Retarget Pose 通过人工视觉 Gate 前不接入。目标硬件、DCC、Root/Capsule 与动画许可证尚未冻结。
- **Source-control truth**: Abyss Git 仓库当前为 `master` 且没有 commit，`Abyss.uproject` 未跟踪；
  Content/LFS 策略未定，当前切片仅以全新、自包含的 `Plugins/HeroAnimation` 目录作为可删除回退边界。
- **Source truth**: 契约来自 `Single_Hero_Deep_Animation_Execution_Blueprint_zh-CN_v2.0.docx`
  （v2.0，2026-08-12，48 页）；已完成全文结构提取与逐页渲染检查。

## Current Focus

先人工检查 `PostureMVP` 五倍总量并带 Shoulder + UpperArm 整臂前移校正的 Idle，重点确认胸腰曲线、肩部松弛、手臂位置与头部补偿；
通过后再同步到 Walk_F/Run_F，检查动态脚底接触并扩展到所需 Locomotion 子集，再决定 Movement/Capsule 对接并填充当前空的
`Locomotion` State Machine；不改源动画、参考库或 VRoid 导入资产。

## Constraints

- 单人 Technical Artist + AI；工期按全职等效 FTE，系统样机 9–12 个月，商业级垂直切片
  18–30 个月；范围冻结后至少 6 个月不增加武器、骨架族或交互类别。
- C++ Character State Authority / ActionCoordinator 是唯一动作权威；AnimBP 只读 Snapshot，
  所有跨系统切换经过 Continuity Bridge。
- 每个 Sprint 只交付一个从输入到表现的纵向闭环；真实场景回放、自动验证、性能 Trace、
  失败降级与回退点不可省略。
- AI/动捕/商业库产物最多自动进入 Q0/Q1；核心战斗与英雄演出必须人工通过 Q3–Q5。
- 完整 Motion Matching、学习型物理控制和高级形变仅在核心闭环成立后通过隔离 A/B 或 ROI Gate。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/Kinesis/`.

## Document Map

- `AI-BRIEF.md`: contract and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
