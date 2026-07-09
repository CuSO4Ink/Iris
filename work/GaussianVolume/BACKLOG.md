# GaussianVolume · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [x] 实现加速结构（uniform grid / macro cell）——结论：grid 不减少 actual candidate 数，只减少被测试 primitive 数；纯 Python 和 Numba 下均比 BF 慢。真正瓶颈是 O(n_cand^2) compositing。详见 LOG 2026-07-07。

## 待办

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

- [x] 明确预研定位：Gaussian volume 优先作为 VDB 中远景 LOD / proxy / compression，而非 hero 云完整替代。
- [x] 建立交叉验证论文池：Don't Splat your Gaussians、VoGE、Vol3DGS、3DGEER；辅助看 3DGRT/3DGUT、BiGS、NeMF、SmokeSeer。
- [x] 设计 MVP primitive 结构：center / scale / rotation(quat) / sigma_t / albedo（phase 预留）。
- [x] 搭建 standalone 最小 renderer（mvp/）：手工 Gaussian cloud + 解析 transmittance + front-to-back single scattering。
- [x] 测试 primitive 数量曲线 512~8192（candidate 比例稳定 ~45%）。
- [x] debug view：optical depth / transmittance / candidate count 热图。
- [x] MVP 三问结论：体积感✅、解析 transmittance✅、traversal 可控性⚠️（见 LOG 2026-06-05）。

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。


