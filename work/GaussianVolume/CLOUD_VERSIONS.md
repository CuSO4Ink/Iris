# 云版本账本

> 更新日期：2026-07-27
> 当前结论：Hero Congestus 主线已有 **14 个整云版本**，最新版本为 **H13**。旧 Smoke2 线另记录 **9 个 Gate 版本**。SVT 只作画质／资源参照，不计入云版本。

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
| H12 | 2026-07-27 |                 H4 Pointwise Light T D2；1,112,674 points | 固定 H4 的全部空间／静态字段，直接从同源 density grid 为每点监督 24 个灯向的 light-space transmittance，并拟合 degree-2 `J` SH | 4 个留出灯向 T MAE/RMSE=`0.08067/0.13218`，静态参数误差=`0`；优于 D3 direct-T 与 D2 optical-depth 候选，UE 已部署 | 待用户视觉 Gate | |
| H13 | 2026-07-27 |                   H6 Directional Tau Basis；50,000 kernels | 在 H6 initializer 上离线烘焙 local ±X/±Y/±Z 六方向光程，复用 48 B/kernel 现有 transport 空位 | 50,000 kernels 全部位于源 grid，六轴 τ median=`3.455/3.404/4.583/4.798/3.029/3.356`；UE 已部署 | 待用户视觉 Gate | |

H5–H7 是 initializer；H8 是第一版短程 τ/T recovery；H9 补齐任意方向内部透射／自阴影；H10 是唯一一次 100K 纯容量诊断，不属于最终 `≤50K` 性能目标；H11 证明 H4 原图像协议续训无效；H12 改为逐点 light-space T 监督；H13 把同一方向光程能力接回 H6 的 50K 布局。

## 当前 UE 对比状态

- `H12 | H4 PointwiseLight24 D2 1.112M`
- `H13 | H6 Adaptive 50K Directional Tau`
- `SVT | CGHEVEN Hero Congestus 50 U8`
- 三者当前全部可见；H13 使用用户确认的 Density Multiplier=`0.416`、Density Gamma=`1.515627`、Directional/Sky Light Scale=`0.5/0.1`，并以 Directional Shadow Density Scale=`0.3` 预览。
- 当前重开的关卡中没有 H0 Actor；本次没有隐藏或删除它。H12／H13 部署后关卡保持未保存。
- Smoke2、H7、H8、H9、H10 Actor 已从关卡删除，源 JSON／PLY／SVT 资产未删除。

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

## 下一版本触发条件

H13 之后只在产生新的独立整云资产并完成离线 Gate 或 UE 预览后建立。只调 Density、Gamma、阴影强度、灯光、位置或相机不虚增版本号。
