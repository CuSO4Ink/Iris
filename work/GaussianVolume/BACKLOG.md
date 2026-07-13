# GaussianVolume · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- **下一步：G4 固定机位性能基准**（详见下方"G4 profiling"任务）。G3 渲染技术前提已全部落地，正式进入按数据决定是否优化的阶段；性能取证可在最终成片前完成。
- G1/G2/G3 缺陷修复验证（2026-07-12，均已实现，多数已用户实测确认）：
  - [x] 场景物体遮挡：深度视口改用 `FViewInfo::ViewRect`（已重编，用户确认）。
  - [x] 单 Actor 内高斯顺序：逐 ray `t_star` 排序 —— 用户手填 primitive 实测近远遮挡正常，确认有效。
  - [x] 跨 Actor 遮挡：改用 `UGaussianVolumeWorldSubsystem` 共享单例渲染器，聚合所有 Component 到单一 pass；每 Actor 保留独立参数，删除 Actor 即时清理无残留。用户实测确认有效。
  - [x] ProbeActor 改为 BeginPlay 单次密度采样，消除 UE 5.8 GPUScene stale-light ensure。
  - [x] 合成迁到 HDR/bloom 前（hook 从 `Tonemap` 改 `MotionBlur`）：交叉处发光死白 → tonemap 滚降 + bloom 柔和高光。
  - [x] SPEC §10 跨 primitive 光照（`LightTauCS` O(N²) prepass + O(1) 查表）：已重编、重启并通过 128 primitive PIE smoke test。
  - [x] 64-hit 满载时保留最近 `t_star` 命中，避免结果依赖 CPU traversal order。
  - [x] 删除重复全屏 SceneColor copy 与无效 CPU 深度排序。
- **G4 profiling 任务**：建立固定机位基准场景（`L_GaussianVolume_TechLab`），测 1080p 下 1/32/64/128 primitive 的 LightTau prepass / Gaussian 主 pass / composite / CPU upload ms，判断是否超出 64 primitives/1080p/≤2ms 初始预算；仅超预算才决定 half-res / PBF / tile 等优化优先级。

## 待办

- [x] UE 集成 Phase 3 验证通过后：关闭 `DebugMode`（设为 0），验证 single scattering + powder effect 光照效果。——已完成，DebugMode=0 光照验证通过。
- [x] 对比基准 vs Niagara Ribbon：2026-07-12 决策不搭并排场景，差异由 Gaussian 自身镜头和口头说明承担；G4 仅保留 Gaussian 自身 GPU 时间/primitive 数矩阵。
- [ ] 为 Gaussian field 增加高层生成参数：spline flow、thickness、density、breakup、emission、LOD。
- [ ] 验证同一 field 同时驱动体积外观、光束衰减和 Niagara/材质 query。
- [ ] 根据对比结果决定是否进入生产工具化；未形成可测量收益时收束为研究型渲染内核。
- UE 集成 Phase 4：Half-res + temporal upsample、PBF-CSF tile association、Depth composite with scene、N×N light tau 矩阵 GPU 化。
- UE 集成 Phase 5：Material/Blueprint interface、VDB import pipeline、Performance profiling。

- [x] 交叉阅读 VoGE，提取 Gaussian ellipsoid renderer、coarse-to-fine rendering、CUDA 结构参考。——已完成 `notes/voge_cross_reading.md`：数学公式与本项目完全一致（CUDA kernel 确认 A/B/C→t_star/peak 映射）；Top-K 截断可借鉴；coarse-to-fine tile rasterization 适合 GPU 化；闭式 cross-activation compositing 与 single scattering 有序 compositing 冲突需评估。
- [x] 交叉阅读 Volumetrically Consistent 3D Gaussian Rasterization，判断 analytic alpha + rasterization 是否可作为 full ray tracing 的实时近似。——已完成 `notes/vol3dgs_cross_reading.md`：**结论：可作 view ray transmittance 的实时近似，不可替代 shadow ray/single scattering**。解析 alpha（erf 无限积分限）可在 rasterizer 框架内 drop-in 替换 splatting alpha，但本项目需保留有限积分限（更精确）+ 逐步 compositing（云 Gaussian 有 overlap，不满足 non-overlapping 假设）。
- [x] 交叉阅读 3DGEER，重点看 ray-Gaussian integral 与 Particle Bounding Frustum / ray-particle association。——已完成 `notes/3dgeer_cross_reading.md`：**PBF 是三篇中对本项目最有价值的 candidate reduction 方案**（不依赖 BVH，per-Gaussian closed-form angular bounds + tile intersection）。canonical space transmittance 与本项目 A/B/C 数学等价。"maximum response" t_star 被 3DGEER 证明是 projective-exact（非启发式）。三篇横向对比表已整理。
- [x] 推导并整理 isotropic / anisotropic Gaussian 的 ray density integral（MVP 已用各向异性版，待补文档）。——已完成 `ray_density_integral.md`：3D 各向异性高斯沿 ray 投影为 1D 高斯 → erf 解析积分，含完整推导 + 实现映射 + 性能汇总。
- [x] MVP renderer Numba JIT 加速——BF + Numba 达 5347 ray/s@N=256（20x 加速）、2097 ray/s@N=1024。
- [x] 预计算光源方向 tau 矩阵——纯 NumPy 6.7x（549→3675 ray/s@N=1024），color diff=0。
- [x] Numba + tau 矩阵集成——prange 竞争修复（每线程独立像素写），NB 76万 ray/s@N=1024，154x vs NP。color diff=1.5e-11。详见 LOG 2026-07-07。
- [x] 后置：实现简单 VDB block → Gaussian primitive 转换。——已完成 `mvp/vdb_converter.py`：支持 pyopenvdb 读取 + NumPy fallback；各向同性/梯度各向异性模式；max_primitives 限制；测试通过（24³ grid, 7928 prims → 512 limited, 18K ray/s, color diff 0.012 iso vs aniso）。
- [x] 后置：UE 集成方案调研（StructuredBuffer、fullscreen pass、half-res + temporal、depth composite）。——已完成 `notes/ue_integration_plan.md`：推荐 Compute Shader 方案（FSceneViewExtension + RDG pass），5 阶段实施路线图（plugin scaffold, data upload, ray tracing renderer, optimization, polish），含 HLSL 伪代码、PBF-CSF tile association、depth composite 方案。

## 已完成（近期，便于回忆）

- [x] 历史预研定位：Gaussian volume 曾优先按 VDB 中远景 LOD / proxy / compression 验证，明确不替代 hero 云；2026-07-10 已将结构化 Gaussian Field FX 提升为当前主验证方向。
- [x] 建立交叉验证论文池：Don't Splat your Gaussians、VoGE、Vol3DGS、3DGEER；辅助看 3DGRT/3DGUT、BiGS、NeMF、SmokeSeer。
- [x] 设计 MVP primitive 结构：center / scale / rotation(quat) / sigma_t / albedo（phase 预留）。
- [x] 搭建 standalone 最小 renderer（mvp/）：手工 Gaussian cloud + 解析 transmittance + front-to-back single scattering。
- [x] 测试 primitive 数量曲线 512~8192（candidate 比例稳定 ~45%）。
- [x] debug view：optical depth / transmittance / candidate count 热图。
- [x] MVP 三问结论：体积感✅、解析 transmittance✅、traversal 可控性⚠️（见 LOG 2026-06-05）。

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。


