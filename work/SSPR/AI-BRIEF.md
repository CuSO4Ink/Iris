<!-- iris-project-kind: ue -->
# Screen Space Particle Reconstruction

> **UEAgent first（UE live/MCP 强制前置）**：先导航到 [UEAgent 入口](../UEAgent/AGENTS.md) 和 [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md)，再处理本项目 brief。先读取目标项目 `Saved/UEAgent/route.json` 并运行 `../UEAgent/scripts/compact_context.ps1`；只有 `CACHE_READ` 才停止 MCP，`NEEDS_DOCTOR` 则运行一次 `scripts/doctor.ps1` 并直接用其 receipt，`BLOCKED` 需修复路由。确认路由状态后才读取项目任务内容。纯离线源码/cache/config/log/文档分析可跳过 MCP，但不得声称 live editor 状态；live 修改或保存必须走已授权的 task-gated 路径。

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

搭建一套与具体密度/场算法解耦的屏幕空间粒子重建架构：把 3D 粒子按当前摄像机投影到二维空间，生成可组合的 RT/G-buffer，再由通用材质派生流体、烟雾、能量、卡通等效果。

## 当前状态

活跃；当前执行主线已于 2026-08-12 **回退为 Gather-only 干净重启基线**。本 checkpoint 只锁定：Niagara GPU 粒子 → Stage A 屏幕空间 `AddParticleWithRadius` 有界注册 → Stage B 2048² current-cell/K gather + erf 解析核 → Main/Aux P0c 原始矩。Body、Medium、Filament、Depth/Lighting 及任何连续场后处理都不属于当前已实现层，必须从该基线重新讨论、分层实现和逐层视觉验收。Main/Aux 均为 2048² RGBA16F；Fixed Tick `0.01667s`。正式视觉主线仍是 `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev`，干净性能锚点仍是 `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`；新候选在视觉 Gate 通过前不得替换正式主线。

**性能/数据层真实状态**：当前可编辑重启基线为 `/Game/SSPR_Validation/M3/Performance/P0_GatherOnly_Clean_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`。它精确只含 `SSPR Rasterize Trails` 与 `SSPR Resolve Grid To Material` 两个 Simulation Stage、1 个 2048² Grid2DCollection 和 2 张 2048² RGBA16F Raw RT；Stage A/B HLSL 与冻结 HQ 中的对应生产核逐字符一致。40k/K64 运行抽样证明两张 RT 均非零、八通道全有限、无 NaN/Inf；系统 7 个脚本全部 UpToDate、0 error/0 warning。此前 P0c Gate S0/A/A2/B/C 与性能数据继续作为 Gather 数据层历史证据，但不等于新分支的视觉或完整性能验收。诊断参数 rate=40,000、K=64、DensityPerParticle=0.03 仅用于固定对照，不是视觉终态。

**视觉纠偏状态**：RawMoments Streamline、V2/V2.1 的 8 steps×5 lanes、单 dispatch R2 V1～V6，以及 HQ v15～v40 均已被用户否决并冻结为失败证据；不得复用 Raw 单粒子兜底、宽 Streamline、刷毛排线、有限 Point stencil 印章或 18-stage 滤波堆叠。旧 `/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1` 已在逐文件哈希一致备份和 StarterMap 引用解锁后从 Content 清除；失败证据只保留在 `Saved/CodexBackups` 与项目日志中，不再占用活动资产目录。新基线的 `M_SSPR_GatherRawDensity_Debug` 只把 RawMain.R 显示为密度连通调试，不代表气体最终效果。当前金标准仍是 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的 Niagara Fluids/NS 气体形态；正式预算只认视觉通过后的同场景、同机位、同分辨率、单系统完整链路 A/B。

**Stage C 当前真实进度**：没有活动实现。R0～R1.6、R2 V1～V6 与 HQ v15～v40 只保留为历史正确性、性能或失败证据；旧 HQ 的 18 Stage、7 张 RT 不继承到新分支。新基线中不存在 Continuous seed、Atrous、Closure、Tensor Diffuse、Pass Through、Streamline 或任何 Stage C，资源下限已回到 2 张 Raw RT + 1 个 Grid2DCollection。正式 M3、金标准和源粒子运动均未改。

**Reader 封装接口（2026-08-12）**：`/Game/SSPR_Validation/M3/_RecordPoint_12ms/ReaderWrapped_V1/NS_SSPR_V4Dev_RecordPoint_12ms_ReaderWrapped_V1` 的 `SSPR_Reader` 已改为通过 Emitter 级 Particle Attribute Reader 直接读取标准 `Particles.Position` 与 `Particles.Velocity`，不再要求源 Emitter 写入 `Particles.SSPR_FlowVelocity`。零修改接入仍要求源是同一 Niagara System 内、绑定名称可解析且使用 GPU Compute Sim；直接改 Position、瞬移或自定义约束但未同步 Velocity 的特殊运动不保证拉丝方向准确。封装内置对照源仍保留旧 `SSPR_ResetVelocityAfterSolve`，会把其标准 Velocity 清零；这是对照源兼容事项，不属于外部标准 Emitter 的接口要求。

**RecordPoint NeighborQuery 隔离候选（2026-08-17）**：当前待用户动态视觉审核资产为 `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NeighborQuery_V1/NS_SSPR_V4Dev_RecordPoint_12ms`。它保持当前最佳 RecordPoint 的粒子源、投影、两段 Simulation Stage、G5 材质、Renderer 绑定及 2 张 2048² RGBA16F RT 合同不变，只把 Stage A/B 的 `RasterizationGrid3D` 原子归约/读取替换为 `NeighborQuery.AddParticleWithRadius` 与 current-cell/K128 粒子 gather。精确 HLSL/拓扑/参数审计已过；修复继承自原资源、在 Raster 路径中未被使用的 `Emitter.P0_ParticleRead=Other/None` 为 `Self` 后，4k 与 40k 同机位瞬态 PIE 均证明两张 RT 持续非零、八通道 finite、无 NaN/Inf，候选 SHA-256=`f6e931…196ed`。40k 截图确认有真实输出，但相对原 RecordPoint 覆盖更宽、主体更亮，尚未取得用户对动态画面、密度标定和视觉等价的批准；GPU median/P95 也未采。引擎的 side-effect-only `AddParticle` 警告仍登记为已知风险，但本资产的实际注册/gather 已由跨帧 RT 证据证明可运行。候选在视觉与性能 Gate 前仍不替换原 RecordPoint。

## 当前焦点

下一执行点从 Gather-only 基线重新定义连续重建，不再删改旧 HQ 或继续叠滤波。先提出并审查 Raw moments → 连续 Body 的最小合同与 Body-only 调试画面；Body 通过后才设计 Medium，最后才叠 Filament 与 Depth/Lighting。每一层必须有独立调试输出，任何重新显出粒子落点、轨迹印章、二维薄片或无支撑孤立分支都直接失败。源粒子运动调整保留为后置备选，只在重建端确实需要特殊运动形态时再讨论。硬边界继续是禁止 native RDG、C++、USF、插件、引擎源码和项目源码修改；正式 M3 与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 不动。用户已确认当前性能无问题，完整性能 Gate 延后到视觉通过后。

**工具链前提（已铺好，勿重踩）**：VibeUE `ResolveType()` 已支持 NeighborQuery/ParticleRead（DLL 2026-08-04 17:16）；K11 scratch 崩溃已由 niagara-authoring profile 解除（走 `RequestNewTypedPin`）；System 级 DI 被 UE5.8 引擎堵死，用 Emitter 级；构建用 `-NoUba -MaxParallelActions=4` + 输出重定向，勿大 yield 轮询吞日志。详见 LOG.md 与 `NIAGARA-RASTER-MCP-PITFALLS.md`。

## 技术栈与硬约束

- Unreal Engine / Niagara GPU Simulation / HLSL / Render Target 或 Grid Data Interface。
- 每帧基于当前 View/Projection 矩阵工作，结果是 view-dependent 的屏幕空间 2.5D 表示。
- 架构必须与具体重建算法解耦；KDE、线段距离、各向异性 splat、MLS/RBF、双边/曲率流平滑均作为可替换模块。
- Neighbor Grid 2D 仅在后续需要枚举邻居粒子时使用；纯 min/max/sum 归约优先评估 RWTexture/RasterizationGrid，避免无意义的索引存储。
- 广告牌/代理几何只作为材质载体；需要立体感时必须由每像素深度反算视图/世界位置，不能只依赖面片跟随相机旋转。
- 性能评估统一使用 N（粒子数）、G（处理像素数）、k（平均邻居数）、q（邻域遍历次数）：投影 O(N)，邻域处理 O(qGk)，材质解析 O(G)。

## 术语表

- **Projection layer**：把世界空间粒子投影到屏幕/局部 RT 空间，并输出中心、半径、深度和属性。
- **Binning layer**：二维分桶或原子归约层，为后续场处理提供局部数据。
- **Field operator**：可插拔场算法；输入粒子/格子数据，输出连续密度、距离、深度或厚度。
- **Particle G-buffer**：供材质使用的 RT 组，候选通道包括 FrontDepth、BackDepth/Thickness、Density、Normal/Tangent/Velocity、Color/Temperature 和 Validity。
- **Resolve material**：读取 Particle G-buffer，重建位置/法线并组合最终视觉效果的材质。
- **2.5D**：只对当前视角有效的深度化屏幕表示，不等价于完整三维体数据。

## 外部参照基线

- **Niagara Fluids**：已验证其抽象同样是“粒子/源 → Grid2D/Grid3D → Simulation Stages → Renderer/Material”；可借鉴数据接口、scatter、分阶段计算和调试方式，但官方模板主要工作在模拟域，不等价于本项目的屏幕空间 Particle G-buffer。
- **Niagara 3D Liquid**：公开拆解显示其 PIC/FLIP 粒子可经 sphere rasterizer、SDF/Jump Flood 等步骤重建液面，再交给水材质；这是最接近本项目“粒子 → 连续表面 → 材质”的官方体系参照。
- **FluidNinja LIVE**：公开功能明确暴露 Density、Velocity、Pressure 到 Render Targets，并支持 Niagara 双向数据流、ActorComponent 驱动材质/体积组件；其“模拟缓冲与表现解耦”高度相似，但 2D 模拟容器不必然是由摄像机投影粒子产生的屏幕空间深度场。
- **FluidNinja VFX Tools**：主要是烘焙 2D 流体数据到 flipbook/flowmap，再由 Niagara 或材质采样；适合参考数据接口和播放器层，不是本项目每帧动态重建的直接同类。

## 文档地图

- `AI-BRIEF.md`：项目目标、边界、架构接口与当前工作状态。
- `BACKLOG.md`：当前 P0 gather 重启主线、验证 Gate 与后续任务。
- `LOG.md`：历史决策、事故、根因与验证证据；只用于追溯，不作为当前实现规格。
- `M3-PERF-OPTIMIZATION-SPEC-20260731.md`：当前性能路线权威依据（P0 gather / P0b 解析核 / P0c 原始矩布局 / 坑 checklist / P2）。
- `ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md`：AGS erf 解析核；当前作为 gather Stage B 的 P0b 内核参考。
- `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`：六属性字段契约与 M3 G5 视觉基线参考。
- `P0C-NORMALIZED-FIELD-RECON-PLAN.md`：当前纠偏实现的结构合同、禁止项、资产边界与分层 Gate。
- `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md`：current-frame Stage C 权威执行合同；当前状态为 R2.2 v33～v40 结构/职责纠偏完成但视觉失败，源运动实验等待用户明确批准。
- `P0C-R2-BODY-GATE-REPORT-20260809.md`：R2 V1～V6、数值/视觉/性能证据、恢复点与后端决策边界。
- `NIAGARA-RASTER-MCP-PITFALLS.md`：UE 5.8 Niagara Raster、MCP 与资产自动化排坑手册。
- `NIAGARA-USER-PARAMETERS.md`：当前 M3 Dense 参数与资产约定。
- `archive/2026-08-05-cleanup/docs/`：已完成阶段规格、快照、交接和合并记录，只作历史回溯，不作为当前执行入口。
- `archive/2026-08-05-cleanup/scratch/`：历史探针、运行时 dump 与临时脚本，不作为执行入口。

## 协作约定

- 当前阶段不提前绑定某一种密度/边缘重建算法；先保证模块接口可替换。
- 技术讨论先写清几何前提、复杂度与适用范围，再进入 Niagara/HLSL 操作步骤。
- 文档中的算法示例必须做数学自洽检查；参考资料不直接视为可运行实现。
- 项目文件改动限定在本目录；新文件名只用英文。

---

## 维护

- 阶段切换、RT 通道约定、模块接口或性能目标变更时更新本文件。
- 本文件保持在 100 行以内；大任务确有必要时再建 `tasks/T-xxx.md`。
- 项目归档时本文件随项目目录迁移。
