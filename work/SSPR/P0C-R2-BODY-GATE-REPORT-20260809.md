# P0c R2 Body-only Gate Report — 2026-08-09

## Verdict

**R2 = FAIL / REQUEST CHANGES.**

R0、R1、R1.5、R1.6 的数值、结构、资源所有权和 33-tap 生产基线继续有效；本结论只否决当前 **单次 Niagara Stage C + 固定 Point compact stencil** 作为可交付 Body 重建后端。R2 的技术闭环已完成，但画面仍出现局部重复椭圆/stencil，无法满足“连续、有内部浓淡、可拉长/卷曲/分叉且无规则采样图案”的 Gate。R3 Medium、R4 Filament 和 R5 Lighting 不得启动来掩盖该失败。

下一步不是再调 BodyGain 或继续堆 tap，而是在**纯 Niagara 资产范围**把单 dispatch 改成 current-frame multipass/transient intermediate。用户明确禁止 native RDG、C++、USF、插件、引擎源码和项目源码修改；RDG 不再是候选或 fallback。

## Frozen scope

- 数据候选：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`
- 固定输入：rate=`40,000`、K=`64`、DensityPerParticle=`0.03`、Raw/Field=`2048² RGBA16F`、Fixed Tick=`0.01667s`
- Stage A/B、P0b erf、P0c Raw0/Raw1、P1 gate 与源粒子运动未改。
- 正式 M3 `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev` 与金标准 `/Game/NewNiagaraSystem.NewNiagaraSystem` 未改。
- R2 只显示 `FieldMain.R = B/F_body`；Medium、Filament、Depth lighting、Raw core 和 History 均关闭。

## Implemented R2 assets

- Debug parent：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/R2_BodyDebug/M_SSPR_P0c_FieldBodyDebug_R2`
- Debug instance：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/R2_BodyDebug/MI_SSPR_P0c_FieldBodyDebug_R2`
- 当前 MI：`BodyGain=14`、Body-only Debug；父材质/默认纹理已显式改为 Bilinear、Clamp、NoMip、non-streaming、linear data。
- 当前隔离候选保存为 V6 实验终点：System 文件 SHA-256=`48F9C1E9698667796062051D7A7727536CC0641B2DEB055AC49399BF40991F23`。
- 当前 Stage C HLSL SHA-256=`5bdb675e7646a818da807a0af8aae1692bb969635a3090e85fd6caaa289b65fc`，长度 `173,546` chars；强制 reload 后精确回读一致，Niagara `0 error / 0 warning`。

V6 不是新的生产预算。R1.6 通过的生产基线仍是 `9 Pilot + 24 Main = 33` logical taps、Point/Load、HLSL SHA-256=`c87f1ca81c432ea21ac3090efc55bd26323432da2c49c759a77ee2dfa8682b8a`，干净 Stage GPU 中位数 `2.04 ms`。V6 只保留为证明固定 Point compact stencil 质量上限的失败实验。

## Iteration record

| 版本 | 有效变化 | 结果 |
|---|---|---|
| R2 initial | 33-tap production field + Body-only debug | Body 很弱且离散，FAIL |
| V1 | 收紧/扩展 Pilot 与 Body closure、加强 front/mean core | 未形成连续体量，FAIL |
| V2 | 九个 Pilot 寄存器样本复用于 Main 累计，避免把 Pilot 当隐藏成本 | 孔洞改善但仍见规则点阵，FAIL |
| V3 | 明确 Tight/Mid/Body=`5/11/24 px` | Body 支撑扩大，但固定采样印章更明显，FAIL |
| V4 | 像素交错 0°/22.5° dual-phase Point quadrature | 相位锁定降低，局部规则椭圆仍显形，FAIL |
| V5 | Pilot RawMain 做 valid-aware 手工 2×2 bilinear；RawAux Front 与 Main 仍 Point | 33 logical、93 physical loads；更平滑但仍有局部 stencil，FAIL |
| V6 | 9 Pilot + 32 Main；四个 D4 八点环，半径 `.18/.40/.64/.88`，相位 `0°/22.5°/0°/22.5°` | 41 logical、109 physical loads；数值全过，画面仍为更密的椭圆印章，FAIL |

V1～V6 均为同一隔离候选上的可恢复实验；每次写入前均有二进制恢复点，未覆盖正式 M3。

## Numeric and runtime evidence

V6 synthetic schema：`sspr-p0c-r2-body-closure-v6-dualphase-d4-41tap`。全部强制项通过：

- 常量场内部相对误差 `4.0668e-05`；方向交叉转置误差 `0.0096749`。
- signed-band 重建最大相对误差 `0.00039115`。
- 典型 blob 积分相对误差 `0.0040427`；亚像素 L1 `0.074454`。
- 双团空洞 Body/peak=`0.93194`，没有新增超输入亮峰。
- 单层中心 confidence=`0.85010`；双层降到 `0.048065`；Front 不落到 Mean 后方。
- 全部输出 finite，zero input 严格为零。

V6 live 2048² scalar aggregation 也通过技术 Gate：Body 正值像素约 `212,092`，Raw/Field 无 NaN/Inf、无 half saturation、无负密度，Sigma 非负，Front<=Mean，signed reconstruction 无非法负最终密度。运行 RT 的数字后缀会在 reload 后变化，验证脚本已改为按通道合同动态识别 RawMain/RawAux/FieldMain/FieldAux，禁止再按 `TextureRenderTarget2D_*` 后缀猜角色。

## Visual evidence and failure

- V5：`D:\Work\Company\Advance\Fluid\precisefluid\Saved\CodexEvidence\P0_R2_Body\P0_R2_Body_ClosureV5_Console.png`
- V6 / Gain 20：`D:\Work\Company\Advance\Fluid\precisefluid\Saved\CodexEvidence\P0_R2_Body\P0_R2_Body_ClosureV6_Gain20_Age10.png`
- V6 / Gain 14：`D:\Work\Company\Advance\Fluid\precisefluid\Saved\CodexEvidence\P0_R2_Body\P0_R2_Body_ClosureV6_Gain14_Age10.png`
- 无候选背景对照：`D:\Work\Company\Advance\Fluid\precisefluid\Saved\CodexEvidence\P0_R2_Body\P0_R2_Background_NoCandidate.png`

`CaptureViewport` 会在整个天空产生全局点/条纹伪影；无候选背景对照已证明该部分不是 SSPR。R2 的失败依据是只集中在 Body 内、随 Body 形状出现的重复椭圆印章：Gain 20 只把它们过曝连成白膜，Gain 14 去掉饱和后印章仍在且 Body 更薄。显式 Bilinear/Clamp/NoMip 清理也未改变该局部结构，因此失败不能归咎于材质采样器或曝光。

## Performance evidence

- 可比较基线：R1.6 33-tap production Stage C 干净样本 `3.14/1.94/2.04 ms`，中位数 `2.04 ms`。
- V6 spot：Stage C `2.89/6.90/9.00 ms`，中位数 `6.90 ms`；但回调 `deltaSeconds=0.125`，受编辑器后台 8 Hz/fixed-tick 追帧污染，**不得作为正式性能失败或完整帧 A/B**。
- 该 spot 只作为成本上升信号：V6 从 33 logical/93 physical 提升到 41 logical/109 physical，画质仍未过 R2，继续堆 tap 没有质量/成本依据。
- R1.5 已证明手工 Bilinear 等价 256 physical loads 在 2048² 达 `30.87 ms`，不能靠把所有 Main tap 改成手工 Bilinear 解决。

## Root cause

Raw 场是稀疏的；固定 Point compact stencil 的单像素脉冲响应天然由有限离散采样位置组成。扩大半径、交错相位、复用 Pilot 或增益只能改变印章的尺度、相位和亮度，不能把它变成真正连续的低频滤波。V6 已给出必要反证：更多且更对称的采样仍保留可见 impulse footprint，同时成本上升。

因此 Niagara 单 dispatch 实现现在只能作为数学/字段正确性 oracle，不能宣称已经得到可交付 Body。要继续，必须让邻近像素复用滤波结果或 tile 数据，而不是每个像素再次独立枚举一个稀疏二维 Point stencil。

## Corrected Niagara-only implementation

1. `Body Resolve X`：对 RawMain/RawAux 做逐 texel、单调权重的一维 support/depth-aware 累计，写 Niagara 自管 TempMain/TempAux；不在这一轴提前放大弱样本。
2. `Body Resolve Y`：读取 TempMain/TempAux，做第二轴累计后一次性计算 `N/S * Q`，写现有 FieldMain/FieldAux。
3. 首轮只测试 9/13/17 taps per axis。连续 offset 的冲激响应必须单峰、无角向副瓣；不再增加稀疏环形 tap。
4. 两个 Stage 都在当前帧依次执行，临时 RT 每帧覆盖，不是 History。Stage A/B、Raw、源运动、正式 M3和金标准不改。
5. Body 通过后，R3 才允许在连续 Body 上使用局部张量引导的小邻域连接；Filament/Lighting 继续关闭。

硬边界：禁止 native RDG、C++、USF、插件、引擎源码和项目源码修改。新路线仍需在 2048²重新记录临时 RT 显存、Stage GPU 与完整链 median/P95。

## Recovery and postflight

- V5 恢复点：`D:\Work\Company\Advance\Fluid\precisefluid\Saved\CodexBackups\P0_R2_BodyClosureV5_20260809-184100`
- V6 前各版本及材质增益/采样器恢复点均在 `Saved\CodexBackups\P0_R2_*`。
- SIE 已停止；确认 `running=false`、无脏 Content/Map。
- 编辑器相机已恢复并独立读回：Location=`(-287.36989082890921,986.84100779236428,2579.6384621685947)`，Rotation=`(-4.7051612883806282,-156.46260058879855,7.8654392118147245e-7)`。
