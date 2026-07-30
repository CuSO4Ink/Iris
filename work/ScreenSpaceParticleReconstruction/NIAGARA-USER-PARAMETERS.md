# SSPR Niagara User 参数说明

> 当前对象：`/Game/SSPR_Validation/Performance/DenseG5SparseV2/NS_SSPR_AnisotropicSplat_Main`
>
> 数值来自 2026-07-30 对 Dense G5 恢复基线的有效值读回。Sparse V2 没有修改这些数值。

## 1. Splat 几何与密度

| User 参数 | 当前值 | 调整内容 | 性能影响 |
| --- | ---: | --- | --- |
| `User.SSPR_DensityPerParticle` | `0.03` | 每个粒子写入 Raster 的密度强度。提高会更浓、更快饱和；降低会更透明。 | 不改变循环次数，主要改变原子累加数值。 |
| `User.SSPR_GaussianCutoffSigma` | `2.5` | 高斯核截断范围。提高会保留更远尾部、轮廓更软；降低会让核更紧、更容易显粒子。 | 直接影响有效写入覆盖和动态循环范围。 |
| `User.SSPR_WidthPx` | `1.25 px` | 粒子 Splat 短轴标准差。提高会加粗、增强横向连接；降低会更尖细。 | 宽度增大时横向有效样本增加。 |
| `User.SSPR_MinLengthPx` | `2 px` | 低速粒子的最小长轴长度。 | 只影响低速粒子有效样本。 |
| `User.SSPR_MaxLengthPx` | `48 px` | 高速粒子的最大总长度；对应 Dense 最大半长 `24 px`。 | 是 Raster 核成本上限的主要参数。 |
| `User.SSPR_VelocityLengthScale` | `1.5` | 把当前帧屏幕位移换算为长轴长度。提高会拉得更长。 | 间接提高平均有效样本数。 |
| `User.SSPR_MinDirectionSpeedPx` | `0.05 px` | 屏幕位移低于该值时不采用噪声方向，回退默认切线。 | 几乎无成本影响，主要抑制低速方向闪烁。 |

长轴关系：

```text
LongLengthPx =
    clamp(MinLengthPx + ScreenSpeedPx × VelocityLengthScale,
          MinLengthPx,
          MaxLengthPx)
```

## 2. 深度字段

| User 参数 | 当前值 | 调整内容 | 性能影响 |
| --- | ---: | --- | --- |
| `User.SSPR_DepthNearUU` | `0 uu` | 深度归一化近端。 | 不改变样本数。 |
| `User.SSPR_DepthFarUU` | `10000 uu` | 深度归一化远端。值越大，同样距离差异在 RT 中越弱。 | 不改变样本数。 |
| `User.SSPR_FrontDepthWeightThreshold` | `0.1` | 只有高斯权重大于阈值的贡献才参与 FrontDepth 原子最大值，避免稀薄尾部抢占前表面。 | 提高可减少 FrontDepth 原子写入，但过高会破坏边缘深度。 |

当前归一化：

```text
DepthNorm = saturate((ViewDepth - DepthNearUU) /
                     (DepthFarUU - DepthNearUU))
```

## 3. User Data Interface

| User 参数 | 当前配置 | 作用 |
| --- | --- | --- |
| `User.SSPR_DensityRaster` | `2048×2048×1`，6 属性，Precision `65535`，逐步 Clear | 原子累积 Density、方向张量、DepthMoment1/2 和 FrontDepth。 |
| `User.SSPR_SimRT` | `2048² RGBA16F`，Bilinear，Mip Disabled | Main RT：`Density / TensorCos2 / TensorSin2 / MeanDepth`。 |
| `User.SSPR_AuxRT` | `2048² RGBA16F`，Bilinear，Mip Disabled | Aux RT：`DepthSigma / FrontDepth / Reserved / Coverage`。 |
| `User.SSPR_TrajectoryGrid` | 遗留 Grid2DCollection | 兼容性遗留，不参与当前 Raster→Main/Aux 最终链。 |
| `User.SSPR_TrajectoryRT` | 遗留名称 | 不参与当前 Renderer 绑定。 |

Renderer 当前绑定：

```text
TrajectoryTexture    <- User.SSPR_SimRT.RenderTarget
TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget
```

## 4. 不是 User 参数，但决定粒子成本

| Niagara 设置/模块输入 | 当前值 | 作用 |
| --- | ---: | --- |
| Spawn Rate | `50000/s` | 每秒生成粒子数量。 |
| Lifetime Min/Max | `5 s / 5 s` | 稳态约 `250000` 个存活粒子。 |
| Shape Sphere Radius | `50 uu` | 发射体范围。 |
| Curl Noise Strength | `5000` | Curl 力强度。 |
| Curl Noise Frequency | `10` | Curl 空间频率。 |
| Drag | `1` | 速度阻尼。 |
| Fixed Tick | `true / 0.01667 s` | 固定 60 Hz 模拟；必须保留，已解决整片亮度波动。 |

当前性能优化没有修改以上数值。Dense Raster 的最大候选数为
`49×11=539/粒子`；Sparse V2 改为质量守恒的
`33×7=231/粒子`，最大原子写入候选下降 `57.14%`。

## 5. 建议调参顺序

1. 先用 `DensityPerParticle` 调整体浓度，不用粒子数补亮度。
2. 用 `WidthPx` 调横向连接，用 `Min/MaxLengthPx` 和
   `VelocityLengthScale` 调拉丝长度。
3. 粒子感过强时先小幅提高 `WidthPx` 或 Medium/Body 材质支撑；
   不先扩大 `GaussianCutoffSigma`，因为它会增加 Raster 有效覆盖。
4. 深度分层错误时只调 `DepthNear/Far` 和
   `FrontDepthWeightThreshold`，不要同时改密度核。
5. 只有经过同机视觉对照后才评估 Spawn Rate/Lifetime；它们直接改变
   稳态粒子数和视觉采样密度。

## 6. 原始粒子对照模式

默认 Renderer 0 只用于保活 Custom HLSL 读取的粒子属性，因此保持隐藏；Renderer 1 才是 G5 HQ 重建显示。需要对照原始粒子时，Renderer 0 应使用 `RendererVisibility=0` 和 `Particles.SpriteSize`。此前绑定 `Particles.SSPR_ScreenDeltaUV` 会使尺寸接近零，看起来像透明。该切换必须完成 Apply/Compile/Save/Reinitialize 后再进行视觉判断。
