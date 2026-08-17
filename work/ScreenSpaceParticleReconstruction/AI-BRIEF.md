<!-- iris-project-kind: ue -->
# Screen Space Particle Reconstruction

> **UEAgent first.** Before reading or changing live Unreal state, read
> [UEAgent](../UEAgent/AGENTS.md) and the
> [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md), then locate the target project's
> `Saved/UEAgent/route.json` and run `compact_context.ps1` without loading either file unless it fails. Stop on `CACHE_READ`; on
> `NEEDS_DOCTOR`, run the routed `doctor.ps1` once and use its receipt. Offline
> source/cache/config/log analysis may skip MCP but must not claim live Editor state.

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

搭建一套与具体密度/场算法解耦的屏幕空间粒子重建架构：把 3D 粒子按当前摄像机投影到二维空间，生成可组合的 RT/G-buffer，再由通用材质派生流体、烟雾、能量、卡通等效果。

## 当前状态

活跃；正式主线仍是无 History 的 Niagara GPU 粒子→六属性 Raster→Main/Aux RT→屏幕空间重建。旧 `25×5` Sparse V1 因运行 RT 全零判失败；当前独立候选 `/Game/SSPR_Validation/Performance/DenseG5SparseV2/NS_SSPR_AnisotropicSplat_Main` 由可运行 Dense G5 二进制直接复制而来，使用保守质量守恒 `33×7` 核，保持 2048²、约 25 万粒子、Fixed Tick 与旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 不变。候选新增的 Main/Aux 已跨请求独立读回非零。此前得到的 `0.697～0.715 ms/步` Profile 没有记录相机姿态，不能与用户近景 Dense `.profViz` 的 `17.70～18.88 ms/步` 直接相除；随后在约 `1194 uu` 近景重抓时只捕获 Slate 帧。故 RT Gate 仍有效，但性能 Gate 已重新打开，`24.8～27.1×` 不再作为成立结论。FieldRecon 仍为实验候选，不代表当前视觉基线。

当前高品质稳定基线：Main/Aux 均为 2048² RGBA16F、Bilinear、自动 Mip 关闭；Niagara System 开启 `Fixed Tick Delta=0.01667s`；旧 G5 HQ 使用无 History 的双向 RK2 Streamline 与原始低强度 DepthCue。Main/Aux 六属性仍完整生成，但 FieldRecon 的 Coverage 归一化和较强 DepthTransport 暂不参与最终显示。

## 当前焦点

当前显示为旧 G5 HQ + Sparse V2；下一焦点是固定同一近景相机，对 Dense 与 Sparse V2 分别抓取包含 Niagara 场景渲染的 ProfileGPU，再判断实际收益。`33×7` 还保留 `49+11+33+7` 次质量归一化循环和大量 `exp()`，理论原子候选下降 `57.14%` 并不等于 Stage 时间下降 `57.14%`。完成同机位 A/B 后再决定是否改为解析质量补偿和低样本 Streamline Kernel。参数定义见 `NIAGARA-USER-PARAMETERS.md`。

当前编辑器会话已将 `fx.Niagara.SystemSimulation.MaxTickSubsteps` 从源码默认 `100` 临时设为 `4`。这不关闭 60 Hz Fixed Tick，只限制单个慢帧最多补做 4 步，避免旧 Profile 中 24 步追帧螺旋；该设置尚未写入项目配置，重启后会恢复默认，不能替代 Raster 本身的优化。

为方便性能与视觉对照，已定位原始粒子 Renderer 变透明的原因：Renderer 0 的 Visibility 为隐藏值，Sprite Size 又绑定到很小的 `Particles.SSPR_ScreenDeltaUV`。当前候选已备份，并提交了切回 `RendererVisibility=0`、`Particles.SpriteSize` 的待验证设置；仍需 Apply/Compile/Save/Reinitialize 后才算对照模式完成。最终 G5 Renderer 1 不变。

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

- `AI-BRIEF.md`：项目目标、边界、架构接口与术语。
- `BACKLOG.md`：阶段任务和验证项。
- `LOG.md`：关键决策、否决方案与发现，追加式维护。
- `WISPY-FLUID-SPEC.md`：正式主线总体规格与 M0～M5 里程碑。
- `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`：V2 各向异性 Splat 与 G0～G6 规格。
- `NIAGARA-RASTER-MCP-PITFALLS.md`：UE 5.8 Niagara Raster、MCP 与资产自动化排坑手册。
- `tools/install-direct-rt-writer.py`：需要重建旧 Direct RT Writer 时使用的可复用安装工具。
- `tools/reinitialize-g5-runtime.py`：不重新绑定资产、只重初始化 G5 运行实例的安全工具。

## 文件边界

- `work/ScreenSpaceParticleReconstruction/` 只保留正式文档与可复用工具。
- 截图、回读、恢复副本、Profile、一次性脚本和其他实验过程文件写入 `tmp/ScreenSpaceParticleReconstruction/`，验证完成后删除。
- 完成项和失败实验只追加到 `LOG.md`，不继续堆在 `BACKLOG.md`。

## 协作约定

- 当前阶段不提前绑定某一种密度/边缘重建算法；先保证模块接口可替换。
- 技术讨论先写清几何前提、复杂度与适用范围，再进入 Niagara/HLSL 操作步骤。
- 文档中的算法示例必须做数学自洽检查；参考资料不直接视为可运行实现。
- 正式项目文件改动限定在本目录；过程产物按上面的文件边界进入 `tmp/`。新文件名只用英文。

---

## 维护

- 阶段切换、RT 通道约定、模块接口或性能目标变更时更新本文件。
- 本文件保持在 100 行以内；大任务确有必要时再建 `tasks/T-xxx.md`。
- 项目归档时本文件随项目目录迁移。
