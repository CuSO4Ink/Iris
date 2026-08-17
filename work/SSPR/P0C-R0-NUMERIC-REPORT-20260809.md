# P0c Stage C — R0 Numeric Contract Report

> 结论：**PASS**（2026-08-09）。
>
> 作用域：只冻结 Stage C 的 Coverage、epsilon、front-cluster 与 half 误差合同；不修改已通过的 Stage A/B、K64、erf、Raw0/Raw1、40k 输入或源粒子运动。
>
> 可复现脚本：`scratch/p0_mainline_20260806/p0c_r0_numeric_reference.py`。

## 1. 定标依据

- 历史 P0c Gate B：2048² RGBA16F，Density 覆盖 `716,764 / 4,194,304`，其中 `Density>1e-3` 为 `346,648`；八通道 finite、无 half saturation。
- 本次正确 Simulate/固定 Gate C 机位 fresh readback：一帧 Density p50/p75/p95=`0.000927/0.003380/0.020966`，`D>ε_D` 为 `476,696` 像素；另一稳定帧 p50/p75=`0.001076/0.003689`。`D_ref=0.003` 同时接近解析单粒子峰值与 live p75，不依赖单帧最大值。
- 实际深度统计：MeanDepth p50/p95/max=`0.0664/0.0820/0.1051`，DepthSigma p95/max=`0.00977/0.03227`。
- 冻结输入：`DensityPerParticle=0.03`、`WidthPx=1.25`、`MinLengthPx=2`、DepthNorm=`0..1` 对应 `0..10000 uu`。
- 解析核单粒子中心尺度：点核峰值 `0.003055775`，2 px 最短线核峰值 `0.002758534`。因此 `D_ref=0.003` 对应一个冻结输入下的紧凑单粒子中心贡献，而不是凭视觉猜值。

## 2. 冻结常量

| 常量 | 数值 | 精确语义 |
| --- | ---: | --- |
| `D_ref` | `0.003` | `C(D)=D/(D+D_ref)` 的半可信密度尺度 |
| `ε_D` | `2^-13 = 0.0001220703125` | Raw texel/FrontDepth 有效性下限；`D<=ε_D` 严格为空 |
| `ε_Front` | `2^-14 = 0.00006103515625` | Stage B `FrontDepth=0` sentinel 的有效性阈值；与密度 epsilon 分离 |
| `ε_S` | `2^-18 = 0.000003814697265625` | confidence-weighted denominator 下限 |
| `ε_Z` | `2^-20 = 0.00000095367431640625` | nominal in-bounds kernel denominator 下限 |
| `ε_Tensor` | `2^-12 = 0.000244140625` | raw tensor magnitude 有效性下限 |
| `ε_Variance` | `0.002` | 只用于负方差容错：`[-ε_Variance,0)` clamp 为 0；更小则 Depth invalid；不得从正方差中扣除 |
| `PilotSupportAbort` | `0.01` | 9-tap Pilot 的 `Q` 低于此值时严格零输出 |
| `PilotFrontWindow` | `1/128 = 0.0078125` | Pilot 前部 cluster 窗口 |
| `MainFrontWindow` | `1/64 = 0.015625` | Main accepted front-cluster 窗口 |
| `SigmaWarn` | `0.01` | DepthConfidence 开始衰减 |
| `SigmaReject` | `0.03` | DepthConfidence 归零；不扩大连接半径 |

Coverage 关键点：`D=0.0003/0.001/0.003/0.01/0.03` 时，`C≈0.091/0.25/0.5/0.769/0.909`。这保留弱支撑的连续过渡，但不会把一个接近 epsilon 的 texel 提升成完整主体。

## 3. 自动 Gate 结果

- 全零严格为零。
- 常量场内部相对误差 `<1e-12`，通过 `<=1%`。
- 单脉冲峰值比 `0.102686`，没有超输入亮峰。
- 单脉冲积分相对误差 `0`，通过 `±10%`。
- 粒子数 ×2、单粒子质量 ×0.5 的相对变化 `0`，通过 `<=5%`。
- Body 扩核峰值比 `0.007448`，没有新亮峰。
- signed B/M/H 经 RGBA16F round-trip 后重建 Tight 的峰值相对误差 `0.014806%`，通过 `<=1%`。
- Front cluster 90 个远离阈值的稳定分类样例错误 `0`：Pilot 在 `0.0075` 内合并、从 `0.01` 起分开；Main 在 `0.015` 内合并、从 `0.02` 起分开。
- Fresh live 在 `D>ε_D` 的 `476,696` 像素中有 `12,347` 个 FrontDepth sentinel（2.59%）；有效 FrontDepth 的 `abs(Mean-Front)` p95=`0.011923`，落在 `MainFrontWindow=0.015625` 内。Stage C 因此必须显式处理 sentinel，并为无 Front 的小比例样本使用降置信 MeanDepth fallback，不能把零解释为近景。

## 4. RGBA16F 深度精度合同

- Density 相对误差 p99=`0.0421%`；MeanDepth 绝对误差 p99=`0.0005245`，冻结容差 `0.002`。
- 当前工作深度 `z<=0.10`：Sigma 绝对误差 p95 最坏 `0.00477`，冻结容差 `0.005`；`sigma>=0.002` 时相对误差 p95 容差为 `100%`。
- 全 `[0,1]` 深度压力测试：远深度 `z=0.9` 的 Sigma 绝对误差 p95=`0.02481`，冻结远深度容差 `0.025`。这是 `M2/D-Mean²` 在 RGBA16F 相近数相减下的已知精度上限，不伪装成高精度。
- 负方差最小值 `-0.000860`，落在 `ε_Variance=0.002` clamp 合同内。

因此首版必须保持：Sigma 只降低 DepthConfidence，绝不能扩大 front window 或连接半径；当前实际效果工作在 `z≈0.06..0.11`，使用严格的 operating-depth 容差。若未来把效果推到远归一化深度且要求精确厚度，必须变更 Raw 深度编码/格式，不能靠调大 Sigma 窗口掩盖。

## 5. R0 结论与下一 Gate

R0 已闭合，允许进入 R1。R1 的顺序仍是：精确二进制备份 → 新建 FieldMain/FieldAux 与空 Stage C marker → 独立 apply/compile → 真实帧 → RT/所有权/冷启动回读。

最初用普通 `editor_request_begin_play` 得到 `SSPR_ScreenUV=(-1,-1)` 与 Raw 全零；改用 UEAgent `StartPIE(bSimulate=true)` 并恢复历史 Gate C 精确机位后，Raw current-frame 闭环立即恢复且得到上述 fresh 聚合统计。该结果已判定为启动模式假阴性，不是 Projection/Stage A/B 回归。SIE 已停止，执行前视口已恢复。
