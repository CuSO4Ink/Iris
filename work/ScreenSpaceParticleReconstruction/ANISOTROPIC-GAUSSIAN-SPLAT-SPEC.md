# 各向异性高斯 Splat 拉丝烟雾规格

- 版本：0.3
- 日期：2026-07-29
- 状态：用户已批准；G0～G3 已完成并通过基础视口结果，G4 LOD0 多尺度烟雾材质已安装，等待最终视觉 Gate
- V1 冻结快照：`/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729`
- V2 当前开发目录：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2`
- V2 Niagara：`NS_SSPR_AnisotropicSplat_Main`
- V2 显示材质：`M_SSPR_AnisotropicSplat_Display`
- V2 调参实例：`MI_SSPR_AnisotropicSplat_HQ`

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

## 4. 总体管线

```text
Niagara GPU 粒子运动
    -> Solver 前记录 PositionBeforeSolve
    -> Solver 后计算 FlowDelta
    -> 在 Velocity 清零前缓存 FlowVelocity / FlowDelta
    -> 当前与上一位置分别投影到屏幕
    -> 得到屏幕切线、速度和长度
    -> 各向异性高斯 Splat 累积到内部 Grid
    -> Resolve 为 Niagara 自管 SimRT
    -> 材质细丝层 / 烟体层 / 密度整形 / 光照
    -> Emitter SourceMode 面片显示
```

不引入外部 Content Browser RenderTarget，不恢复 Blueprint Ping-pong，不依赖历史画面产生拖尾。

### 4.1 当前已落地的 GPU 管线

```text
Particle Spawn/Update
    -> 保存 Position 与 SSPR_ScreenDeltaUV
    -> Stage1 从 Position 用当前 PrimaryView.WorldToClip 重新投影
    -> RasterizationGrid3D(2048×2048×1) Q10 原子累加高斯密度
    -> Stage2 逐像素 Resolve 到 Niagara 自管 SimRT
    -> Emitter SourceMode 显示面片材质采样
```

实现约束：

- Raster Stage 只写 `User.SSPR_DensityRaster`，必须保持 `WritesParticles=False`；不得为调试标记回写 `Particles.*`。
- 当前 UE 5.8 编译器会裁掉“只在 Custom HLSL 副作用中读取、但没有 Renderer 消费”的粒子属性。V2 保留 Renderer 0 作为编译属性保活器：启用、`RendererVisibility=1` 隐藏，并把 `SpriteSizeBinding` 指向 `Particles.SSPR_ScreenDeltaUV`；正式显示仍由 Renderer 1 完成。
- Stage1 不再依赖缓存的 `SSPR_ScreenUV` 作为中心位置，直接从持久化 `Particles.Position` 重投影；缓存 `SSPR_ScreenDeltaUV` 只控制高斯长轴。
- `RasterizationGrid3D` 仅使用 Z=0 的一个切片，本质仍是二维屏幕密度场；选择该 DI 是为了使用 UE 5.8 已验证的整数原子加法。
- `clear_before_non_iteration_stage=True`，每帧清空当前密度；连续轨迹来自大量不同年龄粒子的空间分布，不来自 RT 历史累积。
- Niagara System 开启 `Fixed Tick Delta=0.01667s`。可变时间步曾导致静止视口下整张面片亮度脉动；固定 60 Hz 后消失。

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

这里仅使用单个 Z 切片。若后续扩展多通道时该 DI 无法稳定支持，再评估 SM6 原子浮点或分桶归约；不得退回非原子的普通覆盖写入。

## 7. Grid 与 SimRT 通道

### V2-A：密度单通道

先只验证各向异性核本身：

| 通道 | 内容 |
| --- | --- |
| R | 高斯 Splat 累积密度 |
| GBA | 保留为 0 |

通过条件是原始 Density 调试图中已经出现细尖流丝，而不是依赖最终材质才看起来像流体。

### V2-B：方向张量扩展

密度单通道通过后，再增加无正负歧义的二维方向张量：

```text
TensorX = Density × (tx² - ty²)
TensorY = Density × (2 × tx × ty)
```

建议 SimRT：

| 通道 | 内容 |
| --- | --- |
| R | Density |
| G | 累积 TensorX |
| B | 累积 TensorY |
| A | 局部速度、年龄或方向一致性 |

材质中：

```text
Theta = 0.5 × atan2(TensorY, TensorX)
Coherence = length(TensorXY) / max(Density, Epsilon)
```

方向张量用于沿流线卷积，不能使用普通带符号 Velocity 平均；相反方向的粒子在视觉上属于同一根线，普通平均会互相抵消。

## 8. 材质函数架构

G4 当前采用确定性的 LOD0 空间重建，不依赖 SimRT 自动 Mip。原 V1 Mip 资产继续留在冻结快照中；V2 的 `MF_SSPR_MipPyramidDensity` 为保持既有函数调用接口暂未更名，但内部已经替换为 7×7/13×13 LOD0 二项式核，旧 MipBias 输入不再参与计算。

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

### 8.1 三层输出

```text
Filament = 原始各向异性密度 + 窄范围流向连接
Medium   = LOD0 7×7 二项式空间核，当前半径 14 px
Body     = LOD0 13×13 二项式空间核，当前半径 48 px

FinalDensity = FilamentWeight × Filament
             + MediumWeight × Medium
             + BodyWeight × Body
```

不允许使用一个超大各向同性 Blur 把三层全部替代。

当前 HQ 混合基线为 `Filament/Medium/Body = 0.18/0.50/0.32`、`DensityGain=2`、`Contrast=0.48`、`Extinction=2.4`、`OpacityScale=0.82`。中央暗块已定位为梯度光照，不是场景阴影；视觉连续性 Gate 期间暂用 `AmbientLight=1 / LightStrength=0`，最终受光尚未封版。

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
- 接入 RasterizationGrid2D 或等价的无竞争累积方案。
- 验证 1、4、16 个重叠粒子的中心密度单调增加。
- 长时间运行不铺满，每帧正确清理。

### G4：细丝 + 烟体材质

- 状态：技术链已安装，最终视觉 Gate 进行中。
- 各向异性密度作为 Filament。
- 当前用 LOD0 7×7/13×13 空间核形成 Medium/Body；是否长期恢复 Mip 方案留给 M5 性能比较。
- 完成三层混合、密度整形和消光。

### G5：方向张量与流向卷积

- 在 G4 仍有断裂时才增加方向张量通道。
- 材质沿局部方向做有限步数卷积。
- 不引入二维 History 拖尾。

### G6：视觉与性能 Gate

- 首先冻结最高质量参数。
- 最高质量通过后，再建立 High / Medium / Low 档位。

G4 当前尚未通过的视觉项：独立粒子感、连续尖细流丝、中尺度连接、柔软烟体层次、最终受光、静止/转镜头/拉远、屏幕边缘和长时间运行。Fixed Tick 已解决整片闪烁，但不能替代这些画面 Gate。

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

### 最终画面 Gate

- 标准相机距离下不再能逐个辨认圆形粒子。
- 可同时观察到尖细流丝、致密核心和柔软宽烟体。
- 左右转动、平移和拉远相机时投影保持对齐。
- 屏幕边缘不 Wrap、不 Clamp 拉花。
- 关闭 TAA/TSR 后仍保留连续拉丝结构。
- 固定 Niagara 60 Hz 时间步后，静止与交互视口均不出现整片亮度脉动。

## 12. 高品质基线与预算

第一阶段优先最高品质：

- 2048×2048 内部 Grid / SimRT；
- 约 25000 个存活 GPU 粒子；
- 最大拉伸长度 40～48 px；
- 横向宽度约 1～2 px；
- RGBA16F SimRT；
- 原子密度固定点精度至少 10 bit 小数；
- 材质当前保持最高质量 LOD0 7×7/13×13 空间重建；梯度光照先中性关闭，待密度视觉通过后单独恢复。

高品质 Gate 通过前，不以降分辨率、减少粒子数或恢复圆形大模糊作为优化手段。

## 13. 主要风险与应对

| 风险 | 应对 |
| --- | --- |
| 原子写入不支持浮点 | 使用 RasterizationGrid2D 固定点整数累积 |
| 每粒子覆盖像素过多 | 限制 MaxLength、GaussianCutoff，并采用有界循环 |
| 高速产生整屏直线 | 长度 Clamp；速度响应使用平滑曲线 |
| 低速方向闪烁 | 最小速度阈值和上一有效方向回退 |
| 线很多但烟体太薄 | Filament、Medium 与 Body 分层混合 |
| 重新变成软泡 | 降低各向同性 Body 权重，检查 Raw Splat 是否已经拉伸 |
| 方向场正负抵消 | 使用二阶方向张量，不直接平均 Velocity |
| 相机移动产生伪速度 | 使用同一帧一致的当前相机矩阵投影前后位置；相机运动项单独审计 |
| 整张面片忽明忽暗 | 固定 Niagara 60 Hz 时间步；再分别排查 RT/Mip/时序抗锯齿，不用右键交互掩盖 |

## 14. 已批准决策

用户已批准以下四项并授权 V2 实施：

1. 允许 V2 使用内部 RasterizationGrid2D 固定点原子加法，仍不创建外部 RT。
2. 允许在 Velocity 清零前缓存 `FlowDelta/FlowVelocity`，但保留现有清零行为。
3. 接受“各向异性 Splat 负责细丝，多尺度空间重建负责宽烟体”的职责划分；当前高品质基线不依赖 SimRT Mip。
4. 先完成密度单通道 G1～G4；方向张量 G5 只在画面仍断裂时启用。

下一审批点是 G4 最终视觉结果。通过后先完成冷启动回归、函数命名/接口收口和 V2 完整快照，再决定是否进入可选 G5 方向张量与 M4 深度融合。
