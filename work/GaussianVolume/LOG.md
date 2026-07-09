# GaussianVolume · LOG

> 决策流水。追加式，新条目加在**文件末尾**。由 `/log` 命令维护。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签（可选，加在标题前）

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

<!-- 新条目追加在下方 -->

### 2026-05-29 15:50 — [决策] 启动 Gaussian volume 预研

先按 Don't Splat your Gaussians 的论文结构做工程验证，暂时抛开最终精度，重点看 Gaussian volume primitive 的 runtime 结构、解析透射率、遍历/加速和 UE 落地可优化点。

### 2026-05-29 15:58 — [决策] 收窄 MVP 范围

第一版不追完整 VDB 拟合和多次散射；先用手工/程序化 Gaussian cloud 验证体积感、ray-Gaussian 积分、single scattering 与 primitive traversal 成本曲线。

### 2026-05-29 16:24 — [决策] MVP 通过标准

MVP 只回答三件事：能否形成基本体积感、解析 transmittance 是否替代大量固定步 raymarch、primitive traversal/candidate 数是否可控；通过后再接 VDB block → Gaussian primitives。


### 2026-06-05 16:30 — [发现] MVP 复现跑通，三问有结论

standalone CPU renderer（mvp/，纯 NumPy）跑通：手工 Gaussian cloud + ray-Gaussian 解析 optical depth（erf 区间积分，零固定步 raymarch）+ front-to-back single scattering。
① 体积感：✅ N=1024 出连续云团、明暗柔和、无硬边噪点。
② 解析 transmittance 替代 raymarch：✅ 每个 primitive 一次 erf 即得整段 tau，view/light 两个方向都解析。
③ traversal 可控性：⚠️ brute-force bounding sphere 的 candidate/ray 随 N 近似线性（稳定 ~45%，N=8192 时均值 3677），是后续头号瓶颈。

### 2026-06-05 16:30 — [决策] 下一步优先做加速结构

MVP 结构成立，瓶颈定位在 traversal。下一步先上 uniform grid / macro cell 把 candidate 比例从 ~45% 压下来，再谈精度与 VDB→primitive 转换。性能基线：N=1024、200x150、纯 Python 约 85s（355 ray/s），后续可向量化/分块加速。

### 2026-07-07 16:41 — [决策] 项目重新激活

从 archive 取回 work/。MVP 三问已有结论，结构成立。重新激活后首要任务不变：加速结构（uniform grid / macro cell）降低 candidate/ray 比例。

### 2026-07-07 16:57 — [发现] Uniform grid 加速结构实验结论

实现 uniform grid + Amanatides-Woo DDA 遍历，正确性验证通过（Python 版 color diff=0）。但性能结论反转预期：
① 纯 Python 下 grid 比 brute-force 慢（0.66x）——NumPy 向量化的全量 bounding sphere 测试比 Python 逐 cell DDA 循环快。
② Numba JIT 编译后 BF 获 ~20x 加速（270→5347 ray/s@N=256），但 grid 仍比 BF 慢（0.23x-0.78x）。
③ 根因：grid 不能减少 actual candidate 数（ray-primitive 相交是几何属性），只减少被测试的 primitive 数。而真正的性能瓶颈是 compositing 中的 O(n_cand^2) 光照衰减循环——每个 candidate 要对其他所有 candidate 算光源方向 tau。
④ Numba grid 版有并行竞争 bug（prange 共享 buffer），修复后仍有 diff=0.81 的正确性问题待查。

### 2026-07-07 16:57 — [决策] 加速方向转向 compositing 优化

uniform grid 对当前场景（密集 cloud、~45% candidate rate）不是正确的加速路径。下一步优先：
① 预计算光源方向 tau 矩阵（O(n_cand^2) 一次算完，避免逐 candidate 重复）
② early termination 已有（T<1e-3），考虑 tighter threshold
③ Numba BF 已达 2097 ray/s@N=1024，可作为短期可用基线
④ Grid 保留代码但降优先级，等 VDB→primitive 转换后数据稀疏时再评估

### 2026-07-07 19:10 — [发现] tau 矩阵预计算实现，6.7x 加速

实现 `precompute_light_tau_matrix`：光源方向固定时一次性算 (N,N) tau 矩阵（chunked einsum），shade_ray 中 O(M²) 逐 candidate `ray_gaussian_taus` 调用替换为 O(M) 查表 `tau_light[idx[k], idx].sum()`。
① 正确性：color max diff = 0.00e+00，与原始路径完全一致。
② 性能：N=1024 200x150，旧路径 54.67s（549 ray/s）→ 新路径 8.16s（3675 ray/s），6.70x 加速。precompute 仅 0.18s（占 2%），amortized 3535 ray/s。
③ N scaling：256→4.81x、512→5.16x、1024→5.90x，加速比随 N 增大（M² 项主导）。
④ 纯 NumPy 3675 ray/s 已接近 Numba BF 基线（2097 ray/s@N=1024），叠加 Numba 后预期可达 1万+ ray/s。

### 2026-07-07 19:20 — [发现] Numba + tau 矩阵集成，prange 竞争修复，76万 ray/s

实现 `numba_renderer.py`：全管线 Numba JIT（candidate 查找 + tau 积分 + compositing + tau 矩阵查表），prange 并行每像素。
① prange 竞争修复：上一版 diff=0.81 的根因是线程写共享 color/od/trans/cand buffer。修复方案——每线程写唯一像素索引 j*W+i，无交叉。
② 正确性：tau 矩阵 NB vs NP diff=2.8e-9，color diff=1.5e-11，candidate diff=0。PASS。
③ 性能：N=1024 200x150，NB 0.04s（76万 ray/s）vs NP 6.41s（4682 ray/s），154x 加速。precompute NB 0.004s。
④ N scaling：256→320万、512→214万、1024→76万 ray/s。N=1024 下 76万 ray/s 已达实时级（200x150 单帧 0.04ms）。
⑤ 结论：prange 竞争 bug 已修，grid 版降优先级（BF+tau+Numba 已足够快，grid 不减少 actual candidate）。

### 2026-07-07 19:30 — [发现] VoGE 交叉阅读完成

阅读 VoGE（ICLR 2023, arXiv:2205.15401）论文+源码，提取 4 个可落地模块：
① 数学一致性确认：VoGE CUDA kernel 中 `hit_length = m_sig_k/k_sig_k`（= t_star）、`hit_activation = C - B²/A`（= -2×peak），与本项目 `ray_density_integral.md` 完全吻合。
② Top-K 选择：VoGE 不做全 candidate compositing，每 ray 取最近 K=20 个（bubble sort insert in CUDA kernel），比本项目 early termination 更激进。
③ Coarse-to-fine：screen-space tile rasterization（2D projection → bin assignment）→ fine ray trace，适合 GPU 并行，不适合当前 CPU/Numba。
④ 闭式 cross-activation：用 erf-based mutual occlusion 替代 front-to-back 累积，O(K²) 闭式计算，无序可并行，但与 single scattering 有序 compositing 冲突。
⑤ VDB→Gaussian 启示：VoGE 的 surface converter 不直接适用，但 percentage 参数和 neighbor-based sigma 估计有参考价值。

### 2026-07-07 19:50 — [发现] Vol3DGS 交叉阅读完成

阅读 Vol3DGS（CVPR 2025 Highlight, arXiv:2412.03378）论文+源码，回答 backlog 问题：
① **analytic alpha + rasterization 可作 view ray transmittance 实时近似**——Vol3DGS 在 3DGS rasterizer 框架内用解析 erf 积分替换 splatting alpha，drop-in replacement，速度持平 3DGS。
② **不可替代 shadow ray/single scattering**——Vol3DGS 不涉及光照，本项目的 tau 矩阵优化仍必要。
③ 数学一致性：γ_j=t_star, β_j=1/√A, peak=G_j(γ·d)——与本项目完全一致。
④ 关键差异：Vol3DGS 用无限积分限 `[-∞,+∞]`（适合 surface），本项目用有限积分限 `[t_near,t_far]`（体积云必需，更精确）。
⑤ Non-overlapping 假设：Vol3DGS 假设 Gaussian 不重叠（alpha blending 精确条件），本项目云 Gaussian 有 overlap，需逐步 compositing 而非 alpha 链。

### 2026-07-07 20:10 — [发现] 3DGEER 交叉阅读完成，三篇交叉阅读全部结束

阅读 3DGEER（ICLR 2026, Bosch Research, arXiv:2505.24053）论文+源码：
① **PBF（Particle Bounding Frustum）是三篇中最有价值的 candidate reduction 方案**——per-Gaussian closed-form angular bounds + tile intersection，不依赖 BVH，3DGEER 证明比 BVH 方法快 5×，接近 3DGS 帧率。
② **canonical space transmittance** 与本项目 A/B/C 分解数学等价（各向同性化 → perpendicular Mahalanobis distance² = C - B²/A）。
③ **"maximum response" t_star 被 3DGEER 证明是 projective-exact**（非启发式近似），间接验证本项目数学正确性。
④ **无限积分限**（同 Vol3DGS）不适用于体积云 overlapping Gaussian，本项目保留有限积分限。
⑤ **三篇横向对比表**已整理在 `notes/3dgeer_cross_reading.md` 第 5 节。
⑥ Action items：短期实验 PBF-style candidate reduction + Top-K 截断；中期 GPU 化采用 PBF-CSF tile association。

### 2026-07-07 20:40 — [实现] VDB to Gaussian 转换器

实现 mvp/vdb_converter.py，将 VDB voxel density grid 转换为 Gaussian volume primitives：
1. 双输入模式：pyopenvdb.Grid（真实 VDB 读取）+ NumPy dense array（测试 fallback）。
2. 转换逻辑：每个 active voxel -> 一个 Gaussian。center = voxel world pos，sigma_t = density * density_scale，scale = voxel_size * sigma_max_scale / 2。
3. 各向异性模式：梯度方向 = 密度变化最快方向（有限差分），沿梯度方向 scale 压缩为 ratio * base（类似 VoGE normal-based anisotropy）。
4. max_primitives 限制：按密度降序保留 Top-K，用于控制渲染成本。
5. 测试结果：24^3 grid（13312 active voxels）-> 7928 prims（1.7x 压缩），各向异性 scale [0.06, 0.20]。渲染 N=512, 120x90, 0.5s, 21K ray/s。iso vs aniso color diff = 0.012。
6. 待完善：VDB 空间稀疏性利用、merge 相邻低密度 voxel、pyopenvdb 实际 .vdb 文件测试。

### 2026-07-07 20:55 — [调研] UE 集成方案完成

编写 
otes/ue_integration_plan.md，完成 UE5 集成方案调研：
1. 推荐 Compute Shader 方案（FSceneViewExtension + RDG pass），理由：per-pixel ray-Gaussian 天然适合 CS thread-per-pixel，PBF-CSF tile association 可直接映射到 CS thread group。
2. 数据传输：GaussianCloud -> StructuredBuffer<float4>（5 float4 per Gaussian：center_sigma_t / scale_quat / rotation / albedo）。
3. 渲染管线：PostOpaqueRenderDelegate -> RDG CS pass -> half-res ColorOutput + DepthOutput -> temporal upsample -> depth composite。
4. HLSL 伪代码已写（含 A/B/C -> erf transmittance + front-to-back compositing + single scattering）。
5. 5 阶段实施路线图：Plugin Scaffold(1-2d) -> Data Upload(1d) -> Ray Tracing Renderer(2-3d) -> Optimization(2-3d) -> Polish(1-2d)。
6. 性能优化路径：half-res + TAA、PBF-CSF candidate reduction、GPU bitonic sort、tau 矩阵 CS 并行。
7. 风险评估：RDG 集成复杂度中等、erf 在 HLSL 有 intrinsic、大 N 用 PBF 替代排序。
8. BACKLOG 全部清零。
