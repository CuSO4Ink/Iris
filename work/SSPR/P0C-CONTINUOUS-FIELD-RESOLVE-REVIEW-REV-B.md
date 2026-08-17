# P0c Continuous Field Resolve — Implementation Spec Rev B

> 状态：**APPROVED CONTRACT / R0～R1.6 PASSED / R2 SINGLE-DISPATCH FAILED / R2.2 v33～v40 STRUCTURE PASSED, VISUAL FAILED / SOURCE-MOTION EXPERIMENT AWAITS EXPLICIT APPROVAL**（2026-08-10：离散章已去除，但整体粒子感只转化为二维薄片与重复轨迹条纹；性能不是限制，Niagara Fluids/NS 气体 Gate 未过）。
>
> 权威角色：本稿是 P0c Stage C 的当前执行合同；`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 保留总体视觉/历史 G5，`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 保留 Stage A/B 与性能基线，`ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md` 保留 erf/P0c 数学。
>
> 被审版本：`P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-DRAFT.md`。
>
> 实施边界：对称 `9 Pilot + 24 Main = 33` total taps 继续作为单 dispatch 的正确性/历史性能基线；41-tap V6 仍是失败证据、不得升级。活动实现位于 `/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1/NS_SSPR_V4Dev_P0_Multipass_HQ_V1`：18 个同帧顺序 Simulation Stage、2 Raw + 2 Field + 2 Temp + 1 TightBand 私有 RT。Stage A/B、源粒子运动、正式 M3 与金标准保持冻结。Body/Medium/High 的职责已纠正，旧单颗粒点、椭圆章和全卡 haze 已去除；当前失败形态是平滑二维薄片、重复源轨迹条纹以及缺失 NS 大中尺度卷吸。用户已冻结“画面优先；性能预算不足时再优化”的优先级，故此时只记录资源成本，不以降质换性能。

## 0. 需求背景与准确进度

本项目用屏幕空间粒子重建获得接近 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的气体形态：连续体积、中大尺度卷曲/拉伸、中尺度结构、边缘细丝和自然耗散。目标是在不默认求解完整 Navier–Stokes、且完整系统 GPU 成本不高于该参考的前提下，提高可见精度。

已通过的是 P0c 数据/性能层与连续场生产输入层：Stage A 有界注册、Stage B 2048² current-cell/K64 gather、erf 解析核、Raw0/Raw1 八通道原始矩，以及 R0/R1/R1.5/R1.6。33-tap 单 dispatch Stage C 已写出有限、非空、语义闭合的 FieldMain/FieldAux；HLSL SHA-256=`c87f1ca81c432ea21ac3090efc55bd26323432da2c49c759a77ee2dfa8682b8a`，Synthetic Gate 全部通过，历史干净 ProfileGPU 中位数 `2.04 ms`。R2 的 V1～V6 随后坐实有限 Point stencil 的椭圆印章上限，41-tap V6 保留为失败证据。

2026-08-10 的活动 HQ 候选已完成纠偏后的同帧多阶段重建。v33 把物理 Stage 槽位重新分工为：d2/d4/d8/d16 Body 低频族之后先执行 d32 Body Closure X/Y，再执行 signed Medium A/B，最后两段严格 identity pass-through；这修复了旧顺序中 Body 在 Medium 之后继续变化并注入未扩散 residual 的结构错误。v34～v40 随后把 Final Opacity 固定为 Body 主导、Medium 限幅且主要承担内部明暗、raw High/Filament 只调光。精确读回、编译与持久化均通过，旧单颗粒点、椭圆章和全卡 haze 也已去除；但用户所指的整体粒子感仍成立：v40 是沿离散输入轨迹组织的平滑薄片和重复条纹，没有大中尺度卷吸、回流、涡团与自然耗散。v38～v40 又证明仅靠重建参数会在“Medium 过弱/过平”与“归一化后泡沫孔洞/条纹”之间摆动。当前结构证据保留，最终视觉 Gate 仍失败；源粒子运动继续冻结，正式 M3 与金标准不变。

## 1. Rev B 对审查意见的处置

已接受并写入本稿：

1. Stage C 迁移方向成立，但不能沿用 Rev A 未定义的 Coverage。
2. Stage C 为单次 dispatch，内部明确分为 Pilot Gather 与 Main Gather；两者合计 tap，不隐藏预滤波成本。
3. FrontDepth 与 M1/M2 分开处理，先选前部 cluster，再在 cluster 内计算矩。
4. 三尺度是同一 guided scale family；频带使用有符号差，positive residual/ridge 只作 feature mask。
5. 验证期允许 `2 Raw + 2 Field`，但仅限单实例，并先执行 R1.5 微基准。
6. 2048²仍是最终视觉 Gate；512²/1024²只用于微基准和开发诊断。
7. R6 拆为 Frozen-motion Acceptance 与 Residual Gap Classification；源运动不再被循环条件永久锁死。
8. Body 前增加合成输入单元测试。
9. 明确坐标 metric、边界 mask、half 精度对拍与多实例成本。

仍属后续实施测量 Gate、不得猜测的项目：

- `D_ref`、各 epsilon、Depth cluster 阈值和数值误差容差已由 R0 float32/half reference 冻结，详见 `P0C-R0-NUMERIC-REPORT-20260809.md`；修改冻结输入后必须重跑 R0。
- 32～48 taps 只作为实验上限；最终 tap 数必须由 R1.5 选出，不能提前写成性能预算。
- R2 实测已把 Niagara 单 dispatch 固定 Point compact stencil 降级为正确性验证载体；继续所需的 Niagara multipass/transient intermediate 属合同修订。用户已明确禁止 native RDG、C++、USF、插件、引擎源码和项目源码修改，不再把 RDG列为 fallback。

## 2. 冻结边界

本轮不修改：

- `/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1` 的 Stage A/B、K64、erf 核和 P1 last-substep gate。
- Raw0/Main=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`。
- Raw1/Aux=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`。
- Raw RT 的 2048²、RGBA16F、Bilinear、Mip Disabled 与 Fixed Tick `0.01667s`。
- 固定诊断输入 `rate=40,000`、`DensityPerParticle=0.03`。
- 正式 M3、旧 G5/GS 和 V2.1 失败资产。
- Fountain/CurlNoise/Drag/Velocity；源运动只在 R6b 证明 source-motion-limited 后另行审批。

继续禁止 History、跨帧 Ping-pong、Raw Core、`Contrast<1` 抬粒子、大半径圆形 Blur、宽 Streamline Body，以及要求所有 wisps 全局连接主 Body。

## 3. Rev B 总管线

```text
Frozen particle motion
    -> Stage A register                 [unchanged]
    -> Stage B P0c raw moment gather    [unchanged]
    -> Stage C current-frame resolve    [new, one dispatch]
         1. Pilot Gather
         2. Shared Guided Main Gather
         3. Front-cluster depth resolve
         4. Signed scale decomposition
    -> FieldMain / FieldAux             [new, current frame only]
    -> Material composition / lighting
```

Stage C 的“单次 dispatch”指一次 Simulation Stage dispatch；Pilot/Main 是 shader 内两个逻辑阶段，Pilot 样本保存在寄存器中供 Main 共用，不创建跨帧状态。

## 4. Coverage 与 Confidence 的完整定义

### 4.1 信号与可信度分离

Raw Density `D(q)` 是 Stage B 的加性密度信号，不是 Coverage。V2.2 不增加 Stage B 通道；Coverage-like certainty 由 Stage C 通过一套明确的非线性模型推导：

```text
C(q) = 0                                      , D(q) <= ε_D
C(q) = D(q) / (D(q) + D_ref)                 , D(q) >  ε_D
```

- `C(q)` 由 Stage C 推导，不由 Stage B 写出。
- 范围为 `[0,1)`；空 texel 为 `0`，不存在“默认有效”。
- `D_ref > 0`，单位与 Raw Density 相同，是质量档固定参数，不允许逐帧自适应。
- `D_ref` 会受核、DensityPerParticle 与质量档影响；改变这些输入必须重新跑粒子率不变量和积分 Gate。
- “粒子数 ×2、DensityPerParticle ×0.5”理论上保持 `D`，因此也应保持 `C`；实测容差见 §10。

R0 已冻结 `D_ref=0.003`：冻结输入下点核峰值为 `0.003055775`，2 px 最短线核峰值为 `0.002758534`，故该值对应约一个紧凑单粒子中心贡献。`D=0.0003/0.001/0.003/0.01/0.03` 时 `C≈0.091/0.25/0.5/0.769/0.909`。若改变 `DensityPerParticle/WidthPx/MinLengthPx`，必须重跑 R0，禁止沿用该值。

### 4.2 每尺度的 normalized convolution

对尺度 `r`：

```text
K_r(p,q) = spatial kernel in primary-view pixel metric
G(p,q)   = pilot validity * front-cluster depth weight * coherence fallback
Bnd(p,q) = explicit in-bounds mask

N_r = Σ K_r * G * Bnd * D(q)
S_r = Σ K_r * G * Bnd * C(q)
Z_r = Σ K_r     * Bnd

V_r = N_r / max(S_r, ε_S)         // confidence-normalized conditional value, internal only
Q_r = saturate(S_r / max(Z_r, ε_Z))
F_r = V_r * Q_r                   // public confidence-applied density
```

首版刻意采用 canonical `Q_r=S_r/Z_r`，因此在非退化区域 `F_r=N_r/Z_r`。这相当于保守的 guided convolution，不采用“弱单样本快速饱和到完整强度”的强 inpainting 曲线。以后若修改 `Q(S)`，必须另开算法修订和全部不变量 Gate。

明确语义：

- `V_r` 是置信度作用前的条件值，只在 Stage C 内部存在。
- `Q_r` 是该尺度的支撑置信度。
- `F_r` 是置信度作用后的公开密度，也是分频输入。
- `Q_tight/Q_mid/Q_body` 都在 Stage C 内计算；Debug 模式可将三者临时输出到 RGB，但生产打包不额外占 RT。
- 生产 `FieldMain.A` 明确为 `Q_BM`，即 canonical Body+Medium 合成所对应的支撑；不再使用含糊的单一 `SupportConfidence`。

## 5. Pilot Guidance：消除空中心循环依赖

### 5.1 Pilot Gather

Pilot 是固定、对称、各向同性的小 stencil，首版拓扑为中心加八邻域共 9 taps；偏移在 primary-view pixel metric 中定义。它执行：

1. 读取 `D/C`、Raw Tensor、M1/M2 和 FrontDepth validity。
2. 计算 `PilotSupport`；低于 `PilotSupportAbort` 时 Stage C 对该像素严格输出零。
3. 从有效 FrontDepth 样本选出 `z_min`，再以固定有界 `PilotFrontWindow` 形成前部候选 cluster。
4. 在该 cluster 内以 `D` 加权得到 `z_anchor`、Tensor 和 Coherence。
5. 只有 Pilot 通过，Main Gather 才执行。

当前 Stage B 的明确落盘语义是：没有通过解析峰值阈值的 front 候选时写 `FrontDepth=0`。因此首版 `FrontValid = D>ε_D && finite && bounds && FrontDepth>ε_Front`，其中 `ε_Front=2^-14`；零必须按 sentinel 拒绝，不能解释为近景。Fresh live 在 `D>ε_D` 的像素中 sentinel 占 2.59%。若未来必须表达真正的 `depthNorm≈0` 前层，需新增独立 validity 字段/编码并重跑 R0，不能继续复用零 sentinel。

若 9-tap Pilot 有 Density/M1 支撑但没有任何 `FrontValid` 样本，允许一次明确的 **MeanDepth fallback**：用有效 `M1/D` 选择/形成 anchor，`PilotDepthConfidence` 乘 `0.5`；Main 中无 Front 的样本只能用 MeanDepth 与 anchor 比较并乘 `0.35`，不能参与 FrontDepth minimum。若 accepted cluster 最终仍无有效 Front，`FieldAux.B` 回退为 `MeanDepth_BM` 且 `DepthConfidence_BM` 再乘 `0.5`。该 fallback 只补 sentinel 空洞，不扩大 front window。

### 5.2 方向回退

- Coherence 足够：解码张量方向，生成 Tangent/Normal。
- Coherence 下降：各向异性连续退回 1:1，并把最大半径限制为低 Coherence 小半径。
- Coherence 无效：不调用 `atan2(0,0)`；仅允许有 Pilot 支撑的小型各向同性核，或在 Support 不足时输出零。
- Pilot Tangent、DepthAnchor、坐标系由 Tight/Mid/Body 三尺度共享；每尺度不得重新求一套引导。

### 5.3 Main Gather 与 tap 记账

- Pilot 固定为 9 taps。
- Main 使用共享、嵌套的二维 sample set；实验候选为 24/32/39 taps，对应总计 33/41/48 taps。
- 每个 Main sample 同时更新 Tight/Mid/Body 三组 `N/S/Z`，而不是为三个尺度各读一遍纹理。
- 32～48 是实验范围，不是批准的性能预算；R1.5 决定首个 2048²候选能使用哪一档。
- 首轮语义基线用显式 integer `Load`/Point 读取 Raw 数据；FrontDepth 始终 valid-aware Point/Load，禁止 Bilinear sentinel 插值。Bilinear 只作为 R1.5 性能/质量实验，不自动进入合同。
- R2 最终验证了 33-tap 基线与 41-tap V6：V6 数值通过但视觉仍显示固定 impulse footprint，且读取增至 109 次；因此 41 taps 不升级为生产预算，48 taps 不再继续。

VelocityMomentX/Y 在 V2.2 首轮只保留 P0c 兼容与 Debug，不参与 `G/W`、不写 Field 输出。若以后用于有符号方向或速度一致性，须单独修改 spec 和字段 Gate；当前文档不把两个通道假装成已使用。

## 6. Depth Front Cluster 合同

### 6.1 Pilot 前部锚点

Pilot 寄存器样本先求 valid-aware `z_min`，再选：

```text
pilotFrontCandidate(q) = valid(q)
                      && FrontDepth(q) <= z_min + PilotFrontWindow

z_anchor = Σ C(q) * FrontDepth(q) / Σ C(q)   over pilotFrontCandidate
```

这一步不使用空中心 `p` 的深度，因此能在待填充像素启动。Stage C 首轮不访问 SceneDepth；SceneDepth soft intersection 明确留在 R5 材质阶段，不能在 Stage C 中含糊声称已约束。

### 6.2 Main sample 接受条件

```text
accept(q) = valid(q)
         && abs(FrontDepth(q) - z_anchor) <= MainFrontWindow
```

只有 accepted samples 才参与 D、Tensor、M1/M2 和三个尺度的 N/S。`MainFrontWindow` 有固定上下限，不允许简单随 Sigma 无界增大。

### 6.3 M1/M2 与 FrontDepth 分开归约

- `M1/M2`：在 accepted front cluster 内做加权和，Stage C float32 寄存器中再求 Mean/Sigma。
- `FrontDepth`：在 accepted cluster 内做 valid-aware minimum；不做加权平均，不做 Bilinear。
- 无有效 Front 的小比例样本只走 §5.1 的降置信 MeanDepth fallback；任何零 sentinel 都不得参与 minimum。
- 大 Sigma 不扩大连接；`DepthConfidence` 随 Sigma 增大而下降，并在 `SigmaReject` 处归零。
- 首版只重建最前 cluster。屏幕同位置的后层可能被舍弃，这是明确的 2.5D 妥协，不把单一 Mean/Sigma 冒充多峰分布。

### 6.4 一套 Depth 对应哪个尺度

首版只维护一套 Field Depth，明确绑定 canonical Body+Medium：

```text
B  = F_body
M  = F_mid - F_body
F_BM = B + kM * M
```

`kM` 是 Stage C 与材质共享并回读校验的固定参数。DepthAux 使用与 `F_BM` 相同的 accepted samples/组合支撑；`FieldMain.A=Q_BM`，`FieldAux.A=DepthConfidence_BM`。

Filament/H 不允许扩张几何深度支撑：只在 Tight sample 与共享 `z_anchor`/front cluster 一致且 `Q_BM` 有效的区域可见，继承 FieldAux，不另造前后深度。

FieldAux 的生产打包固定为：

```text
R = MeanDepth_BM
G = DepthSigma_BM
B = FrontDepth_BM
A = DepthConfidence_BM
```

不再存在 `DepthConfidence(or Coherence)`。

## 7. 同一尺度族与有符号分频

Tight/Mid/Body 必须共享：Raw 输入、Pilot 引导、DepthAnchor、坐标系、嵌套 sample set 和 normalized rule。它们构成同一 guided scale family，但不自动宣称是严格频域分解。

生产分频：

```text
B = F_body
M = F_mid   - F_body
H = F_tight - F_mid

FinalDensity = max(B + kM * M + kH * H, 0)
```

- `kM=kH=1` 时，clamp 前严格重建 `F_tight`，作为 canonical reconstruction Gate。
- M/H 保留正负值；RGBA16F 支持 signed band。
- `positive residual`、ridge、Laplacian/DoG 响应只用作 Filament feature mask、extinction/lighting modulation，不作为额外正密度相加。
- Body 是低频连续体量，但保持流向、卷曲和分叉；不由宽 Streamline 生成。
- Medium 调节中尺度结构；Filament 调节高频细节，不承担主体。
- 局部密度、方向和 front-cluster 支撑成立的脱离 wisps 可以保留；不要求全局连接主 Body。

FieldMain 的生产打包固定为：

```text
R = B                  // F_body
G = M                  // signed F_mid-F_body
B = H                  // signed F_tight-F_mid
A = Q_BM               // Body+Medium support confidence
```

Debug 可由 `B`、`B+M`、`B+M+H` 重建三个直接尺度。

## 8. 资源与实例所有权合同

验证期采用审查批准的质量隔离路线：

```text
Raw Main/Aux   = 2 × 2048² RGBA16F
FieldMain/Aux  = 2 × 2048² RGBA16F
TempMain/Aux   = 2 × 2048² RGBA16F
TightBand      = 1 × 2048² RGBA16F
持久 RT 下限   = 7 × 32 MiB = 224 MiB / live system instance
```

- 224 MiB 是当前视觉优先 HQ 候选的七张持久 RT 下限，不包含 NeighborQuery、Grid2D、UAV 临时资源、驱动对齐或渲染材质开销；它不是最终性能预算。
- V2.2 验证关卡合同为 `MaxConcurrentInstances=1`。
- 每个 Niagara Component 必须拥有私有 DI-managed RT；不得让多个实例共享同一外部 RT。R1 必须用对象身份/DI clone 回读证明所有权，若不成立则 BLOCKED。
- 第二个实例的预算按线性增加处理，未经独立多实例 Gate 不支持产品化多实例。
- Field RT 每帧完整覆盖、只保存当前帧，不是 History。
- 不为了省 RT 先推翻已通过的 Stage B 或降低当前画质。用户已明确“画面优先；预算不足时再优化”；最终视觉通过后再评估 Stage 融合、Temp 生命周期压缩、格式压缩或低频降分辨率。

## 9. 坐标、半径与边界规则

### 9.1 唯一 kernel metric

所有核距离和半径以 **Primary View display pixel space** 定义：

```text
deltaViewPx = deltaRTTexel * ViewRectSizePx / RTSizePx
```

Raw Tensor 若由 UV 方向生成，Stage C 先把解码切线乘 `ViewRectSizePx` 做 aspect correction，再归一化；核偏移在 display pixel space 旋转后转换回 RT texel 坐标。不得直接在未校正的正方形 UV 中旋转核。

### 9.2 半径语义

- `r_tight/r_mid/r_body` 首版是 Primary View display pixel 单位，不是归一化 UV。
- 当前 Raw 合同没有 projected radius moment，因此首版不假装能按每粒子半径精确自适应；仅允许 Pilot Support/Coherence 对半径做有界收缩。
- FOV、距离或 Screen Percentage Gate 若证明固定 display-pixel 半径不可接受，新增 radius moment/字段属于 Stage B 合同变更，必须另行审批。

### 9.3 边界

- 每个 tap 在 shader 中显式 bounds test；越界贡献严格为零。
- 不依赖 Clamp sampler；Point/Load 不得把越界坐标钳到边缘。
- `Z_r` 只累计 in-bounds nominal kernel weight，避免边界常量场无故变暗；屏幕边缘视觉衰减由独立 ScreenEdgeMask 决定。
- 测试覆盖 16:9、21:9、Editor/PIE、不同 FOV、TSR on/off 和 Screen Percentage。

## 10. 数值不变量与 Half 精度合同

### 10.1 冻结单位

- Raw DepthMoment 使用 P0c 已冻结的 `depthNorm=saturate((ViewDepthUU-NearUU)/(FarUU-NearUU))`，范围 `[0,1]`。
- M1=`ΣD*z`，M2=`ΣD*z²`；Stage C 使用 float32 寄存器累计/相减，RT 存储仍为 RGBA16F。
- `ε_D`、`ε_Front`、`ε_S`、`ε_Z`、`ε_Tensor`、`ε_Variance` 必须是不同常量，禁止复用一个 epsilon。
- R0 冻结值：`ε_D=2^-13=0.0001220703125`、`ε_Front=2^-14=0.00006103515625`、`ε_S=2^-18=3.814697265625e-6`、`ε_Z=2^-20=9.5367431640625e-7`、`ε_Tensor=2^-12=0.000244140625`、`ε_Variance=0.002`。
- `ε_Variance` 只处理负方差：`[-ε_Variance,0)` clamp 为 0，更小则 Depth invalid；绝不能从正方差中扣除。
- Depth/cluster 冻结值：`PilotSupportAbort=0.01`、`PilotFrontWindow=0.0078125`、`MainFrontWindow=0.015625`、`SigmaWarn=0.01`、`SigmaReject=0.03`。
- 误差容差：Density 相对 `<=1%`；MeanDepth 绝对 `<=0.002`；当前工作深度 `z<=0.10` 的 Sigma p95 绝对 `<=0.005`、`sigma>=0.002` 时相对 `<=100%`；全深度压力测试 Sigma p95 绝对 `<=0.025`。远深度 half 方差精度只允许降低 Confidence，不得扩大连接。
- 可复现证据与已知限制见 `P0C-R0-NUMERIC-REPORT-20260809.md`。

### 10.2 canonical 算子 Gate

R2 前必须自动验证：

1. 全零输入严格保持零。
2. 常量场重建相对误差 `<=1%`（内部区域）。
3. 单脉冲输出峰值不高于输入峰值。
4. 粒子数 ×2、单粒子 Density ×0.5 时输出变化 `<=5%`。
5. 典型测试场屏幕密度积分变化首轮控制在约 `±10%`。
6. 支撑增加时输出连续，无 threshold 跳变。
7. Body 半径增加不产生新的超输入亮峰。
8. `kM=kH=1` 时 signed bands 重建 `F_tight` 的误差只来自 RT half/采样误差。

### 10.3 Depth 精度 Gate

必须与 float32 reference 比较，而不只检查 finite/saturation：

- 同一薄层位于近/中/远三个 depthNorm；
- 两层非常接近；
- 两层明显分离；
- 空 texel 邻接有效 FrontDepth；
- M2/D 与 Mean² 接近的小方差场。

记录 MeanDepth 绝对误差、Sigma 绝对/相对误差、负方差 clamp 次数和 cluster 分类错误率。容差由该测试冻结并写入最终 spec；RGBA16F `±65504` 只证明范围，不证明方差差分仍准确。

## 11. Gate 顺序（Rev B）

### R0 — 复审、Numeric Contract 与 spec 收口（PASS）

- 已复审本稿定义并运行离线 float32/half reference。
- 已冻结 `D_ref`、各 epsilon、FrontWindow、SigmaWarn/Reject 与误差容差；operator、half、cluster 自动 Gate 全部通过。
- 已同步视觉、性能、解析核三份 spec 与执行计划；证据见 `P0C-R0-NUMERIC-REPORT-20260809.md`。

### R1 — 空 Stage、资源所有权与闭环

- **状态：PASS。** 完整结构、编译、私有 DI、冷启动 Raw→Field 精确配对与恢复点见 `P0C-R1-STAGEC-CLOSURE-REPORT-20260809.md`。
- 精确二进制备份，不以普通 Niagara `duplicate_asset` 作为恢复点。
- 新建 Stage C、FieldMain/Aux 和 Debug material；先做 pass-through/marker。
- 验证 Stage 顺序、P1 gate、每帧清空、冷启动、私有 RT、单实例和零编译错误。

### R1.5 — Resolve Microbenchmark

- **状态：PASS。** Point/2 Raw/2 UAV/32 taps 在 2048² 的重复 Stage 结果为 `1.42–1.47 ms`；48 taps 为 `2.74 ms`，手工 Bilinear 等价实现为 `30.87 ms`，均不进入首版。
- 首版选择 `9-tap Pilot + 24-tap shared Main = 33 total taps`、Point/Load、2 Raw、2 Field 与 Pilot support early-out；生产 guidance/depth 算术仍须重新 Profile。
- 编辑器后台 8 Hz 导致整帧含 fixed-tick 追帧，完整帧数值不作为本 Gate 的可比较证据；详情见 `P0C-R15-RESOLVE-MICROBENCH-REPORT-20260809.md`。

矩阵至少包含：

```text
Resolution : 512² / 1024² / 2048²
Total taps : 16 / 24 / 32 / 48
Input      : 1 RT / 2 RT
Sampling   : Point / Bilinear experiment
Output     : 1 UAV / 2 UAV
Support    : full / 25% / sparse early-out
```

记录 Stage GPU、完整帧 GPU、生成 HLSL/Generated Code、可取得时的 shader assembly、重复纹理读取、分支和实际 dispatch。32～48 tap 只能在本 Gate 后选择。若 Niagara 单 dispatch 生成代码重复采样或成本无法进入参考预算，只允许在 Niagara 资产内改为顺序 multipass/transient RT；若该路线也失败则停止并复审，不得转向 RDG/源码。

### R1.6 — 合成输入算法 Gate

- **状态：PASS。** 33-tap 生产基线的完整 Synthetic/live 证据见 `P0C-R16-PRODUCTION-AND-SYNTHETIC-REPORT-20260809.md`。

在复杂烟雾前运行：

- 单脉冲；
- 均匀常量场；
- 同深度同方向两团；
- 同深度、方向垂直交叉；
- 同屏幕位置前后两层；
- 中间有空洞的两团支撑；
- 低 Coherence；
- 屏幕边界；
- 固定粒子下亚像素相机移动。

分别检查 stencil 图案、方向错误、跨层、Confidence 增亮、signed-band 重建、边界 Clamp 和无 History 抖动。R1.6 未过，不进入真实烟雾 Body Gate。

### R2 — Body-only

- **状态：FAIL / REQUEST CHANGES。** Body-only Debug、V1～V6、增益与显式 Bilinear/Clamp/NoMip 排除均已执行。V6 的 41 logical/109 physical loads、Synthetic/live 数值 Gate 通过，但局部重复椭圆 stencil 在 Gain 20 与 Gain 14 下均存在；详见 `P0C-R2-BODY-GATE-REPORT-20260809.md`。
- 只显示 B/F_body 与 Q_body/Q_BM Debug，不显示 Medium、Filament、灯光。
- 要求连续、有内部浓淡、可拉长/卷曲/分叉；禁止粒子点、规则 stencil、平行刷毛、圆泡和均匀白板。
- 同时通过 §10 密度积分和峰值 Gate。
- 该单 dispatch 分支违反“禁止规则 stencil”，当时不得直接启动 R3；此结论已由后续 R2.1 Niagara-only multipass 修复并取代，不能再误读成当前 R3 未实施。继续在旧 V6 上堆 tap、调增益或叠 Medium/Filament/Lighting 仍不属于修复。

### R2.1 — Niagara-only multipass 合同

- **状态：HISTORICAL STRUCTURE/NUMERIC PASS，VISUAL FAIL；已由 R2.2 取代。** 单 dispatch R2 失败后，当时先改为 Niagara 资产内 14 个顺序 current-frame stages；没有 History、RDG、C++、USF、插件或源码改动。2026-08-10 用户近景仍能明确辨认粒子感，“无旧椭圆章”不能继续作为 Body 视觉通过依据。
- 当时 Stage 顺序为：A、B、旧 C seed、Body Y、d2/d4/d8/d16 的 X/Y 八个连续尺度 Stage、Medium Tensor Diffuse A/B；这不再代表当前 18-stage 顺序。
- `Body Resolve/Body Atrous` 使用连续逐 texel X/Y 累计与 TempMain/TempAux ping-pong；d16 作为 Body，d8 与 Body 形成 Medium 基带，d4 另存 TightBand。
- 2048² direct Body 证据显示低频主体连续且不再出现 R2 的椭圆印章；常量、有限性、支撑、深度与 half Gate 继续成立。
- 所有 Stage 都在同一帧完成，不读取上一帧；Stage A/B、Raw 通道、源运动、正式 M3 与金标准未改。完整性能 A/B 尚未执行。

### R2.2 — Body-first frequency order 与支持体 Gate

- **状态：STRUCTURE/RESPONSIBILITY PASS，VISUAL FAIL。** v33 把 d32 Body Closure X/Y 放到 Medium A/B 之前；v34 soft support gate 去掉全卡 haze、近零支撑尾部和旧离散章。当前 18-stage 精确顺序见 §16。
- Body 是唯一主体密度载体；连续逐 texel d2/d4/d8/d16/d32 尺度族负责完整支持体，不能再由 wide Streamline、raw High 或 Ridge 承担。
- 视觉失败不再表现为椭圆 point stencil，而是平滑二维薄片与沿输入轨迹重复的条纹；因此结构纠偏完成不等于气体 Gate 通过。

### R3 — Medium

- **状态：STRUCTURE/RESPONSIBILITY PASS，VISUAL FAIL。** 两次张量引导扩散当前位于 Stage 15/16，按同 front/depth/support 连接局部空洞，并对无双侧支撑、无主体连接的分支衰减。v40 已把 Medium 限制在 Body envelope 内，对密度只作有限修正并主要驱动内部明暗；不再复用 v15 的 `kM=1.0` 直接密度注入。
- 分别看 B、signed M、B+kM*M。
- 只连接同 front cluster、方向/支撑成立的局部空洞；禁止跨层桥、周期纹和能量偏置。
- direct signed Medium 已同时保留正负值；第二 pass 确实生效。v38 证明绝对 M 在大部分 Body 内过弱，v39 的 Body-relative 归一化又产生泡沫孔洞；v40 的限幅调光仍只得到轨迹条纹。它只能修补/调制中尺度结构，不能承担 Body，也不能凭空创造输入中没有的涡团。

### R4 — Filament

- **状态：STRUCTURE/RESPONSIBILITY PASS，VISUAL FAIL。** d4 TightBand 与 d8/d16 同属一套尺度族；运行态 H 正负均非空、支撑外严格为零，canonical 重建误差在 half 容差内。v40 已把 `HighMix=0`，raw signed H 不再进入 FinalDensity/Opacity；Filament/Ridge 只调光且没有重新引入旧离散章，但可用的长程连续 ridge 仍不足。
- 分别看 signed H、ridge feature mask 和最终合成。
- H 保持有符号；正 ridge 只调制细节、不作为额外密度。v15 的违规路径已在 v40 移除。
- 允许局部有支撑 wisps；禁止 Raw Core、胶囊头和可见 stencil。
- 通用 Hessian 边缘响应因形成闭环“脑纹/细胞边”已拒绝；当前只保留张量主轴线脊，旋转 90° 对照近空，证明方向选择有效。世界图中的线脊仍偏短、偏弱，不能视为气体拉丝通过。

### R5 — Depth/Lighting

- **状态：TECHNICALLY INTEGRATED，VISUAL FAIL。** v40 消费深度矩、低频梯度与 signed Medium ratio 形成当前帧内部明暗；FinalDensity 已不再混入 raw High，Medium 也被 Body envelope 限幅。但该受光仍不能消除二维薄片和重复轨迹条纹，不能用于掩盖结构失败。
- 分别检查 Mean/Sigma/Front/DepthConfidence/Thickness。
- 先验证 front cluster 与 BM 深度一致，再启用 Beer–Lambert、低强度受光和 SceneDepth soft intersection。
- 灯光不得掩盖孔洞、排线或跨层。
- 非预乘透明输出错误已修复；失败的烟灰高 Ridge 色调试验 v16 已撤销，当前保存 v40 中性浅灰参数。SceneDepth soft intersection 尚未作为最终 Gate 完成，动态/用户视觉仍未通过。

### R6a — Frozen-motion Resolve Acceptance

冻结源运动，检查：连续性、三频带、深度、转镜/拉远/边缘、TAA/TSR、稳定性以及候选完整链性能。这里只要求忠实重建并明显改善当前运动，不要求 Resolve 凭空生成输入轨迹中不存在的宏观涡旋。

最终视觉证据仍必须为 2048²。512²/1024²不能作为视觉通过结论。

### R6b — Residual Gap Classification

把相对 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的剩余差距逐项归类：

1. Resolve-limited；
2. Source-motion-limited；
3. Renderer/lighting-limited。

每项必须有 Frozen-motion Debug/动态证据。Resolve-limited 返回 R2～R5；Renderer-limited 返回 R5；若 R2～R5 的字段职责与负面 Gate 已通过、且多轮冻结输入对照仍只在“过平”与“条纹/泡沫”之间摆动，可把缺失的大中尺度卷吸归类为 Source-motion-limited 并提出 R7，即使整体视觉目标尚未通过。R7 仍需用户再次明确批准。

### R7 — 可选源运动提案

只处理 R6b 已证明的轨迹级缺口，需用户再次批准。修改后必须重新跑 R2～R6，不能继承旧视觉/性能 Gate。

## 12. 完整性能 A/B 合同

- 使用同一 packaged profiling build、同一 GPU/驱动/电源状态、同一分辨率/ViewRect/Screen Percentage/TSR、同一相机和相近屏幕覆盖。
- 冻结随机种子、Spawn 参数、预热时间和采样窗口；一次只启用一个系统。
- 参考链：Particle Source + Grid3D Simulation + Volume Renderer。
- 候选链：Particle Simulation + Stage A/B + Stage C + Translucent Renderer。
- 每项至少记录多次代表性运行窗口的完整帧 GPU median/P95，同时报告各链路事件；单帧或孤立 Stage 不能宣称通过。
- 建议首个正式合同为预热 `>=10s`、每次采样 `>=300 frames`、至少 5 个窗口；最终数值可由复审调整后写入 spec。
- 硬目标仍为候选完整 GPU 不高于参考完整 GPU，同时可见精度更高；若失败，先定位 Resolve/Renderer/多实例成本，不自动降 Raw 2048²或粒子量。

## 13. 与现行 spec 的同步结果

2026-08-09 已完成原始合同同步；2026-08-10 追加 v33～v40 活动 HQ 回写：

1. 视觉 spec §4/§7/§8 已从旧 Dense/材质 RK2 执行入口更新到 P0c Raw + Stage C + signed bands，并记录 R2 失败。
2. §14 已记录 current-frame Stage C 的批准范围、当前 18-stage 边界与源运动仍需明确批准。
3. §11/§12 已用 Synthetic/Body/Medium/Filament/Depth Gate 取代旧 Streamline Gate，并写入 2 Raw +2 Field 单实例预算和 R1.5。
4. 性能 spec 已把 RawMoments/FieldRecon/R2 从“等待”改为对应视觉失败，并加入完整参考链 median/P95 合同。
5. 旧 V2/V2.1 计划已标成失败快照；`8×5` 不再约束 Stage C，tap 由 R1.5/R2 实测决定。
6. 视觉、性能、解析核 spec、Brief、Backlog 与 Log 已统一金标准、完整成本上限、R6a/R6b/R7 边界，以及当前 R2.2～R5 职责纠偏完成但整体视觉失败的状态。
7. R2.2 Body-first multipass、R3 bounded signed Medium、R4 lighting-only Ridge 与 R5 深度内部明暗已落入隔离 HQ 候选；正式 M3、旧失败候选、源粒子运动与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 未改。
8. 当前资源下限已从原合同 `2 Raw + 2 Field = 128 MiB` 更新为视觉优先 HQ 的 `2 Raw + 2 Field + 2 Temp + 1 TightBand = 224 MiB`；性能结论仍待画面通过后的完整同机位 A/B。

## 14. 批准决议与未授权扩展

用户批准按本稿直接推进，因此以下内容已成为执行合同：Stage C current-frame Resolve；Stage 内 9-tap Pilot + 共享 Main 实验矩阵；Stage C-derived `C(D)` 与 canonical 保守密度；front-cluster Depth；单套 BM Depth；signed B/M/H；验证期单实例 2 Raw+2 Field；Point/Load 语义基线；Primary View pixel metric；R1.5/R1.6；R6a/R6b 后按证据开放 R7。该合同已诚实执行到 v40 并得到视觉 FAIL；批准实施不等于授权在失败后自动扩大范围。

批准不等于预判 Gate 通过。以下扩展仍未授权：

- 未经 R1.5 直接把 32～48 taps 写成生产预算；
- native RDG shader、C++、USF、插件、引擎源码和项目源码修改（用户明确禁止，不是待审批 fallback）；
- 超出当前已审计的 18-stage、7-RT 隔离 HQ 路线而新增持久状态、History 或源码路径；
- 在视觉 Gate 前降 Raw 2048²、粒子率或 K64；
- 增加 History、多层深度 RT、radius moment；
- 修改 Fountain/CurlNoise/Drag/Velocity 等源粒子运动；当前证据已支持把它列为下一实验，但 live mutation 仍须用户明确批准；
- 多于一个 live HQ instance；
- 用编译、空 RT 或单帧 Profile 替代运行/视觉/完整链路证据。

## 15. 2026-08-10 v15 历史实施与证据

本节保留 v15 的历史闭环与失败归因，不再代表当前资产状态。活动资产与隔离材质路径未变；当时精确为 14 段，v12 数值、direct bands、材质 SHA `b874173b…2ef` 和 v15 世界图仍是“Medium/High 重新注入 Opacity 会放大颗粒”的有效反证。备份位于 `Saved/CodexBackups/P0_HQ_FilamentV12_PreMaterialV13_20260810-004628/`。正式 M3、旧 V6 与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 未修改。

## 16. 2026-08-10 v33～v40 当前 checkpoint

- 活动资产：`/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1/NS_SSPR_V4Dev_P0_Multipass_HQ_V1`；隔离材质：`R2_BodyDebug_HQ/M_SSPR_P0c_HQ_BandDebug` 与 `MI_SSPR_P0c_HQ_FieldBodyDebug`。
- 精确 Stage 顺序为 18 段：`Rasterize Trails` → `Resolve Grid To Material` → `Resolve Continuous Field` → `Resolve Body Y` → d2 X/Y → d4 X/Y → d8 X/Y → d16 X/Y → `Body Closure X d32` → `Body Closure Y d32` → `Medium Tensor Diffuse A` → `Medium Tensor Diffuse B` → `Field Pass Through A` → `Field Pass Through B`。最后两段为严格 identity，不再隐藏深度滤波。所有 Stage 脚本 UpToDate，Niagara 0 error/0 warning。
- v33 通过重命名物理 Stage 槽位并交换模块职责，纠正了旧“Medium A/B 在 Body Closure 前执行”的顺序错误。六个相关模块已精确回读，Body X/Y、Medium A/B 与两个 pass-through 的 HLSL SHA 分别为 `a8e5b13…`、`e9bd987…`、`cf7ab1…`、`0449d187…`、`93f562e3…`、`93f562e3…`。
- v40 父材质 Custom HLSL SHA-256=`dbc0897d81e637b16fe1534cbb8435fa69fe2e6c46b62d05ee21d72e4a929127`；保存值为 Mode 7、MediumGain=`24`、MediumMix=`1.25`、FinalGain=`130`、HighMix=`0`、RidgeGain=`0.4`、RidgeLightBoost=`0.2`、OpacityScale=`0.68`、FinalColor=`(0.50,0.53,0.58,1)`。Body 是密度载体；Medium 被限制到 Body envelope 内并主要用于内部明暗；High/Filament 不进入 Opacity；Ridge 只调光。
- 诊断序列：v34 去掉全卡 haze 与离散章但形成平滑轮廓；v38 signed Medium-only 证明绝对 M 只集中在很小的中心区域；v39 Body-relative 归一化把 M 扩到主体后产生 Swiss-cheese/泡沫孔洞；v40 把 M 改为轻量密度修正和内部明暗，孔洞减弱但回到二维薄片与重复轨迹条纹。
- 当前审核图：`Saved/CodexEvidence/P0_HQ_R40_MediumShadingV40/P0_HQ_R40_MediumShading_Mode7_Close250_40k_Mature_v40.png`。诚实结论是 **视觉 FAIL**：旧点状/椭圆印章问题已在局部意义上消失，但用户定义的整体粒子感未解决；画面没有 Niagara Fluids/NS 参考的连续体积、大中尺度卷吸、回流、涡团和自然耗散。
- 下一项有证据的实验是只在隔离 HQ 候选中改变源粒子运动，增加低频相干 curl/卷吸和尺度分离；它不等于完整 NS，也不触碰插件/源码/RDG。该实验尚未获本轮明确批准，因此源运动仍冻结。正式 M3、金标准和参考资产未修改。
