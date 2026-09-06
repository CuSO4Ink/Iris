# Kinesis · BACKLOG

本阶段唯一目标是可玩移动闭环（locomotion 为 in-place 播放 + velocity-driven 位移，Idle/Walk/Run/Jump）。
资产线只在需要供货时动，验收一律在闭环内边移动边判读。架构见 `AI-BRIEF.md` 的 Animation architecture。

## Doing

- [ ] 把输入接线到 `BP_KinesisCharacter`。**资产侧已完成**：`/Game/Neow/Kinesis/Input/` 下
  `IA_Move`（Axis2D）、`IA_Look`（Axis2D）、`IA_Jump`（Boolean）、`IMC_Kinesis`（priority 0），6 条
  映射为 W、S+Negate、D+SwizzleAxis、A+SwizzleAxis+Negate、Mouse2D、SpaceBar，13 次 mutation 全部
  已 save 并经 snapshot 与 `GetMappings` 独立验证（详见 Verification truth）。**剩余**：先确认
  `BP_KinesisCharacter` 的组件构成（有无 Camera/CameraBoom 可被 `IA_Look` 驱动），再加
  `EnhancedInputComponent` 绑定、BeginPlay 里 `AddMappingContext`，Move 走
  `AddMovementInput(GetActorForwardVector(), X)` 与 `AddMovementInput(GetActorRightVector(), Y)`，
  Jump 走 `Character::Jump`。输入走 Enhanced Input → CharacterMovement 标准路径，Coordinator 只观察
  不拦截。
- [ ] 建 Preview Map（平地、坡面、台阶），冻结 Walk/Run 速度、加减速与 Capsule 参数。
- [ ] **root lock 运行时观察（承重验证）**：让角色在 Preview Map 上走起来，确认 Walk_F/Run_F 播放时
  mesh 不漂出胶囊、循环末尾不跳回。必须排在上面两项之后——没有输入与关卡就无从观察，此前把整块 root
  lock 提前是错的（那条门的前置条件正是它挡着的两项）。若仍漂，切臂 A `IgnoreRootMotion` 判定问题在
  资产侧还是模式侧；两臂都漂则回退方向是回到 root motion 驱动，不是别处。**未过之前不填 State Machine。**
- [ ] 确认源库 `Study/Ref/FemaleMoveAnimSet` 的 `In-Place/Jump_Out_Anim` 是否确为落地收势（决定 Landing
  状态用哪条资产）。属语义/视觉判断，需用户在 Persona 里看：`Demo/AnimMontage/` 下的资产 class 实为
  `/Script/Engine.AnimSequence` 而非 Montage，无法从 section 名反推用法，文件夹名是误导的。
- [ ] 填 `ABP_Kinesis` 当前空的 `Locomotion` State Machine，**只作模式层**：Grounded / InAir / Landing。
  姿态选择放状态内部的叶子里——Grounded 叶子为速度 BlendSpace（Idle/Walk/Run 是采样点，不是三个
  状态），由 `LocalVelocity` 驱动；InAir 由 `bIsFalling` 驱动。AnimBP 保持只读 Snapshot，不写回。
  顺带给这四条资产**从零标** Sync Marker：`ListSyncMarkers` 实测 Kinesis 四条与源库 Walk_F/Run_F/
  Jump_Out 全部返回空数组，商业源库自带 0 个 authored marker，没有任何可继承的标记，所以这是新建不是
  补齐；趁只有 4 条时做，将来 50 条时是灾难。本阶段只标不用，作为阶段 2 Sync Group 的前提。
- [ ] 加 Foot IK：Preview Map 含坡面与台阶，缺它则脚部穿模/漂浮会污染体态判读。
- [ ] 建 Control Rig 体态层挂进后处理链，作用在 `Animation/Locomotion/` 的四条**未烘焙基底**
  （`A_Kinesis_Idle_Anim`、`A_Kinesis_Walk_F_Anim`、`A_Kinesis_Run_F_Anim`、`A_Kinesis_Jump_Loop_Anim`）
  上，初始值取 PostureMVP 已验证的那组（`+10/+15/+20/-35` / `-25/-25` / `+20/-20`）；改一个数字即生效，
  不再重写资产。`Preview/PostureMVP` 三条烘焙版直接作废、只留参照，既不作供货也不作判读对象；首批四条
  原判废禁令随之撤销（判废理由是体态，体态已改由本层承担）。随后在闭环内判读这四条基底，通过即定版；
  若只有 Run 后摆过度，只修 Run 的动态摆臂，不动共享体态。编辑器静止并排 Gate 已废止。
- [ ] 出 Gate 证据：一段未经剪辑的连续游玩录屏 + 60 FPS Trace。

## Next

### 阶段 1 — 第一条 Action 纵向切片

- [ ] Montage（仅回放机制）+ Motion Warping（扭曲 root 轨迹做目标/距离适配，1 条 → N 个有效 Action）。
- [ ] cancel 窗口表建在 Coordinator C++ 里，不用 Notify/Montage 存——契约禁止第二份动作真相。
- [ ] `FHeroAnimStateSnapshot` 扩 Action 相位字段（phase index、cancel 窗口、Montage 位置）。
- [ ] 把 `UHeroActionCoordinatorComponent.h:24-35` 四个 `BlueprintCallable` setter 改为 C++ 内部阶段机
  驱动、对外只暴露请求语义，堵住第二真相源入口。
- [ ] Continuity Bridge：处理三个速度交接突变（进入 Montage 时 `Velocity` 被硬覆盖、退出时收招帧
  root delta 近零导致原地僵住、中途被打断时继承或丢弃峰值速度）。引擎均不自动处理。

### 阶段 2 — 铺量与并行

- [ ] Linked Layers 上下半身分离、additive 受击、Smart Objects 承载 6 类环境交互共用协议。
- [ ] 平地步幅脚滑（stride sync）；本阶段只接受不修。
- [ ] 衣摆二级运动解冻：在 DCC 把下摆权重分给现有 `CoatSkirt` 链并以 Kinesis 自有 Mesh 重新导入，
  或明确改走 Chaos Cloth（先拆服装 section 再建碰撞与权重蒙版）。

### 带触发条件，未到不投入

- [ ] **PoseSearch / Motion Matching**：仅替换 `Grounded` 状态里的 BlendSpace **叶子**，图结构与 C++
  不改（`FAnimNode_MotionMatching` 对 AnimStateMachine 零耦合）。触发条件：locomotion 库超过约
  30–40 条，或 traversal 变体多到 BlendSpace 维护不动。届时 locomotion 须同步切回 root motion 驱动，
  否则丢掉 MM 的真实步幅收益。需新增启用 `PoseSearch` 与 `MotionWarping`（引擎内有、`Abyss.uproject`
  未启用）；Abyss 为多项目共用宿主工程，插件开关只做新增、不改现有。
- [ ] **AnimGen ROI Gate**：插件已启用但零训练数据，本阶段不投入。前置条件是积累足量过 Gate 的自有
  动画集；阶段 0–2 每条过 Gate 动画天然就是训练数据。以 ARDY/MotionBricks 为引擎外延迟参照
  （33 ms / 2 ms），依据见 `research/motion-frontier-survey-2026-08.md`。

### 其他

- [ ] 清理已两次人工否决、判废的 `Kimodo/Retargeted/` 旧批次；`Kimodo/Baked/A_Kimodo_Baked_*_Loop`
  九条保留为备选供货与后续 Root Motion 评估素材，本阶段不扩产。
- [ ] 为 Snapshot 增加最小只读 Debug 输出（Movement、Action、Interaction、Target、FrameId、
  StateRevision）；随后冻结源码管理/LFS 策略并建立首个正式回退提交。
- [ ] 冻结目标 PC、主 DCC、必要 UE 插件与 Source Manifest；决定是否把 `PHYS_AvatarSample_A` 绑定给
  主 Mesh。

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
