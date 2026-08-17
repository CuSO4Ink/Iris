# Screen Space Particle Reconstruction · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务才转成 `tasks/T-xxx.md`。

## 进行中

- [~] **【当前主线 2026-08-12】P0c Gather-only 干净重启**：活动隔离候选为 `P0_GatherOnly_Clean_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`。只保留 Stage A 有界注册 + Stage B 2048² current-cell/K64 + erf/P0c 双 Raw moments；系统精确为 2 个 Simulation Stage、1 个 2048² Grid2DCollection、2 张 2048² RGBA16F Raw RT。Body/Medium/Filament/Depth/Lighting 均回到待讨论、待实现、待逐层验收。正式 M3、金标准和源粒子运动未改；性能数字只认最终同机位完整 Gate。
- [~] **RecordPoint NeighborQuery_V1（运行数据 PASS；用户动态视觉/性能待验）**：`/Game/SSPR_Validation/M3/_RecordPoint_12ms/NeighborQuery_V1/NS_SSPR_V4Dev_RecordPoint_12ms` 已在原资源同级隔离目录落地；原 RecordPoint 与文件备份均保持 SHA-256=`746719…d4ce`。候选只替换 gather 前端：Stage A=`AddParticleWithRadius`，Stage B=current-cell/K128 NeighborQuery gather；源粒子、投影、G5 后端、Renderer、材质、2×2048² RT 与 17 个公共 User 参数保持不变。修复 `Emitter.P0_ParticleRead` 从无效的 `Other/None` 到 `Self` 后，4k/40k 同机位 PIE 与跨帧读回均证明双 RT 非零、全通道 finite、无 NaN/Inf；候选 SHA-256=`f6e931…196ed`。40k 有可见输出但覆盖/亮度相对原版已偏移，`AddParticle` Stage 警告仍保留；下一门只剩用户动态视觉、密度标定及 GPU median/P95，通过前不得替换原 RecordPoint。
- [x] **GatherCompat BinarySafe 实现 donor（已冻结）**：`/Game/SSPR_Validation/M3/Performance/P0_GatherCompat_RecordPoint_Binary_V1/NS_SSPR_V4Dev_RecordPoint_12ms` 提供本次 NeighborQuery Stage A/B 的已审计实现文本与二进制来源；不再作为用户审核入口，也不宣称其旧瞬态 harness 结果代表真实运行。
- [x] Gather-only 基线闭环：Stage A/B HLSL 与冻结 HQ 对应生产核逐字符一致；40k/K64 运行抽样两张 RT 均非零、八通道全有限、无 NaN/Inf；7 个脚本全部 UpToDate、0 error/0 warning。rate=40,000、K=64、DensityPerParticle=0.03 仅保留作固定诊断口径。
- [x] gather 重启前置：钉死**满量同机位 Dense+P1 真实基线**（关闭 System 编辑器、仅关卡实例、记录粒子数/GPU/相机 Transform）；用户于 2026-08-05 明确确认已完成，后续候选必须沿用该记录口径。
- [~] 最终视觉 Gate：旧 HQ v40 为 **FAIL / Request Changes** 并已冻结；新 Gather-only 基线没有最终视觉效果，其 Raw 密度材质只验证连通性。下一轮必须按 Body-only → Medium → Filament → Depth/Lighting 逐层重建和验收，不能把 Raw 调试画面误报为气体完成。用户确认性能无问题，禁止以性能为理由接受不合格画面。
- [x] **Continuous Field Resolve R0→R1.6 已通过**。Rev B 的 Coverage、Pilot/front cluster、signed bands、坐标/half 与单实例合同已落地；最终生产核为对称 `9 Pilot + 24 Main = 33` total taps、Point/Load、2 Raw/2 Field、预计算权重与真实 Pilot early-out，HLSL SHA-256=`c87f1ca81c432ea21ac3090efc55bd26323432da2c49c759a77ee2dfa8682b8a`。live Field 数值闭环与 Synthetic 强制项全过，干净 Stage GPU 中位数 `2.04 ms`。证据见 `P0C-R1-STAGEC-CLOSURE-REPORT-20260809.md`、`P0C-R15-RESOLVE-MICROBENCH-REPORT-20260809.md`、`P0C-R16-PRODUCTION-AND-SYNTHETIC-REPORT-20260809.md`。
- [x] **R2 单 dispatch Body-only：历史 FAIL / REQUEST CHANGES**。V1～V6、Gain 与 sampler 排除均完成；V6=`9 Pilot+32 Main`、41 logical/109 physical loads、HLSL `5bdb675e…5fc` 数值全过但椭圆 stencil 可见，只保留为反证。详见 `P0C-R2-BODY-GATE-REPORT-20260809.md`。
- [~] **R2.2 Niagara-only multipass Body：结构纠偏完成，视觉 FAIL**。v33 把 Body Closure d32 X/Y 前移到 Medium A/B 之前；v34 soft support gate 清掉全卡尾部和离散章，但 Body 变成平滑薄片，尚无合格气体体量。
- [~] **R3 signed Medium：结构 PASS，视觉 FAIL**。v38 诊断证明绝对 M 在主体内过弱；v39 的 Body-relative 归一化产生 Swiss-cheese/泡沫孔洞；v40 改为 Body 包络内的有限密度修正与内部明暗后压住孔洞，但只留下轨迹条纹，未形成中尺度涡团。
- [~] **R4 Filament/Ridge：职责纠偏完成，视觉 FAIL**。raw High 已从主体密度/Opacity 移除，Filament/Ridge 只调光且没有重新出现离散粒子；但当前连续场没有足够的长程相干 ridge，不能生成自然气体拉丝。
- [~] **R5 Depth/Lighting：技术集成存在，视觉 FAIL**。v40 使用深度矩、低频梯度和 signed Medium ratio 做内部受光；它没有解决二维薄片与重复条纹，不能作为掩盖结构失败的验收理由。
- [x] **当前基线资源账本**：2 Raw RT + 1 Grid2DCollection，均为 2048²；旧 HQ 的 2 Raw + 2 Field + 2 Temp + 1 TightBand/约 224 MiB 只保留为历史失败账本与 `Saved/CodexBackups` 证据，Content 中的旧 HQ 分支已清除，不继承到新分支。
- [x] **SSPR Content 全目录收口（2026-08-13）**：`/Game/SSPR_Validation` 已从 192 个可见资产、851 个 External Actor、35 个 External Object 收敛为 40/154/10，约 `223.96 MiB → 42.86 MiB`。当前只剩 `M3` 与 `Versions/V4` 两条顶层闭包。`P0_Gather_RawMoments_V1` 仅因 GatherOnly 内嵌三类 DI 默认对象而保留，`NeighborGather_V1` 仅因 RecordPoint/ReaderWrapped/BinarySafe 内嵌 DI 路径而保留，Versions V4 仍被当前 M3 地图 ExternalActor 直接引用；这三组均标为当前依赖，不得按旧命名误删。完整证据见 `ASSET-CLEANUP-AUDIT-20260812.md`。
- [ ] **源粒子运动形态调整（后置备选）**：优先把当前 Raw moments 重建为合格连续场；只有确认某类卷吸/回流必须依赖特殊输入运动时，才在隔离候选上讨论低频相干 curl、卷吸与尺度分离。Fountain/CurlNoise/Drag/Velocity 当前继续冻结，正式 M3 与金标准不动。
- [x] M2 输入链与 G5 字段契约已冻结：GPU 粒子 → 当前相机投影 → `RasterizationGrid3D` → 2048² Main/Aux → Renderer 双纹理绑定 → ViewportUV 材质采样。
- [x] 当前 Particle G-buffer 契约（自 P0c 起，2026-08-06 修订为原始矩布局 v2）：Raw0(Main)=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`，Raw1(Aux)=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`，2048² RGBA16F、Bilinear、Mip Disabled、每帧完整覆盖。gather 内核只写线性原始矩，MeanDepth/DepthSigma/Coherence/Velocity/Coverage 在 Resolve/材质端归一化派生（Coverage 由 `Density>ε` 推、不占通道）。原 Aux.B 的 Reserved 通道已回收为速度矩；候选调试期的 overflow 若需输出必须临时且明确标记，不得混入最终材质语义。

## 待办

- [x] 备份 M3 Dense `.uasset`，把 P1 bool Enabled Binding 合入 Raster/Resolve，并验证只在最后一个 Fixed Tick substep 执行。（2026-08-03：主线 ProfileGPU 为 `12 ParticleSpawnUpdate : 3 Raster : 3 Resolve = 4∶1`；Main/Aux 有效 RT、DI `1 Raster + 2 RT + 1 Grid2D`、零编译错误。）
- [x] P0 gather 落地（进度见“进行中”）：`P0_GatherOnly_Clean_V1` 已成为唯一活动重启基线；三个早期错误候选继续禁止复用，旧 HQ 冻结不再修补。只有在该干净基线上重新完成 Body/Medium/Filament/Depth 分层视觉与性能复验后，才可决定是否替换正式 M3 主线。
- [x] 记录目标 GPU、粒子量与正式近景相机 Transform：用户确认 Dense+P1 基线记录已完成；候选正式 Gate 必须同机位、同负载、视口前台采集。
- [~] 四层架构进度：Projection、Raster/Binning、P0c Raw moments 已通过并锁定；Body、Medium、Filament 与 Depth/Lighting 的旧实现全部退出活动分支，当前进度统一回到“未实现”。下一轮从 Body-only 最小连续场合同开始，不继承旧 multipass 滤波链。
- [x] 对比 NeighborQuery、NeighborGrid3D fallback、RasterizationGrid 和自定义 RWTexture/Compute：NeighborQuery current-cell/K64 路线已通过 S0/A/A2/B/C；fallback 继续封存，除非 Gate D 证明当前预算下视觉不可接受。
- [x] 建立基础投影验证：World Position → Clip/UV/ViewDepth，并验证相机移动时稳定性。（2026-07-24 效果级通过：单发射器 ProjParticles（GPU sim）SpawnRate=200 + ShapeLocation 球半径 300，SSPR_Projection 用 View.WorldToClip 投影、UV/Depth 写回并编码进 Color；用户实机确认能打开不崩、球状粒子喷出、按投影渐变色、转相机颜色实时变=投影正确工作）
- [ ] 实现局部屏幕包围盒与半/四分之一分辨率 RT，避免默认全屏处理。
- [x] 建立 RT/字段调试视图：历史 Occupancy/M1 已效果级通过；当前 G5 Field Debug 已覆盖 Density、DirectionTensor、Coherence、MeanDepth、DepthSigma、FrontDepth 与 Coverage。NeighborCount/Overflow 仅在 P0 Gather 候选需要时新增。
- [x] Field Operator A 基线结论：point occupancy 已完成正确性验证；“各向同性点模糊作为生产路线”已按 Spec 否决，不再单独投入实现。
- [~] Field Operator B：FrontDepth、MeanDepth、DepthSigma 与深度双边约束已完成；BackDepth 可由 Mean/Sigma 推导，SceneDepth 遮挡与软交界尚未完成。
- [x] Field Operator C / M1 方向性胶囊完成历史技术验证并归档；正式 M3 已改用当前帧各向异性 Splat + 方向张量 + RK2 Streamline，不再审批或恢复 M2 Current/History Ping-pong。
- [x] 旧 M2-B/M2-C Ping-pong 原型已完成技术验证并归档；正式主线不再依赖 Current/History、多张外部 RT 或相机跟随 SmokeCard。
- [x] 从正式验证关卡移除已归档的 `SSPR_M2A_TemporalOrchestrator` 实例，保留归档 Blueprint 资产；新 PIE 不再执行旧 MID/Ping-pong 调度。
- [x] 建立并隔离 M3 V4 Dev 函数闭包：1 个父材质、1 个 MI、7 个自包含函数，引用不回流 M2/V4 源目录。
- [x] 正式 M3 仍保持 `MI_SSPR_AnisotropicSplat_G5_HQ_V4_Dev`，未被失败的 P0c 视觉候选替换。
- [x] 新建隔离的 P0c FieldRecon V2 函数/父材质/MI；按 P0c Raw0/Raw1 重新解码，未覆盖失败 V1 或正式 M3。2026-08-09 已绑定候选 Renderer。
- [x] 删除 Raw 单粒子可见兜底；V2.1 使用双侧/单侧支撑包络、三带 seed confidence、coherence 与深度一致性决定连接，`Contrast=1`；空矩不再以屏幕 X 方向驱动长核。
- [x] **历史失败快照**：V2.1 曾输出 Filament/Medium/Body，权重 `0.12/0.43/0.45`，但用户已否决其刷毛/排线画面；这些结果不得冒充当前 multipass 的 R3/R4 证据。当前 R3/R4 的通过只来自 HQ v11/v12 signed-band 结构与运行读回。
- [x] 接入 Front/Mean/Sigma Depth Transport；父材质 5 函数闭包、0 error，保存后 reload SHA 与参数一致，无 History/旧 Streamline/Raw core 引用。
- [~] M3 视觉 Gate：40k 近景动态已把 v15 与 v40 都判为未达到气体目标；v40 虽不再显示旧点章，但仍是二维薄片与重复轨迹条纹。下一视觉提交不再接受同一冻结输入上的纯滤波参数微调；若用户批准源运动实验，则仍按 Body-only → Body+受约束 Medium → 不进 Opacity 的 Ridge → Depth/Lighting 顺序逐层复验。
- [ ] M3 材质函数命名收口：在视觉 Gate 后处理仍带 Mip 历史命名/接口的函数；不破坏当前已发布函数原地重建。
- [ ] M3 冷启动回归：重启编辑器后验证 Fixed Tick、Main/Aux 无 Mip、单活动实例、RT 非零、零编译错误和动态视觉稳定。
- [ ] M3 最终资产备份：完成视觉与性能 Gate 后冻结 System、Material、MI、7 个函数和验证关卡的完整快照。
- [x] M3/V2 资产清理：已按 live referencer、全 Content 二进制路径扫描和 World Partition ExternalActor 闭包完成；未引用 Probe、失败候选、旧 HQ、M2、V1/V3、Archive、旧 Performance/Recovery 均已清除。仍保留的旧命名资产均有当前内嵌依赖证据，不直接删除。
- [ ] 可选验证有序粒子链的线段/胶囊距离场，与 MLS 类方案比较成本和质量。
- [ ] 设计多层深度策略，验证同一视线存在两个分离粒子团时 min/max 错误填充问题。
- [ ] 从平滑 ViewDepth 重建 ViewPosition 与 Normal，并与 SceneDepth 做遮挡。
- [ ] 建立至少三种 Resolve Material：水/史莱姆、烟/火、能量/全息。
- [x] 旧时间重投影原型已完成技术验证并归档；正式 M3 每帧从三维粒子重新投影，不把 Current/History 作为主要拖尾。若未来需要时序稳定，只能作为独立可选模块重新评估。
- [~] 建立 GPU Profile 表：Dense、P1、P0 Gather 与 33-tap Stage C 基线已有归因证据；R1.6 Stage C 历史干净中位 `2.04 ms`。当前 18-stage/7-RT HQ 的完整链尚未正式 Profile；用户要求先以画面为主，视觉通过后再跑同机位完整链 median/P95，并与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 对照。
- [ ] 设计 VR、反射和多摄像机情况下的 per-view 重建策略。
- [ ] 拆解 UE Content Examples 中 Niagara Fluids 的 Grid2D、3D Liquid、sphere rasterizer、SDF/Jump Flood 资产，记录真实 Stage 与 DI 连接。
- [ ] 若可取得 FluidNinja LIVE Student/正式版，验证 Density/Velocity/Pressure RT 的格式、更新顺序、坐标映射和 Niagara 双向接口。
- [ ] 评估是否兼容外部 Field Provider：让 Niagara Fluids Grid 或 FluidNinja RT 直接接入 Resolve Material，而不经过本项目 Projection 层。

## 已完成（近期，便于回忆）

- [x] 按 Iris project-kit 初始化项目三件套；确定"先架构、后算法"方向；调研 Niagara Fluids/FluidNinja 可借鉴边界。
- [x] 2026-07-24~27 早期通路与 M1/M2-A 技术验证（buffer scatter、Occupancy RT、Grid2D 稀疏写、Direct RT 方向胶囊、Temporal A/B 调度器）均已归档；正式 M3 不再依赖，细节见 LOG.md。
- [x] 2026-07 VibeUE 插件根因修复（`RequestNewTypedPin` 解 scratch AddPin 越界崩溃 K11、System 资产 scratch 归属 ScratchPadScripts）；后续 gather 又修 ResolveType 缺 NeighborQuery/ParticleRead 类型（仅需 rebuild），细节见 LOG.md。
- [x] 2026-08-03 P1 Last-Substep Enabled Binding 合入 M3 Dense：ProfileGPU `4∶1`、Main/Aux 有效 RT、零编译错误（40ms→22ms 主要功臣；22ms→12ms 那段为糊涂账，需满量同机位复测）。
- [x] 2026-08-04 完成 NeighborQuery→ParticleRead 数据链探针；该粒子端原型只证明 API 连通性，已作废，不代表 P0 像素端架构完成。

---

完成超过 2 周的项移除；有长期保留价值的结论写进 LOG.md。
