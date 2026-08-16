# Vol3DGS 交叉阅读笔记

> 论文：Volumetrically Consistent 3D Gaussian Rasterization
> 作者：Chinmay Talegaonkar, Yash Belhe, Ravi Ramamoorthi, Nicholas Antipa
> 发表：CVPR 2025 Highlight | arXiv:2412.03378 | 代码：https://github.com/chinmay0301ucsd/Vol3DGS

## 0. 与本项目的定位关系

Vol3DGS 的核心贡献是在 3DGS 的 tile-based rasterizer 框架内，用 **解析积分替代 splatting 近似** 来计算 alpha。关键判断：

> **analytic alpha + rasterization 是否可作为 full ray tracing 的实时近似？**

**结论：可以作为 view transmittance 的实时近似，但不是本项目需要的 full ray tracing 替代。** 原因见下。

| 维度 | Vol3DGS | GaussianVolume (本项目) |
|-----|---------|------------------------|
| 目标 | view synthesis（可微渲染 + 逆向优化） | VDB 体积云降耗（正向渲染 + runtime） |
| 光照 | 无（emissive volume，纯 alpha blending） | single scattering + shadow rays |
| Primitive | 3D Gaussian（同构） | Gaussian volume primitive（同构） |
| Transmittance | 解析 erf（无限积分限） | 解析 erf（有限积分限 [t_near, t_far]） |
| Compositing | alpha blending（front-to-back, 无 overlap） | front-to-back + tau 矩阵 |
| 排序假设 | tile-based sorting + no overlap | brute-force 全 candidate sorting |
| 实现层 | Slang.D rasterizer（GPU tile-based） | Numba（CPU prange） |

---

## 1. 核心数学：解析 Alpha 替代 Splatting

### 1.1 3DGS 的 splatting 近似（被 Vol3DGS 批判的三条）

1. **指数线性化**：`e^(-x) ≈ 1-x`，把 transmittance 变成线性 alpha blending
2. **无自遮挡**：假设每个 Gaussian 沿 ray 的积分 = 峰值密度 × 1（即 `α_i = o_i * G_i(x_i)`，x_i 是峰值点）
3. **协方差线性化**：3D→2D projection 近似（affine approximation），丢失 z-scale 信息

### 1.2 Vol3DGS 的解析 alpha

不 splat，直接沿 ray 积分 3D Gaussian。3D Gaussian `G_j(x)` 沿 ray 投影为 1D Gaussian：

```
g_j(t) = G_j(γ_j·d) * exp{-(t - γ_j)² / (2β_j²)}
```

其中（**与本项目完全一致的 A/B/C 分解**）：

```
γ_j = (μ_j - o)·Σ_j^{-1}·d / (d^T Σ_j^{-1} d)    ← = t_star = -B/A
β_j = 1 / sqrt(d^T Σ_j^{-1} d)                     ← = 1/sqrt(A)
G_j(γ_j·d) = peak density                          ← = exp(-0.5*(C - B²/A))
```

积分结果（假设无限积分限）：

```
∫_{-∞}^{+∞} g_j(t) dt = G_j(γ_j·d) * sqrt(π/2) * β_j

Transmittance: T̄_j = exp(-κ_j * G_j(γ_j·d) * sqrt(π/2) * β_j)
Alpha:         α_j = 1 - T̄_j = 1 - exp(-κ_j * peak * sqrt(π/(2A)))
```

### 1.3 与本项目的关键差异

| 方面 | Vol3DGS | 本项目 |
|------|---------|--------|
| 积分限 | **[-∞, +∞]**（假设无限 support） | **[t_near, t_far]**（有限 bounding interval） |
| Alpha 公式 | `1 - exp(-κ * peak * sqrt(π/2β))` | `erf(z_far) - erf(z_near)`（精确有限积分） |
| 误差 | 无限积分限引入误差（对小/窄 Gaussian 显著） | 有限积分限精确（但需 candidate bounding sphere） |
| 多 Gaussian | alpha blending（front-to-back，无 overlap） | front-to-back compositing（有 overlap，逐步累积 T） |

**Vol3DGS 的无限积分限近似**在本项目的体积云场景下不适用：云的 Gaussian 通常沿 view ray 有有限 extent，无限积分会过度计算 transmittance。本项目的有限积分限 erf 公式更精确。

但 Vol3DGS 验证了一个重要结论：**解析 alpha 可以直接替换 splatting alpha，在 rasterizer 框架内无缝工作**。如果本项目后续上 GPU rasterizer，可以同样做 drop-in replacement。

---

## 2. Alpha Blending vs Volume Rendering Equation

### 2.1 Vol3DGS 的推导路径

Vol3DGS 证明：假设 Gaussian **sorted front-to-back + non-overlapping**，volume rendering equation（Eq.1-2）可以精确写为 alpha blending（Eq.5/14）：

```
C(p) = Σ_i c_i α_i Π_{j<i}(1-α_j)
```

其中 α_i 是 **per-Gaussian 的解析 transmittance**（Eq.19），不是 3DGS 的 splatting alpha。

**关键洞察**：alpha blending 不是近似——在 non-overlapping + sorted 假设下，它是 volume rendering equation 的精确重写。3DGS 的问题不在 alpha blending 本身，而在 α_i 的计算方式（splatting 近似）。

### 2.2 对本项目的意义

本项目的 front-to-back compositing 本质上就是 alpha blending，且 α_i 用的是精确的有限积分限 erf。所以本项目的 compositing 在数学上 **比 Vol3DGS 更精确**（Vol3DGS 用无限积分限，本项目用有限积分限）。

但本项目有一个 Vol3DGS 没有的开销：**tau 矩阵**（光源方向的 shadow ray transmittance）。Vol3DGS 不涉及光照，只有 view ray。本项目的 O(n_cand²) 瓶颈来自 shadow ray 的 multi-Gaussian transmittance，不是 view ray 的 compositing。

---

## 3. 实现细节

### 3.1 Slang.D Rasterizer

Vol3DGS 基于 [slang-gaussian-rasterization](https://github.com/google/slang-gaussian-rasterization)（Google 的 Slang 实现 3DGS），用 slangtorch 编译。核心改动：**仅替换 alpha 计算函数**，其余 rasterizer 管线（tile sorting、binning、blending）不变。

```slang
// 伪代码：3DGS alpha → Vol3DGS alpha
// 3DGS:  alpha = opacity * projected_2d_gaussian(p)
// Vol3DGS: alpha = 1 - exp(-kappa * peak * sqrt(PI / (2 * A)))
//         where A = d^T Sigma^{-1} d, peak = exp(-0.5 * (C - B^2/A))
```

### 3.2 Density Reparameterization

```python
κ = -log(1 - 0.999) * sigmoid(κ_raw)
```

用 sigmoid + scale 确保 κ 可达到高值（fit opaque surfaces），同时避免梯度消失。

### 3.3 性能

Vol3DGS 的渲染速度与 3DGS 基本持平（alpha 计算开销可忽略），训练速度略慢（erf 的 backward 梯度比 2D Gaussian 复杂）。在 MipNeRF-360 上 SSIM/LPIPS 一致优于 3DGS。

---

## 4. 对本项目的可落地 Action Items

### 4.1 直接验证：无限积分限 vs 有限积分限

Vol3DGS 用 `[-∞, +∞]` 积分限，本项目用 `[t_near, t_far]`。可以做一个对比实验：

- 当 Gaussian scale 很大（β_j >> bounding radius）时，两者趋同
- 当 Gaussian scale 小或 bounding 紧时，差异显著
- 本项目应保留有限积分限（更精确），但可以记录这个对比作为理论 backup

### 4.2 Rasterizer Drop-in Alpha Replacement

如果本项目后续做 GPU rasterizer（Compute Shader / CUDA），Vol3DGS 验证了 **只需替换 alpha 函数**，无需改 rasterizer 管线。具体：

1. Tile-based binning + sorting：复用 3DGS/VoGE 的 coarse rasterization
2. Alpha 计算：用本项目的 erf 公式（有限积分限）替换 3DGS 的 splatting alpha
3. Blending：标准 front-to-back alpha blending

这比 full ray tracing 快得多（tile 利用 pixel coherence），且物理精度接近 ray tracing。

### 4.3 Non-overlapping 假设的适用性

Vol3DGS 假设 Gaussian non-overlapping（sorted alpha blending 的前提）。本项目的体积云 Gaussian **有重叠**（云不是离散表面）。这意味着：

- 本项目不能直接用 Vol3DGS 的 alpha blending（会丢失 overlap 的 mutual occlusion）
- 需要保留 front-to-back 逐步 compositing（每步更新 T），或用 VoGE 的 cross-activation 闭式近似
- **但 view ray 的 transmittance 可以用 Vol3DGS 式的 per-Gaussian alpha**（每个 Gaussian 的 α 独立计算），只是 blending 需要逐步累积而非乘法链

### 4.4 Tomography 启示

Vol3DGS 的 analytic transmittance 直接适用于 tomography（CT 重建），因为 tomography 就是 volume density integration。这验证了 Gaussian volume primitive 用于体积介质渲染的物理正确性——本项目的方向（VDB 体积云 → Gaussian volume）在数学上是 sound 的。

---

## 5. 关键公式对照表

| 概念 | Vol3DGS 符号 | 本项目符号 | 关系 |
|------|-------------|-----------|------|
| Ray-Gaussian peak param | γ_j | t_star = -B/A | 相同 |
| Ray-Gaussian width | β_j = 1/√(d^TΣ^{-1}d) | 1/√A | 相同 |
| Peak density | G_j(γ_j·d) | exp(-0.5*(C-B²/A)) | 相同 |
| Alpha (infinite) | 1-exp(-κ·peak·√(π/2β)) | — | 本项目用有限积分限 |
| Alpha (finite) | — | erf(z_far)-erf(z_near) | 本项目更精确 |
| Blending | α_i·Π(1-α_j) | T_i·α_i 累积 | 等价（non-overlapping 时） |

---

## 6. 总结

**回答 backlog 问题**：analytic alpha + rasterization **可以**作为 full ray tracing 的实时近似——**但仅限于 view ray transmittance**（无光照场景）。

对本项目的具体影响：
1. **view ray compositing**：Vol3DGS 验证了 rasterizer + analytic alpha 可行，且比 full ray tracing 快。本项目后续 GPU 化可参考。
2. **shadow ray / single scattering**：Vol3DGS 不涉及，无法替代。本项目的 tau 矩阵优化仍然必要。
3. **无限 vs 有限积分限**：本项目保留有限积分限（更精确），Vol3DGS 的无限近似在 surface rendering 场景够用，但体积云不行。
4. **non-overlapping 假设**：Vol3DGS 假设不重叠，本项目云 Gaussian 有重叠，需要逐步 compositing 而非简单 alpha 链。
