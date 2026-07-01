# GaussianVolume · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 实现加速结构（uniform grid / macro cell），把 candidate/ray 比例从 brute-force 的 ~45% 压下来。

## 待办

- [ ] 交叉阅读 VoGE，提取 Gaussian ellipsoid renderer、coarse-to-fine rendering、CUDA 结构参考。
- [ ] 交叉阅读 Volumetrically Consistent 3D Gaussian Rasterization，判断 analytic alpha + rasterization 是否可作为 full ray tracing 的实时近似。
- [ ] 交叉阅读 3DGEER，重点看 ray-Gaussian integral 与 Particle Bounding Frustum / ray-particle association。
- [ ] 推导并整理 isotropic / anisotropic Gaussian 的 ray density integral（MVP 已用各向异性版，待补文档）。
- [ ] MVP renderer 向量化/分块加速（当前纯 Python 355 ray/s，太慢）。
- [ ] 后置：实现简单 VDB block → Gaussian primitive 转换。
- [ ] 后置：UE 集成方案调研（StructuredBuffer、fullscreen pass、half-res + temporal、depth composite）。

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
