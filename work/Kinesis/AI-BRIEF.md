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
- **Non-goals**: 首期 Motion Matching——locomotion 首期用 in-place 资产 + velocity-driven；重评触发
  条件为 locomotion 库超过约 30–40 条，或 traversal 变体多到 BlendSpace 维护不动，且届时 locomotion
  须同步切回 root motion 驱动（in-place 播放会丢掉 MM 的主要收益，即数据库里的真实步幅）；
  运行时生成核心攻击；MimicKit/ProtoMotions 主线；
  多可玩角色、多独立武器、联机预测、跨平台最低规格、任意物体/高度自动交互、双 DCC 生产线，
  以及由 Notify、Montage、AnimBP 或 GAS 维护第二份动作真相。
- **Mature baseline / proven pattern**: UE 5.8 原生 Gameplay Tags/GAS、Motion Warping、IK Rig、
  Control Rig、FBIK、Smart Objects、Data Validation；ALS 只学问题拆解，Lyra 学线程安全数据与
  Linked Layers，GASP 学 Trajectory/Pose Search；第一版采用可控的传统 Locomotion。
- **Smallest end-to-end pass**: Preview Map 上 `BP_KinesisCharacter` 由键盘输入驱动，经 velocity-driven
  的 CharacterMovement、Coordinator Snapshot 与 `ABP_Kinesis` Locomotion State Machine（模式层 +
  速度 BlendSpace 叶子）跑通 Idle/Walk/Run/Jump 四态，位移正确、无死锁、无 Root/Capsule 跳变、
  mesh 不漂出胶囊，留下一段未经剪辑的连续游玩录屏与 60 FPS Trace。`Light_01` 的完整链路
  （输入 → ActionCoordinator → 阶段/Root/Target → Hit → Reaction → Camera/VFX/SFX →
  Continuity Bridge）是这条闭环成立之后的下一条纵向切片，不是本阶段目标。
- **Pass**: 垂直切片从探索、Traversal、战斗、Boss 到演出无隐藏状态重置；6 类交互共用协议；
  5 个英雄动作达到 Q5、普通动作/受击达到 Q3/Q4；命令行验证可运行；目标 PC 60 FPS 且降级可用。
- **Stop / rollback**: 任一月度 Gate 不通过就停止扩动作/交互/效果，回到最近已验证基线修复；
  两周无未经剪辑的可玩闭环即缩减范围。不得用兼容层保留失败路线。

## Implementation

- **Canonical path**: 目标工程为 `F:/Omni/Project/Abyss/Abyss.uproject`（2026-08-25 自
  `D:\Work\Personal\Project\Abyss` 迁移，引擎根 `F:\Omni\Enigine`）；资产根为
  `/Game/Neow/Kinesis`，后续运行时代码以 `Plugins/HeroAnimation/` 为唯一实现入口；
  `work/Kinesis/` 只保存项目契约、未完成工作和耐久决策。
- **Character source assets**: 导入源区为 `/Game/Neow/NPRRendering`；当前主 Mesh 为
  `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Model/SK_AvatarSample_A`，Skeleton 为
  `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Rig/SKEL_AvatarSample_A`，Post Process
  AnimBP 为 `/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA/Animation/ABP_Post_AvatarSample_A`。
  导入器生成的 IK Rig、Retargeter 与 Pose Asset 只作为候选源资产，不成为 Kinesis 的动作权威；
  Kinesis 自有资产仍进入 `/Game/Neow/Kinesis`。
- **Reused foundation**: UE 5.8 原生插件与 Lyra/GASP/ALS 的已证明局部模式；不迁移整套样例工程。
- **Animation architecture**: 运行时是五层单向数据流，权威只在上层，下层永不写回。
  1. **输入层**：Enhanced Input，Kinesis 自有 `IA_*` 与 IMC。
  2. **权威层**：`UHeroActionCoordinatorComponent`（C++，唯一写者）。阶段 0 只采集速度与腾空；
     阶段 1 起持有 Action 阶段机与 cancel 窗口表。
  3. **边界层**：`FHeroAnimStateSnapshot` 纯值，单向、只读、线程安全。
  4. **消费层**：`UHeroAnimInstance` 在 Game Thread 复制合法快照；`RootMotionMode` 设为
     `RootMotionFromMontagesOnly`，使非 Montage 帧走 velocity-driven、Montage 帧由 root motion 覆盖
     `Velocity`（`CharacterMovementComponent.cpp:2952-2969`，该处为硬覆盖、无混合）。
  5. **图层**：`ABP_Kinesis` 的 Locomotion State Machine **只作模式层**（Grounded / InAir / Landing，
     个位数状态），姿态选择放在状态内部的**叶子**里——阶段 0 为速度 BlendSpace，将来可原地换成
     `FAnimNode_MotionMatching`（继承 `FAnimNode_BlendStack_Standalone`，PoseSearch 插件对
     AnimStateMachine 零引用），换叶子不改图结构也不改 C++。禁止把每条动画做成一个状态。
     Slot 节点是动作侧 Montage 播放口。后处理链顺序为 Control Rig 体态层 → Foot IK →
     Linked Layers/additive → 二级运动。

  动作侧成熟件为 Montage（**仅回放机制**，权威仍在 Coordinator）+ Motion Warping（扭曲 root 轨迹做
  目标/距离适配，1 条 → N 个有效 Action）+ Smart Objects（6 类交互共用协议）。IK 与 Control Rig 解决
  的是「适配」轴，与姿态选择方式正交，不因是否采用 MM 而取舍——用 MM 的作品同样大量使用 Foot IK。
  Continuity Bridge 的三份具体职责是三个速度交接突变：进入 Montage 时 `Velocity` 被硬覆盖、退出时
  收招帧 root delta 近零导致原地僵住、中途被打断时继承或丢弃峰值速度，引擎均不自动处理。
- **Module boundaries**: 首期保持一个 `HeroAnimation` 插件；运行时职责仍集中在 Runtime 模块，开发期
  测试放在同模块 `Private/Tests`。`HeroAnimationEditor` 仅封装 UE 原生 IK Retarget 批量导出并向
  UEAgent 注册可靠入口；职责或依赖真正分离后再拆独立 Tests 模块，不建立空模块。

## Current Gate

**P0 — 可玩移动闭环 Gate（阶段唯一目标）**：locomotion 用 in-place 播放 + velocity-driven 位移。
链路为 Enhanced Input → `CharacterMovement` → Coordinator 每帧写 Snapshot → `UHeroAnimInstance`
只读复制 → `ABP_Kinesis` Locomotion State Machine（模式层）+ 速度 BlendSpace（叶子）。验收为
Preview Map（平地、坡面、台阶）上一段未经剪辑的连续游玩：位移正确、四态切换无死锁与 Root/Capsule
跳变、mesh 不漂出胶囊、60 FPS。

本阶段**接受平地步幅脚滑且不声称压低它**。压低步幅失配的机制不是速度 BlendSpace——BlendSpace 只改
姿态插值、不改播放速率，中间速度下得到的是 Walk/Run 的混合姿态而速率仍为 1.0，步幅与胶囊位移照样
不匹配。正确机制是 **Sync Group + `bEnableAutoPlayRate`（距离驱动播放速率）**，按 BACKLOG 排在阶段 2；
本阶段只把 Sync Marker 标好作为其前提。marker 有无**离线不可判定**：二进制探针在商业资产与程序化
生成的 Kimodo 资产上命中数完全相同，说明命中的是属性名而非实例数据，须 Editor 在线后直接看 Markers
轨道，这是上线后第一项资产检查。

**Foot IK 必须在本阶段内做**：Preview Map 含坡面与台阶，缺 Foot IK 的脚部穿模与漂浮会污染体态判读，
让人分不清看到的是体态问题还是接触问题；本项目已付过一次读错信号源的学费（Run 动态后摆被误判为 Idle
静态体态）。同源风险还有一条：源库为写实女性 mannequin、目标是 VRoid 二次元体态，腿长比例失配同样
表现为脚滑与步幅不符，而 Control Rig 体态层按既定值只重塑 Spine/Chest/UpperChest/Neck/Shoulder/
UpperArm、**不动腿**，因此这类失配只能靠 Sync 自动播放速率与 Foot IK 压，不得再读成体态问题。
本阶段没有 Action/Interaction，因此不存在跨系统切换，Continuity Bridge 随第一条 Action 切片引入。

**供货线（不单独开 Gate，验收一律在闭环内边移动边判读）**

- **Locomotion 资产基底**：`Animation/Locomotion/` 的四条**未烘焙校正**版 `A_Kinesis_Idle_Anim`、
  `A_Kinesis_Walk_F_Anim`、`A_Kinesis_Run_F_Anim`、`A_Kinesis_Jump_Loop_Anim`（Jump_Loop 在
  `Locomotion/` 下，不在 `Animation/` 根）。`Preview/PostureMVP` 三条**直接作废、不作为供货**：它们是
  把体态校正烘焙进资产的产物，校正改由 Control Rig 层负责后已无用途，仅留作参照。首批四条曾被人工
  Gate 判为表现无效并禁作 Locomotion 输入，但判废理由是体态，而体态现已改由 Control Rig 层处理，
  因此该禁令在本阶段撤销：四条作为 Control Rig 层的基底，体态结论随该层建成后一并重验。这样省掉
  「先用烘焙版判读一轮、再换 Control Rig 重判一轮」。
- **Root lock 实测（本阶段第一项实测）**：Walk/Run **带 root motion 轨道**，velocity-driven 下仅
  「不消费」不够——根骨骼平移仍留在姿态里，会让 mesh 漂出胶囊、循环末尾跳回。开关分两级且是「并且」
  不是「或者」：资产级 `UAnimSequence::bForceRootLock`（注释 "Force Root Bone Lock even if Root Motion
  is not enabled"）与 `RootMotionRootLock`（`RefPose`/`AnimFirstFrame`/`Zero`，见
  `AnimSequence.h:318-328`）；AnimInstance 级 `RootMotionMode`。互斥只发生在 AnimInstance 级的
  `IgnoreRootMotion`（"Extract root motion but do not apply it"）与 `RootMotionFromMontagesOnly`
  之间，二者不可同时成立。实测按两臂 A/B：**臂 A** = `IgnoreRootMotion`，提取即锁根，是已知良好基线；
  **臂 B** = `RootMotionFromMontagesOnly` + 资产级 `bForceRootLock`。`RootMotionFromMontagesOnly` 单独
  是否锁根**未经运行时验证**（`ShouldExtractRootMotion()` 于 `AnimInstance.h:446` 只对该模式返回 false，
  据此推断仍需 root lock），A/B 正好隔离这个变量。
  **2026-09-03 决定直接走臂 B、不用臂 A 过渡**：阶段 1 为 Montage root motion 必须用
  `RootMotionFromMontagesOnly`，若阶段 0 先用臂 A，阶段 1 就要再换一次 AnimInstance 模式，等于在最不该
  引入第二个变量时引入。臂 B 的资产侧已落地（Walk_F/Run_F 的 `bForceRootLock` 已置 True 并保存，命令与
  SHA 见 Verification truth）；剩余是设 `ABP_Kinesis` 的 `RootMotionMode` 与运行时观察。臂 A 降为
  **诊断对照**：若臂 B 运行时仍漂，切臂 A 即可判定问题在资产侧还是模式侧。
  编辑器静止并排 Gate 已废止：它曾把 Run 的动态后摆误判为 Idle 静态体态，造成 `-75 → -45 → -25`
  三轮返工。
- **体态校正改走 Control Rig 层**：PostureMVP 那组校正（`J_Bip_C_Spine/Chest/UpperChest/Neck` 本地
  Roll `+10/+15/+20/-35` 度、`J_Bip_L/R_Shoulder` 本地 Roll `-25/-25` 度、`J_Bip_L/R_UpperArm` 本地
  Yaw `+20/-20` 度）本质是程序化姿态重塑，正解是挂在后处理链的 Control Rig 层，不是烘焙进资产。
  烘焙方案下每轮审美调整都要重写资产（已发生 18 次窄 `ApplyBoneRotation` 写入与三轮返工），且每条新
  资产都要重做一遍，是**线性成本**；Control Rig 层改一个数字即生效、对全库一次生效，是**常数成本**——
  这对还要产 30–50 个 Action 与 Kimodo 草坯的单人配置是决定性的。该层作用在上一条的
  `Animation/Locomotion/` 四条未烘焙基底上，初始值直接取上述这组已验证数值。这不违反「AnimBP 不得
  维护第二份动作真相」：动作真相是「此刻播什么」，仍在 Coordinator；Control Rig 只重塑姿态，
  不决定播放。
- **Kimodo 草坯**：`Kimodo/Baked/A_Kimodo_Baked_*_Loop` 九条只作备选供货与后续 Root Motion 评估素材，
  本阶段不扩产、不单独开 Gate；已两次人工否决的 `Kimodo/Retargeted/` 旧批次判废待清理。
- **衣摆二级运动（本阶段冻结）**：自有资产为 `VM_Kinesis_SecondaryMotion` 与 `ABP_Kinesis_Post`。
  运行时角色继续使用导入的 `SK_AvatarSample_A`，由 `BP_KinesisCharacter` 的 Construction Script 调用
  一次 `SetOverridePostProcessAnimBP(...ABP_Kinesis_Post_C, false)`；首轮仅把 56 个非末端 `CoatSkirt`
  关节调为 stiffness `0.18`、gravity `0.25`、drag `0.18`，头发与其他链不变；
  `SK_Kinesis_AvatarSample_A` 仅为 Kinesis 自有预览 Mesh，运行时 Pawn 不依赖它。源 VRM 权重审计确认
  可见衣服对 80 根 `CoatSkirt` 骨的权重实际接近零：`Onepiece_00_CLOTH_01` 有 97.6% 顶点由 Hips/Leg
  主导，`Onepiece_00_CLOTH_02` 为 95.3%，`Tops_01_CLOTH_04` 为 83.6%。因此 Spring 参数与 Collider
  无法让衣摆脱离腿部；解冻后的两条路是在 DCC 重做衣摆蒙皮，或明确改走 Chaos Cloth。

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
  中的原资产。该首批输出曾于人工 Gate 判为表现无效并禁作 Locomotion 输入；2026-09-02 体态校正改走
  Control Rig 层后该禁令撤销——判废理由是体态，而体态已不再由资产承担——四条现为 Control Rig 层的
  未烘焙基底，体态结论随该层建成后一并重验。次轮候选（2026-09-02 起作废、仅留参照，见 Current Gate
  供货线）位于 `/Game/Neow/Kinesis/Animation/Preview/PostureMVP`，包含
  `A_Kinesis_PostureMVP_Idle_Anim`、
  `A_Kinesis_PostureMVP_Walk_F_Anim` 与 `A_Kinesis_PostureMVP_Run_F_Anim`。三条动画均在完整帧范围内为
  `J_Bip_C_Spine/Chest/UpperChest/Neck` 叠加本地 Roll `+10/+15/+20/-35` 度，为
  `J_Bip_L/R_Shoulder` 叠加本地 Roll `-25/-25` 度，并为 `J_Bip_L/R_UpperArm` 叠加本地 Yaw
  `+20/-20` 度以从肩根带动整条手臂前移。Root、骨盆、腿、肘、手腕与源动画不变；Walk/Run 保留原有
  Root Motion。
- **Code truth**: 2026-09-02 离线源码审计确认移动系统尚未存在。`Plugins/HeroAnimation` Runtime 连测试
  约 390 行；`UHeroActionCoordinatorComponent::TickComponent` 每帧只写 `LocalVelocity`、`bIsFalling`
  与 `FrameId`，`SetActionState`/`SetInteractionState`/`SetTargetState`/`PublishPresentationCue`
  四个入口没有任何生产调用方，仅 `HeroAnimStateSnapshotTest` 调用。运行时无 Continuity Bridge 代码、
  不消费 Root Motion、无 Jump 处理；`HeroAnimationEditor` 中的 Root Motion 引用只属于 IK Retarget
  导出（`RootMotionSource = CopyFromSourceRoot`）。`Source/Abyss` 只有 Bifrost/Niagara 遗留，无输入或
  Controller 代码。`BP_KinesisCharacter` 的图表离线不可读，但 `/Game/Neow/Kinesis` 下只有
  `ABP_Kinesis`、`ABP_Kinesis_Post`、`BP_KinesisCharacter`、`BP_KinesisGameMode`、
  `SK_Kinesis_AvatarSample_A`、`VM_Kinesis_SecondaryMotion` 与 `Animation/` 子树。2026-09-04 已在
  `/Game/Neow/Kinesis/Input/` 下新建 Kinesis 自有 `IA_Move`（Axis2D）、`IA_Look`（Axis2D）、
  `IA_Jump`（Boolean）与 `IMC_Kinesis`（priority 0），不复用 `Bifrost/Input/IMC_Default`；仍未建 Maps
  目录，Preview Map 待做。
  `UHeroAnimInstance`（35 行）在 `NativeUpdateAnimation` 里读 Snapshot、`IsValid()` 校验后赋值给成员，
  未设 `RootMotionMode`——**这不需要修**：`AnimInstance.cpp:202` 的构造函数默认值就是
  `RootMotionFromMontagesOnly`，2026-09-04 live 读 `ABP_Kinesis` 的 CDO
  （`/Game/Neow/Kinesis/ABP_Kinesis.Default__ABP_Kinesis_C`）确认生效值即为此，故阶段 0 与阶段 1 都不
  需要为它新增 C++ 或改 Class Defaults。`FHeroAnimStateSnapshot` 目前没有任何 Action 相位字段
  （无 phase index、cancel 窗口、Montage 位置），阶段 1 需扩，这是设计好的扩展点。
  **隐患**：`UHeroActionCoordinatorComponent.h:24-35` 的四个 setter 全为 `BlueprintCallable` 且当前无
  生产调用方，所以暂时无害；但一旦出现调用方，任何 BP（含 AnimBP 取得引用、Montage Notify 的 BP、
  gameplay BP）都能写 Action 状态，即构成 Non-goals 禁止的第二真相源。阶段 1 落地 Action 时应改为
  C++ 内部阶段机驱动，对外只暴露请求语义。
  引擎侧已核实的 API：`UAnimInstance::RootMotionMode`（`AnimInstance.h:372`，另有 `SetRootMotionMode()`
  于 1066 行）；`ERootMotionMode` 四值 `NoRootMotionExtraction` / `IgnoreRootMotion` /
  `RootMotionFromEverything` / `RootMotionFromMontagesOnly`（`AnimEnums.h:26-41`，最后一个的注释即
  "Root motion is only taken from montages"）；`ERootMotionRootLock` 三值 `RefPose` / `AnimFirstFrame` /
  `Zero`（`AnimEnums.h:9-24`）；`FAnimNode_MotionMatching` 继承 `FAnimNode_BlendStack_Standalone`、
  自带 `BlendTime = 0.2f` 与 `bResetOnBecomingRelevant = true`，PoseSearch 插件对 AnimStateMachine
  零引用；`PoseSearch` 与 `MotionWarping` 引擎内有、`Abyss.uproject` 未启用，`AnimGen` 与
  `AnimGenExample` 已启用但无训练数据，`Mover` 已启用。Abyss 为多项目共用宿主工程，插件开关只做
  新增、不改现有。
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
  Shoulder 先以本地 Roll `-15/-15` 度从肩根前移整臂，再提高到 `-25/-25` 度。后续曾把 Run 的动态
  后摆反馈误判为 Idle 静态体态，因而将 Idle 临时放大到 `-75/-75`、再回调到 `-45/-45`；用户澄清后，
  Idle 已恢复为 `-25/-25`，Walk_F/Run_F 也从一倍躯干版本同步到同一完整校正。该同步共执行 18 个窄
  `ApplyBoneRotation` 写入，每项均为 `succeeded/verified` 并由对应的一次性能力精确保存为 `saved`。
  2026-08-14 最终磁盘资产 SHA-256 为 Idle
  `606368D38A030EE4694059F75013ADE593A5471070E68EA655C05225E8E41E81`、Walk
  `0896E1524618300420FFCC099D57ED7FEBCDAEABD11D9D86BE40B292E6D9313D`、Run
  `2AC167F37A8214EB081E172F20EA6434A74BC006CF13F8DC4D09DCA0EEA1F90B`；未修改源 Locomotion、
  Retargeter、关卡或其他任务包。PostureMVP 作废后，其姿态独立读回与审美结论不再待办，体态判读改在
  移动闭环内进行。截图工具
  曾使参考演示地图发生一次非预期重存；Editor 关闭后已用任务前同尺寸、同时间戳的原始文件恢复，恢复后
  SHA-256 为 `86A8322C36919BA811A87588627EC1738D254253B6ED95B8E17AC0E52DEC12D1`。
  2026-09-03 至 09-04 在 epoch `314C3435-4507-33BC-3E8A-7FB8B547A726` 内完成阶段 0 第一批 live 读写，
  每项均经 `ueagent_submit` → 终态 receipt → 独立回读 →（写操作）一次性 save token。**日期一律以 receipt
  的 `accepted_at` 为准**，不以本地 `date` 为准——本机 `date` 输出曾滞后约半天。
  ① **Sync marker 全库为零**（09-03）：`ListSyncMarkers` 对 Kinesis 四条与源库 `Root-Motion/Walk_F`、
  `Root-Motion/Run_F`、`In-Place/Jump_Out` 均返回 `{"returnValue":[]}`。即商业源库自带 0 个 authored
  sync marker，不是重定向丢失，阶段 2 的 Sync Group 必须从零标（`AddSyncMarker`/`SetSyncMarkerTime`
  在 AnimSequenceService 内，可程序化）。② **root motion 配置实测**（09-03）：Walk_F/Run_F 为
  `bEnableRootMotion=True` + `bForceRootLock=False` + `RootMotionRootLock=RefPose`，`GetAnimatedBones`
  确认 `root` 是首条动画轨道，`GetAnimationLength` 为 1.0666667 秒（与上述 65 帧记录一致，证明读取链路
  可信）；Idle 与 Jump_Loop 为 `bEnableRootMotion=False`，本就是 in-place，无需处理。漂移条件实成立，
  仅 2 条资产需改。③ **已将 Walk_F/Run_F 的 `bForceRootLock` 置 True 并保存**（09-04 10:35 本地，cmd
  `71c0d146` / `fbf261d7`，均 `succeeded/changed/verified`；`GetForceRootLock` 独立回读 `true`；save
  receipt `saved` 且 `packages` 仅含目标包，无 `unexpected_saved_packages`；磁盘各 +48 字节，save 后
  `dirty=False`、`save_generation=1`）。回退锚点为改前磁盘 SHA-256：Walk_F
  `A250172348B709239C7CFF5611CB55DE57B61D91A47AE8338FEEC1C5883A7CA4`（554628 字节）、Run_F
  `C59197C11179B26BAECAE203476947AA8CB96FD698F89611A543211C1B411B51`（447440 字节）；改后为 Walk_F
  `D31296A6B83E06E72E1D93EF531C976090AB3AB40E8BC5EF81B8A5AD8FA585DE`（554676）、Run_F
  `0E753558D767678545F330278322B57754C2B470B225C9BA842C438D85556161`（447488）。
  ④ **`RootMotionMode` 无需设置**（09-04）：live 读 `ABP_Kinesis` 的 CDO 得
  `RootMotionFromMontagesOnly`，与 `AnimInstance.cpp:202` 的构造函数默认值一致。root lock 的配置两侧
  因此均已齐全：资产侧 `bForceRootLock=True`，实例侧默认模式即所需模式。
  ⑤ **输入资产已建**（09-04 10:54–10:56 本地）：`/Game/Neow/Kinesis/Input/` 下 `IA_Move`（Axis2D）、
  `IA_Look`（Axis2D）、`IA_Jump`（Boolean）、`IMC_Kinesis`（priority 0）。13 次 mutation 全部
  `succeeded/changed/verified` 并逐个 save；snapshot 独立确认 class 为
  `/Script/EnhancedInput.InputAction` ×3 与 `/Script/EnhancedInput.InputMappingContext`，四者
  `dirty=False`，且 `IMC_Kinesis` 的 `save_generation=11` 恰等于 1 次创建 + 6 条键位映射 + 4 个
  modifier，写入次数独立对上。`GetMappings` 回读 6 条映射为 W、S+Negate、D+SwizzleAxis、
  A+SwizzleAxis+Negate、Mouse2D、SpaceBar。`AddModifier` 不收参数、只能用默认值，经查默认即正确：
  `InputModifiers.h:420` 的 `Order = EInputAxisSwizzle::YXZ`（X/Y 互换）、`InputModifiers.h:260-264`
  的 Negate `bX=bY=bZ=true`，故 W=(1,0)、S=(-1,0)、D=(0,1)、A=(0,-1)，二维移动向量正确。
  **仍未验证**：root lock 的运行时半边（mesh 是否真不漂出胶囊）需角色在关卡里走起来才能观察，排在输入
  接线与 Preview Map 之后。`GetBoneTransformAtTime`、`GetTotalRootMotion`、`GetInputActionInfo`、
  `GetMappingContextInfo` 均为 out-param 形式，receipt 只回显 `returnValue`，故漂移量级无法经可靠内核
  数值测出；`AuthoredSyncMarkers` 亦不可经 `get_properties`（明确报 could not be read）或
  `ueagent_snapshot` 的 47 属性模型读取。`get_properties` 只要有一个属性不可读就整条失败。
- **Runtime / external truth**: 工程与引擎于 2026-08-25 迁至 `F:\Omni`；`Saved/UEAgent/route.json` 已由
  `bootstrap -TargetProfile Abyss -SkipBuild` 以新 `targetProfile` 格式重建，VibeUE 因迁移丢失 `.git`
  已按钉住的 merged tree `4612cc04` 重克隆并复打补丁。2026-08-25 Doctor 为 `OFFLINE`（无 listener，
  epoch null，插件指纹 `c3b7c2f1…`）；旧 epoch `057C7FF7-4483-6E26-10CA-CC94DC00328C` 的 receipt 全部
  作废，但不影响上述已落盘的三条候选。`AbyssEditor Win64 Development` 已于 2026-08-26 在新路径全量构建
  成功（Result: Succeeded，约 2.7 小时）。2026-08-26 10:05 Editor 冷启动后 Doctor 为 `HEALTHY`：
  listener PID 14912，Editor epoch `A4F54B9C-4657-0C57-E467-7DA76CB652F8`，插件指纹 `18422b7b…`，
  `-ProbeAdvancedCapabilities` 确认 Niagara 扩展存活。该 epoch 已作废：2026-09-02 日间
  `compact_context.ps1` 报 `NEEDS_DOCTOR/STALE/editor_pid_changed`，doctor 一度为 `OFFLINE`（无
  listener，epoch null）。2026-09-02 20:50 重跑 doctor 恢复 `HEALTHY`：listener PID 49668
  （`AbyssEditor`，20:07 冷启动），epoch `314C3435-4507-33BC-3E8A-7FB8B547A726`，插件指纹仍为
  `18422b7b…`——与 8-26 同一二进制，HeroAnimation 无需重编。live 读改能力已恢复，阶段 0 可在本 epoch
  内执行。同期另有 `UnrealEditor` PID 8236（17:35 启动）在跑，doctor 未绑定它，应为其他工程实例。
  本切片未保存或修改其他任务正在使用的关卡与材质包。当前日志确认
  UE `5.8.1-0+UE5`。现有 Bifrost 测试动画绑定
  `/Game/Bifrost/Animation/TestVroid/SKEL_1`，不能直接作为 AvatarSampleA 动画使用；在移动闭环内判读
  通过前不接入。本阶段 locomotion 已定为 in-place 播放 + velocity-driven，动作侧 root motion 走
  `RootMotionFromMontagesOnly`；这是**阶段 0 的决定而非永久约束**——将来若采用 MM，locomotion 须同步
  切回 root motion 驱动，否则丢掉 MM 的真实步幅收益。目标硬件、DCC 与动画许可证尚未冻结。
- **Source-control truth**: 迁移后 Abyss 的 `.git` 未随副本保留（原仓库本就为无 commit 的 `master` 且
  `Abyss.uproject` 未跟踪）；Content/LFS 策略未定，当前切片仍以全新、自包含的 `Plugins/HeroAnimation`
  目录作为可删除回退边界。
- **Kimodo truth**: 2026-08-26 起 `RTG_Kinesis_Female` 与 `IK_Kinesis_Female_Source` 的源已切换为
  SOMA 表征（服务 Kimodo 重定向；女性源可随时由 RetargetAnimations 重跑重建）。
  `/Game/Neow/Kinesis/Animation/Kimodo/` 存 SOMA 源资产（SK_Kimodo_Soma* 9 mesh + 9 anim + 1
  skeleton），`Kimodo/Retargeted/A_Kimodo_*` 存 9 条已重定向至 AvatarSampleA 的草坯动画（idle/walk/
  run ×2 + girl 三条），均为 Q0/Q1 候选，未接 AnimBP。生成链路脚本与中间件在 `tmp/Kinesis/`
  （render_npz.py、bvh2fbx.py、ue-call.ps1 等）。
  2026-08-26 晚更新：`Kimodo/Retargeted/` 批次经人工视觉 Gate **判废**（IK Retargeter 自动黑盒第二
  次失败），待清理。现行链路为**离线数值烘焙**（方案 B）：npz 直读 + 世界空间 delta 重定向（52 骨
  映射、Procrustes 帧转换 M（scale=80.36）、Root 承担地面位移），经离线 GIF 闸后由
  `ProgrammaticToolset.execute_tool_script` 沙箱调 `CreateAnimSequence` 写入并直接落盘。产物在
  `/Game/Neow/Kinesis/Animation/Kimodo/Baked/A_Kimodo_Baked_*`（9 条，121/91 帧 @30fps，53 骨轨道），
  UE 内截图验收姿态自然。烘焙脚本 `tmp/Kinesis/retarget_stage_b.py`，批量提交 `bake-batch.ps1`。
- **Source truth**: 契约来自 `Single_Hero_Deep_Animation_Execution_Blueprint_zh-CN_v2.0.docx`
  （v2.0，2026-08-12，48 页）；已完成全文结构提取与逐页渲染检查。

## Current Focus

只推进移动闭环，按序执行，每步跑一个最小检查。Editor 已 `HEALTHY`，receipt 与当前 epoch 见
Runtime / external truth。

root lock 分两侧，**不可合并成一步**：配置侧已完成（资产级 `bForceRootLock=True` 于 2026-09-04 保存；
实例级 `RootMotionMode` 经 live 读 CDO 确认本就是引擎默认 `RootMotionFromMontagesOnly`，无需改）；
运行时观察侧要看「mesh 是否漂出胶囊」，必须有输入与关卡才能让角色走起来，因此只能排在输入接线与
Preview Map 之后。此前把它整块提前是错的——那条「未过之前不做后面任何事」的门照字面执行不了，因为
它的前置条件正是它挡着的两项。

1. 把输入接线到 `BP_KinesisCharacter`。**资产侧已完成**：`/Game/Neow/Kinesis/Input/` 下 `IA_Move`
   （Axis2D）、`IA_Look`（Axis2D）、`IA_Jump`（Boolean）、`IMC_Kinesis`（priority 0）与 6 条键位映射
   均已存盘并验证。剩余是先确认该 BP 的组件构成（有无 Camera/CameraBoom 可被 `IA_Look` 驱动），再加
   `EnhancedInputComponent` 绑定、BeginPlay 里 `AddMappingContext`，Move 走 `AddMovementInput`，
   Jump 走 `Character::Jump`。输入走 Enhanced Input → CharacterMovement 标准路径，Coordinator 只观察
   不拦截。
2. 建 Preview Map（平地、坡面、台阶），冻结 Walk/Run 速度、加减速与 Capsule 参数。
3. **root lock 运行时观察（承重验证）**：让角色在 Preview Map 上走起来，确认 mesh 不漂出胶囊、循环
   末尾不跳回。若仍漂，切臂 A `IgnoreRootMotion` 判定问题在资产侧还是模式侧；两臂都漂则回退方向是回到
   root motion 驱动，不是别处。**未过之前不填 State Machine。**
4. 填 `ABP_Kinesis` 当前空的 `Locomotion` State Machine，**只作模式层**：Grounded / InAir / Landing，
   姿态选择放在状态内部的叶子里——Grounded 叶子为速度 BlendSpace（Idle/Walk/Run 是采样点，不是三个
   状态），由 `LocalVelocity` 驱动；InAir 由 `bIsFalling` 驱动。AnimBP 保持只读 Snapshot，不写回。
   Landing 用哪条资产取决于 `In-Place/Jump_Out_Anim` 的语义确认（**待用户在 Persona 里看**：
   `Demo/AnimMontage/` 下的资产 class 实为 `AnimSequence`，无法从 section 名反推用法）。
   同时给这四条资产**从零标** Sync Marker：实测全库为 0（含商业源库），是新建不是补齐；本阶段只标不用，
   作为阶段 2 Sync Group 自动播放速率的前提。
5. 加 Foot IK：Preview Map 含坡面与台阶，缺它则脚部穿模/漂浮会污染第 6 步的体态判读。
6. 建 Control Rig 体态层挂进后处理链，作用在 `Animation/Locomotion/` 四条未烘焙基底上，初始值取
   PostureMVP 已验证的那组；改一个数字即生效，不再重写资产。随后在闭环里边移动边判读，通过即定版。
   若只有 Run 后摆过度，只修 Run 的动态摆臂，不动共享体态。
7. 出 Gate 证据：一段未经剪辑的连续游玩录屏 + 60 FPS Trace。

不改源动画、参考库或 VRoid 导入资产。Kimodo 与衣摆本阶段不推进。

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
