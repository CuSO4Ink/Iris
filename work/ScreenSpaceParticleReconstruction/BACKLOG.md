# Screen Space Particle Reconstruction · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务才转成 `tasks/T-xxx.md`。

## 进行中

- [~] V2 各向异性高斯 Splat：规格已批准，G0～G3 技术链和视口基础结果已通过；G4 已安装 LOD0 7×7/13×13 多尺度材质，当前等待最终烟雾视觉 Gate。
- [x] M2 正式主线已验收并冻结：GPU 粒子 → 相机投影 → Grid2D → Niagara 自管 2048² RGBA16F SimRT → Renderer 参数绑定 → ViewportUV 材质采样完整跑通。
- [~] M3/G4 函数化高品质烟雾重建：Raw、LOD0 7×7/13×13 Filament/Medium/Body、Density Shape、Edge Mask、Beer–Lambert Resolve 和可选 Gradient Lighting 已组成正式函数链；当前 HQ 实例用中性光照优先验收密度连续性，暂不做性能降级。
- [ ] 定义四层架构接口：Projection、Binning、Field Operator、Resolve Material。
- [ ] 确定最小 Particle G-buffer 通道、格式、清屏值和读写语义。

## 待办

- [ ] 明确第一版运行约束：UE 版本、目标 GPU、粒子数量 N、目标分辨率、帧预算和摄像机数量。
- [ ] 对比 Neighbor Grid 2D、RasterizationGrid 和自定义 RWTexture/Compute 的职责与成本。
- [x] 建立基础投影验证：World Position → Clip/UV/ViewDepth，并验证相机移动时稳定性。（2026-07-24 效果级通过：单发射器 ProjParticles（GPU sim）SpawnRate=200 + ShapeLocation 球半径 300，SSPR_Projection 用 View.WorldToClip 投影、UV/Depth 写回并编码进 Color；用户实机确认能打开不崩、球状粒子喷出、按投影渐变色、转相机颜色实时变=投影正确工作）
- [ ] 实现局部屏幕包围盒与半/四分之一分辨率 RT，避免默认全屏处理。
- [~] 建立 RT 调试视图：Occupancy/M1 已效果级通过（`RT_SSPR_Occupancy` 256×256 R16F/UAV；Projection 输出 UV/屏幕速度，Direct RT writer 写速度方向胶囊并用每粒子 64 点分布式衰减避免永久画满；2026-07-28 再次完成长时间运行回归）。M2 已改用独立 `M2/NS_SSPR_ProjTest_M2`，避免 Current-only Writer 污染 M1 独立预览；FrontDepth、BackDepth/Thickness、Density、NeighborCount、Overflow 待建。
- [x] Field Operator A 基线结论：point occupancy 已完成正确性验证；“各向同性点模糊作为生产路线”已按 Spec 否决，不再单独投入实现。
- [ ] 实现 Field Operator B：FrontDepth + Thickness + edge-aware smoothing，验证流体表面。
- [~] 实现 Field Operator C / M1 方向性胶囊：Curl Noise + Solve Forces 生成运动，Projection 输出屏幕速度，Direct RT writer 写半径 1.5 px/最长 12 px 的方向胶囊。基础动态结果已通过；相机运动横条经无方向像素置换与 0.78 衰减后，用户反馈“好多了”。单 RT 历史正式降级为调试实现，剩余严格相机稳定交给待审批的 M2 Current+History Ping-pong。
- [x] 旧 M2-B/M2-C Ping-pong 原型已完成技术验证并归档；正式主线不再依赖 Current/History、多张外部 RT 或相机跟随 SmokeCard。
- [x] 从正式验证关卡移除已归档的 `SSPR_M2A_TemporalOrchestrator` 实例，保留归档 Blueprint 资产；新 PIE 不再执行旧 MID/Ping-pong 调度。
- [x] 建立 M3 函数库 `/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQBaseline`：Raw、MultiScale、DensityShape、SmokeResolve 四个函数，父材质仅编排参数和输出。
- [x] V1 历史阶段建立 `MI_SSPR_ParticleTrails_HQ_Default` 作为视觉调参层；V2 当前已切换为自包含的 `MI_SSPR_AnisotropicSplat_HQ`。
- [ ] M3 视觉 Gate：在正式相机距离与运动下消除独立粒子点感，确认连续拉丝、柔软团块、层次和屏幕边缘均满足目标。
- [ ] V2 材质函数收口：将已经不读取 Mip 的 `MF_SSPR_MipPyramidDensity` 正式版本化/更名，移除失效的 MipBias 接口并归档旧函数。
- [ ] V2 冷启动回归：重启编辑器后验证 Fixed Tick、无 Mip SimRT、单活动实例、RT 非零、零编译错误和动态视觉稳定。
- [ ] V2 最终资产备份：完成视觉 Gate 后冻结 System、Material、MI、引用函数和验证关卡的完整快照。
- [ ] V2 资产清理：依赖扫描后归档未引用的 Probe、旧函数副本和 AnisotropicSplat 原型；不直接删除未知引用资产。
- [ ] 可选验证有序粒子链的线段/胶囊距离场，与 MLS 类方案比较成本和质量。
- [ ] 设计多层深度策略，验证同一视线存在两个分离粒子团时 min/max 错误填充问题。
- [ ] 从平滑 ViewDepth 重建 ViewPosition 与 Normal，并与 SceneDepth 做遮挡。
- [ ] 建立至少三种 Resolve Material：水/史莱姆、烟/火、能量/全息。
- [x] 旧时间重投影原型已完成技术验证并归档；正式 V2 每帧从三维粒子重新投影，不再把 Current/History 作为主要拖尾。若未来需要时序稳定，只能作为独立可选模块重新评估。
- [ ] 建立 GPU Profile 表：O(N)、O(qGk)、O(G) 各阶段实测时间与显存。
- [ ] 设计 VR、反射和多摄像机情况下的 per-view 重建策略。
- [ ] 拆解 UE Content Examples 中 Niagara Fluids 的 Grid2D、3D Liquid、sphere rasterizer、SDF/Jump Flood 资产，记录真实 Stage 与 DI 连接。
- [ ] 若可取得 FluidNinja LIVE Student/正式版，验证 Density/Velocity/Pressure RT 的格式、更新顺序、坐标映射和 Niagara 双向接口。
- [ ] 评估是否兼容外部 Field Provider：让 Niagara Fluids Grid 或 FluidNinja RT 直接接入 Resolve Material，而不经过本项目 Projection 层。

## 已完成（近期，便于回忆）

- [x] 按 Iris project-kit 初始化项目三件套。
- [x] 确定“先架构、后算法”的项目方向。
- [x] 记录屏幕空间粒子重建的初始模块边界和候选 RT 数据。
- [x] 调研 Niagara Fluids 与 FluidNinja 的公开架构并记录可借鉴边界。
- [x] 2026-07-24 buffer scatter 通路效果级打通：`SSPR_WriteOccupancy` scratch 模块（RT2D DI `OccupancyRT` + 按 `SSPR_ScreenUV` 的 `SetRenderTargetValue` 写入）→ 绑定 `RT_SSPR_Occupancy`（经 DI 的 Render Target User Parameter 字段 → user param `OccupancyRTParam`）→ 中心红块验证通过。配套：`SSPR_InitAttrs`（spawn 初始化属性）、emitter 改 `NoInterpolation` 解决 read-before-set。
- [x] 2026-07-24 VibeUE 插件两处根因修复（分支 `sspr-scratchpad-fixes`）：路A（scratch AddPin 越界崩溃，改引擎导出宏+RequestNewTypedPin）；scratchpad 系统级归属（commit `8b43efa`：System 资产模式脚本须进 `System->ScratchPadScripts`，否则编辑器无图标/点不进）。
- [x] 2026-07-26 修复 Occupancy RT 近似全黑：恢复 `SSPR_Projection.OutUV` 并写回 `Particles.SSPR_ScreenUV`；重建 `SSPR_WriteOccupancy` 的 MapGet，写入前验证 UV/RT 尺寸且不再把越界粒子 clamp 到边缘；RT/DI 统一 256×256 R16F，开启 UAV 与最近点过滤。5 个 Niagara 脚本 UpToDate、零错误零警告，System 与 RT 已保存。
- [x] 2026-07-26 M1 技术实现：加入 CurlNoiseForce（Strength=250、Frequency=20）与 SolveForcesAndVelocity；Projection 以固定 `1/60s` 参考步长输出归一化屏幕速度；Writer 按实际 RT 尺寸换算并用固定上限循环写入二值胶囊。图结构读回、原生 GPU 编译、日志与保存均通过；视觉 Gate 待用户确认。
- [x] 2026-07-27 修复方向轨迹画满 RT 及首次 Grid 全红：确认外部 RT2D DI 只写 1、无帧清理会永久累积；改用系统级 Grid2DCollection 做粒子稀疏写入，开启非网格迭代 Stage 前清理并覆盖复制到 `RT_SSPR_Occupancy`。首次用命名 Attribute 时运行组件未同步新 Grid DI，且预览克隆仍保留 0 个匿名通道，外部 RT 只显示 Grid 重建时的红色 ClearColor；最终改为固定 1 个匿名通道、`SetValueAtIndex(...,0,...)`，并重建关卡/预览组件参数存储。图连线、两个运行 DI、RT 绑定、5 脚本编译与保存均独立读回通过。
- [x] 2026-07-27 修复 Grid 版纯黑：重建 Writer MapGet 时只恢复了 RT/Grid DI，漏掉 `Particles.SSPR_ScreenUV` 与 `Particles.SSPR_ScreenVelocityUV`，导致 HLSL 输入默认为零但编译仍通过；现已补回两个 vec2 Pin 与两条连线，5 脚本 UpToDate、零错零警并保存，唯一 Niagara 预览实例已绑定外部 RT、Active/Tick/ForceSolo。
- [x] 2026-07-27 修复 VibeUE DI 动态输入注册：`AddModuleInput`/动态 `AddPin` 改走 `RequestNewTypedPin`，使隐藏默认 Pin、模块签名和 stack topology 一致；离线编译成功，插件分支提交 `44d9f72`。
- [x] 2026-07-27 M1 最终视觉验收：Grid2D 外部 RT 输出路线仍黑后改用已验证的 Direct RT DI，加入分布式历史衰减和速度方向胶囊；Niagara PreviewScene 中动态轨迹正确，用户确认通过。正式 Writer 安装脚本：`_black3_install_direct_rt_writer.py`。
- [~] 2026-07-27 相机运动回归：Direct RT 屏幕历史未重投影，且旧衰减连续访问 64 个 row-major 像素，左右转视角时形成水平条带。现已改为逐帧旋转的无方向置换覆盖并缩短历史半衰期；5 脚本全绿、资产保存和预览重启完成，待视觉复验。
- [x] 2026-07-27 M2-A 技术实现：三张 256×256 R16F RT、Current-only Writer、Temporal Material、History A/B Blueprint 调度器、显式 PlayerCameraManager 代表深度重投影、Camera Cut 历史拒绝与 `ResetTemporalHistory` 均已保存。材质与 Blueprint 零编译错误；A/B 保持、平移、衰减归零自动化验证通过。

---

完成超过 2 周的项移除；有长期保留价值的结论写进 LOG.md。
