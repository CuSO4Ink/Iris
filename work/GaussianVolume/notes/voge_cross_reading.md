# VoGE 交叉阅读笔记

> 论文：VoGE: A Differentiable Volume Renderer using Gaussian Ellipsoids for Analysis-by-Synthesis
> 作者：Angtian Wang, Peng Wang, Jian Sun, Adam Kortylewski, Alan Yuille
> 发表：ICLR 2023 | arXiv:2205.15401 | 代码：https://github.com/Angtian/VoGE

## 0. 与本项目的定位关系

VoGE 和 GaussianVolume（基于 Don't Splat your Gaussians）共享同一个数学核心：Gaussian reconstruction kernel 沿 ray 的解析积分。但二者目标不同：

| 维度 | VoGE | GaussianVolume (本项目) |
|-----|------|------------------------|
| 目标 | 可微渲染（analysis-by-synthesis，逆向优化） | VDB 体积云降耗（正向渲染 + runtime 性能） |
| 光照 | 无显式光照，纯 volume density blending | single scattering + 解析 transmittance |
| 可微 | 是（PyTorch autograd + CUDA backward kernel） | 否（暂不需要） |
| Primitive | Gaussian ellipsoid（等价结构） | Gaussian volume primitive（等价结构） |
| 候选查找 | coarse-to-fine rasterize → ray trace | brute-force bounding sphere（grid 已降优先级） |
| Compositing | 近似闭式 cross-activation（erf-based 互遮挡） | front-to-back + tau 矩阵查表 |

**可提取模块**：① coarse-to-fine candidate reduction ② 近似闭式 aggregation ③ CUDA kernel 结构 ④ mesh/point → Gaussian 转换器。

---

## 1. Gaussian Ellipsoid Renderer

### 1.1 Primitive 结构

VoGE 的 Gaussian ellipsoid 与本项目完全一致：

```
density(x) = exp(-0.5 * (x - mu)^T iSigma (x - mu))
```

- `mu` (P, 3)：center
- `iSigma` (P, 3, 3)：inverse covariance（可各向异性）
- 存储的是 inverse sigma 而非 sigma，省运行时求逆

代码中 `isigma = 2 * sigma`（或 `2 * torch.inverse(sigmas)`），系数 2 来自 `exp(-(x-mu)^T iSigma (x-mu))` vs 标准高斯 `exp(-0.5 * ...)` 的差异。

### 1.2 Ray-Gaussian 交集参数（CUDA kernel 核心）

从 `ray_trace_voge.cu` 的 `RayTraceFineVogeKernel` 提取：

```cuda
// 对每个 candidate Gaussian p：
k_sig_k = d^T iSigma d          // = A（本项目符号）
m_sig_k = mu^T iSigma d          // = B（本项目符号）  
m_sig_m = mu^T iSigma mu         // = C（本项目符号）

hit_length  = m_sig_k / k_sig_k       // = -B/A = t*（ray 参数到峰值密度点）
hit_activation = m_sig_m - m_sig_k^2 / k_sig_k  // = C - B²/A = -2*peak
```

**关键发现**：VoGE 的 `hit_length` = 本项目的 `t_star`，VoGE 的 `hit_activation` = 本项目的 `C - B²/A`（= -2×peak）。两者数学完全一致，只是变量命名和符号约定不同。

VoGE 还额外存储 `dsd = k_sig_k = A`，用于后续 aggregation 阶段的 cross-activation 计算。

### 1.3 Top-K 选择（替代 sorted compositing）

VoGE 不做全 candidate compositing，而是对每条 ray 选 **Top-K nearest**（K = `max_assign`，默认 20）：

- 用 **bubble sort 插入** 在 CUDA kernel 内维护 K 长度的有序数组
- 筛选条件：`hit_activation < thr_act && hit_length < current_max_len`
- `thr_act = -log(thr + 1e-10)`（activation threshold，对应 density 衰减到 thr 以下）

**对比本项目**：本项目对全部 ~45% candidate 做 front-to-back compositing。VoGE 的 Top-K 是一种更激进的截断——只取最近的 K 个，跳过远处 candidate。这在密集云场景下可大幅减少 compositing 成本。

---

## 2. Coarse-to-Fine Rendering

### 2.1 Coarse 阶段：Rasterize

`rasterize_coarse()` 将 3D Gaussian 投影到 screen-space ellipse，做 tile-based bin assignment：

1. 将 Gaussian center 变换到 camera space → NDC
2. `convert_to_box()`：用 iSigma 的 2D 子矩阵 + threshold 计算屏幕空间 bounding box
   ```
   box = sqrt(-log(thr) * M @ inv(iSigma_2x2) @ M) * z
   ```
3. CUDA kernel `_RasterizeCoarse`：tile-based（bin_size 默认 `max(2^(ceil(log2(max_image_size)-5)), 10)`），每个 bin 最多存 `max_points_per_bin` 个 candidate

输出：`pixels_to_points_idx` (B, BH, BW, M) — 每个 tile 的 candidate 列表。

### 2.2 Fine 阶段：Ray Trace

`ray_tracing_fine()` 在 coarse 的 bin candidate 范围内，对每个 pixel 的 ray 做精确 ray-Gaussian 计算 + Top-K 选择。

### 2.3 Bypass 模式

`max_points_per_bin == -1` 时跳过 coarse，直接全量测试。用于小规模场景或调试。

### 2.4 对本项目的启示

VoGE 的 coarse-to-fine 解决的是 **candidate reduction**（减少每 ray 测试的 primitive 数），这正是本项目 uniform grid 实验的目标。区别：

- VoGE 用 **screen-space tile rasterization**（2D projection → bin），适合 GPU 的并行 pixel 处理
- 本项目 uniform grid 是 **3D spatial hashing**（DDA traversal），在 CPU/Numba 上不占优

**可借鉴**：如果后续上 GPU（CUDA/Compute Shader），VoGE 的 tile-based coarse rasterization 比纯 3D grid 更适合——它直接在 screen space 做 culling，避免 3D traversal 的分支发散。

---

## 3. 近似闭式 Aggregation

### 3.1 Cross-Activation（互遮挡近似）

VoGE 的 compositing 不用 front-to-back 累积 transmittance，而是用 **closed-form mutual occlusion**：

```python
# Aggregation.py: get_cross_activation()
# 对每对 (m, k) candidate along a ray:
cross_act[m, k] = (l_m - l_k) * sqrt(d^T iSigma_k d)
                = (hit_length_m - hit_length_k) * sqrt(A_k)

# assign2weight():
density_dist[m, k] = exp(-act_k) * (erf(cross_act[m, k]) + 1) / 2
density_weight[m]  = exp(-sum_k(density_dist[m, k]) * occupation_weight)
weight[m] = density_weight[m] * exp(-act_m)
```

**数学含义**：

```
weight_m = exp(-act_m) * exp(-sum_{k≠m} [exp(-act_k) * Φ((l_m - l_k) * sqrt(A_k))])
```

其中 Φ 是标准正态 CDF（= `(erf(x)+1)/2`）。

这实际上是 **近似 transmittance**：`sum_k exp(-act_k) * Φ(...)` 近似了其他 Gaussian 对 m 的遮挡。erf 积分恰好是 Gaussian density 的解析积分——与本项目 `ray_density_integral.md` 中的 erf 公式一致。

### 3.2 对比本项目的 Compositing

| 方面 | VoGE | GaussianVolume |
|------|------|-----------------|
| Compositing 方式 | 闭式 cross-activation（O(K²) per ray） | front-to-back 累积（O(M) per ray） |
| 光照 | 无（纯 density blending） | single scattering + tau 矩阵 |
| 截断 | Top-K (K=20) | early termination (T<1e-3) |
| 可微 | 是（erf 在 autograd 中可微） | 否 |
| 复杂度 | O(K²) 但 K 小（≤20） | O(M²) → 优化后 O(M) with tau matrix |

**关键差异**：VoGE 的 cross-activation 是 **O(K²) 闭式**，不需要排序和逐步累积——适合 GPU 并行（所有 K 个 candidate 同时算权重）。本项目的 front-to-back 是顺序依赖的（每步依赖前一步的 T），难以完全并行。

**可借鉴**：如果本项目的 Numba 版需要进一步并行化 compositing，可考虑切换到 VoGE 式的闭式 weight 计算。但需要适配光照项（single scattering 需要有序的 front-to-back）。

---

## 4. CUDA 结构参考

### 4.1 模块划分

```
csrc/
├── ext.cpp                    # PyTorch C++ extension binding
├── rasterize_coarse/          # Coarse 阶段 CUDA kernel
│   ├── rasterize_coarse.h
│   └── rasterize_coarse.cu
├── rasterize_points/          # 点云 rasterization utilities
│   └── rasterization_utils.cuh
├── ray_trace_voge/            # Fine 阶段 ray tracing CUDA kernel
│   ├── ray_trace_voge.h
│   └── ray_trace_voge.cu
├── sample_voge/               # Feature sampling CUDA kernel
├── voge_ray_tracing_ray/      # 单 ray 版本（无 coarse）
└── utils/
```

### 4.2 Fine Kernel 并行策略

```cuda
// RayTraceFineVogeKernel
// grid: 1024 blocks × 64 threads = 65536 threads
// 每线程循环处理 num_pixels / num_threads 个 pixel
for (int pid = tid; pid < num_pixels; pid += num_threads) {
    // 解码 pid → (batch, bin_y, bin_x, pixel_y, pixel_x)
    // 遍历 bin_points[by][bx] 的 M 个 candidate
    // 对每个 candidate: 3 次 Innerdot3d → hit_length, hit_activation, dsd
    // Top-K bubble sort insertion
}
```

- 线程映射：**pixel-parallel**，每线程一个 pixel
- candidate 遍历：串行遍历 bin 内 M 个 candidate
- Top-K：每线程维护 K 长度的私有 sorted array（无竞争）
- backward kernel：`atomicAdd` 累积梯度到 `grad_mus`、`grad_isigmas`、`grad_rays`

### 4.3 对本项目的 GPU 化启示

如果后续做 UE 集成或 CUDA 化，VoGE 的结构可直接参考：

1. **Coarse rasterization → Fine ray trace** 两阶段管线适合 GPU
2. **Tile-based bin** 与 GPU compute shader 的 thread group 天然匹配
3. **Top-K per pixel** 用插入排序在 thread-local 内存完成，避免全局同步
4. **Innerdot3d** 手写展开（避免矩阵乘法 overhead），3×3 矩阵 9 个乘加

---

## 5. Mesh/Point → Gaussian 转换

VoGE 的 `Converter/Converters.py` 提供了从 mesh/point cloud 生成 Gaussian ellipsoid 的方法：

### 5.1 Mesh → Gaussian（`normal_mesh_converter`）

1. 计算每个 vertex 的平均边长 `average_len`
2. `isigma_base = 1 / (average_len² / (2 * log(1/percentage)))` — percentage 控制密度衰减
3. 构造各向异性 iSigma：沿法线方向 `shape_ratio` 倍压缩
   ```
   base = diag(1, 1, shape_ratio) * isigma_base
   iSigma = R @ base @ R^T    (R = look_at_rotation(-normal))
   ```

### 5.2 Point Cloud → Gaussian（`naive_point_cloud_converter`）

1. 对每个点找 n_nearest=4 最近邻
2. `average_len = mean(min(topk_dist, mean(topk_dist) * thr_max))`
3. `sigma = average_len² / (4 * log(1/percentage))`

### 5.3 对本项目 VDB→Gaussian 的启示

VoGE 的转换器是 **surface-oriented**（mesh/point → surface Gaussian），不适合 volume density（VDB voxel → volume Gaussian）。但有两个可借鉴思路：

1. **percentage 参数**：控制 Gaussian 衰减到多远等于 threshold，可直接复用为 VDB→Gaussian 的 density mapping 参数
2. **neighbor-based sigma estimation**：VDB 的 voxel grid 可以用邻域密度梯度估计各向异性 scale（高密度梯度方向 = 细长方向）

本项目后续 VDB→Gaussian 转换需要从 **体素密度场** 出发，而非 surface normal。可能路线：
- 对每个 VDB active voxel 生成一个 Gaussian
- scale 由 voxel size 决定
- sigma_t 由 voxel density 决定
- 各向异性由邻域密度梯度方向决定（类似 VoGE 的 normal-based anisotropy）

---

## 6. 关键公式对照表

| 概念 | VoGE 符号 | 本项目符号 | 关系 |
|------|----------|-----------|------|
| Ray direction | `rays` | `d` | 相同 |
| Gaussian center | `mus` (P,3) | `center` / `c` (N,3) | 相同 |
| Inverse covariance | `isigmas` (P,3,3) | `Sinv` / `_Sinv` (N,3,3) | VoGE 多了系数 2 |
| d^T iSigma d | `k_sig_k` | `A` | 相同（忽略系数） |
| mu^T iSigma d | `m_sig_k` | `B` | 相同 |
| mu^T iSigma mu | `m_sig_m` | `C` | 相同 |
| Peak ray param | `hit_length = m_sig_k / k_sig_k` | `t_star = -B/A` | hit_length = -t_star（符号差） |
| Peak exponent | `hit_activation = C - B²/A` | `peak = -0.5*(C - B²/A)` | activation = -2*peak |
| Density integral | `erf(cross_act)` in aggregation | `erf(z1) - erf(z0)` in tau | 同一个 erf，不同积分路径 |

---

## 7. 总结与可落地 Action Items

### 直接可复用
- [x] **数学公式已验证一致**：VoGE 的 CUDA kernel 确认了 A/B/C → t_star/peak 的映射，与 `ray_density_integral.md` 完全吻合
- [x] **Top-K 选择策略**：可考虑在本项目 Numba 版中增加 Top-K 截断（当前用 early termination，Top-K 可更激进地限制 compositing 成本）

### 需要适配
- [ ] **Coarse-to-fine rasterization**：本项目当前 CPU/Numba，screen-space tile rasterization 不适用；但如果上 GPU 则是首选方案
- [ ] **闭式 cross-activation compositing**：与本项目 single scattering 的有序 compositing 冲突，需评估是否可用于 view transmittance 部分（无序）而保留 scattering 的 front-to-back
- [ ] **VDB→Gaussian 转换**：VoGE 的 surface converter 不直接适用，但 percentage 参数和 neighbor-based sigma 估计有参考价值

### 后续优先级
1. **短期**：在 Numba renderer 中实验 Top-K 截断（K=20~50），对比 early termination 的性能/质量
2. **中期**：GPU 化时参考 VoGE 的 tile-based coarse rasterization + pixel-parallel fine kernel 结构
3. **后置**：VDB→Gaussian 转换器设计时参考 VoGE 的 percentage 参数和各向异性构造方式
