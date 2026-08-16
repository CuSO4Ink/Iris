# 3DGEER 交叉阅读笔记

> 论文：3DGEER: 3D Gaussian Rendering Made Exact and Efficient for Generic Cameras
> 作者：Zixun Huang, Cho-Ying Wu, Yuliang Guo, Xinyu Huang, Liu Ren
> 发表：ICLR 2026 | Bosch Research | arXiv:2505.24053 | 代码：https://github.com/boschresearch/3dgeer

## 0. 与本项目的定位关系

3DGEER 是交叉阅读三篇中最接近本项目 full ray tracing 方向的工作。它用 **closed-form ray-Gaussian transmittance + PBF association** 替代 BVH traversal，在 GPU 上达到接近 3DGS 的帧率。

| 维度 | 3DGEER | GaussianVolume (本项目) |
|-----|--------|------------------------|
| 目标 | view synthesis（通用相机模型，含 fisheye） | VDB 体积云降耗（正向渲染 + runtime） |
| 光照 | 无（emissive volume，纯 transmittance blending） | single scattering + shadow rays |
| Transmittance | 闭式解（canonical space 各向同性化 → erf） | 闭式解（直接 3D 各向异性 erf） |
| Ray-particle 关联 | PBF（Particle Bounding Frustum）— 无 BVH | bounding sphere + brute-force |
| 实现层 | CUDA（GPU tile-based PBF association） | Numba（CPU prange） |
| 相机模型 | 通用（pinhole + fisheye + BEAP） | pinhole（暂不需要 fisheye） |

**核心可提取模块**：① canonical space 闭式 transmittance（与本项目数学一致性验证）② PBF 替代 BVH（candidate reduction 的新思路）③ BEAP 均匀射线采样。

---

## 1. 闭式 Ray-Gaussian Transmittance

### 1.1 Canonical Space 方法

3DGEER 的核心数学创新：将各向异性 Gaussian 通过 `x = R·S·u + μ` 映射到 **canonical isotropic space**，在 canonical space 中积分得到闭式解。

```
World: G_{Σ,μ}(x) = (1/ρ) exp(-0.5 (x-μ)^T Σ^{-1} (x-μ))
Canonical: G_{I,0}(u) = (1/ρ) exp(-0.5 ||u||²)

Ray canonical form:
  o_u = S^{-1} R^T (o - μ)
  d_u = S^{-1} R^T d

Transmittance (infinite integral):
  T(o,d) = σ · ∫ G_{I,0}(o_u + t·d_u) dt
         = σ · exp(-0.5 · D²_{μ,Σ}(o,d))

where D²_{μ,Σ}(o,d) = ||o_u × d_u||² / ||d_u||²  (squared perpendicular Mahalanobis distance)
```

### 1.2 与本项目的数学对比

3DGEER 的 canonical space 方法和本项目的直接 A/B/C 分解 **数学等价但路径不同**：

| 步骤 | 3DGEER (canonical) | 本项目 (direct A/B/C) |
|------|-------------------|----------------------|
| Gaussian | R·S 分解 → isotropic | 直接用 Σ^{-1} (各向异性) |
| Ray-Gaussian peak | `D²_{μ,Σ}` = perp. distance² | `C - B²/A` = peak exponent |
| Transmittance | `σ · exp(-0.5 · D²)` (infinite) | `σ · [erf(z_far) - erf(z_near)]` (finite) |
| 积分限 | `[-∞, +∞]` | `[t_near, t_far]` (bounding sphere) |

**关键差异（同 Vol3DGS）**：3DGEER 也用无限积分限。其 transmittance `T = σ · exp(-0.5·D²)` 实际上是 **全空间积分**（整个 ray 上 Gaussian 的总贡献），不是 per-segment transmittance。

这意味着：
- 3DGEER 的 transmittance 是 **per-Gaussian total opacity**（类似 Vol3DGS 的 α_i），用于 alpha blending
- 本项目的 `erf(z_far) - erf(z_near)` 是 **per-segment transmittance**，用于 front-to-back 逐步 compositing，可处理 overlap

两者在 non-overlapping 场景下等价，在 overlapping 场景（体积云）本项目更精确。

### 1.3 "Maximum Response" 的理论证明

3DGEER 的一个重要理论贡献：证明了 Keselman & Hebert (2022) 的 "maximum response" 启发式（ray 在 Gaussian 峰值处求值）具有 **projective exactness**——即它不是近似，而是精确的投影几何结果。3DGRT (NVIDIA) 之前用这个启发式但没证明其正确性。

这对本项目有间接验证意义：本项目的 `t_star = -B/A`（Gaussian 沿 ray 的峰值密度点）被 3DGEER 证明是 projective-exact 的，不是启发式近似。

---

## 2. Particle Bounding Frustum (PBF)

### 2.1 核心思想

3DGEER 的 **PBF** 是本次三篇交叉阅读中对本项目最有价值的 candidate reduction 方案：

- **不用 BVH**（EVER/3DGRT 的 BVH traversal 并行化困难）
- **不用 screen-space rasterization**（3DGS/3DGUT 的 splatting 有投影近似误差）
- **用 3D frustum–particle intersection**：每个 Gaussian 计算一个 tight bounding frustum（4 个 tangent plane），与 camera sub-frustum (CSF = tile) 做精确交集测试

### 2.2 PBF 构造

对每个 Gaussian（center μ_c, covariance Σ_c in camera space）：

1. 计算两个 spherical angles (θ, φ) 定义 ray 方向
2. 在 canonical space 中，Gaussian 是 isotropic sphere
3. 求 4 个 tangent plane：在 (θ, φ) 方向上，sphere 的切平面定义了 frustum 的 4 个面
4. 解 quadratic equation 得到 angular bounds (θ_min, θ_max, φ_min, φ_max)
5. PBF = 这 4 个 angular bound 定义的 frustum

**关键**：PBF 的计算是 **per-Gaussian closed-form**（解 quadratic），不需要 BVH traversal 或 multi-level spatial query。

### 2.3 PBF-CSF Association

- Camera image 被分成 tiles，每个 tile 对应一个 Camera Sub-Frustum (CSF)
- Gaussian 的 PBF 与 CSF 做 angular intersection test
- 如果 PBF ∩ CSF ≠ ∅，则该 Gaussian 是该 tile 的 candidate

这类似于 3DGS 的 tile-AABB mapping，但在 **3D angular space** 而非 2D screen space，因此对 fisheye/wide-FoV 也精确。

### 2.4 对本项目的启示

本项目当前的 candidate reduction 是 **bounding sphere + brute-force**（每个 ray 测试所有在 bounding sphere 内的 Gaussian）。PBF 提供了一个替代方案：

**方案 A（CPU/Numba）**：对每个 Gaussian 预计算 angular bounds (θ_min, θ_max, φ_min, φ_max)，然后对每条 ray 用 ray direction 的 (θ, φ) 做 4 次比较。这是 O(N) per ray（N = total Gaussians），但每次比较是 O(1)，比 bounding sphere 的 3D distance test 更快（少一次 sqrt）。

**方案 B（GPU）**：直接采用 3DGEER 的 PBF-CSF tile association，在 compute shader 中做 tile-parallel PBF intersection。

PBF 的优势在于 **不需要 BVH**——BVH 在 CPU Numba 上实现复杂且分支发散严重。PBF 是 flat array + closed-form per-Gaussian computation，适合 SIMD/Numba prange。

**但需注意**：PBF 的 angular bounds 是在 camera space 定义的，每帧相机移动后需要重新计算。本项目的 bounding sphere 是 world space 的，可以预计算。如果相机不动（体积云通常用固定视角或缓慢移动），bounding sphere 更优；如果相机频繁移动，PBF 的 per-frame overhead 需要评估。

---

## 3. BEAP (Bipolar Equiangular Projection)

### 3.1 动机

BEAP 是一种新的 image representation，将任意 FoV 相机的像素均匀映射到球面角度 (θ, φ)。优势：
1. 无 FoV 损失（fisheye 全覆盖）
2. tile 和 CSF 共享 (θ, φ) 参数化，PBF association 更高效
3. 射线分布更均匀 → 训练效率和质量提升

### 3.2 对本项目的适用性

**低优先级**。本项目是体积云渲染，不需要 fisheye/wide-FoV 支持。BEAP 的均匀射线采样对体积云的 view-dependent scattering 有一定帮助（边缘射线更均匀），但不是瓶颈。

如果后续需要支持全景天空盒或反射捕获（reflection probe），BEAP 可以提供均匀的射线分布。

---

## 4. 性能数据

### 4.1 渲染速度

3DGEER 在 RTX 4090 上：
- MipNeRF360: ~134 FPS（3DGS ~300 FPS, EVER ~26 FPS, 3DGRT ~22 FPS）
- 比 exact ray-tracing 方法（EVER/3DGRT）快 **5× 以上**
- 比 splatting 方法慢 ~2×（ray-based rendering 的固有开销）

### 4.2 Gaussian 数量

3DGEER 用更少的 Gaussian 达到更高 PSNR：
- ScanNet++: 592K vs FisheyeGS 921K vs 3DGS 1396K
- 这是因为 projective-exact transmittance 减少了 approximation error，不需要用更多 Gaussian 补偿

### 4.3 对本项目的性能预期

3DGEER 验证了 **PBF association 的效率**：per-Gaussian closed-form computation + tile-parallel intersection → 接近 3DGS 的帧率。如果本项目上 GPU，PBF 是 candidate reduction 的首选（优于 BVH 和 bounding sphere）。

---

## 5. 三篇交叉阅读横向对比

| 维度 | VoGE (ICLR'23) | Vol3DGS (CVPR'25) | 3DGEER (ICLR'26) | 本项目 |
|------|----------------|-------------------|-------------------|--------|
| **数学核心** | A/B/C → hit_length/activation | γ/β → analytic α (infinite) | canonical → D² → T (infinite) | A/B/C → erf (finite) |
| **积分限** | Top-K (no explicit integral) | [-∞, +∞] | [-∞, +∞] | [t_near, t_far] |
| **Candidate reduction** | Coarse rasterize → Top-K | Tile-based (3DGS inherited) | PBF (frustum intersection) | Bounding sphere + BF |
| **Compositing** | Cross-activation (O(K²)) | Alpha blending (non-overlap) | Alpha blending (non-overlap) | Front-to-back (overlap-aware) |
| **光照** | 无 | 无 | 无 | Single scattering + tau |
| **可微** | 是 | 是 | 是 | 否 |
| **GPU 策略** | Pixel-parallel + Top-K sort | Tile-based rasterizer | Tile-parallel PBF | — (CPU Numba) |
| **对本项目最大价值** | Top-K + CUDA kernel 结构 | Rasterizer drop-in alpha | PBF candidate reduction | — |

---

## 6. 对本项目的 Action Items

### 短期（Numba 优化）
1. **实验 PBF-style candidate reduction**：对每个 Gaussian 预计算 camera-space angular bounds，per-ray 做 4 次比较替代 bounding sphere distance test。预期减少 candidate 数（tighter bounds）并加速 per-candidate test（O(1) 比较 vs O(1) sqrt）。
2. **Top-K 截断实验**（来自 VoGE）：在 compositing 阶段限制 K=20~50，对比 early termination 的性能/质量。

### 中期（GPU 化）
3. **PBF-CSF tile association**（来自 3DGEER）：GPU 上做 tile-parallel PBF intersection，替代 BVH。3DGEER 证明这比 BVH 快 5×。
4. **Pixel-parallel fine kernel**（来自 VoGE）：每线程一个 pixel，线程内串行遍历 tile candidate + Top-K sort。

### 后置
5. **BEAP 均匀射线采样**：仅在需要全景/反射捕获时考虑。
6. **无限积分限对比实验**：验证 `[t_near, t_far]` vs `[-∞, +∞]` 在体积云场景的差异（预期本项目更精确）。

---

## 7. 总结

3DGEER 是三篇中对本项目最有直接工程价值的工作：

1. **PBF** 提供了不依赖 BVH 的 candidate reduction 方案——这在 CPU Numba 和 GPU Compute Shader 上都更容易实现，且 3DGEER 证明其效率接近 3DGS。
2. **闭式 transmittance 的 canonical space 推导**与本项目 A/B/C 分解数学等价，但提供了另一个推导视角（isotropic 化），可用于验证或简化实现。
3. **"maximum response" 的 projective exactness 证明**间接验证了本项目 `t_star = -B/A` 的数学正确性。
4. **无限积分限**与 Vol3DGS 一样不适用于体积云的 overlapping Gaussian——本项目保留有限积分限。

三篇交叉阅读全部完成。下一步是 BACKLOG 中的 VDB→Gaussian 转换和 UE 集成调研。
