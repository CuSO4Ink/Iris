# GaussianVolume 三维密度去网格训练器 SPEC

状态：**失败并退役：P2/P2b/P2c numeric Gate 均失败；最终 best=35K；P3 禁止启动**  
日期：2026-07-29  
目标 Gate：`WDAS404K-DENSITY-DEGRID`  
当前画质基线：G2 `Sigma038 + Anisotropy115`

最终裁决（2026-07-29）：本 SPEC 已完成其 ROI 可行性验证，但自由密度重建
无法在消除 B8 lattice 的同时保持 G2 的全局/ROI 光学质量，因此不得继续扩展
到 P3，也不得作为最终视觉路线重新启动。空间索引、断点恢复、ROI held-out
和导出验证代码仍可复用；若无新的表示假设，不再追加训练步数或候选。

## 1. 结论与工程边界

本阶段不再对 G2 做规则 jitter，也不把
`recover_contracted_50k.py` 描述为可直接复用的核心训练器。

需要新增一个独立的三维密度训练器，完成：

1. 在源 density grid 内随机采样连续三维位置；
2. 使用 additive Gaussian extinction 重建三维密度；
3. 训练自由 center、covariance 和 extinction；
4. 使用空间索引避免 `samples × all Gaussians` 暴力求和；
5. 按三维重建误差增删 Gaussian；
6. 保存 round/step checkpoint、optimizer 和完整 RNG state；
7. 先用“50K 区域候选 + 冻结 G2 其余部分”验证；
8. 通过后才扩展到 exact `404,524`；
9. 最终输出既有 compact `64 B/record`，不增加运行时字段。

本 SPEC 是文献方法的项目适配，不是现成论文实现的复刻：

- W-VEG 支撑 world-space sampling、random in-cell sampling 和
  sample-error densification：
  <https://arxiv.org/abs/2607.01164>
- Capacity-Constrained Point Distributions 支撑密度自适应蓝噪声种子：
  <https://graphics.uni-konstanz.de/publikationen/Balzer2009CapacityconstrainedPoint/index.html>
- 本项目的 additive extinction、固定 `404,524 × 64 B`、六轴 transport、
  DGSM 和 Gate 组合仍是项目特定适配，论文没有证明其必然通过 G2 质量 Gate。

## 2. 不可改变的产品约束

- 静态单 density 云；
- 一盏 Directional Light + SkyLight；
- 目标为 1080p 中远景 screen-space 同质量；
- 最终 exact `404,524` 个空间 Gaussian；
- 最终每点 `64 B`：
  center、opacity、对称 covariance 六值、六轴 transport；
- 禁止恢复每点 `×6` 完整几何叶片；
- DGSM、UE phase、当前 relight 路径和运行时 shader 布局冻结；
- 不增加神经网络运行时、额外纹理或额外 primitive；
- G1/G2 不得被原位覆盖；
- 用户 live viewport 签字前，不发布“同质量更快/更省”的最终结论。

## 3. 当前基线

### 3.1 G1 保底

- Gate：`WDAS404K-BALANCED-G1`
- 备份：`artifacts/gates/2026-07-28_wdas_404k_balanced/`
- 用户已确认“效果好很多”，后续失败时可恢复。

### 3.2 G2 直接父版本

- exact points：`404,524`
- bytes/record：`64`
- primitive payload：`25,889,536 B`
- B8 pitch：约 `6.5 cm`
- held-out：
  - `τ PSNR = 42.66593 dB`
  - `τ MAE = 0.060181`
  - `foreground-T PSNR = 35.62273 dB`
  - `edge L1 = 0.059441`
  - `Gabor energy/phase = 0.001511 / 0.002945`
  - `IoU = 0.981230`
  - `B8 lattice-order = 0.810900`
- 已知失败：中心仍继承“一 B8 block 一 Gaussian”的规则相位。

## 4. 现有代码：可复用与禁止误用

### 4.1 直接复用

- `evaluate_heldout.py::compute_metrics`
- `recover_contracted_50k.py::_edge_loss`
- `recover_contracted_50k.py::_frequency_loss`
- `run_degrid_overnight.py::masses`
- `run_degrid_overnight.py::lattice_order`
- `run_degrid_overnight.py::strict_gate`
- `run_degrid_overnight.py::bounded_gate` 的质量容差
- 现有 ray/patch 数据加载
- `grid_to_7drgs.py::convert_initializer`
- `test_lift_volprim_to_7drgs.py` 的 fixed-budget compact export 测试模式

### 4.2 禁止误用

`recover_contracted_50k.py` 仅作为函数来源，不作为新 trainer 基类：

- 它只有 2D ray/patch `τ/T/edge/Gabor` 监督；
- center/scale/rotation/extinction 是 anchored delta；
- `center_limit_factor`、`scale_factor` 和 extinction `×4` 限制不允许自由重建；
- `anchor_weight` 会把几何拉回规则初始化；
- 它不能插入/删除点；
- 它没有 round 级 checkpoint 和完整 RNG 恢复。

`run_degrid_overnight.py` 仅复用 Gate/统计函数，不复用其恢复粒度：

- 旧执行器只能判断整个候选是否完成；
- 新 trainer 必须从当前 round/step 恢复。

`export_volprim_ply.py` 不进入导出链：

- 该脚本方向是 DSYG/GFields PLY → GaussianVolume JSON；
- 它不是 compact PLY exporter。

## 5. 最小新增实现

只新增：

```text
mvp/train_density_degrid.py
mvp/test_train_density_degrid.py
```

不新建训练框架、插件或通用数据层。空间索引、sampling、densification、
checkpoint 和 CLI 都先保留在一个 trainer 文件内；只有文件明显失控且 P2 已证明
路线有效后，才允许拆分。

### 5.1 Trainer 输入

必需输入：

- `wdas_cloud_half.npy`
- G2 initializer NPZ：
  - `center_m [N,3]`
  - `covariance_m2 [N,3,3]`
  - `sigma_t_per_m [N]`
- 固定 train/held-out rays；
- P2 使用的 exact 50K ROI indices；
- source、baseline、ROI indices 的 SHA256。

### 5.2 Trainer 输出

核心输出始终为 NPZ：

```text
center_m          float32 [N,3]
covariance_m2     float32 [N,3,3]
sigma_t_per_m     float32 [N]
```

伴随输出：

```text
checkpoint.pt
metrics.json
summary.json
stdout.log
stderr.log
```

不先输出 JSON，不增加 JSON → compact adapter。

## 6. 三维表示与参数化

预测 extinction field：

```text
sigma_hat(x) = sum_i sigma_t_i * exp(
    -0.5 * (x - center_i)^T covariance_i^-1 (x - center_i)
)
```

每点质量沿用现有定义：

```text
mass_i = sigma_t_i * (2*pi)^(3/2) * sqrt(det(covariance_i))
```

训练参数使用绝对参数，不使用 G2 anchored delta：

- center：直接优化，投影/约束在源 grid 范围内；
- scale：优化 log-scale；
- rotation：优化 quaternion，每次归一化；
- covariance：由 rotation 和正 scale 构造，天然 positive-definite；
- extinction：`softplus(raw_sigma_t)`，天然非负。

初版不增加 generalized Gaussian、Gabor residual、neural field 或新材质字段。

## 7. 空间加速：第一前置 Gate

### 7.1 结构

使用规则空间 bins + Gaussian 3σ AABB：

1. 对每个 Gaussian 从 covariance 计算 world-axis 3σ AABB；
2. 枚举 AABB 覆盖的 bins；
3. 将 `(bin_id, gaussian_id)` 排序；
4. 生成紧凑 `cell_offsets + gaussian_ids`；
5. 每个 sample 只读取所在 bin 的 Gaussian 列表；
6. 当前尺度上限必须阻止单个 Gaussian 覆盖不可接受数量的 bins。

索引不参与反向传播；Gaussian 参数仍参与 field evaluation 的 autograd。

### 7.2 重建时机

- initializer 创建后；
- 每次 densification/prune 后；
- center/scale 优化期间按实测位移设置固定 rebuild interval；
- AABB 使用安全 padding，避免两次 rebuild 之间漏掉已移动 Gaussian。

rebuild interval 不是预设常数；P0 benchmark 必须记录中心最大单步位移和索引耗时后再确定。

### 7.3 正确性检查

最小测试必须包含：

1. 小型合成 Gaussian 集；
2. 相同 support cutoff；
3. 空间索引结果与暴力遍历结果比较；
4. forward 与 parameter gradient 均 finite；
5. 空 bin 返回零，不产生 false positive；
6. 边界 bin 不越界。

### 7.4 P0 性能检查

在不训练的情况下分别测：

- 50K Gaussians；
- 404,524 个 G2 Gaussians；
- 固定三维 sample batch；
- pair count；
- neighbors/sample 的 P50/P95/P99/max；
- index build time；
- field forward/backward time；
- GPU peak memory。

若 404K benchmark OOM，或外推单步时间无法接受，停止路线；不得先写完整 trainer 再补加速。

P0 只测新增三维 field evaluator，不重复测已有 ray integrator。P3 ETA 必须同时引用：

1. P0 的 50K/404K field forward/backward、pair count 和显存实测；
2. G4 overnight 的 404K ray recovery 实测：`8` 个 `80–100 step`
   候选共 `126.26 min`，即每候选约 `15.8 min` 的量级。

两部分按 P3 每轮实际 field/ray step 数分别外推，禁止只用其中一项估算全量耗时。

预计实现和 benchmark：`1–3 h`。运行本身为分钟级。

## 8. 三维采样与 Loss

### 8.1 Source sampling

每个 sample 必须位于连续三维空间，而不是固定 voxel/block center：

- active voxel 内均匀随机位置；
- density/gradient 边界位置；
- ROI halo 内低密度或空位置；
- densification 使用当前误差最高的位置。

target density 使用源 grid 三线性插值。固定 seed 只保证实验可复现，
不允许把采样位置固定成同一批格心。

### 8.2 三维 Loss

最低集合：

```text
L_3d =
    w_density  * smooth_l1(log1p(sigma_hat), log1p(sigma_target))
  + w_coverage * false_negative_loss
  + w_empty    * empty_space_loss
  + w_mass     * mass_conservation_loss
```

- `density`：连续三维 density reconstruction；
- `coverage`：源 density 有效但预测无有效 kernel coverage；
- `empty`：源为空但 Gaussian 向外泄漏；
- `mass`：候选与被替换 G2 区域的总质量比。

不使用 center/scale/rotation anchor loss。

### 8.3 Ray Loss

复用现有多视角：

```text
L_ray =
    w_tau       * L_tau
  + w_T         * L_transmittance
  + w_edge      * L_edge
  + w_frequency * L_Gabor
```

三维 loss 负责覆盖与几何；ray loss 负责保持 screen-space G2 质量。
只改善 `L_3d`、却使 held-out ray 指标回退的结果不得晋升。

## 9. Densification 与 Prune

### 9.1 初始种子

初版不实现完整 CCVT solver。使用最小的 density-weighted、cell 内随机种子，
并做最小距离拒绝，避免增加新依赖和第二套优化器。

只有 P2 证明 error densification 有效但种子质量成为明确瓶颈时，
才升级为 capacity-constrained Lloyd/CCVT。

### 9.2 Error densification

每轮：

1. 对 source samples 计算 `abs(log1p(sigma_hat)-log1p(target))`；
2. false-negative samples 获得最高优先级；
3. 按误差排序；
4. 对已被现有 Gaussian 充分覆盖或距离过近的位置做抑制；
5. 在剩余位置创建新 Gaussian；
6. center 使用该 sample 位置；
7. covariance 使用局部 density 二阶矩；
8. extinction 使用局部残差/质量初始化；
9. 重建空间索引。

### 9.3 Prune

只删除：

- 质量接近零；
- 长期无 sample/ray 贡献；
- 与邻点重复且删除后误差不升的点。

prune 后必须在同一 round 用高误差位置补回预算。最终点数不能依赖导出时补齐。
进入导出前，所有保留点必须满足 `mass > 0` 且 `sigma_t_per_m > 0`；
零质量/零 extinction 点必须在最后一次 prune 中删除并由有效误差点补回。

## 10. Checkpoint 与恢复

`checkpoint.pt` 至少保存：

- phase、round、step；
- center、log-scale、quaternion、raw extinction；
- optimizer state；
- densification/prune state；
- Python `random` state；
- NumPy RNG state；
- Torch CPU RNG state；
- Torch CUDA RNG states；
- source/G2/ROI hashes；
- 当前点数和空间索引 rebuild 参数。

写入规则：

- 每个 densification round 完成后强制保存；
- 长训练按实测耗时设置 step checkpoint，使最多损失约 5 分钟；
- 先写 `.tmp`，完成后原子 rename；
- `--resume checkpoint.pt` 必须继续当前 round，不重跑已完成 rounds。

最小恢复测试：

```text
连续运行两步
vs.
运行一步 → 保存 → 新进程恢复 → 再运行一步
```

两者的下一批 sample、点数、参数和 metric 必须在确定性容差内一致。

## 11. P2：50K ROI 合成试验

### 11.1 ROI 定义

- 从 G2 选择点阵最明显区域的 exact `50,000` 个中心；
- 保存排序后的 indices 和 SHA256；
- 将这 50K 中心映射回其来源 B8 block，ROI core 固定定义为这些
  **B8 block cell 的轴对齐几何并集**；边界 block 裁剪到 source grid；
- 保存 `roi_core_mask.npy` 及 SHA256，禁止用点集的包围盒替代 cell 并集；
- ROI field supervision 域为 ROI core 向外扩张“当前允许的最大 3σ support”
  得到的 halo；每轮 scale 上限变化后重算 halo；
- 所有 candidate center 限制在 ROI core + halo 与 source grid 的交集内；
- frozen G2 的外部 Gaussian 仍参与 ROI core/halo 内的 field prediction，
  避免把跨边界贡献错误归给 candidate。

### 11.2 合成方式

```text
冻结 G2：354,524
训练候选：
  10,000
  → 20,000
  → 30,000
  → 40,000
  → 50,000

最终合成：354,524 + 50,000 = 404,524
```

三维预测和 ray optical depth 都使用：

```text
frozen G2 outside ROI + trainable ROI candidate
```

因此完整 ray 仍穿过完整云体，`τ/T` 与 G2/VDB 参考具有相同定义。
中间 round 不做最终点数 Gate；只有 50K round 完成后执行完整质量 Gate。

### 11.3 P2 Gate

质量为主，lattice 为诊断。

全局 `1,000` 条 held-out rays 继续报告，但不能单独决定 P2 晋升。
训练开始前必须冻结一组 ROI 专用 held-out patches：

1. 从全局 held-out 集选择“中心 ray 穿过 ROI core B8 cell 并集”的完整 patch；
2. edge/Gabor 必须保留完整 patch，禁止只抽取其中命中的单 ray；
3. 若全局集合中不足 `8` 个完整 ROI patches，则使用同一 camera/reference
   协议补充确定性的 evaluation-only ROI patches，且不得进入训练；
4. 保存 `roi_heldout_patch_indices.npy`、ray/reference hash 和 patch 数量；
5. 对 ROI 子集单独报告 `τ PSNR/MAE`、foreground-T、edge、Gabor 和 IoU。

`quality_strict` 直接复用现有 strict 条件：

- `τ PSNR` 不下降；
- `τ MAE` 不上升；
- foreground-T PSNR 不下降；
- edge/Gabor energy/Gabor phase 不上升；
- IoU 不下降。

`quality_bounded` 复用现有容差，但移除旧的 `lattice >= 2%` 晋升条件：

- `τ PSNR >= baseline - 0.05 dB`
- `τ MAE <= baseline × 1.005`
- `foreground-T >= baseline - 0.05 dB`
- `edge/Gabor <= baseline × 1.005`
- `IoU >= baseline - 0.0011`

ROI 子集另有不可被全局指标替代的强制 Gate：

- `ROI τ MAE <= ROI G2 baseline × 1.005`
- `ROI edge L1 <= ROI G2 baseline × 1.005`

lattice/spectrum 只报告：

- B8 pitch phase order；
- native voxel pitch phase order；
- projected frequency peak；
- 是否在训练后重新锁回 B8 或 voxel 相位。

进入 P3 的必要条件：

1. `quality_strict` 或 `quality_bounded` 通过；
2. ROI 子集 `τ MAE` 与 `edge L1` 强制 Gate 通过；
3. 无 ROI 接缝、孔洞、NaN 或非正定 covariance；
4. B8 点阵确认消失且未在 native voxel pitch 重新格点化；
5. 用户批准全量训练。

预计 GPU 时间由 P0 实测外推；当前只能给 `20–60 min` 的规划范围。
启动前必须重新同步实测 ETA、GPU 占用、日志和恢复点。

## 12. P3：全量 exact 404,524

仅在 P2 通过后启动：

```text
round 0:  80,904
round 1: 161,809  (+80,905)
round 2: 242,714  (+80,905)
round 3: 323,619  (+80,905)
round 4: 404,524  (+80,905)
```

每轮顺序固定：

1. 三维 field fit；
2. ray recovery；
3. held-out metrics；
4. error densification/prune；
5. exact count 检查；
6. 空间索引重建；
7. checkpoint；
8. 下一轮。

round 4 后：

- 禁止继续 densify；
- 只允许 fixed-count geometry/extinction recovery；
- 对完整 G2 baseline 执行同一 `quality_strict/quality_bounded`；
- lattice/spectrum 仍只作为去网格确认。

当前全量规划范围为 `2–6 h`，不作为承诺。必须使用 P2 实测单步、
pair count 和显存，加上 G4 的 404K ray recovery 实测共同重新估算；
启动前再次获得用户批准。

## 13. 导出链

主链固定为：

```text
trainer recovered.npz
  center_m / covariance_m2 / sigma_t_per_m
        ↓
grid_to_7drgs.py
  --compact
  --reference-grid wdas_cloud_half.npy
  --voxel-cm <measured>
        ↓
convert_initializer()
  检查 finite / non-negative / positive-definite
  检查 >=99% centers inside grid
  从 source grid 重算 ±X/±Y/±Z optical depth
        ↓
compact_static_transport PLY
```

最终结构 Gate：

- exact `404,524` records；
- exactly `16 × float32 = 64 B/record`；
- primitive payload `25,889,536 B`；
- `comment compact_static_transport 1`；
- covariance positive-definite；
- 每点 `sigma_t_per_m > 0` 且 mass `> 0`；
- extinction/transport finite；
- source、NPZ、PLY SHA256 落盘。

`bake_directional_tau_basis.py` 保留给 JSON 资产诊断，不进入本阶段最短主链。

## 14. UE 与性能 Gate

禁止 Computer Use。数值和导出 Gate 通过后，由用户手动：

1. 打开 `L_GaussianVolume_TechLab`；
2. 保留 G2 Actor；
3. 复制对照 Actor并替换为新 compact PLY；
4. 保持 opacity、DGSM、phase、Directional Light 和 SkyLight 参数一致；
5. 检查点阵、接缝、边缘绒毛、中尺度团块、暗部、蓝偏、拉丝和方向光连续性。

只有用户确认 matched quality 后才测：

- Gaussian/volume pass GPU time；
- complete-frame GPU time；
- steady/peak GPU working set；
- primitive payload；
- 与同机位 UE SVT/VDB 的 A/B。

## 15. 阶段、工时与审批点

| 阶段 | 内容 | 规划耗时 | 长训练审批 |
|---|---|---:|---|
| P0 | 空间索引、暴力 parity、50K/404K benchmark | 1–3 h 实现；分钟级运行 | 不启动正式训练 |
| P1 | 新 trainer、loss、densify、checkpoint、自检 | 3–6 h | 不启动正式训练 |
| P2 | 50K ROI + 冻结 G2 合成 | 当前保守 ETA `25–45 min` | 已批准；等待 UE 关闭 |
| P3 | 全量 80,904 → 404,524 | P2 后估算；当前 2–6 h | 启动前必须批准 |
| Export | inline transport bake、compact export、结构验证 | 实测记录 | P3 Gate 后自动执行 |
| UE | live viewport 与 matched-quality A/B | 用户决定 | 用户手动操作 |

任何预计超过 5 分钟的运行，启动前必须同步：

- 具体任务；
- 实测/外推耗时；
- GPU 占用预期；
- checkpoint 位置；
- 中断恢复方式；
- 自动停止条件。

## 16. 停止条件

满足任一条件即停止，不扩大全量：

- P0 空间索引在 404K benchmark OOM；
- P0 加速相对相同 cutoff 暴力结果不正确；
- resume 不能恢复同一 round；
- P2 全局 `quality_bounded` 或 ROI 子集强制 Gate 失败；
- P2 出现不可接受 ROI 接缝；
- B8 点阵消失但重新锁到 native voxel pitch；
- P3 point count、64 B layout 或 payload 改变；
- 新表示需要额外运行时网络/字段才能过画质；
- 用户 live viewport 不如 G2。

失败结果只记录到新 artifact/ledger，不覆盖、不部署 G1/G2。

## 17. Artifact 布局

```text
artifacts/wdas_density_degrid/
  p0_spatial_index/
    benchmark.json
    self_check.json
  p1_trainer_selfcheck/
    resume_check.json
  p2_roi50k/
    roi_indices.npy
    roi_core_mask.npy
    roi_halo_mask.npy
    roi_heldout_patch_indices.npy
    global_heldout_patch_indices.npy
    roi.json
    checkpoint.pt
    round_00_010000/
    round_01_020000/
    round_02_030000/
    round_03_040000/
    round_04_050000/
    summary.json
  p3_full404k/
    round_00_080904/
    round_01_161809/
    round_02_242714/
    round_03_323619/
    round_04_404524/
    recovered.npz
    compact.ply
    summary.json
```

## 18. 当前授权边界

用户已批准 P0、P1 与 P2。P2 的输入冻结、调度器、断点恢复和 dry-run
已经通过；正式 `10K→20K→30K→40K→50K` GPU 训练只在用户保存并关闭 UE、
且启动前再次确认 ETA/GPU/checkpoint/停止条件后运行。

P2 不导出 compact PLY、不重烘 transport、不修改或部署 UE。P2 numeric Gate
通过后仍须由用户批准 P3；未经批准不得启动全量 `80,904→404,524`。
