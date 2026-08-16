# 云版本账本

> 更新日期：2026-08-07
> 当前结论：Hero Congestus 的 H0～H13 与 Smoke2 的 S0～S8 均为历史路线；当前 UE 冻结资产仍为 **S10（G35 视觉 + G37 runtime）**。S11 通过离线与 UE 加载结构 Gate，但未通过 Bifrost 视觉 Gate，已退出焦点候选；live Actor 临时换回 S10 用于表现录屏且尚未保存 Level。SVT 只作画质／资源参照，不计入云版本。

## 计数口径

- 只有生成了独立整云资产，并完成离线 Gate 或 UE 预览的版本才编号。
- checkpoint、局部 QIRF／contraction smoke、仅改渲染参数的画面不另算版本。
- 同一资产换灯光、密度或视角不升版本；表示、训练结果或核分配发生变化才升版本。

## Hero Congestus 主线

| ID  | 日期         |                                                           表示／规模 | 核心变化                                                                                 | 视觉或 Gate 结论                                                                                        | 状态              |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --- | ---------- | --------------------------------------------------------------: | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| H0  | 2026-07-26 | B2 Ultra 7DRGS；1,112,674 spatial / 6,676,044 directional points | 从同源 density VDB 解析抬升，6 个方向叶片                                                         | 空间细节、方向重光照通过；轻微全局色差冻结                                                                              | 质量 teacher      |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H1  | 2026-07-27 |                               Trained15K 7DRGS；1,112,674 points | 在旧初始化上训练到 15K                                                                        | 严重颗粒噪声、细节模糊；不是 UE 抗锯齿问题                                                                            | 否决              |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H2  | 2026-07-27 |                                  Teacher D1 1K；1,112,674 points | 六叶片聚合，固定几何，只训练 light-conditioned J                                                   | 数值健康，UE 视觉 Gate 通过                                                                                 | 被后续版本替代         |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H3  | 2026-07-27 |                                    Degree-2 1K；1,112,674 points | 在 H2 上把 J 从 degree 1 升到 degree 2                                                     | 1K held-out 优于 2K/3K 续训，部署供视觉检查                                                                    | 被后续版本替代         |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H4  | 2026-07-27 |                            Directional24 D2 2K；1,112,674 points | 扩为 24 个灯光方向、4 个留出方向                                                                  | held-out PSNR 22.715 dB，高于 H2 的 21.155 dB；质量可用但 320 B/点布局过重                                        | 1.112M 质量参考     |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H5  | 2026-07-27 |                                  Hard Macroblock；50,000 kernels | 4×4×4 独立 macroblock 内做 moment contraction                                            | 严重格子感、细节坍缩；局部正确不等于全局连续                                                                             | 否决              |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H6  | 2026-07-27 |                                  Global Adaptive；50,000 kernels | 全局 adaptive binary partition，质量守恒 moment 初始化                                         | 自然体积光出现，明显优于 H5；高频细节仍不足                                                                            | 被后续版本替代         | 原因已经定位：**H6 不是灯光绑定失效，而是当前 50K 数据没有训练/烘焙方向光传输参数。**<br><br>H6 现在走的是高数量快速通道：<br><br>- `Use Scene Lights`、太阳、天光引用都正常。<br>- 但 H6 初始化数据只有位置、尺度、旋转和密度，没有 `light_tau_axes`。<br>- 50K 数量超过动态精确自阴影的 4096 上限，运行时不会现场计算光线穿透。<br>- 因此方向光透射率被当作恒定 `1`：旋转太阳时云几乎不变，只会整体响应灯光强度、颜色和天光。<br><br>所以这是 **H6 当前数据阶段缺少光照表示**，不是刚才 H4 相机矩阵修改造成的。<br><br>正确下一步是给 H6 烘焙/训练六方向光学厚度 `light_tau_axes`（±X/±Y/±Z），再由着色器按任意灯光方向插值。这样能恢复内部透射和自阴影，又不必让 50K kernel 每帧做昂贵的动态积分。 |
| H7  | 2026-07-27 |                                  Adaptive Detail；50,000 kernels | 在 H6 上以 `mass^0.65` 把预算重分配到薄层／小尺度结构                                                  | 体积光保留；仍有过白、椭圆／斜向 footprint 可见、微细节不足                                                                | H8 initializer  |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H8  | 2026-07-27 |                                  Tau/T Recovered；50,000 kernels | 6 个训练视角、2 个 held-out 视角；联合恢复 extinction、位置、尺度和旋转，并约束 T 与 edge/Laplacian              | held-out τ MAE `2.97→1.65`、前景 T PSNR `13.30→15.17 dB`、edge L1 `0.2030→0.2023`                      | H9 density base |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H9  | 2026-07-27 |                            Directional Tau Basis；50,000 kernels | 离线烘焙 local ±X/±Y/±Z 六方向光程，运行时按灯向连续插值；Atmosphere Sun 只在地平线上半球发光；复用既有 48 B 布局的 12 B 空位 | 修复固定受光方向及地平线下太阳仍照亮云体；细节仍未通过视觉 Gate                                                                 | 触发 100K 诊断      |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H10 | 2026-07-27 |                        Adaptive Detail Capacity；100,000 kernels | 沿用 H7 的 global adaptive `mass^0.65` 分配规则重新生成 exact 100K，并烘焙同一六轴方向光程                  | 质量守恒误差 `1.52e-16`；300/400/600-step recovery 均因 held-out edge 回退未通过数值 Gate，因此 UE 只展示未训练 initializer | 容量诊断；当前已移出场景    |                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| H11 | 2026-07-27 |                      H4 Directional24 D2 4K；1,112,674 points | 从 H2 基线按 H4 原协议训练至 4K，只优化 light-conditioned J；2K/2.5K/3K/3.5K/4K 全部留档 | 4 个留出灯向 PSNR `22.715→23.181 dB`、L1 `0.03109→0.02864`，但 UE 中仍无可辨认内部自阴影；图像 PSNR 提升没有命中目标 | 视觉 Gate 失败；禁止原协议续训 | |
| H12 | 2026-07-27 |                 H4 Pointwise Light T D2；1,112,674 points | 固定 H4 的全部空间／静态字段，直接从同源 density grid 为每点监督 24 个灯向的 light-space transmittance，并拟合 degree-2 `J` SH | 4 个留出灯向 T MAE/RMSE=`0.08067/0.13218`，静态参数误差=`0`；现场 `Dual SH=false` 根因已修复为 `true` | 待修复后视觉复核 | |
| H13 | 2026-07-27 |                   H6 Directional Tau Basis；50,000 kernels | 在 H6 initializer 上离线烘焙 local ±X/±Y/±Z 六方向光程，复用 48 B/kernel 现有 transport 空位 | 六轴 tau median=`3.455/3.404/4.583/4.798/3.029/3.356`；`LightTransmittance` debug 已显示明确方向梯度 | transport 已验证；待强度签字 | |

H5–H7 是 initializer；H8 是第一版短程 τ/T recovery；H9 补齐任意方向内部透射／自阴影；H10 是唯一一次 100K 纯容量诊断，不属于最终 `≤50K` 性能目标；H11 证明 H4 原图像协议续训无效；H12 改为逐点 light-space T 监督；H13 把同一方向光程能力接回 H6 的 50K 布局。

## 当前 UE 对比状态

- `S3 | Standard Geometry + G2 Compact Relight / 312K`
- `SVT | WDAS Half 378MiB Source / 85.8MiB U8`
- 两者当前均在 `/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab` 可见，用于同机位画质与性能对照；GS 为 G35 视觉基线叠加 G37 alpha-support quad crop。
- H 系 Actor 不属于当前冻结场景；其资产与实验记录仍保留为历史证据。

## Smoke2 历史 Gate 版本

这些版本不占用 Hero 的 H 编号，只保留路线证据；未列出一次性 checkpoint 和局部 smoke。

| ID | 表示／规模 | 结论 |
|---|---:|---|
| S0 | GaussianVolume 4K | 早期低档基线，细节不足 |
| S1 | GaussianVolume 10K Adaptive | 早期中档基线，后被质量拟合线替代 |
| S2 | GaussianVolume 30K Adaptive | 运行时内核可行，约 8.5 ms；block/adaptive 聚合画质不足 |
| S3 | GFields Q0 1K | Scout／链路验证 |
| S4 | GFields Q1 4K | 质量下限：full/foreground T PSNR 36.11/24.22 dB |
| S5 | GFields Q2 9,944 | 高保真上限：48.60/36.93 dB，IoU 0.629 |
| S6 | GFields Q3 24,576 | T/τ 明显退化，仅轮廓略升；否决 |
| S7 | Q2 + 4,096 Gabor = 14,040 | step 1200 完成，用户画质否决；归档 |
| S8 | 7DRGS Smoke2 B4；64,815 spatial / 388,890 directional points | 真实 VDB→7DRGS 与方向光链路成立，后换 Hero 源 |

## 版本触发条件

只在产生新的独立整云资产并完成离线 Gate 或 UE 预览后建立版本。只调 Density、Gamma、阴影强度、灯光、位置或相机不虚增版本号；离线 Gate 通过但未完成 UE 视觉 Gate 的版本只能标为候选，不能替换当前 UE 冻结资产。

## S9 — G28 Boundary Morph（历史冻结，2026-07-31）

- 资产：`S3_ViewBoundaryMorph_Mask125_150_MassNormalized_FJ.ply`
- UE 路径：`GaussianSplattingForUnrealEngine/Content/Data/S3BoundaryMorphMask125_20260731/`
- SHA256：`5F0F3F2D4D72523026382966073B04CAE464780DF1DF21EF1E9C9483AF4421B`
- 规模：`311,993` 点，`64 B/point`，`19,967,552 B`（约 `19.043 MiB`）
- 表示：标准 3DGS 几何 + shared opacity + 六列 `J^0.4` compact relight；UE 使用 GPU
  sort/HW Quad/shared-opacity composite/DGSM/phase。
- Gate：中景/远景视觉通过；方向光与天空颜色可重光照；边缘采用有限的外圈自适应滤波。
- 当时限制：近景 Hero 仍非目标；19.043 MiB 不是完整 working set；S9 阶段还没有同机位
  GPU A/B，故该历史版本不能引用后续 S10/G37 的性能结论。
- 版本规则：S9 只读保留；后续发现边缘连接仍不自然，已由 S10 的原始 15K 几何回退取代。

## S10 — G35 视觉 + G37 Runtime（当前冻结，2026-07-31）

- 资产：`S3_Original15KGeometry_CurrentGamma04J_AngularSigma05.ply`
- UE 路径：`GaussianSplattingForUnrealEngine/Content/Data/S3Original15KG32_20260731/`
- SHA256：`AE7177BF3753E9905C34208A9D46A2647018F55A49FF13581A717BA1040EA0FB`
- 规模：`311,993` 点，`64 B/point`，payload `19,967,552 B`（约 `19.043 MiB`），文件 `19,968,040 B`。
- 视觉链：G31 原始 15K 几何回退 → G32 对向支撑补洞 → G33 轮廓切向模糊 → G35 内部 5×5 coverage/depth 联合双边；G34 梳齿退化已回滚。
- Runtime：G37 仅裁剪 alpha-support quad，不改变 conic、opacity、J、DGSM、coverage 或 G35 composite；用户已完成自由视角验收并冻结。
- 性能：同帧 Editor 中 GS `1.343 → 1.093 ms`（`-18.6%`），HW raster `0.819 → 0.5665 ms`（`-30.8%`）；SVT feature `3.241 ms`，当前 GS 为 `2.97×` 更快。
- 冷启动显存：完整 UE 进程 dedicated median 为 SVT `2664.178 MiB`、GS `2343.980 MiB`，GS 节省 `320.198 MiB / 12.019%`；扣除 Empty 后的完整 RHI 资源增量为 SVT `305.566 MiB`、GS `66.476 MiB`，GS 节省 `239.090 MiB / 78.245%`。`2343.980 MiB` 是整个 UE 进程，不是单个 GS 资源。
- 完整报告：`PERFORMANCE-VDB-VS-G35-G37-20260731.md`、`VRAM-COLD-G37-VS-SVT-20260731.md`、`SOP-VDB-TO-GS-G35.md`。
- 限制：结果针对 RTX 5060、Development `-game` 与当前固定场景；Shipping、近景 Hero、多资产扩展仍需另测。

## S11 — CGHEVEN 28 Wide Cumulus（离线候选，2026-08-05）

- 源：CGHEVEN `Hero Cumulus Cloud VDB 28`，CC0；原始密度体重写为 density-only 后补 8 voxel 零边界，训练网格为 `431×145×270 float32`。
- 资产：`runs/bifrost_cgheven28_20260805/30_compact/direct_transport/S3_F_Gamma04J.ply`
- SHA256：`D86CBE6302907B0D87586201C9E08E36C692724FCFD8ABC1285F1D422F9CFFBB`
- 规模：`79,273` 点，`64 B/point`，payload `5,073,472 B`（约 `4.838 MiB`），文件 `5,074,389 B`。
- 训练：64 个 `512²`、256-step 体渲染教师视角；标准 3DGS 的 7K/15K/30K 留出 PSNR 分别为 `45.269 / 45.799 / 45.369 dB`，选择未过拟合的 15K。
- 表示：标准 3DGS 自适应 geometry/shared opacity + VDB direct `J^0.4` 六轴静态 transport，`angular_sigma=0.5`；适配现有 G35/G37 64 B runtime，不新增表示或 Shader 分支。
- 离线 Gate：16 个 float 字段、全部 finite、opacity 在 `(0,1)`、covariance 正定、J 在 `[0,1]`、中心 `100%` 位于参考密度体内；六轴烘焙前后 geometry/opacity 逐 bit 相同。8 个留出视角渲染未见画面外巨型 splat／白色拖影。
- UE 候选：PLY 已复制到 `Plugins/GaussianSplattingForUnrealEngine/Content/Data/BifrostS11CGHEVEN28_20260805/`，并曾由 `L_Bifrost` 的单一 `GaussianSplatting7DActor` 真实载入 `79,273` 点完成自由摆位检查。
- 状态：**独立整云离线 Gate 与 UE 加载结构 Gate 通过，Bifrost 视觉 Gate 失败。** 作者判定其暗色块状实体感与原生远景体积云不在同一品质层级；当前 live Actor 已保留作者 Transform 并临时换回 S10 `311,993` 点用于表现录屏，Level 未保存。S11 文件与训练证据保留，不再作为 Bifrost 焦点候选继续调参。
