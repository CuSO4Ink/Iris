# Screen Space Particle Reconstruction · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务才转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 定义四层架构接口：Projection、Binning、Field Operator、Resolve Material。
- [ ] 确定最小 Particle G-buffer 通道、格式、清屏值和读写语义。

## 待办

- [ ] 明确第一版运行约束：UE 版本、目标 GPU、粒子数量 N、目标分辨率、帧预算和摄像机数量。
- [ ] 对比 Neighbor Grid 2D、RasterizationGrid 和自定义 RWTexture/Compute 的职责与成本。
- [ ] 建立基础投影验证：World Position → Clip/UV/ViewDepth，并验证相机移动时稳定性。
- [ ] 实现局部屏幕包围盒与半/四分之一分辨率 RT，避免默认全屏处理。
- [ ] 建立 RT 调试视图：Occupancy、FrontDepth、BackDepth/Thickness、Density、NeighborCount、Overflow。
- [ ] 实现 Field Operator A：最简单的各向同性粒子 splat，作为正确性基线。
- [ ] 实现 Field Operator B：FrontDepth + Thickness + edge-aware smoothing，验证流体表面。
- [ ] 实现 Field Operator C：各向异性 splat，验证稀疏线状粒子边缘。
- [ ] 可选验证有序粒子链的线段/胶囊距离场，与 MLS 类方案比较成本和质量。
- [ ] 设计多层深度策略，验证同一视线存在两个分离粒子团时 min/max 错误填充问题。
- [ ] 从平滑 ViewDepth 重建 ViewPosition 与 Normal，并与 SceneDepth 做遮挡。
- [ ] 建立至少三种 Resolve Material：水/史莱姆、烟/火、能量/全息。
- [ ] 加入时间重投影或稳定滤波，评估相机运动下的闪烁和拖影。
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

---

完成超过 2 周的项移除；有长期保留价值的结论写进 LOG.md。
