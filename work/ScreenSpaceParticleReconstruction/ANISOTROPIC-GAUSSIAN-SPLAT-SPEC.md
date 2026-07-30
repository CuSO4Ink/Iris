# 各向异性高斯 Splat 拉丝烟雾规格

- 版本：0.9
- 日期：2026-07-30
- 状态：Sparse V1 因跨帧运行全零未通过 Gate；保守 Sparse V2 `33×7` 已通过有效 RT Gate，当前绑定用户更偏好的旧 `MI_SSPR_AnisotropicSplat_G5_HQ`。先前 ProfileGPU 未记录相机姿态，不能与用户近景 Dense Profile 直接对比，性能 Gate 已重新打开。FieldRecon Connected 仍为实验候选
- V1 冻结快照：`/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729`
- V3 冻结快照：`/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730`
- V2 当前开发目录：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2`
- V2 Niagara：`NS_SSPR_AnisotropicSplat_Main`
- V2 显示材质：`M_SSPR_AnisotropicSplat_Display`
- V2 调参实例：`MI_SSPR_AnisotropicSplat_HQ`
- 当前 G5 Visual V2 材质：`M_SSPR_AnisotropicSplat_G5_V2`
- 当前 G5 Visual V2 实例：`MI_SSPR_AnisotropicSplat_G5_V2_HQ`
- 当前活动显示材质：`M_SSPR_AnisotropicSplat_G5`
- 当前活动显示实例：`MI_SSPR_AnisotropicSplat_G5_HQ`
- 实验 FieldRecon V1 材质：`M_SSPR_AnisotropicSplat_FieldRecon_V1`
- 实验 FieldRecon V1 实例：`MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`

## 1. 目标画面

最终基本单元不再是固定圆点或圆形软粒子，而是沿局部流向拉伸的各向异性密度核：

```text
细尖端  ->  逐渐增密  ->  致密中心  ->  逐渐减密  ->  细尖端
                     横向始终较窄
```

大量粒子核叠加后需要同时出现：

- 1～3 px 的尖细流丝；
- 中尺度相互连接的卷曲轨迹；
- 中央高密度、外围柔软的烟团；
- 粒子运动方向改变时，丝线方向同步改变；
- 同一屏幕区域中的前后烟丝不会被无条件糊成一层；
- 烟雾具有可感知的前后深度、厚度、遮挡与柔和受光；
- 关闭 TAA/TSR 后仍不能退化为独立圆点。

目标是获得类似高品质流体烟雾的拉丝感，不追求严格物理正确性，也不求解完整 Navier–Stokes 方程。

## 2. 冻结与隔离规则

V1 是当前“圆形粒子写入 + Mip 多尺度烟体重建”版本的冻结快照。

- 不修改 V1 中的 Niagara、材质、材质函数和验证关卡。
- 新算法只允许写入 `AnisotropicSplat_V2`。
- V2 已从 V1 自包含副本发展为当前主线；后续算法与调参只写入 V2，V1 保持冻结。
- 原正式目录 `/Game/SSPR_Validation/M2/ParticleTrails` 保持当前可运行状态。

## 3. 核心判断

当前各向同性处理链的能力边界是：

```text
圆点 -> 柔化圆点 -> 软泡 -> 宽烟团
```

它适合作为最终烟体的低频层，但无法独立产生稳定的尖细拉丝。

V2 的拉丝必须从写入阶段产生：每个粒子根据本帧真实屏幕位移写入旋转椭圆高斯，而不是先写圆点、再依赖大半径模糊猜测流向。

G4 视觉结果进一步确认了这一边界：把 7×7/13×13 LOD0 重建真正接入最终材质，并用邻域支持门控压制孤立 Core 后，粒子锯齿显著减少，但画面变成宽而均匀的白色软管，尖细流丝、中尺度分叉和纵深仍然不足。继续增加各向同性半径只会进一步丢失高频结构。

因此 G5 不再通过“更宽 Blur”追求连续性，而是把当前帧粒子运动整理为方向场和深度场，再由材质沿局部流场生成弯曲、两端渐细、受深度约束的 Streamline Filament。这里的 Streamline 是当前帧空间重建，不是历史拖尾。

## 4. 总体管线

```text
Niagara GPU 粒子运动
    -> Solver 前记录 PositionBeforeSolve
    -> Solver 后计算 FlowDelta
    -> 在 Velocity 清零前缓存 FlowVelocity / FlowDelta
    -> 当前与上一位置分别投影到屏幕
    -> 得到屏幕切线、速度和长度
    -> 各向异性高斯 Splat 累积密度、方向张量与深度矩
    -> Resolve 为 Niagara 自管 Main/Aux 当前帧 RT
    -> 材质沿方向场做深度约束的双向 Streamline 重建
    -> 细丝层 / 中尺度连接 / 烟体层 / 深度融合 / 柔和受光
    -> Emitter SourceMode 面片显示
```

不引入外部 Content Browser RenderTarget，不恢复 Blueprint Ping-pong，不依赖历史画面产生拖尾。G5 允许新增一张 Niagara 自管的当前帧辅助 RT，但它每帧完整覆盖，不参与 A/B 交换或跨帧反馈。

### 4.1 当前已落地的 GPU 管线

```text
Particle Spawn/Update
    -> 保存 Position 与 SSPR_ScreenDeltaUV
    -> Stage1 从 Position 用当前 PrimaryView.WorldToClip 重新投影
    -> RasterizationGrid3D(2048×2048×1) Q10 原子累加高斯密度
    -> Stage2 逐像素 Resolve 到 Niagara 自管 SimRT
    -> Emitter SourceMode 显示面片材质采样
```

上面是当前 G4 已落地基线。G5 审批通过后扩展为：

```text
Stage1 逐粒子：
    当前相机投影 Position 与 FlowDelta
    -> 原子累加 Density / TensorCos2 / TensorSin2
    -> 原子累加 DepthMoment1 / DepthMoment2 / FrontInvDepth

Stage2 逐像素：
    -> 归一化方向张量、Coherence、MeanDepth、DepthSigma、FrontDepth
    -> 完整覆盖 User.SSPR_SimRT 与 User.SSPR_AuxRT

Renderer 材质：
    -> 当前帧方向/深度场驱动 RK2 Streamline
    -> 与较窄的 Medium/Body 合成
    -> SceneDepth 软交界与低强度体积受光
```

实现约束：

- Raster Stage 只写 `User.SSPR_DensityRaster`，必须保持 `WritesParticles=False`；不得为调试标记回写 `Particles.*`。
- 当前 UE 5.8 编译器会裁掉“只在 Custom HLSL 副作用中读取、但没有 Renderer 消费”的粒子属性。V2 保留 Renderer 0 作为编译属性保活器：启用、`RendererVisibility=1` 隐藏，并把 `SpriteSizeBinding` 指向 `Particles.SSPR_ScreenDeltaUV`；正式显示仍由 Renderer 1 完成。
- Stage1 不再依赖缓存的 `SSPR_ScreenUV` 作为中心位置，直接从持久化 `Particles.Position` 重投影；缓存 `SSPR_ScreenDeltaUV` 只控制高斯长轴。
- `RasterizationGrid3D` 仅使用 Z=0 的一个切片，本质仍是二维屏幕密度场；选择该 DI 是为了使用 UE 5.8 已验证的整数原子加法。
- `clear_before_non_iteration_stage=True`，每帧清空当前密度；连续轨迹来自大量不同年龄粒子的空间分布，不来自 RT 历史累积。
- Niagara System 开启 `Fixed Tick Delta=0.01667s`。可变时间步曾导致静止视口下整张面片亮度脉动；固定 60 Hz 后消失。
- 不允许在构建方向/深度矩的粒子 Raster Stage 中同时读取该 Grid 并沿曲线再次写入。方向场必须先完成原子归约，再由后续 Resolve/材质消费，避免同阶段 UAV 读写竞争。

## 5. Niagara 数据生成

### 5.1 缓存真实流向

当前系统在 `Solve Forces and Velocity` 后执行 `Velocity = 0`。该行为可以继续保留，但必须在清零前缓存本帧位移：

```text
PositionBeforeSolve = Particles.Position
Solve Forces and Velocity
FlowDelta = Particles.Position - PositionBeforeSolve
FlowVelocity = FlowDelta / max(DeltaSeconds, Epsilon)
Particles.Velocity = 0
```

正式 Splat 不直接读取清零后的 `Particles.Velocity`。

### 5.2 屏幕空间方向

```text
UV0 = Project(PositionAfterSolve)
UV1 = Project(PositionAfterSolve - FlowDelta)
DeltaPx = (UV0 - UV1) × RTSize
Direction = normalize(DeltaPx)
SpeedPx = length(DeltaPx)
```

当 `SpeedPx` 很小时，使用上一有效方向、Curl 方向或稳定的短圆核，不能对零向量归一化。

### 5.3 各向异性高斯核

对待写入像素 `x`：

```text
t = 屏幕流向
n = perpendicular(t)
d = x - ParticleCenter
u = dot(d, t)
v = dot(d, n)

Weight = exp(-0.5 × ((u / SigmaLong)^2 + (v / SigmaShort)^2))
```

性质：

- 核中心密度最高；
- 两端自然收尖；
- 横向保持窄；
- `SigmaLong / SigmaShort` 决定拉丝比例；
- 多个核相加后，重叠处自然形成致密烟心。

建议首版参数：

| 参数 | 默认值 | 作用 |
| --- | ---: | --- |
| `MinLengthPx` | 2 | 静止或低速粒子的最短长度 |
| `VelocityLengthScale` | 1.5 | 屏幕位移到长轴的倍率 |
| `MaxLengthPx` | 40 | 防止高速粒子形成整屏长条 |
| `WidthPx` | 1.25 | 横向标准差 |
| `GaussianCutoffSigma` | 2.5 | 超出范围停止写入 |
| `DensityPerParticle` | 1 | 单粒子密度贡献 |
| `MinDirectionSpeedPx` | 0.05 | 方向有效阈值 |

所有参数必须开放到 Niagara User Parameters 或材质实例，不允许散落在 HLSL 常量中。

## 6. 累积语义

V2 不能继续使用二值占用或 Last Writer Wins。否则 1 个粒子和 100 个重叠粒子数值相同，材质无法得到“中间致密”的层次。

正式要求：

```text
Density(x) = Σ ParticleWeight_i(x)
```

当前实现为 Niagara 内部 `RasterizationGrid3D(2048×2048×1)` 固定点整数原子加法：

```text
AtomicContribution = round(Weight × DensityQuantization)
AtomicAdd(GridDensity, AtomicContribution)
```

Resolve 阶段再除以 `DensityQuantization` 写入 RGBA16F SimRT。这样避免 GPU 粒子并发覆盖造成的不确定结果，同时仍不创建外部 RT 资产。

G5 在同一权重 `w` 下增加方向与深度矩：

```text
Density       += w
TensorCos2    += w × cos(2θ)
TensorSin2    += w × sin(2θ)
DepthMoment1  += w × z
DepthMoment2  += w × z²
FrontInvDepth  = max(FrontInvDepth, 1 - z)
```

其中 `z` 是当前相机下归一化的线性 View Depth，范围为 `[0,1]`，不能直接把世界单位深度或其平方写入固定点 Grid，否则容易溢出。`FrontInvDepth` 使用 AtomicMax，使清零值 `0` 自然表示“无样本”；只有高于 `FrontDepthWeightThreshold` 的核贡献才参与最近深度，避免高斯极弱尾部把前表面扩到不合理范围。

方向张量使用双角度表示而不是普通 Velocity 平均。相反运动方向在视觉上仍属于同一根线，普通平均会互相抵消，而 `cos(2θ)/sin(2θ)` 没有正负方向歧义。

`TensorCos2` 与 `TensorSin2` 需要有符号整数原子加法。若 UE 5.8 的目标 Raster DI 路径不能稳定执行 signed AtomicAdd，必须改用正负分量拆分；不得给每次贡献增加固定 Bias，因为 Bias 会随粒子数量累积并污染方向。

各属性必须独立定义固定点倍率和最坏情况溢出上限。Density/方向矩默认沿用 Q10；归一化深度矩与 FrontInvDepth 可使用更高精度，但必须以 32-bit 原子存储可承受的最大重叠粒子数为准。任何 Saturation/Clamp 都必须在 Debug Gate 中可见，不能静默截断。

这里仍只使用 Z=0 单切片。若增加属性后该 DI 无法稳定支持，再评估第二个当前帧 Grid 或 SM6 原子浮点；不得退回非原子的普通覆盖写入。

## 7. Grid 与 SimRT 通道

### 7.1 当前 G4 密度基线

当前已落地的原始输出：

| 通道 | 内容 |
| --- | --- |
| R | 高斯 Splat 累积密度 |
| GBA | 保留为 0 |

该基线必须保留为 `DebugRaw` 与 G5 回退路径。G5 不改变 Density 的加法语义，也不降低 2048×2048 分辨率。

### 7.2 G5 Main RT

`User.SSPR_SimRT` 继续为 2048×2048 RGBA16F、Bilinear、Mip Disabled，但 Resolve 扩展为：

| 通道 | 内容 |
| --- | --- |
| R | Density |
| G | `TensorCos2 / max(Density, ε)` |
| B | `TensorSin2 / max(Density, ε)` |
| A | Mean View Depth |

材质中：

```text
Theta = 0.5 × atan2(B, G)
Tangent = (cos(Theta), sin(Theta))
Coherence = saturate(length(float2(G, B)))
```

`G/B` 同时保存主方向和方向一致性；它们不能在 Resolve 中提前归一化成单位向量，否则会丢失 Coherence。

### 7.3 G5 Aux RT

新增 `User.SSPR_AuxRT`，它是 Niagara 自管的当前帧辅助纹理，不是外部资产，也不是 History。质量基线优先使用 2048×2048 RGBA16F；若 UE 5.8 的 Niagara RT DI 已验证支持 RG16F，可在不改变数值 Gate 的前提下改用 RG16F。

| 通道 | 内容 |
| --- | --- |
| R | Depth Sigma / 局部前后厚度 |
| G | Front View Depth |
| B | 预留：Mean SpeedPx 或散射控制 |
| A | 预留 |

```text
MeanDepth = DepthMoment1 / max(Density, ε)
Variance  = max(DepthMoment2 / max(Density, ε) - MeanDepth², 0)
DepthSigma = sqrt(Variance)
FrontDepth = Density > ε ? 1 - FrontInvDepth : 0
```

空像素必须输出明确的无效标记或零 Coverage；材质不能把空像素的 Depth=0 当作贴近相机的烟雾。

增加 Aux RT 的预计显存成本为一张 2048² RGBA16F 纹理约 32 MiB，另有 Niagara/Grid 中间存储。G5 视觉 Gate 通过前接受该质量成本；格式压缩和属性合并属于后续 G6 性能工作。

### 7.4 Resolve 与绑定规则

- Stage2 每帧完整覆盖 Main/Aux RT，不能依赖上一帧残留。
- Main/Aux 必须使用相同分辨率、ViewportUV 和半 Texel 边界规则。
- Renderer 保留 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget`，新增 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`。
- Aux 绑定失败时材质必须能切回 G4 Density-only 路径，不能输出全黑或读取默认白纹理。
- 禁止把 Main/Aux 做成 A/B Ping-pong；它们描述同一当前帧的不同字段。

## 8. 材质函数架构

G4 当前采用确定性的 LOD0 空间重建，不依赖 SimRT 自动 Mip。原 V1 Mip 资产继续留在冻结快照中；V2 的 `MF_SSPR_MipPyramidDensity` 为保持既有函数调用接口暂未更名，但内部已经替换为 7×7/13×13 LOD0 二项式核，旧 MipBias 输入不再参与计算。

2026-07-29 的资产复核发现，该 219-tap 函数虽然存在，但父材质仍连接旧 3×3/5×5 链。现已把 `MF_SSPR_MipPyramidDensity.Scales` 真正接入 `MF_SSPR_DensityShape` 并通过材质编译 Gate；旧调用节点暂时作为未连接资产保留，视觉 Gate 后再清理。

当前函数链：

| 材质函数 | 职责 |
| --- | --- |
| `MF_SSPR_RawDensity` | 读取原始各向异性密度 |
| `MF_SSPR_MipPyramidDensity` | 当前内部为 LOD0 7×7 Medium + 13×13 Body 空间重建；名称待收口 |
| `MF_SSPR_DensityShape` | 黑位、对比度、细节和边缘整形 |
| `MF_SSPR_DensityGradientLighting` | 密度梯度体积明暗 |
| `MF_SSPR_ScreenEdgeMask` | 屏幕边缘安全衰减 |
| `MF_SSPR_SmokeResolve` | Beer–Lambert 消光与最终颜色 |

父材质只负责编排；全部视觉参数放到 `MI_SSPR_AnisotropicSplat_HQ`。

G5 审批通过后新增独立函数，不破坏现有函数接口：

| 新函数 | 职责 |
| --- | --- |
| `MF_SSPR_DecodeFlowDepth_G5` | 从 Main/Aux RT 解码 Density、Tangent、Coherence、Mean/FrontDepth、DepthSigma |
| `MF_SSPR_StreamlineFilamentDensity_G5` | 沿当前帧方向场做双向 RK2 曲线积分、两端渐细和深度双边过滤 |
| `MF_SSPR_DepthAwareVolumeLighting_G5` | SceneDepth 软交界、深度/密度梯度受光与保守环境光 |
| `MF_SSPR_G5DebugViews` | Density、Tensor、Coherence、MeanDepth、DepthSigma、FrontDepth 独立可视化 |

不得原地删除并重建已发布函数的全部输入节点。G5 使用新的干净函数资产，通过父材质显式编排；G4 路径由静态或标量调试开关保留到 G5 最终验收。

### 8.1 三层输出

```text
G4 Filament = 获得 Medium/Body 邻域支持的原始各向异性密度
G5 Filament = 深度约束的当前帧 Streamline Density
Medium      = LOD0 7×7 二项式空间核
Body        = LOD0 13×13 二项式空间核

FinalDensity = FilamentWeight × Filament
             + MediumWeight × Medium
             + BodyWeight × Body
```

不允许使用一个超大各向同性 Blur 把三层全部替代。

当前 G4 候选为 `Filament/Medium/Body = 0.06/0.58/0.36`、Medium/Body 半径 `16/52 px`、`BlackPoint=0.003`、`DensityGain=1.4`、`Contrast=1.10`、`Extinction=1.7`、`OpacityScale=0.82`。它降低了粒子感，但画面明显过度模糊，因此只作为技术回退基线，不是最终视觉参数。

G5 跑通 Streamline 后，Medium/Body 预期收窄到约 `10～12 / 36～42 px`，再逐步恢复 Filament 权重。精确数值必须由用户观察确认，不能在方向场尚未通过 Debug Gate 前提前固化。

### 8.2 无历史 Streamline Filament

Streamline 从当前像素向正、反两个方向积分。方向张量是无符号线场，每次采样后必须让新切线与上一步切线同向：

```text
if dot(NewTangent, PreviousTangent) < 0:
    NewTangent = -NewTangent
```

首版使用 RK2 Midpoint：

```text
MidUV  = UV + 0.5 × StepPx × Tangent(UV) × TexelSize
MidDir = AlignSign(Tangent(MidUV), PreviousDir)
NextUV = UV + StepPx × MidDir × TexelSize
```

正反方向分别追踪固定最大步数。首个质量候选：

| 参数 | 候选值/范围 |
| --- | ---: |
| `StreamlineHalfSteps` | 6 |
| `StreamlineStepPx` | 3 px |
| `StreamlineHalfLengthPx` | 18 px |
| `StreamlineWidthPx` | 1.25～2 px |
| `StreamlineCoherenceMin` | 0.20～0.30 |
| `StreamlineMaxTurnPerStep` | 30°～40° |
| `StreamlineTaperPower` | 2 |
| `DepthBilateralScale` | 1.5～2.5 × DepthSigma |

核权重使用中心最高、两端归零的紧支撑函数。首版必须正反对称渐细，不区分“头/尾”；这样不依赖张量特征向量的符号，转镜头时更稳定。只有在 signed flow 经过独立稳定性验证后，才允许增加前后不对称尾部。

每个采样位置可使用中心加左右各一个横向 tap 形成窄截面，但不得扩大成二维大 Blur。遇到以下条件时通过 Active Mask 停止后续贡献：

- Direction Coherence 低于阈值；
- Density 低于阈值；
- 与起点或上一点的深度差超过 Depth Gate；
- 单步转角超过上限；
- UV 越过半 Texel 安全范围。

Shader 循环必须有固定编译上限。越界 tap 权重为零，不能 Clamp 后继续累计，否则会在屏幕边缘形成拉花。

### 8.3 深度约束与纵深受光

深度场首先用于重建约束，而不是直接把烟雾画成硬表面：

```text
DepthWeight = exp(
    -0.5 × ((SampleMeanDepth - CenterMeanDepth) / SafeDepthSigma)²
)
```

`SafeDepthSigma` 由中心/样本的 DepthSigma 与最小容差共同决定。这样可以连接同一深度层的曲线，同时抑制屏幕上相邻、实际前后相隔很远的烟丝互相污染。

最终受光使用低频密度梯度与粒子深度梯度的保守组合：

- 通过相邻像素的 View Depth 重建近似 View-space Position/Normal；
- DepthSigma 只控制厚度和柔软度，不直接生成硬轮廓；
- `AmbientLight` 首版不得低于 `0.70`；
- `DepthLightStrength` 首版限制在 `0.15～0.30`；
- 仍由 Beer–Lambert Density 决定主要透明度；
- 不向 Translucent 材质写 PixelDepth，不把伪表面当作真实深度缓冲。

FrontDepth 与 opaque SceneDepth 用于遮挡和 Soft Intersection。无有效粒子深度时必须回退到零 Alpha，不得把默认深度解释为近景烟雾。

## 9. 为什么首版不做邻域 PCA

论文中的 PCA 各向异性核适合从邻域粒子分布推断主轴，但当前 Niagara 已经拥有本帧真实运动位移。

首版直接使用屏幕速度的原因：

- 不需要 Neighbor Grid 和邻域查询；
- 方向与当前 Curl 运动完全一致；
- 成本和实现风险明显更低；
- 更适合烟雾拉丝，而非液体表面重建。

PCA 作为后续可选升级：只在低速、方向不稳定或需要根据粒子团形态修正方向时启用。

## 10. 实施里程碑

### G0：版本隔离

- 状态：已完成。
- V1 冻结快照自包含。
- V2 工作副本自包含。
- 原正式系统不受后续开发影响。

### G1：方向缓存与可视化

- 状态：数据缓存与屏幕位移保活已完成；独立方向 Sprite 可视化不再作为阻塞项。
- 新增 `FlowDelta` / `FlowVelocity`。
- 在 Velocity 清零前缓存。
- 使用 Velocity-Aligned 调试 Sprite 验证方向和长度。
- 尚不修改正式 Grid 输出。

### G2：单粒子高斯 Splat

- 状态：旋转椭圆高斯写入已安装并进入正式密度链；基础视口结果已通过。
- 建立旋转椭圆高斯写入。
- 使用单粒子、低 SpawnRate 检查中心、尖端、横向宽度和速度响应。
- Raw RT 必须直接呈现椭圆尖丝。

### G3：原子密度累积

- 状态：已完成技术 Gate。2048² 原始回读得到 41,353 个非零像素，密度总量约 23,532.89，最大值约 4.20。
- 接入当前 `RasterizationGrid3D` Z=0 单层或等价的无竞争累积方案。
- 验证 1、4、16 个重叠粒子的中心密度单调增加。
- 长时间运行不铺满，每帧正确清理。

### G4：细丝 + 烟体材质

- 状态：技术链已完成；视觉结果降低了粒子感，但因过度模糊、缺少尖细流丝和纵深而未通过最终 Gate。
- 各向异性密度作为 Filament。
- 已确认 LOD0 7×7/13×13 函数真正接入最终 DensityShape。
- 已加入邻域支持门控和低密度抑制，作为 G5 可回退基线。

### G5：方向张量、粒子深度场与无历史 Streamline

- 状态：整体方案已批准。G5.1/G5.2 字段 Gate 已通过；旧 G5 Streamline 是当前人工偏好显示基线。FieldRecon V1 的当前帧归一化场重建与强深度传输未通过用户视觉对照，已降为实验候选。Raster 近景性能 Gate 未通过。

#### G5.1：方向/深度原子矩

- 状态：已实施，字段 Debug Gate 已由用户确认。
- 扩展 Raster Grid 属性，累积 Density、双角度方向张量、Depth Moment 1/2 与 FrontInvDepth。
- 保持 Raster Stage `WritesParticles=False`。
- 分别验证 1、4、16 粒子下密度与矩的确定性。

当前实现使用 `2048×2048×1`、6 属性、`Precision=65535` 的 RasterizationGrid3D。属性 0～4 分别为 Density Q10、TensorCos2 Q10、TensorSin2 Q10、DepthMoment1 Q16、DepthMoment2 Q16；属性 5 使用 `InterlockedMaxFloatGridValue` 累积归一化前沿逆深度。深度归一化范围由 `User.SSPR_DepthNearUU/DepthFarUU` 控制，当前默认 `0/10000 uu`。

**Gate：** Tensor/Coherence Debug 随 Curl 方向连续旋转；Mean/FrontDepth 随相机距离单调变化；空像素无伪深度；长时间运行不累积。

#### G5.2：Main/Aux Resolve 与绑定

- 状态：已实施，字段 Debug Gate 已由用户确认。
- Main RT 输出 Density、Tensor XY、MeanDepth。
- Aux RT 输出 DepthSigma 与 FrontDepth。
- 新增 Renderer 的 `TrajectoryAuxTexture` 子变量绑定。
- 保留 Main RT 的 G4 Density-only 回退。

当前 Main RT 布局为 `R=Density, G/B=TensorCos2/Sin2, A=MeanDepth`；Aux RT 布局为 `R=DepthSigma, G=FrontDepth, B=Reserved, A=Coverage`。两张 RT 均为 Niagara 自管 `2048×2048 RGBA16F`、Bilinear、无 Mip，并在 Resolve 中每帧完整覆盖。独立干净版本 `MF/M/MI_SSPR_G5_FieldDebugV2` 提供 Density、DirectionTensor、Coherence、MeanDepth、DepthSigma、FrontDepth 与四宫格模式；当前 Renderer 临时绑定 Debug V2 MI，四宫格依次为方向/一致性、MeanDepth、DepthSigma、FrontDepth。旧的无 V2 后缀 Debug 原型因 UE 材质函数原地重建残留节点而仅保留为未引用诊断资产，不参与当前渲染。

**Gate：** 两张 RT 同帧、同分辨率、同 ViewportUV 对齐；重绑/冷启动后都非空；Niagara 与材质零错误、零警告。

#### G5.3：Streamline Filament

- 状态：首个生产候选已实施并绑定，等待用户最终烟雾视觉确认。
- 新建独立 G5 函数，使用双向 RK2、符号连续、紧支撑渐细和固定最大步数。
- 使用 Coherence、Density、Depth 与 Curvature 共同停止。
- 不在 Raster 写入阶段采样未完成的方向 Grid。

当前候选为 `MF_SSPR_G5_StreamlineDensityV1`：每侧固定上限 8 步、默认活动 6 步、步长 3 px；从双角度张量解码无向切线，并在 RK2 中用前一步方向维持符号连续。只对 Guidance 做 3×3 小范围扩展，Density 仍由沿流线 Gather；使用 Coherence、曲率、MeanDepth/DepthSigma 双边权重、双侧支持和渐细权重抑制孤立核。生产父材质/MI 为 `M_SSPR_AnisotropicSplat_G5` / `MI_SSPR_AnisotropicSplat_G5_HQ`，G4 材质与 MI 保持原样作为回退。

**Gate：** 相同或更低的 Medium/Body 半径下，尖丝比 G4 清晰，曲线能跟随局部 Curl，且不恢复独立粒子点。

#### G5.4：深度融合与受光

- 状态：首个轻量候选已随 G5.3 接入，等待视觉调参；SceneDepth 软交界尚未启用。
- 深度双边权重阻止跨层卷积。
- FrontDepth 接入 opaque SceneDepth 软交界。
- 深度/密度梯度只提供低强度体积受光，保持高环境光。

当前 `MF_SSPR_G5_DepthCueV1` 已用 MeanDepth、FrontDepth 与 DepthSigma 提供低强度前后亮度和厚度衰减；Streamline 本身已启用粒子深度双边约束。为避免重新出现 G4 中央暗块，本轮仍不启用高强度密度梯度光照，也不写 Translucent PixelDepth。

**Gate：** 前后层次可辨、地面交界柔和、相机转动时没有深度闪烁或二维硬片感。

#### G5.5：Sparse Raster 近景性能 Gate

- 状态：失败并已回滚。短时性能数据仅保留为诊断参考，不能作为通过结论。
- 不降低 `2048×2048` Raster/Main/Aux 分辨率，不降低 `50,000/s` SpawnRate、5 秒 Lifetime 或当前材质采样数。
- 不关闭 Fixed Tick，不引入 History，也不改变 Main/Aux 六属性语义、Q10/Q16 定点倍率或 Renderer 材质绑定。

旧 Dense Raster 每粒子固定枚举 `49×11=539` 个候选，并对每个有效样本最多执行 5 次 `InterlockedAdd` 和 1 次前沿深度 `InterlockedMax`。近景 `.profViz` 中约 `280,839→300,010` 个粒子时，单次 Raster 为 `17.70～18.88 ms`；同一渲染帧因 Fixed Tick 补做了 24 次模拟，所以 Raster 事件累计超过 100 ms。这里不是单个 Raster Pass 突然变成 100 ms，而是单次阶段已经超过 `16.67 ms` 后触发的补步追帧螺旋。

当前 Sparse Raster 保留相同高斯形状参数和六属性输出，但做两项有界优化：

1. 在进入候选循环前完成投影有效性、近平面和屏幕扩展边界剔除，完全离屏粒子不再执行空循环。
2. 使用最多 `25×5=125` 个稀疏采样代表原 `49×11` Dense 核；先计算 Dense 可见核的可分离权重总和，再按 Sparse 权重总和做单粒子质量归一化，因此降低原子操作数量而不靠减少粒子、缩小 RT 或扩大后处理模糊换性能。

在约 `251,666～253,333` 个活动 GPU 粒子下，程序化 `ProfileGPU` 曾得到 Sparse Raster 首次 `0.930 ms`、随后 `0.559/0.563 ms`，Resolve 为 `0.153～0.158 ms`。但该数据来自同一自动化会话内的短时运行；用户随后观察到效果完全消失，跨请求回读证实全部 Main/Aux 为零，因此这组数字只能证明空/失效路径很快，不能证明有效 Raster 达到该性能。

失败后发现活动组件累积为 `2 Raster + 4 RT`，原地恢复 Dense HLSL和替换干净 V2 组件仍全零；复制 System 与 V3 复制关卡也不能作为可靠运行回滚。最终从修改前同包名二进制建立 `/Game/SSPR_Validation/Recovery/DenseG5_20260730/NS_SSPR_AnisotropicSplat_Main`，用两次独立 MCP 请求完成“生成候选→让渲染线程实际跑帧→RT 回读→替换 Actor”。Dense 恢复与 FieldRecon Connected 都通过技术 Gate，但用户对照后明确认为 FieldRecon 的 Coverage/深度传输使近景稀疏支撑、短丝和孔洞更显眼，因此 Renderer 1 已切回 `MI_SSPR_AnisotropicSplat_G5_HQ`。最终组件严格为 `1 Raster + 2 RT`，另有 1 个正式遗留 Grid2D；System `UpToDate`、零错误零警告。

**Gate：** 用户在相同近景、转镜、平移和拉远条件下确认 Sparse 与修改前 V3 的主体宽度、细丝方向、密度连续性和纵深没有不可接受退化。若出现规则点列、核质量跳变或边缘缺口，优先调整 Sparse 样本布局/归一化，不降低粒子数或分辨率；必要时从 V3 或已记录的 Dense HLSL 恢复。

### G6：视觉与性能 Gate

- 首先冻结最高质量参数。
- 最高质量通过后，再建立 High / Medium / Low 档位。
- 保守 Sparse V2 已通过有效 Main/Aux Gate：最大原子写入候选 `539→231`。但候选为了精确质量守恒仍执行 `49+11+33+7` 次一维权重求和，并在写入循环中保留大量 `exp()`；此前 `0.697～0.715 ms/步` 的 Profile 没有相机姿态，不能与近景 Dense `17.70～18.88 ms/步` 直接比较。后续必须在固定近景相机下做 Dense/Sparse V2 A/B，性能 Gate 暂不判通过。
- UE 5.8 源码确认 `fx.Niagara.SystemSimulation.MaxTickSubsteps` 控制 Fixed Tick 系统每帧最大子步数。当前会话临时设为 `4`，保留 `0.01667s` Fixed Tick，仅阻止慢帧扩张为几十次补步；同机位确认后再决定是否写入项目配置。

当前尚未通过的视觉项：连续尖细流丝、中尺度连接、柔软但不糊的烟体、纵深与最终受光、静止/转镜头/拉远、屏幕边缘及关闭 TAA/TSR。Fixed Tick 已解决整片闪烁，但不能替代这些画面 Gate。

## 11. 验收条件

### 单粒子 Gate

- 核中心值高于两端和横向边缘。
- 长宽比随屏幕速度连续变化，无突然翻转。
- 两端为渐隐尖端，不是硬矩形或圆头胶囊。
- 静止粒子不会产生 NaN 或随机方向。

### 密度 Gate

- 1、4、16 粒子重叠时密度严格单调增加。
- 不出现 Last Writer Wins、随机闪烁或并发覆盖条纹。
- 停止 Spawn 后按粒子 Lifetime 自然消失。
- 运行数分钟后 Grid 不会铺满。

### 方向场 Gate

- Tensor Debug 的主方向与粒子 Curl/FlowDelta 一致。
- 相反方向粒子叠加时 Coherence 不因符号抵消而错误归零。
- 低 Coherence 区域不会产生随机长线、NaN 或整屏旋涡。
- 左右转镜头、平移和拉远时方向场与当前帧粒子重投影保持一致。

### 深度场 Gate

- MeanDepth、FrontDepth 与粒子真实 View Depth 单调一致。
- DepthSigma 在单一薄层接近零，在前后分散粒子重叠处增大。
- 空像素不会输出近景 FrontDepth。
- 深度双边过滤能阻止相隔明显的前后烟丝互相连接。
- SceneDepth 交界柔和，无硬切、穿地或整块消失。

### Streamline Gate

- 中心最强、正反两端连续渐细，不出现胶囊形硬圆头。
- 曲线跟随局部方向变化，不只是更长的直椭圆。
- 方向符号翻转时积分轨迹连续。
- 关闭 TAA/TSR 后仍保留主要弯曲细丝。
- 屏幕边缘所有越界 tap 贡献零，无 Wrap/Clamp 拉花。

### 最终画面 Gate

- 标准相机距离下不再能逐个辨认圆形粒子。
- 可同时观察到尖细流丝、致密核心和柔软宽烟体。
- 前后烟丝具有可辨别的深度层次，不再像一张均匀白色面片。
- 深度受光只增强纵深，不产生硬塑料表面或大块伪阴影。
- 左右转动、平移和拉远相机时投影保持对齐。
- 屏幕边缘不 Wrap、不 Clamp 拉花。
- 关闭 TAA/TSR 后仍保留连续拉丝结构。
- 固定 Niagara 60 Hz 时间步后，静止与交互视口均不出现整片亮度脉动。

## 12. 高品质基线与预算

第一阶段优先最高品质：

- 2048×2048 内部 Grid / SimRT；
- G5 允许一张额外的 2048×2048 Niagara 自管 Aux RT；不允许 History A/B；
- 原始设计目标约 25,000 个存活 GPU 粒子；当前性能 Gate 的实际高品质负载为 `SpawnRate=50,000/s`、Lifetime=`5s`，稳态约 250,000 个存活粒子；
- 最大拉伸长度 40～48 px；
- 横向宽度约 1～2 px；
- Main RT 为 RGBA16F；Aux RT 首版按 RGBA16F 验证，格式压缩后置；
- 原子密度固定点精度至少 10 bit 小数；
- 材质保持最高质量 LOD0 7×7/13×13 空间重建，并增加固定上限的双向 RK2 Streamline；
- G5 初始预算为每方向 6 步、每步最多 3 个横向密度 tap；优化必须在视觉 Gate 通过后进行；
- 深度受光先保持高环境光和低强度，分别通过 Density/Flow/Depth Debug 后再合成。

高品质 Gate 通过前，不以降分辨率、减少粒子数或恢复圆形大模糊作为优化手段。

## 13. 主要风险与应对

| 风险 | 应对 |
| --- | --- |
| 原子写入不支持浮点 | 使用当前 RasterizationGrid3D Z=0 单层固定点整数累积 |
| 每粒子覆盖像素过多 | 限制 MaxLength、GaussianCutoff，并采用有界循环 |
| 高速产生整屏直线 | 长度 Clamp；速度响应使用平滑曲线 |
| 低速方向闪烁 | 最小速度阈值和上一有效方向回退 |
| 线很多但烟体太薄 | Filament、Medium 与 Body 分层混合 |
| 重新变成软泡 | 降低各向同性 Body 权重，检查 Raw Splat 是否已经拉伸 |
| 方向场正负抵消 | 使用二阶方向张量，不直接平均 Velocity |
| signed 方向矩原子累加不可用 | 正负分量拆开累积；禁止每贡献加 Bias |
| 同阶段读取未完成方向场 | Raster 只累积矩，后续 Resolve/材质读取；禁止同一 UAV 阶段边建边采 |
| Streamline 在 Curl 中打圈或突折 | 固定步数、单步最大转角、Coherence/Density/Depth Stop Mask |
| 跨深度层错误连接 | MeanDepth + DepthSigma 双边权重，必要时以 FrontDepth 进一步裁剪 |
| 空像素被解释为近景深度 | 独立 Coverage/密度有效性判断，空像素输出零 Alpha |
| View Depth 固定点溢出 | 累积归一化深度及其平方，不使用原始世界单位 z² |
| 额外 Aux RT 显存与带宽过高 | 高品质 Gate 后优先验证 RG16F、属性合并和局部范围，不提前降质量 |
| 深度梯度看成硬表面 | 高 Ambient、低 DepthLightStrength，与密度梯度混合且不写 PixelDepth |
| 相机移动产生伪速度 | 使用同一帧一致的当前相机矩阵投影前后位置；相机运动项单独审计 |
| 整张面片忽明忽暗 | 固定 Niagara 60 Hz 时间步；再分别排查 RT/Mip/时序抗锯齿，不用右键交互掩盖 |

## 14. 审批状态

### 14.1 已批准并已实施

用户已批准以下四项：

1. 允许 V2 使用内部 RasterizationGrid3D Z=0 单层固定点原子加法，仍不创建外部 RT。
2. 允许在 Velocity 清零前缓存 `FlowDelta/FlowVelocity`，但保留现有清零行为。
3. 接受“各向异性 Splat 负责细丝，多尺度空间重建负责宽烟体”的职责划分；当前高品质基线不依赖 SimRT Mip。
4. 先完成密度单通道 G1～G4；方向张量 G5 只在画面仍断裂时启用。

G4 结果已经满足“触发 G5 评估”的条件：粒子感有所改善，但过度模糊、流丝不足且完全缺少纵深。

### 14.2 已批准的 G5 决策

用户已批准以下整体方案：

1. 允许扩展当前 Niagara Raster/Resolve 数据链，增加方向张量和粒子深度矩；不回退旧 Ping-pong。
2. 允许在现有 Main RT 外增加一张 Niagara 自管 Aux RT，用于 DepthSigma/FrontDepth；两张纹理都只保存当前帧。
3. 方向使用无正负歧义的双角度张量，不直接平均带符号 Velocity。
4. Filament 从“直椭圆 Core”升级为材质内双向、对称渐细、固定步数的 RK2 Streamline；禁止在同一 Raster Stage 读取未完成方向场。
5. Streamline 使用 MeanDepth/DepthSigma 做双边过滤，FrontDepth 负责 SceneDepth 软交界。
6. 深度场只提供轻量纵深受光与遮挡提示，不写 Translucent PixelDepth，不实现完整体积求解。
7. G4 当前资产继续作为可回退基线；G5 新建独立函数与 Debug View，视觉通过前不清理旧接口、不降低 2048 分辨率、粒子数或现有多尺度采样质量。

G5.1/G5.2 字段生成与 Debug Gate 已由用户观察确认，随后 G5.3/G5.4 与 Visual V2 均已接入最终烟雾且保持无 History。Visual V2 技术 Gate 全部通过，但用户近景截图仍能辨认稀疏末端粒子，主体纵深也不足，因此该实现不算最终视觉 Gate 通过。

### 14.3 已批准的当前帧归一化场重建

Visual V2 的失败说明，仅在最终材质中对离散密度做更长 RK2 采样、五通道横向 Gather、宽尺度 Blur 与孤立核门控，仍然是在离散粒子结果上做后处理；它既不能稳定估计局部采样间距，也会在“保留末端”与“抹成宽糊块”之间摇摆。后续开发按以下顺序推进，并保持 V3 冻结资产不变：

1. Raster 继续输出当前相机下的紧支撑粒子贡献、二阶方向张量与深度矩，不读取 History，不恢复 Ping-pong。
2. 先对 Coverage、方向张量和深度矩做当前帧、密度加权的局部正则化，低支持区明确输出低置信度，不让单粒子随机方向直接驱动长核。
3. 使用正则化切线执行自适应、归一化的场对齐卷积：Density 作为分子，Coverage/支持度作为分母和置信度，核半径由局部支持缺口与 Coherence 限制；只在同深度层内连接。
4. Filament、Medium、Body 都从同一连续重建场分频得到，不再把 Raw 单粒子 Core 作为可见兜底，也不再用大半径各向同性 Blur 掩盖断裂。
5. 由 FrontDepth、MeanDepth 和 DepthSigma 估计前表面、后层与厚度；深度先约束连接，再驱动非饱和的透射、自遮蔽和色调变化，使纵深在最终白烟中可见。
6. 材质只负责最终重建、分频和着色；若材质采样成本或场一致性仍不满足 Gate，再把相同的无历史算子迁入单独的当前帧 Resolve Stage，而不是增加跨帧反馈。

该路线继续保持 2048×2048、现有粒子数、RGBA16F Main/Aux、Bilinear、Mip Disabled 和 Fixed Tick 0.01667 s。视觉 Gate 通过前不做分辨率、粒子数或采样质量降级。

首个候选 `MF_SSPR_G5_NormalizedFieldReconstructionV1` 已按该路线接入：查询点先用 3×3 Coverage/密度加权邻域正则化方向、MeanDepth、FrontDepth 与 DepthSigma，再执行每侧最多 8 步、每步 5 条横向通道的无历史场对齐采样；每个 Filament/Medium/Body 频段分别累积分子与置信度分母，并以双侧支持和支持包络抑制孤立粒子。它不调用旧 `MF_SSPR_MipPyramidDensity`，也不调用 G5 Streamline V1/V2。`MF_SSPR_G5_DepthTransportLightingV1` 由 Front/Mean/Sigma 推导 BackDepth、厚度与透射，并输出 RGB 深度色调/受光因子。初始 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ` 已完成技术 Gate，并由首轮用户截图进入下一轮 Connected 参数候选。

首轮用户截图确认圆点已明显转化为顺流向短丝，但仍存在刷毛/排线、低密度区域过透明、背景穿孔和 Medium/Body 支撑不足。为隔离算法与参数问题，保留初始 MI 不变，新增并绑定 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`：沿流步距由 `3.25` 收紧到 `2.25 px`，Medium/Body 横向通道由 `4/13` 收紧到 `2.75/8.5 px`，SupportGain 由 `0.38` 提高到 `0.85`，降低 Filament、提高 Medium/Body，关闭 Detail/Edge 锐化并把 BlackPoint 降到 `0.001`。该候选专门验证排线和孔洞能否收敛，不修改 Niagara 字段契约。

后续用户在恢复 System 上直接对照旧 G5 HQ 与 FieldRecon Connected，明确选择旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 作为当前视觉基线。判断依据是旧 G5 的主体与外缘更连续；FieldRecon 虽增强了深度色调和局部结构分离，却同时把稀疏 Coverage、短丝与孔洞显著化，主观粒子感更重。当前只撤下 FieldRecon 的 Coverage 归一化和强 DepthTransport，Main/Aux 的方向与深度字段仍继续生成；旧 G5 原有的低强度 `MF_SSPR_G5_DepthCueV1` 保留。若再推进深度表现，必须先在不削薄 Medium/Body 连续支撑的前提下做独立 A/B，不得直接覆盖该基线。
