# Screen Space Particle Reconstruction

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

搭建一套与具体密度/场算法解耦的屏幕空间粒子重建架构：把 3D 粒子按当前摄像机投影到二维空间，生成可组合的 RT/G-buffer，再由通用材质派生流体、烟雾、能量、卡通等效果。

## 当前状态

活跃；项目已初始化，处于架构设计阶段，尚未锁定具体场重建算法。

## 当前焦点

先定义稳定的“粒子投影与分桶 → 可插拔场处理 → RT 组 → 材质消费”接口和数据约定，再分别验证不同密度/场域算法。

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
