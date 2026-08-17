# P0c R1.6 Production Resolve and Synthetic Gate — 2026-08-09

> Gate result: **PASS**. Stage C 的生产连续场实现已通过静态闭环、live 数值闭环、合成输入形状测试和隔离 Stage GPU 复测；下一 Gate 是 R2 Body-only 调试画面。本结论不等于最终视觉、完整链路性能或用户 Gate D 已通过。

## 实施对象与冻结边界

- 候选：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`。
- Stage C：`SSPR Resolve Continuous Field`；模块：`SSPR_ResolveContinuousField`。
- Stage A/B、K64、erf、P1、Fountain/CurlNoise/Drag/Velocity 均未修改；正式 M3、失败 V2.1 与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 均未覆盖。
- 所有 live 调用均走 UEAgent，PowerShell private-memory guard=`1024 MiB`；2048² RT 只在 UE 内聚合为标量，不把像素数组送入 MCP/PowerShell。

## 最终生产核

- 单次 2048² Simulation Stage dispatch。
- Pilot：中心 + `±2 px` 四向/对角，共 9 taps。
- Main：24 taps；两个半权中心、8 个近环对称样本、8 个中环对称样本、6 个六向外环样本。
- 采样：2 Raw integer Point/Load；输出：2 Field UAV；Pilot 不通过时整个 Main gather/guide/depth/bands 分支跳过。
- 核权重全部预计算为编译期常量；禁止像素内动态 `exp`。
- 当前 Custom HLSL SHA-256：`c87f1ca81c432ea21ac3090efc55bd26323432da2c49c759a77ee2dfa8682b8a`；字符数 `100,541`。
- 输出仍为 `FieldMain=B/M/H/Q_BM`、`FieldAux=MeanDepth/SigmaDepth/FrontDepth/DepthConfidence_BM`；Front 最终强制 `FrontDepth<=MeanDepth`，原始次序误差同时衰减 DepthConfidence，不用 clamp 掩盖置信度问题。

## 静态与 live 数值闭环

- 三条 Simulation Stage 脚本均 `UpToDate`，Niagara `0 error / 0 warning`；回读确认对称 stencil、两个半权中心、六向外环、预计算核、真实 Pilot 分支和 Front-order 修复均存在，旧 `±1.5` Pilot 与动态 `exp` 均不存在。
- live 用户变量映射经组件 API 独立确认：RawAux=`DI0/Texture0`、RawMain=`DI1/Texture3`、FieldMain=`DI2/Texture2`、FieldAux=`DI3/Texture1`。Managed Texture 后缀不等于 DI 后缀；后续审计禁止按数字后缀猜角色。
- 四张绑定 RT 均为独立 2048² RGBA16F；运行聚合证明所有输出有限、非空、无 half 饱和，Body/Sigma 非负，Q/DepthConfidence 范围成立，有符号 M/H 可重建且负误差不越 `-0.002`，`FrontDepth<=MeanDepth`，SigmaReject 生效。
- 代表性 512² 中心 probe：Body 正值 `164,833` 像素、Q 正值 `164,816`、DepthConfidence 正值 `164,648`；signed 重建最大 `0.15837`、最小 `-5.72e-6`。

## Synthetic Gate

部署前的非对称 Point stencil 在单脉冲测试只通过 `14/19`：质心漂移 `0.59 px`、镜像误差 `41.8%`。这不是调参问题，而是 `floor` + `±1.5` 量化成 `-1/+2`，且 Main 外环缺少反向配对。

最终对称 stencil 通过全部强制项：

| Case | 结果 |
|---|---:|
| zero | strict zero |
| constant field | max error `4.07e-5` |
| impulse | centroid error `0 px`; mirror error `0`; peak/input `0.230` |
| rate invariant | error `0` |
| signed-band reconstruction | max relative error `0.000299` |
| two-blob hole | center/peak `0.4219`; peak/input `0.392` |
| typical blob integral | relative error `0.005219` (`0.52%`) |
| crossing / transpose | error `0` |
| two depth layers | center confidence `0` vs single-layer `0.887` |
| Front/Mean order | max violation `0` |
| low coherence mirror | error `0` |
| boundary | peak/input `0.323`; opposite-edge leak `0` |
| subpixel camera shift | L1 `0.0630`; measured centroid `0.24148 px` for expected `0.25 px` |

孤立单脉冲积分损失 `57.7%` 保留为诊断但不作失败项：Rev B 的 `±10%` 积分合同约束典型连续场，弱孤立支撑必须保守衰减且不得增亮；典型 blob 已以 `0.52%` 通过。

## 性能演进与最终复测

- 初始生产算术版：`6.07 / 6.33 / 6.09 ms`。
- 核权重预计算后：干净样本 `4.54 / 5.62 ms`；`6.86 ms @ 102.26 ms frame` 为污染样本。
- 将 Main 的全部加载与算术放入真实 Pilot 分支后：干净早期样本 `1.87 / 1.90 ms`。
- 部署最终对称 stencil 后，三张干净帧为：`3.14 ms @ 35.31 ms frame`、`1.94 ms @ 36.51 ms`、`2.04 ms @ 36.12 ms`；中位数 `2.04 ms`。`5.42 ms @ 101.36 ms frame` 明确标记为 8 Hz/fixed-tick 追帧污染，不计入干净中位数。

这些数字只证明隔离 Stage C 在首版预算内可运行。编辑器后台仍以 `DeltaSeconds=0.125` 节流，故完整系统 Gate A/B 仍须在前台固定窗口做同机位、同分辨率、单系统、warmup、median/P95 的候选/金标准 A/B。

## 可恢复备份

- Pre-front-order：`Saved/CodexBackups/P0_StageC_PreFrontOrderFix_20260809-160740/`，SHA-256=`04BE5F7843FF9C3E2E1BDA5875685FA08DD6400108234989CB80D91FDBC7A9B7`。
- Pre-kernel-constant：`Saved/CodexBackups/P0_StageC_PreKernelConst_20260809-161538/`，SHA-256=`CFE7B6B4F3D6D4069E520056C25D91D75F03670F2A87AEE6AAC28C5FB459DF7C`。
- Pre-real-early-out：`Saved/CodexBackups/P0_StageC_PreRealEarlyOut_20260809-162140/`，SHA-256=`1DDCD2E390CE48DFFD8F8A909D1E6E81E32D51ABD7591C607CF7C152DCEA0E85`。
- Pre-symmetric-R1.6：`Saved/CodexBackups/P0_StageC_PreSymmetricR16_20260809-163535/`，SHA-256=`4295512257BD77B9DFBD80444331A0FE532C10C27808B86FC4EDECBFA49FD517`。

## 决策

R1.6 通过，冻结当前 Stage C HLSL 与 Field RT 语义作为 R2 输入。下一步只接 Body debug：先让材质直接消费 `User.SSPR_FieldMainRT`/`FieldAuxRT`，只显示 support-normalized Body 和 Q，不叠 Medium、Filament、Depth lighting 或 Raw core。Body 视觉 Gate 通过后才进入 R3 Medium。
