# GaussianVolume 最终路线实现与优化账本

最后更新：2026-07-30

## 1. 锁定的最终路线

当前作品集主线固定为：

> **标准 3DGS 自适应几何 + 单记录 shared-opacity 六向静态 transport +
> DGSM 重光照**，在 screen-space 同质量下与同源 UE SVT 比较完整 GPU
> working set 和 GPU 时间。

不可擅自改变的边界：

- 静态单 density 云、一盏 Directional Light + SkyLight、1080p 中远景；
- 当前主线为 `311,993` 个空间 Gaussian，禁止恢复每点 `×6` 完整叶片；
- 每点 `64 B`：center、opacity、对称 covariance 六值、六轴 transport；
- DGSM 分辨率、point count 和 per-point layout 默认冻结；训练只允许在不增点
  的前提下细化 geometry/opacity；
- 优化优先改变已有 center、covariance、extinction 和离线 transport，不增加运行时网络、采样器或额外 primitive；
- 增加点数、新增字段或更高 DGSM 只有当前路线明确无法过视觉 Gate 且用户重新批准后才能进入；
- 最终性能结论必须先通过用户 live viewport 同质量 Gate，再测同机位 complete frame、volume pass、steady/peak working set。

当前候选：
`WDAS_S3_StandardGeometry312K_SharedOpacity_DirectJ_NoBakedDC.ply`  
当前候选 SHA256：
`2CC4C78200369389E42A208A6BA2F3EEA6CB042362209B643D7F3A884B8A6607`  
历史保底 Gate：`WDAS404K-BALANCED-G1`  
历史完整备份：`artifacts/gates/2026-07-28_wdas_404k_balanced/`

## 2. 端到端实现流程

1. 从同源 VDB 生成多视角标准 3DGS 训练集。
2. 使用标准 3DGS 自适应 densify/prune 训练 geometry/opacity。当前选用
   `iteration_15000`：`311,993` points、test L1=`0.00240468`、
   PSNR=`43.5372 dB`；30K checkpoint test PSNR 回落，判定过拟合。
3. 将 G2 同源六轴 transport 按空间邻域传递到标准几何；shared-opacity 路径
   每个空间点只保留一份 geometry/opacity，不展开六叶片。
4. 移除 baked DC 对 direct J 的重复光照，导出当前 compact PLY：
   `311,993 × 64 B = 19,967,552 B` primitive payload。
5. UE runtime：
   - 一点只投影、排序和 rasterize 一次；
   - DGSM 提供轻量屏幕空间深阴影；
   - dual HG phase 提供前/后向散射；
   - scene directional light 直接消费 SkyAtmosphere 解析后的颜色；
   - Lumen indirect 使用组件已有 intensity/tint；
   - shared-opacity composite 从 latent J/T 恢复最终重光照。
6. 画质 fine-tune 只处理连续 `T_view/τ`、silhouette 和 opacity tail；
   现阶段禁止用全图颜色模糊替代轮廓训练。
7. 依次通过：
   - finite、positive-definite、record count、hash；
   - held-out `τ/T/edge/Gabor/IoU` numeric Gate；
   - UE D3D12 load/save/readback；
   - 用户 live viewport；
   - matched-quality GPU/显存 A/B。

## 3. 训练优化规则

- 每个优化使用新目录和新 Gate ID；不得原位覆盖已通过版本。
- 所有候选必须与直接父版本在同一 held-out rays 上比较。
- 固定预算训练允许修改 center、covariance、extinction；transport 在 center 未变化时逐条复用，center 变化后必须从源 grid 重烘焙。
- 只改善训练 loss、不改善 held-out 指标的版本记录为失败，不部署。
- numeric Gate 最低要求：
  - foreground-T PSNR 不下降；
  - `τ` MAE 下降；
  - edge L1 不上升；
  - 无 negative τ、NaN、非正定 covariance；
  - point count、layout 和 payload 不变。
- visual Gate 重点：规则点阵、边缘绒毛、中尺度团块、暗部层次、蓝偏、拉丝、孔洞和方向光连续性。
- 当前 S3 silhouette Gate 额外固定为：外轮廓只保留大尺度起伏；内部中小团块
  不得逐个穿透外轮廓；最外圈必须以连续密度尾自然消散。
- 当前训练缺口：binary mask BCE 会推高 0/1 硬边；`T_view` L1 只乘前景
  mask，无法监督边缘外侧软尾。下一次 fine-tune 必须使用连续 `T_view/τ`
  覆盖完整轮廓带，并加入多尺度 silhouette 目标。
- 新优化记录必须包含：动机、唯一变量、冻结项、输入、训练设置、held-out 前后数据、runtime 预算、导出 hash、UE 状态、最终裁决。

## 4. 优化记录

### G1 — Balanced 404K 保底 Gate

- 状态：**用户确认“效果好很多”，已冻结保底**。
- 几何：half-grid `8³` moments，spatial sigma=`0.4`。
- runtime：`404,524 × 64 B`，payload=`25,889,536 B`。
- held-out：foreground-T=`35.62960 dB`，τ PSNR/MAE=`42.17195 dB / 0.07027956`，edge=`0.05874429`，IoU=`0.986547`。
- PLY SHA256：`482B53C72728EFC2FB78528DC951000BB8536EE4905500198F59090ABA4F2E39`。
- 保留原因：当前已知可靠视觉底线；后续失败直接恢复此版本。

### G2 — Sigma038 + Anisotropy115

- 状态：**numeric Gate 通过，已部署，等待用户视觉裁决**。
- 动机：在不增点的前提下强化椭球方向性和边缘频率响应。
- 唯一变量：spatial sigma `0.4→0.38`；每点 covariance 体积守恒 anisotropy boost=`1.15`。
- 冻结：center、六轴 transport、point count、64 B layout、DGSM、UE 光照参数。
- 同一 1,000 held-out rays 相对 G1：
  - foreground-T：`35.1396→35.6227 dB`；
  - τ PSNR：`42.6639→42.6659 dB`；
  - τ MAE：`0.06117→0.06018`；
  - edge：`0.06115→0.05944`；
  - Gabor energy/phase：`0.001784/0.003319→0.001511/0.002945`。
- runtime：仍为 `404,524 × 64 B`，payload 不变。
- PLY SHA256：`C4321FCEC040103DF4A615E0598D488F31541F22F2E77007289B4B9EFA564FDF`。
- UE：map check=`0/0`，独立 D3D12 重开 readback 成功。
- 已知问题：用户截图仍出现规则点阵；统一 anisotropy boost 没有改变中心格点相位。

### G3 — Per-Gaussian Geometry De-grid

- 状态：**J15 已否决；下一候选待用户批准**。
- 动机：消除 G2 截图中的规则 block-grid 点阵，同时保持 G2 的对比度和细节。
- 开放参数：每点 center offset、三轴 scale、rotation、extinction。
- 冻结：exact `404,524`、64 B layout、DGSM、六叶片禁止、UE 当前 transfer/phase。
- 训练目标：多视角 `τ + T + edge + Gabor`，配合质量守恒、scale growth 和 geometry anchor。
- 通过后要求：重新烘焙六轴 transport；不得直接复用 G2 transport。
- P0：直接从 G2 做 80-step geometry training。中心中位／P99／max 仅移动 `0.04/0.13/0.23 cm`，远小于约 `6.5 cm` block pitch；Gabor 小幅改善但 τ/T/edge 回退，numeric Gate=`false`。结论：普通 image-space 梯度困在规则格点局部极值，物理上不足以 de-grid。
- J15：先做 deterministic stratified phase kick，block 内 jitter=`15%`，中心位移 P50/P90/P99/max=`0.96/1.28/1.48/1.68 cm`；随后固定 404K 训练 scale/rotation/extinction，并只允许极小额外 center 修正。
- 首次 J15 训练绑定前台工具会话，在 step 20/60 被对话中断而终止，无 checkpoint；之后按用户规则改为独立后台 PID＋stdout/stderr，并从固定 initializer 完整重跑。
- J15 60-step rerun 对抖动初始值自身 numeric Gate=`true`：τ PSNR `37.9300→37.9416 dB`、τ MAE `0.106297→0.106265`、foreground-T `33.3165→33.3519 dB`、edge `0.090415→0.090287`、Gabor energy/phase `0.002675/0.005959→0.002650/0.005891`。但相对真正父版本 G2 的 `42.666/0.06018/35.623/0.05944/0.001511/0.002945` 明显失败，因此禁止部署。
- 将完整 J15 update 回缩到 `25%/50%/75%` 后，25% 已是最优但仍相对 G2 回退：τ PSNR=`42.285 dB`、τ MAE=`0.06423`、foreground-T=`35.483 dB`、edge=`0.06211`、Gabor=`0.001588`。三档全部否决。
- 下一候选：直接从 `25%` 轻抖动 initializer（中心中位移动约 `0.24 cm`，等效 block jitter=`3.75%`）重新训练 scale/rotation/extinction，而不是插值完整 J15 训练结果。预计后台训练 `6–8 min`；按用户规则必须先同步耗时并获准。

### G4 — Overnight Conservative De-grid Search

- 状态：**后台运行中**。
- 用户授权无人值守长训练；启动前已同步计划、预计耗时与 GPU 行为。
- 搜索范围：block jitter=`1%/2%/3%/4%` × `conservative/recovery` 两档有界 shape recovery，共 8 个 exact 404K 候选。
- 预计耗时：`55–75 min`；UE 必须保持关闭，GPU 持续接近满载。
- 执行器：`mvp/run_degrid_overnight.py`；每个候选独立 initializer、训练目录和日志，存在完整 `recovery_report.json` 时自动跳过，因此进程中断只重跑当前候选。
- 自动 Gate：
  - strict：相对 G2 的 τ PSNR、τ MAE、foreground-T、edge、Gabor energy/phase 和 IoU 全部不退；
  - bounded：允许极小数值容差，但必须令几何 lattice-order 至少下降 `2%`，只保留为次日视觉候选，不能自动晋升；
  - point count、finite、positive-definite covariance 和质量均逐候选检查。
- 后台 PID=`89780`；summary=`artifacts/wdas_404k_degrid_overnight/summary.json`。
- Heartbeat automation=`gaussianvolume`，每 15 分钟检查进度；异常时从已完成候选继续，terminal 后自动暂停。
- 禁止自动部署 UE。只有 strict candidate 才允许继续独立 compact export、transport rebake 和结构验证；live viewport 仍由用户手动签字。

### G4 — Overnight Conservative De-grid Search（终局）

- 状态：**已完成并否决；无 strict/bounded candidate**。
- 总耗时：`126.26 min`；8/8 候选完成，stderr 为空。
- G2 基线：τ PSNR/MAE=`42.66593 / 0.060181`，foreground-T=`35.62273 dB`，edge=`0.059441`，Gabor energy/phase=`0.001511 / 0.002945`，IoU=`0.981230`，lattice-order=`0.810900`。

| 候选 | τ PSNR | τ MAE | fg-T | edge | Gabor E/P | IoU | lattice | strict / bounded | 失败原因 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| conservative 1% | 42.70756 | 0.060063 | 35.66996 | 0.059463 | 0.001502 / 0.002939 | 0.981230 | 0.810369 | false / false | edge 微退；lattice 仅降 0.066% |
| conservative 2% | 42.63536 | 0.060827 | 35.64163 | 0.060001 | 0.001518 / 0.002990 | 0.982255 | 0.808771 | false / false | τ/edge/Gabor 回退；lattice 降幅不足 |
| conservative 3% | 42.46425 | 0.062583 | 35.58035 | 0.060946 | 0.001542 / 0.003064 | 0.982255 | 0.806110 | false / false | τ/T/edge/Gabor 回退；lattice 降幅不足 |
| conservative 4% | 42.21821 | 0.064899 | 35.49270 | 0.062387 | 0.001579 / 0.003167 | 0.982255 | 0.802392 | false / false | 质量明显回退；lattice 仅降 1.049% |
| recovery 1% | 42.69362 | 0.060109 | 35.65879 | 0.059475 | 0.001508 / 0.002952 | 0.982255 | 0.810369 | false / false | edge/phase 微退；lattice 仅降 0.066% |
| recovery 2% | 42.61990 | 0.060904 | 35.63329 | 0.060017 | 0.001523 / 0.003001 | 0.982255 | 0.808771 | false / false | τ/edge/Gabor 回退；lattice 降幅不足 |
| recovery 3% | 42.45370 | 0.062582 | 35.57100 | 0.060982 | 0.001551 / 0.003080 | 0.982255 | 0.806110 | false / false | τ/T/edge/Gabor 回退；lattice 降幅不足 |
| recovery 4% | 42.21379 | 0.064813 | 35.48648 | 0.062421 | 0.001588 / 0.003182 | 0.982255 | 0.802392 | false / false | 质量明显回退；lattice 仅降 1.049% |

- 结构验证：全部保持 exact `404,524`，数据 finite，covariance positive-definite，质量守恒检查通过。
- 选中结果：`selected_strict_candidate=null`；strict 与 bounded 集合均为空。最接近的是 conservative 1%，但 edge 超基线约 `0.0000218`，且几何 lattice-order 下降远未达到 bounded Gate 的 `2%`。
- 最终裁决：轻量规则 jitter 存在“去网格越强、screen-space 质量越差”的稳定单调趋势，当前 recovery 无法同时破除点阵并保持 G2 质量。按 Gate 规则停止，不生成 compact PLY、不重烘 transport、不修改或部署 UE；G1 备份与当前 G2 均保持不变。
- 完整机器结果：`artifacts/wdas_404k_degrid_overnight/summary.json`。

### G5 — Density De-grid P0 Spatial Index

- 状态：**P0 已通过；允许进入 P1 审批，不代表画质路线已通过**。
- 动机：为连续三维 density loss 提供 `3σ AABB → regular bins → compact offsets/ids` 候选剔除，避免 `samples × 404,524` 暴力求和。
- 实现：新增 `mvp/train_density_degrid.py` 与最小回归检查 `mvp/test_train_density_degrid.py`；空间索引不参与反向，Gaussian 参数保持 autograd。
- 正确性：同 support cutoff 下 indexed/brute 最大绝对误差=`0`；空 bin、边界、finite gradient、超大 support guard 全部通过。
- bin 扫描：404K 上比较 `10/13/16 cm`，10 cm 的 field forward/backward 与峰值显存最低，冻结为 P1 默认；后两档不进入训练默认值。
- 50K/16,384 samples：pairs=`705,385`，neighbors P50/P95/P99/max=`7/10/12/15`，build=`93.85 ms`，forward/backward=`2.22/2.06 ms`，peak allocated=`42.05 MiB`。
- 404,524/16,384 samples：pairs=`5,660,580`，neighbors P50/P95/P99/max=`48/64/64/68`，build=`829.86 ms`，forward/backward=`7.62/15.11 ms`，peak allocated=`184.34 MiB`。
- 结论：RTX 5060 8 GB 上无 OOM，404K 三维 field evaluator 不是阻断项；P1 仍需实现自由参数化、三维采样/loss、densify/prune 与 round/step checkpoint。rebuild interval 要在 P1 首个优化步测得中心最大位移后确定。
- 证据：`artifacts/wdas_density_degrid/p0_spatial_index/self_check.json` 与 `benchmark.json`；源 initializer SHA256=`1769870a2fd6c78dda06f22c9784bc91b09e8d0e0fb22e88b812cab476974d70`。
- UE：未启动、未修改、未部署。

### G6 — Density De-grid P1 Trainer Core

- 状态：**P1 已通过；P2 画质训练待用户审批**。
- 实现：在 `mvp/train_density_degrid.py` 内加入无 anchor 的 absolute center、log-scale、normalized quaternion 与 softplus extinction；没有新建训练框架或运行时字段。
- 三维监督：连续 active in-cell、edge-biased 与 empty-space sampling；源 grid 三线性 target；density/coverage/empty/mass 四项 loss。
- 各向异性：新 seed/densify covariance 使用局部 `log1p(density)` Hessian，合成检查最大 eigenvalue ratio=`4.916`，不再固定球形或规则 block center。
- ray 接口：复用既有 τ/T/edge/Gabor loss，解析 Gaussian ray integral 自检 finite，prediction=target 时四项 loss 精确为零。
- 增删点：按高三维残差选点、最小距离 cell 抑制、低质量点 prune，同一 round 精确补回目标预算；合成检查 `2→3` 成功且 covariance/extinction 为正。
- checkpoint：原子保存 phase/round/step、全部参数、Adam、densification state、Python/NumPy/Torch CPU/CUDA RNG、输入 hashes 和 index 设置。连续第二步与 `step 1 save → load → step 2` 的下一 sample 完全一致，参数 max error=`0`。
- 真实 WDAS smoke：50K、4096 samples、RTX 5060 单步=`0.346 s`，总检查=`4.535 s`，GPU peak allocated=`46.49 MiB`；loss=`1.61358`，参数 finite，minimum covariance eigenvalue=`1.17e-5`，minimum extinction≈`1e-8`。
- 索引策略：geometry LR=`5e-4` 的首步最大中心位移=`0.0866 cm`；P2 初版每步 rebuild，不先引入多步 stale-index 优化。
- 已知诊断：CUDA 对 50K 个 `3×3` batched `eigvalsh` 返回 cuSOLVER invalid-value；训练步已完成且参数 finite，离线结构 Gate 改用与导出链一致的 NumPy CPU eigensolver 后通过。
- 证据：`artifacts/wdas_density_degrid/p1_trainer_selfcheck/resume_check.json` 与 `real_smoke.json`；source grid SHA256=`7de6a0769e2d6c79ed3e02f3ed05501a53b0608769ca72e9394989d6e8b01512`。
- UE：没有生成、覆盖或部署资产。

### G7 — Density De-grid P2 ROI Training

- 状态：**训练完成，numeric Gate 失败；禁止进入 P3 或 UE**。
- ROI：从 G2 冻结 exact `50,000` 个 26-neighbor 连通 B8 中心；外部冻结
  `354,524` 点。ROI core=`50,000` cells，按最大 G2 `3σ=0.196350 m`
  扩张 4 blocks 后 halo=`122,928` cells。
- 监督集：保存 64 个穿过 ROI core 的 held-out patches；另用独立固定随机种子
  保存 40 个全局 patches=`1,000 rays`。ROI indices、core、halo、两组 patches
  均有 SHA256，正式训练与 resume 强制校验。
- 调度器：`10K→20K→30K→40K→50K`；每轮执行连续三维 field fit、
  ray recovery、全局/ROI 评估和误差驱动 densification。checkpoint 原子保存
  round/phase/step、Adam、完整 RNG、输入 hashes；field 每 20 steps 与每个
  phase 边界保存。
- dry-run：`512 candidate + 354,524 frozen`，1024 个三维 samples；
  split/full field 最大误差=`2.384e-7`，中心最大位移=`0.0866 cm`，
  ROI 外回退点=`0`，hybrid ray finite 且非负；GPU peak allocated=
  `143.72 MiB`，耗时=`5.35 s`。
- 正式设置：每轮 80 field steps、5 ray steps、4096 field samples、
  60,000 densification error samples。实际优化/评估约 `4 min`；含一次保存
  边界修复与恢复的总墙钟约 `5m47s`。
- 恢复事件：round 0 evaluation 首次保存候选时，公共 NPZ 保存函数对
  trainable center 缺少 `detach()`；80 field + 5 ray steps 与 evaluation
  已在 checkpoint 中。共享保存函数、densification 和最终输出的同类调用
  一次性修复并加入导出回归后，从 `round 0 / evaluation` 恢复，未重跑优化。
- 最终全局相对 G2：τ PSNR `42.3511→38.2649 dB`，τ MAE
  `0.062894→0.089898`，edge `0.061049→0.063052`；strict/bounded 均失败。
- 最终 ROI 相对 G2：τ PSNR `42.3031→35.0081 dB`，τ MAE
  `0.073779→0.175599`，edge `0.030191→0.039078`；ROI Gate 失败。
- 去网格诊断：lattice-order `0.793240→0.016421`，说明自由中心成功破坏
  B8 相位；失败原因不是“仍有网格”，而是覆盖/光学深度恢复不足。30K round
  是 τ 最佳中间点，继续 densify 到 40K/50K 后 τ 反而回退，而 edge 继续
  小幅改善，表明当前 `80 field + 5 ray` 配比与逐轮质量归一不足。
- 结构：最终诊断 NPZ exact `404,524`，全部 finite，extinction `>0`，
  covariance positive-definite；SHA256=
  `7461de2437c7afb2c27e7d929214a99c1332a5c34d2e9da7fb83331db10f045a`。
- 自动停止：OOM/NaN、非正定 covariance、非正 extinction、hash/resume
  不一致、最终 global bounded 或 ROI 强制 Gate 失败。失败不导出、不部署。
- 证据：`artifacts/wdas_density_degrid/p2_roi50k/roi.json`、
  `dry_run/report.json`、五个 `round_*` 目录与 `summary.json`。
- UE：未读取、未修改、未部署；G1/G2 保持不变。

### G8 — Density De-grid P2b 30K Recovery

- 状态：**训练完成；40K 自动停止，best=35K，但仍未通过 G2 Gate**。
- 唯一父候选：P2 最佳 τ 中间轮 `round_02_030000/candidate.npz`，
  exact `30,000`，SHA256=
  `057a4b87e391c3175b3c01a0be4efe06697d16390c475642171fc30bef2c0aaa`。
- 调度：先对 30K warm start 做完整 recovery，再按
  `35K→40K→45K→50K` 每次只增加 5K；每轮 `80 field + 40 ray`，
  不再一次增加 10K 后只做 5 个 ray steps。
- 每轮 Gate：相对上一个接受轮分别记录 global/ROI τ MAE 与 edge；
  若 global 和 ROI τ MAE 同时超过前一轮 `0.5%`，立即
  `complete_stopped_regression`，保留此前最佳候选，不继续 densify。
- 最佳候选：以 global/ROI 的 τ MAE 与 edge 相对 G2 baseline 的归一化
  合计分数选择；发生 joint τ regression 的当前轮不得覆盖最佳候选。
- 恢复：复用现有 phase/round/step、Adam、完整 RNG 与 hash checkpoint；
  新增 warm-start 和 parent-metrics SHA256，恢复时强制校验。
- 自检：Python compile、既有 trainer/resume/export 回归、joint-regression
  Gate，以及 30K warm-start CPU 装载→NPZ 再导出均通过；roundtrip count=
  `30,000`，字段全部 finite。
- 正式运行：总计 `2.7115 min`，stderr 为空；GPU working set 峰值观察约
  `3.6 GiB`。
- 30K recovery 相对父候选：global τ MAE `0.082189→0.077857`，
  ROI τ MAE `0.160897→0.135794`，global/ROI edge
  `0.063737/0.040391→0.063368/0.038818`，四项逐轮 Gate 通过。
- 35K 相对 recovery 30K：global τ MAE `0.077857→0.076417`，
  ROI τ MAE `0.135794→0.128172`，ROI edge
  `0.038818→0.038320`；接受并成为 best。
- 40K：global/ROI τ MAE 回退到 `0.079930/0.136811`，分别比 35K
  差约 `4.60%/6.74%`，触发 joint τ regression，45K/50K 未运行。
- best 35K 相对 G2 仍失败：global τ PSNR/MAE
  `42.3511/0.062894→40.0662/0.076417`，ROI
  `42.3031/0.073779→37.5701/0.128172`；global/ROI edge
  `0.061049/0.030191→0.063418/0.038320`。
- best 结构：35,000 trainable + 354,524 frozen=`389,524`，全部 finite，
  extinction `>0`，covariance positive-definite，lattice-order=`0.010843`；
  SHA256=`63b467b698c5449ffa503706989de3b07aa2943ed91128890f2bd9d0df80bbe4`。
- 裁决：更长 ray recovery 与 5K 小步 densification 有明确正收益，但不能
  关闭对 G2 的剩余质量差；当前不是 exact 404,524，禁止 P3、compact
  export、transport bake 与 UE 部署。G1/G2 保持不变。

### G9 — Density De-grid P2c 40K Convergence

- 状态：**完成最大 200 ray steps；40K 未恢复，best 仍为 35K**。
- 动机：验证 P2b 的 40K 回退是否只是新增 5K 后尚未收敛，而非 40K
  表示本身退化。
- 冻结：40K point count、geometry loss、densification、G2 外部点、ROI、
  held-out 与所有 runtime 字段；只追加 ray recovery。
- 调度：每 40 steps 独立评估并原子 checkpoint，累计
  `40/80/120/160/200`；连续两次 global/ROI τ 都无 `0.5%` 恢复趋势才
  提前停止，最大 200。
- 结果（global τ MAE / ROI τ MAE）：
  - 40：`0.082205 / 0.165510`
  - 80：`0.082116 / 0.161475`
  - 120：`0.081607 / 0.160232`
  - 160：`0.081991 / 0.158974`
  - 200：`0.082347 / 0.160726`
- 对照：P2b 刚完成 40K 时为 `0.079930 / 0.136811`；追加 ray-only
  recovery 没有回到该起点，更未达到 35K 的 `0.076417 / 0.128172`。
  训练 patch loss 继续优化，但 held-out 恶化，证实问题是 ray-only
  过拟合/目标失配，不是“再多跑一些就能收敛”。
- 最佳选择：仍为 P2b 35K，SHA256=
  `63b467b698c5449ffa503706989de3b07aa2943ed91128890f2bd9d0df80bbe4`。
- 运行：`1.8521 min`，stderr 为空；UE 未修改或部署。
- 裁决：停止 40K 延长训练；下一候选必须改变初始化/约束，而不能继续增加
  ray steps。P3 继续禁止。

### G10 — P2b 35K UE Diagnostic Export

- 状态：**独立诊断资产已生成；不晋升 Gate**。
- 动机：按用户要求直接观察“lattice 明显消失、但 τ/edge 回退”在 UE 中的
  实际画面，而不是只看数值。
- 内容：冻结 G2 ROI 外 `354,524` 点，并合入 P2b best 的 `35,000` 个自由
  ROI 点，共 `389,524` records；候选参数未继续训练或修改。
- transport：从源 half-grid 按新中心重烘六轴，`density_scale=0.04`、
  `angular_sigma=0.5`、`ambient=0.06`。
- 导出：compact static transport，`64 B/record`，payload=`24,929,536 B`，
  文件=`24,930,324 B`；PLY SHA256=
  `586916c4c97eeafc88ede85c165e8e762244529fdffa9327b3a75ed863729aa7`。
- 结构 Gate：vertex=`389,524`、16 个 float 字段、payload finite、opacity
  在 `(0,1)`、transport 在 `[0.06,1]`、minimum covariance eigenvalue=
  `1.16955e-5`；PLY center/covariance 相对 hybrid NPZ max error=`0`。
- UE：用户启动 MCP 后，在 TechLab 内存态新建独立 Actor
  `DIAGNOSTIC | Free Density 35K + Frozen G2 / 389,524`，完整复制 G2 的
  Transform、Directional/Sky Light、DGSM、Dual SH、phase 与 opacity
  参数，仅替换 PLY；日志确认加载 `389,524` records。诊断 Actor 带 batch/
  semantic tags 并放入 `GaussianVolume/Diagnostics`；原 G2 只设
  `bVisible=false`。首次从 class 新建的 Actor 用户报告空显示并删除；R2
  先恢复 G2 可见，再用 `EditorActorSubsystem.duplicate_actor` 复制现有 G2
  实例，只替换 PLY，因此保留非公开初始化状态和用户当前
  `opacity=1 / power=1.2`。R2 日志再次确认加载 `389,524`，结构读回为
  G2 hidden / diagnostic visible；关卡未保存、G1/G2 资产未覆盖。
- 裁决：该资产只回答视觉诊断问题。P2b 的 global/ROI Gate 仍失败，不得
  因“看起来可用”自动成为最终路线。

### G11 — 冻结中心的 covariance/extinction 去网格训练

- 状态：**两档训练完成，失败并停止；未导出、未部署 UE**。
- 动机：保留 G2 的“一点对应一个 B8 block”覆盖与 VDB 造型，只训练椭球
  covariance、rotation 和 extinction，验证能否用各向异性拉伸消除点阵。
- 冻结项：exact `404,524` 点、center（实际最大位移
  `1.46e-11 m`）、单记录 `64 B` 路线、DGSM 与运行时字段。
- G11a 弱档：τ MAE `0.062782→0.062947`（`+0.263%`），τ PSNR
  `43.491→43.485 dB`；edge 改善 `0.106%`，Gabor energy/phase 改善
  `0.169%/0.218%`。但 covariance 相对变化 p50/p99 仅
  `0.168%/0.413%`，视觉幅度不足。
- G11b 强档：axis scale ratio p01/p50/p99 =
  `0.9708/0.9997/1.0306`，covariance 相对变化 p50/p99 =
  `2.59%/7.05%`，已达到可能可见的变形幅度；但 τ MAE
  `0.062782→0.065600`（`+4.488%`），τ PSNR
  `43.491→43.185 dB`，Gabor energy/phase 分别恶化
  `0.687%/0.892%`，仅 edge 改善 `0.668%`。
- 裁决：弱档不可见，强档超过 bounded `+0.5%` τ MAE 容差近九倍。
  “固定 G2 center、只训练 covariance/extinction”不能同时消除点阵并保持
  VDB 光学身份；不跑第三档，不生成 PLY，不重烘 transport，不进入 UE。
- 证据：`artifacts/wdas_404k_covonly_freq_g1/recovery_report.json`
  SHA256=`2F95E146139CD4F2E754933511FAB1FA06E55DB206C1E5FA1E1484497100AFF4`；
  `artifacts/wdas_404k_covonly_freq_g2/recovery_report.json`
  SHA256=`90E6C029B1E9139CAF2F1B23AAFA1C1C1AFBC7986B43F3D593A1000B964E391C`；
  两份报告的 `numeric_gate_passed=false`，stderr 均为空。

### G12 — Mass-preserving screen-space footprint 原型

- 状态：**仅编译通过，默认关闭，尚未做视觉 Gate；不属于 G11 训练结果**。
- 内容：增加 `r.GaussianSplatting.FootprintScale`，默认 `1.0`，范围
  `[1,2]`；放大投影 covariance 时以 `1/scale²` 修正 opacity，保持积分质量。
- 验证：`mvp/test_footprint_mass.py` 覆盖 `1.0/1.08/1.15/1.25`，二维积分
  质量误差在 `1e-12` 内；AbyssEditor Development 编译通过。
- 裁决：只保留为独立 renderer A/B 工具，未经用户明确批准和 live viewport
  验证，不启用、不声称改善，也不替代训练路线。

### 2026-07-29 — UE 诊断更正

- 当前 Gaussian renderer 只维护一个 active component，且旧可见性路径不足以
  支撑双 Actor 同屏 A/B；因此 G10 的“G2 hidden / diagnostic visible”读回
  不能证明实际渲染的是诊断资产。
- 后续原位替换确认 P2b 35K 诊断云造型偏离 VDB 且仍有明显点阵，进一步支持
  P2 路线失败。
- 更正先前的“重开会自动恢复 G2”判断：后续会话实际读回两个诊断 Actor，
  分别为 ROI-only `35,000` 点和 hybrid `389,524` 点，原 G2 Actor 已被原位
  替换。2026-07-29 通过 UE MCP 将 `35,000` 点 Actor 原位恢复为经 SHA256
  核验的 G2 PLY（`C4321F...64FDF`），删除另一诊断 Actor，并读回确认当前
  只剩 `Compact Transport GS + DGSM | WDAS G2 Sigma038 Aniso115 / 404K`
  一个 GS Actor、point count=`404,524`、位置=`(2600,840,-40)`。恢复参数为
  opacity=`0.6`、power=`0.9`、relight=`0.7`、ambient=`0.01`。
- 当前恢复仅存在于编辑器内存，**关卡未保存**；用户视觉确认并明确批准保存前
  禁止调用 `save_current_level()`。

### G13 — Exact-G2-preserving Multi-scale Moment Split

- 状态：**预处理器与 split=0 identity Gate 通过；正式候选尚未生成或训练**。
- 动机：保留 G2 已通过的 VDB 造型和覆盖先验，仅把高残差的单一 B8
  Gaussian 替换为其 B2 子 Gaussian，再以相邻低细节 singleton 的矩合并抵消
  新增记录，始终保持 exact `404,524` 和总质量／全局一二阶矩。
- 首版 `raw_parent` 路径判定无效：即使 split=`0`，也会从 `412,267` 个原始
  B8 parent 重新合并 `7,743` 次，导致候选已不再是 G2；已有
  `split_000000/001000/002000/004000` 和 `split_004000/recovery_0100`
  只能保留为失败诊断，禁止部署或当作 G2 增量实验。
- 修正：`--base-npz` 模式直接以 G2 initializer 为基底。`397,506` 个可一一
  映射到 B8 parent 的 singleton 可参与 split/merge；`7,018` 个既有 contracted
  records 原样保护。
- identity Gate：`base_split_000000/initializer.npz` 与 G2 initializer 的
  SHA256 同为
  `1769870A2FD6C78DDA06F22C9784BC91B09E8D0E0FB22E88B812CAB476974D70`；
  center/covariance/extinction 逐数组完全相等，mass、global center 与 global
  covariance error 均为 `0`。report SHA256=
  `71CA839386611FE052B2B1CB5BB3B583B7BCD371B0824A497A98FC8144F0BFEA`。
- 代码检查：`test_adaptive_grid_budget.py` 3/3 通过；四个相关脚本
  `py_compile` 通过。另已把大 grid 聚合改为分块、源 grid 加载改为 mmap，
  避免重复占用整份数组。
- 当前断点：没有 Python 训练进程；新的 base-preserving split
  `1K/2K/4K` 尚未生成、未跑 eval0/recovery、未导出 PLY、未重烘 transport、
  未部署 UE。下一次推进必须先给用户同步预计耗时；先跑无训练的 eval0 Gate，
  只有明显接近 G2 的候选才允许短 recovery。

### G14 — G2 Compact Transport 光照正确性修复

- 状态：**六轴与 DGSM 修复已通过；日落光色子项已构建，待用户 live viewport 复验**。
- 用户确认 G2 正面受光仍偏黑。代码审计发现 compact PLY 的 `j_0..j_5`
  按资产局部 `+X/-X/+Y/-Y/+Z/-Z` 存储，但运行时 angular weights 曾按
  `+X/-X/-Z/+Z/-Y/+Y` 配对，导致 Y/Z 灯向读取错误 transport。
- 共享运行时现使用唯一 canonical axis 数组生成权重，Slice 与 HW Raster
  继续消费同一组 uniforms，不增加字段、buffer 或 pass。
- 曾把 compact `J` 与 DGSM 视为重复遮光并暂时令 compact stride 跳过 DGSM；
  用户 live viewport 立即确认该版本对比度拉不开、背面压不暗。该假设判负并
  已回滚，compact 继续严格消费 G2 原配置的 DGSM。
- G2 PLY、关卡和 Actor 配置均未修改；`bEnableRNGDGSM=true`、opacity=`0.6`、
  power=`0.9`、relight=`0.7`、ambient=`0.01` 等原值保持。PLY SHA256 仍为
  `C4321FCEC040103DF4A615E0598D488F31541F22F2E77007289B4B9EFA564FDF`。
- DGSM 回滚后的 `AbyssEditor Win64 Development` 构建与链接成功；NullRHI
  实际加载 `404,524` records，`GaussianSplatting.CompactTransport` 六轴顺序
  自动化测试通过。
- 用户在回滚 DGSM 后确认明暗对比恢复，但后续日落 A/B 显示 VDB 已明显变红、
  Gaussian 仍近白。只读关卡诊断确认唯一方向光已正确绑定，且为 Atmosphere Sun
  Light 0；问题位于 Gaussian 的光色来源，不是 G2 资产或 Actor 配置。
- scene-light composite 现直接使用 UE 已解析 SkyAtmosphere 的
  `ResolvedView.DirectionalLightColor`，只叠加原 relight scale/tint；manual-light
  保持原始光能路径。AbyssEditor 构建／链接成功，NullRHI 与 DX12 offscreen
  均加载 exact `404,524` records 并通过 `GaussianSplatting.CompactTransport`。
  日落光色仍待用户 live viewport 签字；通过后才恢复“点阵是唯一阻断项”。

## 5. 当前交接状态

- 作品集主线与可用保底仍是 **G2：404,524 × 64 B + DGSM**；G1 继续作为
  冻结备份。
- Density De-grid P2/P2b/P2c、overnight jitter、covariance-only 均已否决，
  不得靠追加训练步数重开。
- G14 六轴／DGSM 明暗修复已通过用户 live viewport；新增日落光色修复已通过
  构建、NullRHI 与 DX12 offscreen，待用户 live viewport 复验。通过后唯一未裁决
  方向才是 G13 局部 multi-scale moment split；目前只通过 identity Gate。
- UE 当前内存态已恢复单一 G2，但未保存；诊断 PLY 仍可作为独立文件保留，
  不得再次原位覆盖 G2 后保存。
- 当前无后台训练。用户可正常使用 UE。

## 6. 新优化记录模板

### G15 — B8 点阵消除穷举与 renderer-only live A/B

- 状态：**离线结构路线已裁决；不部署；原 G2 的 renderer-only A/B 已编译，
  待 live viewport Gate**。
- 冻结项：G2 PLY、point count、DGSM、关卡、灯光和 Actor 参数均未修改或保存。
- 已否决：独立／局部矩平衡 jitter、covariance 旋转、连续 center warp、
  screen blur、footprint dilation、时域随机 jitter、分层随机采样、
  exact-count split/merge。它们要么保留规则点阵，要么把点阵换成闪烁、模糊或
  Monte-Carlo 颗粒，并明显破坏 held-out 光学指标。
- 自适应 B4 矩分区把 lattice order 从 G2 `0.810900` 降到
  base `0.002383`、organic05 `0.001269`、organic05+mass05 `0.001637`；
  近景 CUDA raster 对比确认直线点阵消失，但出现细颗粒／斜向分区纹理。
- 同一 1000 held-out rays 上，三者最佳的 organic05+mass05 仍只有
  τ PSNR `37.4646 dB`、τ MAE `0.107946`、foreground T PSNR
  `33.2845 dB`、edge `0.104924`、Gabor energy/phase
  `0.002298/0.004695`、IoU `0.978170`；G2 分别为
  `42.6659 dB`、`0.060181`、`35.6227 dB`、`0.059441`、
  `0.001511/0.002945`、`0.981230`。100-step extinction-only recovery 也只把
  τ PSNR `37.2030→37.2172 dB`，不足以追回质量。三种结构候选全部禁止部署。
- renderer 根因补充：现有 Gaussian pass 挂在 `MotionBlur`，位于 TSR/TAA
  之后，无法获得时域抗锯齿；新增默认关闭
  `r.GaussianSplatting.PreTSR=0`，仅在 live A/B 时切到 `BeforeDOF`。
  AbyssEditor Development 冷编译／链接通过。
- alpha-tail 诊断：默认 absolute cutoff `1/255` 会让 G2 约 `8.151%`
  低密度 splat 整颗丢弃，且中位支持半径约 `2.384σ`，低于 quad 的
  `2.828σ`。新增 `r.GaussianSplatting.AlphaCutoff`，默认仍为旧值
  `1/255`；`1/1024`、`1/4096` 只作为临时 live A/B，不写入配置。
- 证据：
  `evidence/adaptive_b4_final_compare_close/view_00.png`、
  `evidence/adaptive_b4_final_compare_close/view_01.png` 和各候选
  `recovery_report.json`。下一步只在原 G2 上验证 PreTSR 与 alpha tail，
  用户签字前不保存关卡、不替换资产。

### G16 — 正式淘汰 323.6 万点 Sigma8 路线

- 状态：**判负；仅保留研究证据，不部署、不保存到 UE 关卡。**
- 视觉收益：离线点阵指标由 `0.8109` 降至 `0.0332`，但 UE 实测仍有残余放射线，
  且亮度、阴影和 VDB 存在偏差。
- 资源代价：点数 `404,524 → 3,236,192`（`8×`）；PLY
  `24.69 → 197.52 MiB`；稳定 CPU 数组约 `49.38 → 395.04 MiB`；
  GPU 每点缓冲约 `86.42 → 691.33 MiB`；加载约 `0.27 → 2.63 s`。
- 对照 VDB：场景中的 U8 VDB 标注为 `85.8 MiB`，Sigma8 仅 GPU 每点缓冲就约
  `691.33 MiB`，工程价值不成立。
- 后续硬门槛：点数不得超过原 G2 的 `404,524`；GPU 每点缓冲不得超过约
  `90 MiB`；同等画质下还必须不慢于 VDB，未通过离线门槛的候选不进入 UE。
- 当前状态：已恢复单一原 G2 actor，参数保持 `Opacity 0.6 / Power 1.1 /
  Relight 1.0 / Ambient 0.4`，无脏关卡或内容。后续不再靠堆点，只研究固定
  G2 预算内的表示或渲染侧方案；若无法同时满足画质和性能，就直接采用 VDB。

### G17 — 全局 Adaptive B4 UE 肉眼诊断

- 状态：**用户肉眼判负；仅保留诊断资产，不部署、不保存。**
- 复用已有全局 `organic05 + mass05` 训练结果，保持 exact `404,524` 点；
  lattice-order=`0.001637`。补齐六轴 transport 与 compact PLY 导出，不改
  shader、灯光、关卡或 Actor 参数。
- PLY 为 `404,524 × 64 B`，全部 finite，协方差正定，中心/covariance 与
  NPZ 零误差；SHA256=`9892521022D584AC9F6019D75B88219E1DC2ED4D77E1BDA59DEF1F0887462AC7`。
- UE 内存态使用 `Opacity 0.5 / Power 1.1 / Relight 1.0 / Ambient 0.4 /
  DGSM on`。用户截图确认规则相位被打散后出现明显固定空间颗粒／噪点感，
  不能作为干净的光照 A/B，也不满足最终画质。
- 已原位恢复 G2 exact `404,524` 点并保留上述当前参数；关卡与内容脏包均为空。

### G18 — S3 标准 3DGS 几何重光照主线与最终收口

- 状态：**当前主线；规则点阵已解决，等待 silhouette/soft-tail visual Gate。**
- 标准 3DGS 训练从 VDB 多视角图像自适应学习 geometry/opacity。15K checkpoint
  为 `311,993` points，test L1=`0.00240468`、PSNR=`43.5372 dB`；
  30K test PSNR=`42.9078 dB`，没有继续采用。
- 当前资产为
  `artifacts/wdas_s3_standard_geometry_compact6/WDAS_S3_StandardGeometry312K_SharedOpacity_DirectJ_NoBakedDC.ply`，
  `64 B/point`、payload=`19,967,552 B`、SHA256=
  `2CC4C78200369389E42A208A6BA2F3EEA6CB042362209B643D7F3A884B8A6607`。
  最新 editor 日志确认实际加载 `311,993 compact static transport gaussians`。
- 用户 live viewport 确认相较 G2 不再有规则点阵，当前流程可进入收口。剩余问题
  不是像素锯齿，而是 10–50 px 量级的 silhouette 结构：外轮廓由过多中小
  团块顶出密集鼓包/凹口，团块间硬缝穿到外缘，最外圈密度下降过快。
- 正确目标：合并小轮廓起伏、保留大云形；内部细节继续存在但不逐团穿透；
  拉宽最外层 density/opacity tail，而不是把整张颜色、阴影和体积层次一起模糊。
- renderer 试验：shared-opacity composite 曾使用稳定的 bilinear Kawase
  premultiplied filter；最新 2.25 px edge-only filter 和 4 px AABB padding
  经用户同机位观察无可辨识收益。该结果符合尺度判断：它只改 1–2 px fringe，
  不能整理十几到几十像素的轮廓。此方案不计为画质通过。
- 下一实现顺序：
  1. 从 15K checkpoint 做小步、不增点 fine-tune；
  2. 用连续 `T_view/τ` 监督完整边界带，加入多尺度 silhouette loss，降低
     binary-mask BCE 的硬边推动；
  3. 若训练仍不足，再做低分辨率 coverage/τ resolve 与保边上采样，严禁全图
     RGB blur；
  4. visual Gate 后冻结，再进入性能 profile。
- 当前资源事实：`19.043 MiB` 只是 PLY/primitive payload。1080p 总 working set
  还包含 visible/sort、GSColor、DGSM 和 RDG transient；未完成同机位实测前
  不得宣称相对 SVT 总显存或 GPU 时间胜出。
- 2026-07-30 退出编辑器时出现一次 GameThread access violation；日志先进入
  `QUIT_EDITOR/CloseEditor`，crash stack 为 `python311 → PythonScriptPlugin`，
  没有 D3D/DXGI/GPU/shader fatal。后续 shader 调试避免用 Python 触发
  Live Coding，优先 shader-only reload 或干净构建。

### G19 — S3 精确 alpha 训练与边界 coverage 收口

- 状态：**用户 visual Gate 否决；外轮廓改善不足以覆盖主体差异。**
- 唯一变量：训练只从 15K 小步续训且不增点；渲染只改 shared-opacity composite
  的外边界 coverage 重建。组件、灯光、DGSM、phase 和主 PLY 均冻结。
- 训练裁决：`w=0.05/500` 离线 alpha L1=`0.00376314`，但 UE 中景边界更碎；
  `w=0.2/1000` 过拟合；opacity-only `w=0.1/1000` 仍未胜过原 15K。主资产
  保持 `WDAS_S3_StandardGeometry312K_SharedOpacity_DirectJ_NoBakedDC.ply`。
- runtime 候选：4-tap 8 px 边界探测；边界执行 5×5 Gaussian latent coverage
  核（step=4 px、radius=8 px），内部跳过；AABB pad=9 px，无新增 RT/pass。
- UE 五帧平均：中景 roughness GS/SVT=`5.917/4.008`，远景=`4.354/4.012`。
  6 px 核退化，已回退。最终 shader compile 无 error/fatal。
- 性能口径：边界像素最坏为 `4+25` taps，内部为 4 taps；实际成本取决于边界
  像素占比，必须用同机位 GPU profile 后再决定是否做 separable/half-res 优化。

### G20 — S3 transport 自洽性 A/B/C

- 状态：**UE 固定机位 visual Gate 已完成；4-NN transport 不是主因。**
- 动机：当前 S3 geometry/opacity 来自标准 3DGS，但主资产六轴 `J` 实际由
  G2 389,524 点经 4-NN 转移；最近 transport 距离
  P50/P99/max=`3.20/7.04/34.76 cm`，需要排除 geometry 与 transport
  不自洽造成的 10–50 px 内部暗缝。
- 唯一变量：只替换每点最后六个 `j_0..j_5`。A=当前 4-NN J；
  B=在同一 S3 center 从原 VDB 直接重烘 `J=exp(-τ)`，ambient=0；
  C=`J=1`，但 UE 中 DGSM/phase 仍保留。
- 冻结项：`311,993` 点的 xyz、shared opacity、六项 covariance、点序、
  64 B layout、组件参数、DGSM、phase、Shader 和 runtime 全部不变。
- 输入／设置：`wdas_cloud_half.npy`，shape=`994×676×1225`，
  density scale=`0.04`，voxel=`0.8163265306122449 cm`，
  asset axis order=`(0,1,5,4,3,2)`；全部 S3 center 位于 grid 内。
- 结构 Gate：A/B/C 前十列逐 bit 相等；均为
  `311,993 × 16 × float32`、payload=`19,967,552 B`；B J finite 且
  位于 `[0,1]`。A/B J RMSE=`0.0275640`，max abs=`0.9649755`。
- 导出：
  `artifacts/wdas_s3_transport_ab_20260730/`；
  A SHA=`2CC4C78200369389E42A208A6BA2F3EEA6CB042362209B643D7F3A884B8A6607`；
  B SHA=`19058C3D64BEC5A8AD87EB8DC03DB0F5538746FCC9AFA4B13B1F74CE3D462495`；
  C SHA=`49DC0C555BEA34D1F7B296BE856D465A4D49CDB013B6C627A3D008A54230B3DB`。
- runtime 预算：零变化；本轮不改 Shader、不增点、不增 pass/RT。
- UE Gate：同一 actor/transform/机位，固定曝光、灯光、ambient、phase、DGSM、
  fog 和 TSR；加载后暖 8 帧，正面光与侧光各取 5 帧。B 相对 A 的 4 px
  低通 luma MAE 与内部梯度/暗区差距需在两个光向改善至少 20%，轮廓面积
  变化应小于 1%。C 仅用于确认 J 通路可见，不参与画质排名。
- UE 结果：原光向与侧光 `+90°` 下，A/B 肉眼几乎一致；C=`J=1` 时
  Gaussian 近白且内部直射层次消失，证明 J 通路确实生效。由此否决
  “4-NN 搬运误差造成主要视觉差异”，问题转为 `exp(-τ)` 的响应范围过硬。
- 响应诊断：保持前十列逐 bit 不变，只测试 D=`J^0.5`、
  E=`J^0.25`、F=`J^0.4`。D 仍偏硬，E 过亮过平，F 位于两者之间；
  F SHA=`7019CC8092EDFE76A99F3E13A4C52FBF6CD9987A8212631DACAD98E0799A8AB8`。
- 最终裁决：亮暗主候选采用离线 `J^0.4`，不增加 Shader 指令、运行时参数、
  点数、pass 或 RT。剩余主差异是 geometry/opacity 的中小团块过多与
  silhouette 过碎，应与 transport 响应分开处理。

### G21 — S3 视角相关轮廓小步训练

- 状态：**当前最佳轮廓候选；结构和中景 visual A/B 有小幅正收益，待冷启动后
  用户最终签字，不保存关卡。**
- 目标：合并外轮廓小鼓包和小凹口，只保留较大云形起伏；内部团块不得逐个
  穿透外轮廓；不通过全图模糊换取平整。
- 已否决两条路线：
  - 外层约 `7%` 点的统一 scale/spread：UE 中景几乎不可辨识；
  - VDB 低频 3D envelope gate：只影响 `2.08%` 点，视觉收益过小。
- 固定 3D shell mask 的 100/250/500-step 训练也被否决：100-step 太弱，
  250/500-step 开始压平大形并强化硬边。根因是固定 3D shell 与真正
  view-dependent silhouette contributor 只有 `48.6718%` 重叠。
- 新 mask 由 64 个训练视角累计 morphology silhouette loss 的
  xyz/opacity 梯度，选择 top `19,500 / 311,993 = 6.25014%` 点；只允许这些点
  更新 xyz/opacity，其他点和所有 covariance/transport 冻结。
- 100-step held-out 指标：
  - raw alpha L1：`0.01508 → 0.02637`（预期的 coverage 取舍）；
  - morph-boundary L1：`0.15173 → 0.08560`，改善 `43.59%`；
  - silhouette roughness：`0.05772 → 0.05610`，改善 `2.80%`。
- compact 空间中心位移 P50/P95/max=`1.0686/2.0308/3.4229 cm`；只对选中
  mask 做 opacity mass normalization，因子=`0.6189081`，全体 opacity sum
  比例=`1.0000000006`。点数、顺序、covariance、`J^0.4` 和 64 B layout
  均不变。
- 候选：
  `artifacts/wdas_s3_view_boundary_morph_compact_20260731/S3_ViewBoundaryMorph_100_MassNormalized_FJ.ply`；
  payload=`19,967,552 B`；SHA256=
  `ACA976257E9F901950E9E3F1735F802E2B5AADFEAFAD5E6E73268F25D8EAFAC0`。
- UE FOV90 中景 A/B：候选顶部和右侧轮廓更连贯，细小枝杈减少；内部没有
  全局变糊或明显硬化。收益真实但有限，尚不能宣称完成最终 visual Gate。

### G22 — HW Quad 死缓冲清理

- 状态：**冷编译和离屏冷启动通过；等待前台编辑器做同机 GPU profile。**
- 根因：当前 runtime 已完全使用 GPU sort + HW Quad direct blend，但
  Preprocess 仍为已移除的 tile-binning 回退链路分配并写入
  `TilesTouched / VisibleRectMin / VisibleRectMax`。全仓库检查确认没有任何
  后续读取。
- 改动：只删除上述三个 `uint/point` RDG buffer、Shader 参数和对应
  tile-rect 计算；raw/sliced、visible raster 数据、sort、GSColor、DGSM、
  composite、资产和 Actor 参数均保持不变。
- 固定 `311,993` 点下节省
  `311,993 × 12 B = 3,743,916 B = 3.570 MiB` 每视图 transient，并减少
  Preprocess 的三次初始化写、三次结果写和无用 tile-rect 运算。
- 1080p 可明确列名的逻辑资源由约 `83.97 MiB` 降至 `80.40 MiB`：
  per-point raw/sliced/visible/sort=`63.078 MiB`，GSColor RGBA16F=
  `15.820 MiB`，compact DGSM=`1.500 MiB`；实际峰值仍需加 GPU sort scratch、
  RDG aliasing 和引擎公共资源，不能与 SVT 资产文件大小直接等同。
- 首次用 Live Coding 热换全局 Shader 参数结构时，旧元数据布局导致
  `FGSPreprocessCS::OutVisibleCount was not set` fatal。该路径已停止使用；
  编辑器退出后执行完整
  `Build.bat AbyssEditor Win64 Development -NoHotReloadFromIDE`，7/7 actions
  成功。后续此类参数布局变更只能冷编译、冷启动验证。
- 使用项目自带 `AbyssEditor.exe` 以 DX12/PCD3D_SM6 离屏冷启动：
  `FGSPreprocessCS` 成功重编译，关卡成功载入 `311,993` 点并进入首帧，
  日志无 Shader 参数绑定错误或 fatal，随后通过 `quit` 正常退出。说明
  上述 crash 是热替换元数据失配，不是死缓冲删除本身。离屏启动不用于
  帧耗时结论；最终性能数字只在前台编辑器、相同相机和分辨率下复测。

### G23 — Radix sort 初始化写审计

- 状态：**保留 RDG 必需初始化；只删除一项已证明冗余的 clear，冷编译与
  300 帧 DX12 离屏验证通过。**
- 固定 `512×512 / 311,993` 点的 ProfileGPU 显示四个 sort clear 分别约
  `0.004 / 0.004 / 0.005 / 0.005 ms`。源码审计确认：
  `SortKeys0` 必须用 `0xffffffff` 填充不可见尾部；
  `SortKeys1 / SortValues1` 因当前 low-level radix sort 封装在同一 RDG pass
  中声明双侧 SRV/UAV，RDG 要求备用侧先有写入，不能直接删除。
- 曾尝试删除三个理论上会被 radix pass 覆盖的 clear，验证器立即报告
  `SortKeys1 ... was never written to`；未保留该错误版本。
- 最终只删除 `SortValues0` clear：所有可见 slot 都由 Preprocess 写入，
  不可见 slot 的 value 永远不会进入 `VisibleCount` 范围。复测日志中无
  `never written`、Shader 绑定错误或 fatal。收益约 `0.005 ms/帧`，不改变
  缓冲布局、排序结果或画面。

### G24 — 轮廓贡献点覆盖率 10% 候选

- 状态：**离线 held-out 门禁通过，已部署到插件目录；等待 UE 中远景 A/B，
  不保存关卡。**
- 13 px morphology 版本被否决：相对 9 px / 6.25% 候选，held-out
  morph-boundary L1 从 `0.08560` 退化到 `0.09974`，轮廓 roughness 从
  `4.4878` 回升至 `4.5755`。因此不通过扩大模糊尺度追求平整。
- 保持 radius=`9 px` 和 100-step 小步训练，只把 64 视角梯度选中的真实
  silhouette contributor 从 `19,500 / 6.25014%` 扩到
  `31,199 / 9.99990%`；原 6.25% 集合完整包含于新集合。
- 8 个 held-out 视角：
  - morph-boundary L1：`0.08560 → 0.08303`；
  - roughness：`4.4878 → 4.4496`；
  - raw alpha L1：`0.02637 → 0.02692`，为轻微 coverage 取舍。
- 仍只改变选中点的 center/opacity。选中点中心位移 P50/P95/max=
  `1.0027 / 1.9115 / 3.4226 cm`；其余点 center/covariance 逐 bit 不变；
  六列 `J^0.4` 逐 bit 继承；opacity mass normalization factor=
  `0.6502218`，总 opacity 比例=`0.9999999973`。
- 资产维持 `311,993` 点、`64 B/point`、payload=`19,967,552 B`，运行时
  点数和显存布局不变。候选 SHA256=
  `AF5EECB01BCA46C4B776ED3D0AACB4809C1698DB986EC19AA47FC9F1C7ECD155`；
  插件路径：
  `Content/Data/S3BoundaryMorphMask10_20260731/S3_ViewBoundaryMorph_Mask10_100_MassNormalized_FJ.ply`。

### G25 — UE 严格 A/B、组件修复与 12.5% / 150-step 候选

- 状态：**10% 候选已由 UE 固定机位门禁否决；12.5% / 150-step 候选已部署，
  等待近景固定机位与 GPU 门禁，不保存关卡。**
- 先前 10% A/B 截图因相机漂移无效。重新固定相机位置、旋转、FOV90 和曝光后，
  baseline 与 10% 候选在 GS 区域平均差异仅约 `0.98 / 255`，超过 `10 / 255`
  的像素只有 `0.85%`；肉眼收益不足，不能作为最终版本。
- Details 面板参数变灰不是配置值造成的。旧关卡实例的
  `GS7DComponent` 反射属性为 `None`，实际组件仍作为孤儿原生组件挂载；
  根因是热编译/类重实例化遗留。已用干净的同类 Actor 替换旧实例并完整复制
  PLY、Transform、灯光引用和全部 GS 参数。新实例属性与实际组件指针一致，
  点数仍为 `311,993`，opacity 仍为 `0.4`。
- 新候选保持 morphology radius=`9 px`，把 64 视角贡献点覆盖扩到
  `38,999 / 12.49996%`，训练从 100 步延长到 150 步；没有增点、改 covariance、
  改 transport、改 Shader 或改 Actor 参数。
- 150 步相对同 mask 的 100 步：held-out morphology loss
  `0.08843 → 0.08027`，roughness `5.5756 → 5.4634`；raw alpha L1
  `0.02712 → 0.02872`，需要 UE 肉眼判断是否出现大形压平。
- 最终 compact 候选维持 `311,993 × 64 B`，payload=`19,967,552 B`；
  非选中 center/covariance 与 baseline 逐 bit 相同，六列 `J^0.4` 逐 bit相同，
  总 opacity 比例=`0.99999999998`。选中点中心位移 P50/P95/max=
  `1.2194 / 2.4224 / 4.8132 cm`，SHA256=
  `5F0F3F2D4D72523026382966073B04CAE464780DF1DF21EF1E9C9483AF4421B8`。
- 新增可复用的最小收口脚本
  `mvp/build_s3_view_boundary_candidate.py`，只负责质量归一、继承冻结 J、
  写回 64 B compact PLY，并执行点数/位一致性门禁。

### G26 — 远景轮廓滤波尺度修正

- 根因：共享透明度 composite 的边缘滤波固定使用 `8 px` 探测半径和 `4 px`
  核间距；云拉远后投影缩小，但滤波像素宽度不缩小，因此外圈形成过宽光晕。
- 改动：只在 `GaussianSplattingComposite.usf` 内依据当前 source AABB 的屏幕尺寸，
  把滤波步长由固定 `4 px` 改为 `0.75–2 px` 自适应；第一次 `1–4 px`
  在中景大投影下仍接近旧值，经用户截图否决后继续收紧。
- 冻结项：训练资产、点数、opacity、光照、DGSM、phase、Actor 参数和 Shader
  参数结构均未改变；无新增 pass、RT 或 CVar。
- 验证：`recompileshaders changed` 仅重编译 `FGSCompositePS`，日志无 shader
  error/fatal。近景截图保持原柔化；远景 visual Gate 待用户在同机位复验，
  未保存关卡。
- 后续同机位 A/B：完全关闭 composite 边缘滤波后，宽白壳几乎不变，仅最外沿
  `1–2 px` 有差异，因此它不是剩余模糊的主因。`AlphaCutoff=1/64` 能进一步
  收尾，但暴露明显颗粒；运行时已恢复原值 `1/255`，默认配置未修改。

### G27 — 内部连续 alpha 与 footprint 收口

- 状态：**用户 live viewport 否决；内部 opacity 与 4% interior footprint
  候选均已回退到 G25，未保存关卡。**
- 根因：G25 的 12.5% view-boundary mask 冻结了其余 `87.5%` 点，因此只能整理
  外轮廓，无法减少内部细碎团块和裂缝。继续调 AlphaCutoff 或 composite 只会
  改最外沿 1–2 px，不能解决内部结构。
- 训练改动：复用标准 3DGS 的 opacity-only 路径，修正其原先仍使用 RGB loss
  的问题；新路径只以白色 override render 比较连续 alpha，冻结 xyz、scale、
  rotation、SH/color 和点数。新增 5/11/21 px 多尺度内部 alpha loss，并只惩罚
  GS 相对 VDB 多出来的 5 px 内部梯度。
- 8 个 held-out 视角相对 G25：
  - interior alpha MAE：`0.07689 → 0.04634`，改善 `39.7%`；
  - 5 px coarse MAE：`0.06809 → 0.03767`，改善 `44.7%`；
  - excess internal gradient：`0.001308 → 0.001163`，改善 `11.1%`。
- compact 候选保持 `311,993 × 64 B`、payload=`19,967,552 B`；xyz/covariance
  未经训练、六列 `J^0.4` 逐 bit 继承、总 opacity 归一因子=`0.958472`。
  SHA256=`2F39052DF2A4B8CDCE886F4CED85EB57794DB8904BEB52A39DCDA4B0EFCB8BA7`。
- 为隔离“内部点 footprint 太小”这一剩余因素，额外生成一个只处理非外轮廓点
  的 `1.04× sigma` 候选，并按投影面积以 `1/1.04²` 补偿其 opacity；外轮廓
  `12.5%` 点的 geometry/opacity、所有 J、点位、点数和 runtime 均不变。
  SHA256=`1526F5C530A8F7F7912C47963788F4A92F8A32D0E510E444EFD17D84282F0567`。
- UE 裁决：该候选产生大面积发白棉絮壳，上半部被洗平但下半部仍有碎团块和
  硬暗缝。根因是“非 boundary-mask 点”不等于任意视角下都不会参与轮廓；
  统一放大仍会把许多点推到当前视角外沿。该路线否决，运行时已恢复
  G25 的 `S3_ViewBoundaryMorph_Mask125_150_MassNormalized_FJ.ply`。
- 第一次撤回只移除了 `1.04× footprint`，仍保留 Smooth8 opacity，因此肉眼
  几乎没有变化；用户指出后已扩大撤回范围，完整撤掉本轮内部训练候选。

### G28 — S3 验收 Gate 关闭 / 冻结基线（2026-07-31）

- **状态：通过并冻结。** 本 Gate 的验收范围是中景/远景的静态体积代理：外轮廓大形、
  内部体积层次、方向光与天光重光照、可接受的柔化观感，以及不出现规则点阵作为主导瑕疵。
  近景 Hero 质量和严格 matched-quality 性能优于 SVT 不在本次承诺内。
- **冻结资产：**
  `Plugins/GaussianSplattingForUnrealEngine/Content/Data/S3BoundaryMorphMask125_20260731/S3_ViewBoundaryMorph_Mask125_150_MassNormalized_FJ.ply`
 ；SHA256=`5F0F3F2D4D72523026382966073B04CAE464780DF1DF21EF1E9C9483AF4421B`；
  `311,993` 点，`64 B/point`，PLY payload=`19,967,552 B`（约 `19.043 MiB`）。
- **构建链：** VDB teacher → 标准 3DGS 15K 几何拟合 → 12.5% view-boundary / 150-step
  轮廓候选 → 保持 xyz/covariance/点序不变地转移六列 `J` → `J^0.4` 传输压缩 →
  64 B compact PLY → UE Preprocess → count/prefix/scatter → GPU sort → HW Quad →
  shared-opacity composite → DGSM/phase 体积重光照。
- **锁定运行时：** opacity multiplier=`0.4`、opacity power=`1.0`、relight intensity
  scale=`0.3`、ambient=`0.01`、DGSM density=`0.45`，phase 参数保持原配置；不增点、
  不增 pass/RT、不改 Actor transform。Composite 仅保留按投影 AABB 自适应的外圈滤波
  （约 `0.75–2.0 px`），没有全图 RGB blur。
- **已否决并回滚：** AlphaCutoff `1/64`、`1/128`；Smooth8/internal-alpha 训练；
  非边界点 `1.04× sigma`；扩大 composite blur。它们分别造成颗粒、发白棉絮壳、硬暗缝或
  对中景没有可辨识收益，不能进入冻结基线。
- **性能口径：** `19.043 MiB` 只代表 PLY/primitive asset，不是完整 GPU working set。
  历史同机位 ProfileGPU 记录为 7DRGS 总帧约 `9.19 ms`、SVT U8 约 `8.43 ms`；因此本
  Gate 不宣称已胜过 SVT。后续性能优化必须在同机位、同分辨率、同质量口径下重新测量。
- **后续规则：** G25/G28 资产和当前运行时作为回归基线只读保留；任何轮廓、传输、滤波或
  显存优化都新建候选版本并记录 A/B，未通过视觉回归不得覆盖冻结基线。

### G29 — 深度引导的直射光低/高频分离（2026-07-31）

- **状态：用户确认正向提升；已纳入当前运行时基线并保留独立备份。**
- 诊断先关闭 DGSM 与重光照：DGSM 只放大暗部幅度，原有高频形态仍存在；均匀 ambient
  下累计 opacity 相对连续。由此把根因限定在 shared-opacity resolve 后的直射光 latent，
  而不是 coverage、边缘、PLY transport 搬运或 DGSM 本身。
- 只在高 coverage 内部对归一化直射光 `JAcc / coverage` 做深度引导的 `3×3` binomial
  低通，再以残差强度恢复高频；opacity、matte、深度 payload、DGSM、phase 和 PLY 均不改。
  采样步长=`clamp(source AABB px × 0.00625, 1.5, 4.0)`，内部权重=
  `smoothstep(0.70, 0.95, coverage)`，深度权重=
  `exp2(-32 × |sample mean log depth - center mean log depth|)`。
- 已否决的首版使用更宽半径、无深度引导和 `0.25` 残差，造成大块圆形模糊斑；收窄半径并
  加深度引导后，`0.20 / 0.35 / 0.50` A/B 中选择 `0.35`。换光向和近景复核均保持宏观阴影，
  同时减少密集皱纹和细暗缝，没有重现圆形糊斑。
- 新增唯一调节项 `DirectLightDetailStrength`：`1` 为旧画面，降低会抑制密集内部的高频
  光照变化；用户当前 Actor=`0.3056`，类默认=`1.0`。当值 `>=0.999` 时 Shader 直接跳过全部
  9 次邻域采样，其他资产保持旧画面且没有新增采样成本。
- 冷构建 `AbyssEditor Win64 Development` 成功；DLL SHA256=
  `EAC4EB44786C263943780E10D30E7CAB19AC89AD757C678B30150D2B04507B8A`。编辑器重启后
  属性反射、近景画面和日志检查通过；同一 PIE 的简短 A/B 中，`0.35` 与 `1.0` 的 GPU
  中位数均约 `1.00 ms`，当前测量精度下无可辨识回退。
- 备份与构建元数据：
  `artifacts/runtime_j_detail_filter_g29_20260731/`。G28/G25 PLY 不被覆盖。

### G30 — 连续边缘与结构引导直射光滤波（2026-07-31）

- **状态：Shader 热编译候选已部署；参数控制权已修复，等待用户 live viewport visual Gate。**
  父基线为已确认正向的 G29；当前 Actor 已精确恢复并保存为
  `EdgeFadeThreshold=0.5077329874`、`DirectLightDetailStrength=0.6538670063`。
- 边缘不再对 absolute coverage 全段压缩。新路径以中心 coverage 相对四向邻域最大 coverage
  的比例识别真实 fringe；`EdgeFadeThreshold` 恢复为相对 coverage 阈值，`0` 完全关闭，
  opacity 在该阈值内渐隐。R/G/B 三个预乘 latent 与 coverage 使用同一缩放，不再额外压制
  直射光；因此参数只降低边缘透明度，不改变边缘的归一化光照响应。
- 内部仍复用原 `3×3` 九次采样和 mean-log-depth guide，不增 pass/RT/tap。新增中心—邻域
  coverage 相似度权重，并根据 depth/coverage guide mismatch 局部提高残差保留率：平坦区域
  继续去除无结构高频，几何断层与密度过渡趋向保留原细节。
- 参数回归与修复：首版把 `EdgeFadeThreshold` 误映射为很弱的混合强度，0/1 肉眼几乎无差；
  同时结构 mismatch 把非内部邻点也计作结构并可完全回到 identity，吞掉了
  `DirectLightDetailStrength`。当前边缘恢复阈值控制；结构 mismatch 仅来自 depth/coverage
  guide，且最多只向 identity 恢复 50%。随后否决“边缘再单独压直射光”的错误耦合，最终
  Edge Fade 只改 opacity。固定机位 0/1 A/B 已确认两个滑杆都有明确差异。
- `DirectLightDetailStrength>=0.999` 的 identity fast path 保持不变。Shader SHA256=
  `A5A8C92A5CB1C93A7D7988BC568D3B43655A25996ED40209D9288632B2CC2E2A`，
  `recompileshaders changed` 成功且日志无 shader/fatal error；关卡保存后 dirty content/map 均为空。
- 同一 PIE 简短测量中，候选与 identity 的 GPU 中位数约为 `27.92 / 28.25 ms`；波动大，
  只能判定本轮新增 ALU 未出现可辨识回退，不能替代最终 ProfileGPU。
- 元数据：`artifacts/runtime_structure_guided_filter_g30_20260731/candidate.json`。

### G31 — 原始 15K 几何 + 当前 J 回退诊断（2026-07-31）

- **状态：与 G32 组合后通过用户自由镜头 visual Gate，已冻结为新的边缘资产基线并保存关卡。**
  `EdgeFadeThreshold=0` 后空槽仍在，证明 Edge Fade
  不是根因。随后恢复原始 15K 的前十列 geometry/opacity，并逐 bit 继承当前资产六列 J 与
  `angular_sigma=0.5`；点数=`311,993`、布局=`64 B/point`、opacity 总量保持不变。
- 无结构滤波时的固定机位及近景 A/B 中，原始 15K 外缘更细丝化；用户复看后认为该形态可能
  更合适，要求与 G32 结构支撑式 coverage 桥接组合复验；组合后用户确认明显改善并判定边缘空洞已解决，
  因此前人工否决撤销。资产 SHA256=`AE7177BF3753E9905C34208A9D46A2647018F55A49FF13581A717BA1040EA0FB`。
- 冻结部署：`Plugins/GaussianSplattingForUnrealEngine/Content/Data/S3Original15KG32_20260731/`
 ；关卡当前 `EdgeFadeThreshold=1.0`、`DirectLightDetailStrength=0.0`。
- 存档：`artifacts/wdas_s3_original15k_geometry_current_transport_g31_20260731/`。

### G32 — 相对两侧结构支撑的 coverage 桥接（2026-07-31）

- **状态：通过用户自由镜头 visual Gate并冻结为 G32 回退基线。** 不再对边缘做对称低通。
  复用现有四向探针与 `5×5 / 25 taps`，以水平/垂直相对两侧 coverage 几何均值的最大值作为
  结构支撑，只提高被两侧结构夹持的低 coverage 像素；任一侧是真背景零值时支撑严格为零，
  因而不向纯背景方向扩轮廓。
- 近景按投影 AABB 把既有 kernel step 从 `0.75–2 px` 扩为 `0.75–4 px`；远景仍为 `0.75 px`。
  没有新增 texture tap、pass、RT、参数或 PLY 改动。首版最小值支撑和低通目标过弱，A/B
  几乎无差，已否决；最终几何均值桥接在固定机位明确缩小蓝底贯穿空槽，同时保留外侧薄尾。
- Shader SHA256=`0ECFDAC47B39612751494CD598D9CAD8E7639AC6E9D90BF8DF160385A6339DB1`；
  `recompileshaders changed` 成功且日志无 shader/fatal error。当前 Actor 保持用户值
  `EdgeFadeThreshold=1.0`、`DirectLightDetailStrength=0.0`，用户确认蓝底贯穿空槽/边缘空洞已解决；
  稳定 PLY 路径与关卡均已保存，关卡与内容无 dirty package。
- 元数据：`artifacts/runtime_opposed_support_hole_fill_g32_20260731/candidate.json`。

### G33 — coverage 结构切线引导的轮廓模糊（2026-07-31）

- **状态：通过用户自由镜头 visual Gate；用户满意参数已完整快照并保存关卡。** 父基线是用户确认通过的
  原始 15K + G32，已先迁入插件稳定目录并保存关卡，因此 G33 可独立回退。
- 复用 G32 已有四向 coverage 探针求屏幕空间梯度，将梯度方向作为轮廓法线；既有 `5×5 / 25 taps`
  的权重沿轮廓切线保持宽度、跨法线以 `exp2(-2 × distance²)` 衰减。方向置信度不足时自动退回
  原 binomial 核，不新增纹理采样、pass、RT 或 PLY 改动。
- 新平滑只在 `0.01–0.80` 的低/中 coverage 轮廓带逐渐启用，强度固定为 `0.35`；密集内部不进入该
  分支，G32 的 `HoleWeight` 与双侧支撑 coverage target 完整保留，避免重新打开已解决的空槽。
- `1200×675` 精确同机位 G32/G33 A/B：全图 RGB MAE=`1.0304 / 255`，绝对通道差 P95=`7 / 255`，
  最大通道差大于 `8 / 255` 的像素占 `0.7019%`；初检变化集中于轮廓结构带，未见大形洗平或空槽回归。
- Shader SHA256=`DC57360F0B43A45C23DBCB190A5E344AC6D5A0B796D83BB8CA83CBCD55E7DA2A`；
  `recompileshaders changed` 成功。未增加新参数；用户已确认方向，后续只需补 GPU profile，因为
  同一 25-tap 分支的激活像素会比 G32 的 hole-only 范围更多。
- 用户最终调参状态：`OpacityMultiplier=0.37666699`、`EdgeFadeThreshold=0`、
  `DirectLightDetailStrength=1`、DGSM density/min-transmittance/contrast=`0.744534 / 0.0152 / 4.0`；
  relight/ambient=`0.105333 / 0.001`，phase mode/g/blend/intensity=`0 / 0.65 / 0.1 / 0.4`。
  完整 Actor、灯光引用、相位、深度和 source 快照见 `user_satisfied_runtime_parameters.json`；关卡保存成功，
  dirty content/map package 均为空。
- 元数据与 A/B：`artifacts/runtime_structure_tangent_blur_g33_20260731/`。

### G34 — 内部 coverage/depth 结构引导直射光模糊（2026-07-31）

- **状态：用户自由镜头 visual Gate 否决，已回退 G33。** G33 边缘切线滤波与双侧 coverage
  桥接完全冻结；当前 Actor=`EdgeFadeThreshold=0`、`DirectLightDetailStrength=0`。
- 根因不是 bypass：用户把 detail 调到 `0` 后旧滤波已全开，但旧 `StructurePreservation` 仍会最多恢复
  `50%` 原高频，且既有 `1.5–4 px` 半径低于当前内部斑驳尺度，因此效果仍不足。
- G34 复用原 `3×3 / 9 taps`，先把同批 sample 保存在局部数组，并以 coverage 与 mean-log-depth 梯度
  求屏幕空间结构法线；沿结构切线保留 binomial 宽度，跨法线按 `exp2(-3 × distance²)` 衰减，再叠加
  原 depth/coverage bilateral guide。只修改直射光 latent `gs.r`，不改 coverage、吸收、深度或边缘。
- G34A 保留原 `1.5–4 px` 尺度，同机全图 RGB MAE 仅 `0.19/255`，视觉过弱，已作为失败分支存档；
  G34B 将同一 9 taps 的步长改为 `clamp(AABB px × 0.0125, 2.5, 7.0)`，不新增采样、pass、RT 或参数。
- G34B Shader SHA256=`7C2922C309AAF009405BAB9B15B8BB74DAAAF9483FE745ADF3FFE540D81AC56B`，
  热编译成功且近期日志无 shader/fatal error；`1200×675` 固定机位相对 G33/detail0 的 RGB MAE=
  `0.2607/255`、P99=`3/255`，变化集中于内部直射光层次。关卡/内容无 dirty package，未改 PLY。
- 用户自由镜头暴露明显失败：右侧大团内部出现连续纵向梳状拖影和块状涂抹。密集内部 coverage
  接近饱和，稀疏 `3×3` 的 depth/coverage 梯度无法稳定决定结构方向；扩大到 `2.5–7 px` 后只把
  九点采样格显影成屏幕空间笔刷。因此“稀疏大步长 + 单方向各向异性”路线终止，不再继续加半径。
  live Shader 已恢复 G33 SHA256=`DC57360F0B43A45C23DBCB190A5E344AC6D5A0B796D83BB8CA83CBCD55E7DA2A`。
- 存档与 A/B：`artifacts/runtime_interior_structure_blur_g34_20260731/`。

### G35 — 内部 coverage/depth joint bilateral（2026-07-31）

- **状态：通过用户自由镜头 visual Gate并冻结为正式视觉基线。** G34 的单方向各向异性路线
  终止后恢复 G33，再只替换内部直射光滤波；边缘 G33 与 coverage 桥接保持逐字不变。
- 内部使用连续 `5×5 / 25 taps` binomial 核；每个 sample 以 coverage 相似度
  `exp2(-8×Δcoverage)` 和 mean-log-depth 相似度 `exp2(-24×Δdepth)` 加权。因此只在同一体积层内
  平均 `gs.r`，跨密度/深度断层自然拒绝，不再从饱和 coverage 猜测一个不稳定的屏幕方向。
- 采样步长=`clamp(AABB px × 0.003125, 1.25, 2.5)`，最远半径=`2.5–5 px`；连续 5×5 覆盖避免
  G34 的九点稀疏格显影。`DirectLightDetailStrength` 仍为残差控制，`1` identity、`0` 完整滤波；
  opacity、吸收、深度、DGSM、phase、PLY、pass 和 RT 均未改。
- 固定视角初检中，G34 纵向笔刷条带已消失；内部高频降低，同时大团块、暗通道和当前边缘仍可读。
  Shader SHA256=`0C01F118173132A6BA0D39F91BD69BA291C702F95CC9DE3B8BBBB6781308C945`，
  热编译成功且近期日志无 shader/fatal error。内部 taps 从 9 增到 25，待视觉通过后再做 GPU profile。
- 用户确认“效果冻结在这一层”。关卡已保存，完整 Actor、灯光、DGSM、appearance、phase、depth、
  PLY 和 Shader hash 快照见 `frozen_visual_baseline.json`；dirty content/map package 均为空。
- 存档：`artifacts/runtime_interior_joint_bilateral_g35_20260731/`。

### G36 — G35 性能基线与 VDB→GS SOP（2026-07-31）

- **状态：G35 保持冻结；完成第一轮 pass 级性能归因和生产 SOP，不修改 Shader、PLY、Actor 或关卡。**
- PIE Simulate、`1990×1198`、固定 TechLab 视角、`311,993` 点的有效 `ProfileGPU`：整帧
  `9.85 ms`，GaussianSplatting total=`1.354 ms`；其中 HW Raster=`0.824 ms`、全量
  `Sort(311993)=0.236 ms`、Slice=`0.087 ms`、Preprocess=`0.081 ms`、G35 Composite=
  `0.016 ms`。因此 25-tap G35 不是性能瓶颈，不再用退回 9 taps 换取不可测收益。
- 源码审计确认 Preprocess 已 GPU compact visible key/value，DrawIndirect 也使用
  `VisibleCount`；但引擎 `SortGPUBuffers` 仍接收 CPU 标量 `PointCount`，所以排序完整
  `311,993` 项。禁止每帧 GPU→CPU readback visible count；只有 sort 成为目标平台主瓶颈时
  才考虑 GPU-count custom sort。
- 优化顺序冻结为：现有 `SubPixelRadius/AlphaCutoff` 会话内 A/B → 按当前 alpha cutoff
  精确收缩低 opacity quad → 证据驱动的远景点预算/LOD → 最后才是 visible-only custom sort。
  首选代码候选只裁掉 PS 原本就会 discard 的 support，不触碰 G35 composite。
- 新增 `SOP-VDB-TO-GS-G35.md`：以最终真实资产链为准，明确标准 3DGS 15K 原始几何、
  VDB direct `J^0.4`、64 B compact PLY、UE 晋升、视觉/性能 Gate、回滚和已终止分支。
  同时记录当前唯一缺口：已验收 `.vdb→.npy` 的具体命令/环境未归档，所以生产自动化
  暂以 validated float32 NPY 为正式输入边界，禁止声称任意 VDB 一键复现。

### G37 — alpha-support quad crop 与同帧 SVT/GS 对比（2026-07-31）

- **状态：冷编译、公式检查、性能收益门和用户视觉复验均通过；已晋升为当前 runtime 冻结基线。**
  G35 composite、PLY、Actor 参数和 `AlphaCutoff=1/255` 全部冻结。
- 对齐方法改为同一 editor viewport 帧内同时显示真实 SVT 与 GS，并分别读取 GPU tree 事件；固定
  `1990×1198` capture、FOV55 和 TechLab 相机。优化前 5 次同帧样本中位数：SVT feature=`3.237 ms`、
  GS total=`1.343 ms`、HW Raster=`0.819 ms`。优化后冷启动 10 次：SVT=`3.241 ms`、
  GS total=`1.093 ms`、HW Raster=`0.5665 ms`。
- 唯一代码改动是按 PS 已有 cutoff 收缩 quad 的 alpha support，并加 `0.05σ` 数值余量；保留片元的
  conic/opacity/J/DGSM/coverage/composite 均不变。GS total=`-0.250 ms / -18.6%`，HW Raster=
  `-0.2525 ms / -30.8%`，超过 `0.07 ms / 5%` 收益门槛；Preprocess/Sort 无可测变化。严格同帧
  baseline 只有 5 次，最终 SOP 的 standalone/shipping 10+10 样本仍未完成。
- P1 结果：`SubPixelRadius=0.25` 无收益；`AlphaCutoff=1/128` 虽有约 4% 快测收益，但命中 G28 已记录的
  颗粒/棉絮壳/硬暗缝视觉失败，恢复 `1/255`，不晋升。
- 完整冷构建成功，冷启动无 shader parameter/fatal error，dirty content/map package 均为空；G35
  composite SHA 仍为 `0C01F118173132A6BA0D39F91BD69BA291C702F95CC9DE3B8BBBB6781308C945`。
- 报告与原始样本：`PERFORMANCE-VDB-VS-G35-G37-20260731.md`、
  `artifacts/perf_g35_vs_svt_g37_20260731/`。

### G38 — G37 / UE SVT 独立冷进程显存闭环（2026-07-31）

- **状态：完成并归档。** 从当前 TechLab 临时复制 Empty、仅 SVT、仅 GS 三张地图，统一
  D3D12、Development `-game`、1920×1080、固定相机；每档 3 次独立冷进程，每次预热
  10 秒并采 20 个稳态 Windows `GPU Process Memory / Local Usage` 样本。临时地图测后
  已通过 UE 资产系统删除，原 TechLab 已恢复，SVT/GS 均可见且 dirty package 为空。
- 整个 UE 进程专用显存中位数：Empty=`2337.764 MiB`、SVT=`2664.178 MiB`、
  GS=`2343.980 MiB`。所以完整场景使用 GS 比 SVT 少 `320.198 MiB / 12.019%`；
  `2343.980 MiB` 是整进程，不是单个 GS。
- 第 300 帧 `rhi.DumpResourceMemory ... Transient=all` 三轮中位数：Empty=
  `2328.946 MiB`、SVT=`2634.512 MiB`、GS=`2395.422 MiB`。相对 Empty 的单体积
  净新增 working set 为 SVT=`305.566 MiB`、GS=`66.476 MiB`；GS 少
  `239.090 MiB / 78.245%`，约为 SVT 的 `1/4.597`。
- GS 净新增分解为 non-transient=`19.063 MiB`、transient=`47.414 MiB`；直接命名的
  `GS7DRGS.*` 17 个资源共 `74.223 MiB`（常驻 `19.063` + 命名瞬态 `55.161`）。
  净增与命名总和的差异来自 RDG alias 和公共 transient pool 复用，两个口径不得混写。
- 3/3 GS 进程均加载 `311,993` 点；3/3 SVT 均报告原生 GPU Memory=`305.566 MiB`；
  9/9 地图加载成功，0 GPU/D3D/shader fatal。
- 报告与证据：`VRAM-COLD-G37-VS-SVT-20260731.md`、
  `evidence/memory-20260731-g37-cold-3x/`。

### G39 — Bifrost Wide Cumulus S11 离线生产（2026-08-05）

- **状态：独立整云离线 Gate 通过；UE 视觉 Gate 待执行。** 选用 CC0 的 CGHEVEN
  `Hero Cumulus Cloud VDB 28`，保留原始横向双峰／低裙结构，不对旧 Gaussian 做非等比拉伸。
  density-only 网格补 8 voxel 零边界后为 `431×145×270 float32`；64 个 `512²`、
  256-step 教师视角全部非空。
- 首轮标准 3DGS 暴露训练根因：普通 RGB 路径把预测图再次乘 teacher alpha，透明区误差被清零，
  因而允许巨型 splat 逃到轮廓外。只在共享训练入口移除该重复 mask，并以“白色 spill 在黑色透明区
  必须产生非零 L1”作最小回归检查；修复后 7K/15K/30K 留出 PSNR 为
  `45.269 / 45.799 / 45.369 dB`，选择 15K 的 `79,273` 点，8 个留出视角无白色拖影。
- 复用既有 S3 生产链，把 15K geometry/shared opacity 转为 16-float compact layout，再从同源
  density 直接烘焙六轴 `J^0.4`。最终资产为
  `runs/bifrost_cgheven28_20260805/30_compact/direct_transport/S3_F_Gamma04J.ply`，
  SHA256=`D86CBE6302907B0D87586201C9E08E36C692724FCFD8ABC1285F1D422F9CFFBB`，
  `79,273 × 64 B`，payload=`5,073,472 B`。
- 结构 Gate：全部 finite，opacity=`0.0047518…0.8040645`，covariance 最小特征值
  `1.07078e-9 > 0`，J=`0.0013575…1`，中心 inside fraction=`1`；direct bake 前后前十列
  geometry/opacity 逐 bit 相同。没有改 G35/G37 Shader、插件资产、Actor 或关卡；S10 仍为当前
  UE 冻结基线。完整参数、代码指纹和哈希见
  `runs/bifrost_cgheven28_20260805/run_manifest.json`。
