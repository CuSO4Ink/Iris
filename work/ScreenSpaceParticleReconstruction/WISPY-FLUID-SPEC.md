# 高密度粒子轨迹屏幕 Raster 烟雾重建规格

- 版本：1.7
- 日期：2026-07-29
- 状态：ParticleTrails 已冻结为 V1；各向异性高斯 Splat V2 已完成 G0～G3，G4 高品质材质已安装并等待最终视觉 Gate
- 目标工程：`precisefluid` / UE 5.8 / Niagara GPU Simulation
- 运动参考资产：`/Game/SSPR_Validation/M2/NewNiagaraSystem2`
- 当前主线系统：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main`
- 当前显示材质：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/M_SSPR_AnisotropicSplat_Display`
- 当前视觉调参实例：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/MI_SSPR_AnisotropicSplat_HQ`
- 当前材质函数库：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Functions/M3_HQBaseline` 与 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Functions/M3_HQFluidV2`
- V1 冻结快照：`/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729`
- V2 当前开发目录：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2`
- 旧屏幕历史归档：`/Game/SSPR_Validation/Archive/PingPong_M2_20260728`

## 0. 架构决策

正式方案不再用屏幕空间 History Ping-pong 作为拉丝连续性的主要来源。

正式方案的核心是：

1. Niagara 持续生成大量、寿命较长的三维粒子。
2. 不同年龄的粒子同时占据同一流线的不同位置，由单帧粒子群自然形成连续轨迹。
3. 每帧将全部存活粒子用当前相机重新投影，并写入单层 `RasterizationGrid3D(2048×2048×1)` 的 Q10 原子密度。
4. 在 Niagara 内将 Raster Grid 最终结果写入系统自管的 `User.SSPR_SimRT`，Renderer 再把 `User.SSPR_SimRT.RenderTarget` 绑定到最终材质参数。
5. 材质在一个 Resolve 中完成多尺度卷积、密度整形、破碎和烟雾着色。
6. 项目不声明 Current、History、Blur、Density 等外部 `TextureRenderTarget2D` 资产。

RasterizationGrid/Grid2DCollection 在 GPU 内部仍会使用纹理资源。UE 5.8 的材质参数需要 `UTexture`，不能直接消费 Grid DI 的原始 RDG 纹理。因此当前正式链路是：

```text
RasterizationGrid3D 单层密度
    -> Niagara Simulation Stage 整理/拷贝
    -> NiagaraDataInterfaceRenderTarget2D：User.SSPR_SimRT
    -> User.SSPR_SimRT.RenderTarget
    -> Sprite Renderer 的材质 Texture Parameter
```

`User.SSPR_SimRT` 在 `bInheritUserParameterSettings=false` 时由 Niagara 为每个系统实例自动创建和管理，不是 Content Browser 中声明的 `TextureRenderTarget2D` 资产。“不需要额外 RT”指不创建和维护外部 Current/History/Blur/Density RT 资产，也不由 Blueprint 执行 Clear、DrawMaterial 和 Ping-pong；并不表示 GPU 上不存在任何纹理。

旧的 Current/History A/B、代表深度重投影、多 RT 卷积和相机跟随 SmokeCard 已整体移动到 `/Game/SSPR_Validation/Archive/PingPong_M2_20260728`，只作为实验原型保留，不再定义生产架构。

### 0.1 当前落地状态

当前 `NS_SSPR_AnisotropicSplat_Main` 是正式主线资产：

- `Fountain` 已切换为 GPU Compute Sim，并保留白色高密度粒子运动骨架。
- `SSPR Rasterize Trails` 为粒子迭代 Simulation Stage，把全部存活粒子投影到 `User.SSPR_DensityRaster`；Stage 只写 DI，保持 `WritesParticles=False`。
- `User.SSPR_DensityRaster` 当前使用 `RasterizationGrid3D(2048×2048×1)`，以 Q10 整数原子加法累积各向异性高斯，并在非迭代 Stage 前自动清零。
- `SSPR Resolve Grid To Material` 按 2048² 全域逐像素读取 DensityRaster，并覆盖写入 Niagara 自管的 2048×2048 RGBA16F `User.SSPR_SimRT`。
- `User.SSPR_SimRT` 使用 `bInheritUserParameterSettings=false`，由 Niagara 为运行实例创建实际纹理。
- `Fountain` 的 Emitter SourceMode Sprite Renderer 使用 `MI_SSPR_AnisotropicSplat_HQ`；另保留一个不可见 Particle Renderer 作为 Position/ScreenDeltaUV 编译属性保活器。
- 材质参数 `TrajectoryTexture` 绑定 `User.SSPR_SimRT.RenderTarget`。
- `TrajectoryTexture` 的 `UVs` 必须连接 `ScreenPosition.ViewportUV`；不得使用 Sprite 自身 0–1 UV，否则显示比例会随面片世界尺寸和深度变化。
- 验证关卡只允许一个可见、可 Tick 的 `NS_SSPR_ParticleTrails_Main` 实例；重复实例必须停用，避免两套粒子与两张内部 SimRT 混合显示。
- 不使用 Content 外部 RT、Blueprint Clear、DrawMaterial 或 History Ping-pong。

当前主线已经不依赖 Niagara Fluids 的 Advect、Pressure、Lighting 等 Gas Simulation Stage。实际场处理已收敛为：

```text
Clear RasterizationGrid3D
-> Rasterize anisotropic particle density
-> Resolve Raster Grid to User.SSPR_SimRT
-> Niagara Sprite Renderer / Material
```

2026-07-29 当前验收结果：运行实例生成 2048×2048 RGBA16F SimRT，Bilinear、自动 Mip 关闭；一次动态原始回读得到 32,030 个非零像素、R 最大约 6.77、R 总量约 23,390.58。Niagara 编译状态为 UpToDate，错误与警告均为 0。材质现场检查确认 `TextureSample.UVs <- ScreenPosition.ViewportUV`。System 已开启 `Fixed Tick Delta=0.01667s`；可变时间步导致的整片亮度脉动已消失。

### 0.2 已冻结的 M2 图像输入基线

用户已确认当前粒子到材质的流程“彻底跑通”。从此版本开始，下列内容作为 M3 的稳定输入契约：

- Niagara 投影、Raster 原子写入和内部 SimRT Resolve 作为 G0～G3 输入基线冻结；烟雾观感优先只改材质函数与 HQ 实例。若改变 Fixed Tick、粒子运动或 Splat 核，必须重新执行完整输入 Gate。
- 材质接收一张 Niagara 自管 2048×2048 RGBA16F `TrajectoryTexture`。
- 材质使用 `ScreenPosition.ViewportUV` 采样，输入图像与当前相机投影逐像素对齐。
- 原始输入允许呈现大量离散亮点；这是待重建的粒子密度数据，不依赖 TSR/TAA 掩盖。
- 关闭 TSR/TAA 的运行时对照已通过：`r.AntiAliasingMethod=0` 时链路仍正确，说明 M3 必须靠确定性的空间滤波和密度整形消除颗粒感。
- 当前抗锯齿关闭只作为本次编辑器会话的观察条件，不写入项目默认配置。

除非出现 RT 为空、比例错位、边缘越界、时间步或相机投影回归，G4 只修改 `M_SSPR_AnisotropicSplat_Display`、`MI_SSPR_AnisotropicSplat_HQ` 及其引用函数，不回头修改 G0～G3 数据生产链。

## 1. 产品目标

实现一种实时、依赖当前相机视角的 2.5D 拉丝烟雾。

目标画面接近 FluidNinja 的连续、卷曲、柔软和高频拉丝感，但不要求使用相同算法，也不要求求解 Navier-Stokes 方程。

系统分工：

- Niagara 粒子提供三维流线和时间分布。
- Grid2DCollection 把当前粒子群变成屏幕空间密度场。
- 材质把离散轨迹重建成高精度烟雾。

最终画面是验收核心，物理正确性不是目标。

## 2. 核心原理

假设粒子生成率为 `R`，寿命为 `L`，稳定状态下存活粒子数近似为：

```text
AliveParticles ≈ R × L
```

参考资产当前为：

```text
R = 5000 particles/s
L = 5 s
AliveParticles ≈ 25000
```

这些粒子具有不同的 `NormalizedAge`。同一流场中，较老粒子已经沿流线移动较远，较新粒子仍靠近发射区域，因此当前单帧内就存在一条由不同年龄粒子组成的空间轨迹。

连续性来自：

```text
高生成率
× 足够寿命
× 相干 Curl 流场
× 小粒子屏幕投影
```

而不是来自：

```text
上一帧二维图像
× History 衰减
× 相机重投影
```

## 3. 总体管线

```text
Niagara GPU 粒子
    -> 高 SpawnRate 与年龄分布
    -> Curl/目标速度场推进三维位置
    -> 当前相机 World-to-Screen 投影
    -> 全部存活粒子写入 RasterizationGrid3D 单层 Q10 密度
    -> Raster Grid 最终结果写入 Niagara 自管 User.SSPR_SimRT
    -> Emitter SourceMode Sprite Renderer
    -> User.SSPR_SimRT.RenderTarget 绑定到烟雾材质参数
    -> 单材质多尺度重建与烟雾 Resolve
```

### 3.1 每帧执行顺序

```text
1. Niagara 更新全部存活粒子的三维位置与年龄
2. 清空本帧 Grid 属性
3. 使用当前相机投影每个存活粒子
4. 将有效粒子写入 Grid
5. Resolve Stage 将结果覆盖写入 Niagara 自管 User.SSPR_SimRT
6. Renderer 把 User.SSPR_SimRT.RenderTarget 绑定给最终材质
7. 材质采样 Grid 结果并输出烟雾
```

每帧 Grid 都从三维粒子重新生成。因此相机移动时无需重投影上一帧二维历史。

## 4. 参考 Niagara System

`NewNiagaraSystem2` 当前保存状态用于说明 Leader 要求的粒子运动骨架。

### 4.1 当前 Emitter

| 项目 | 当前值 |
| --- | --- |
| Emitter | `Fountain` |
| Simulation Target | `CPU Sim` |
| Spawn Rate | `5000/s` |
| Lifetime | `5 s` |
| Spawn Shape | 半径 `50 uu` 的球体内部 |
| Sprite Size | `2-3 uu` |
| Color | 白色 |
| Renderer | 默认 Sprite Renderer |

### 4.2 当前模块顺序

```text
Emitter Update:
    Emitter State
    Spawn Rate

Particle Spawn:
    Initialize Particle
    Shape Location

Particle Update:
    Particle State
    Scale Color
    Curl Noise Force
    Drag
    Solve Forces and Velocity
    Set Particles.Velocity = (0,0,0)
```

### 4.3 当前 Curl 设置

| 参数 | 当前值 |
| --- | --- |
| Strength | `5000` |
| Frequency | `10` |
| Quality | `Baked (Medium)` |
| Coordinate Space | `World` |
| Pan Noise | 开启 |
| Pan Vector | `(0,0,1)` |
| Randomize Sample | 开启 |
| Drag | `1` |

### 4.4 Alpha

`Scale Color` 使用 `Particles.NormalizedAge` 驱动 Alpha 曲线：

```text
出生：Alpha ≈ 1
死亡：Alpha ≈ 0
```

它负责让五秒寿命结束前的粒子平滑淡出，避免硬消失。

## 5. Solver 后 Velocity 清零

### 5.1 目的

`Curl Noise Force` 是力，不是直接速度。若保留求解后的速度，Curl Force 会持续累积动量，粒子可能产生明显惯性、加速和脱离局部流线。

在 Solver 后执行：

```text
Particles.Velocity = 0
```

会让下一帧重新从静止状态接受当前位置的 Curl Force。它的视觉目的可以理解为：

```text
削弱惯性
让粒子更紧地跟随瞬时 Curl 场
避免速度长期积累
```

这不是在撤销本帧移动。`Solve Forces and Velocity` 已经先更新了 Position，随后清零只影响保存给下一帧的 Velocity。

### 5.2 数值结果

简化后，每帧近似为：

```text
Vtemp = Force / Mass × DeltaTime
PositionNext = Position + Vtemp × DeltaTime
VelocityNext = 0
```

因此单帧位移近似：

```text
DeltaPosition ≈ Force / Mass × DeltaTime²
```

这种写法有三个副作用：

1. 有效运动速度会随帧率变化；低帧率下单步位移更大。
2. Drag 的作用明显减弱，因为每一帧开始时旧速度已经为零。
3. 放在清零节点之后的模块读到的 `Particles.Velocity` 为零，不能用它生成 Flow 或方向性 Splat。

### 5.3 正式实现决策

参考资产允许暂时保留 Velocity Reset 用于复现 Leader 的视觉方向，但生产实现必须完成 30/60/120 FPS 对比。

正式优先方案是把 Curl 当作目标速度场，而不是无限累积的力：

```text
TargetVelocity = Curl(Position, Time) × FlowSpeed
Response = 1 - exp(-FollowRate × DeltaTime)
Velocity = lerp(Velocity, TargetVelocity, Response)
Position += Velocity × DeltaTime
```

该方案同时提供：

- 对 Curl 流线的跟随能力。
- 可调的惯性和响应速度。
- 更稳定的帧率表现。
- 可直接用于 Grid Flow 或方向性 Splat 的有效 Velocity。

备选方案是保留 `Curl Noise Force + Solve`，删除 Velocity Reset，并使用足够强的 Drag 抑制惯性。

如果最终为了美术效果继续保留清零，必须在清零前保存：

```text
Particles.FlowVelocity = Particles.Velocity
```

Grid 写入和任何方向性处理读取 `FlowVelocity`，不能读取已清零的 `Velocity`。

## 6. GPU 与屏幕 Raster Grid

正式系统必须从 `CPU Sim` 切换到 `GPU Compute Sim`。

原因：

- 稳态目标粒子数约为 25000 或更高。
- 粒子投影和 Raster Grid 写入需要 GPU Simulation Stage。
- 当前使用 `RasterizationGrid3D` 的 Z=0 单层作为二维 GPU 原子密度场。
- CPU 粒子读回再上传 Grid 不符合性能目标。

### 6.1 Grid 基线

质量优先阶段使用：

| 参数 | 高品质基线 |
| --- | --- |
| Raster Resolution | `2048 × 2048 × 1` |
| SimRT | `2048 × 2048 RGBA16F` |
| Raster Fixed Point | Q10（密度 ×1024 后整数原子累加） |
| Attributes | 当前 Density 单通道 |
| Clear Before Write | 开启 |
| SimRT Filtering | Bilinear |
| SimRT Mip Generation | Disabled |

首个必需属性：

| 属性 | 内容 |
| --- | --- |
| `Density` | 当前帧粒子占据/密度 |

未来允许在同一套内部 Grid/Resolve 中增加属性，而不创建外部 History/Blur RT 链：

| 可选属性 | 内容 |
| --- | --- |
| `FlowX/FlowY` | 屏幕空间流向 |
| `AgeWeight` | 年龄加权 |
| `FrontDepth` | 最近视图深度，需确定性 Min 归约 |
| `Temperature` | 热烟或颜色控制 |

### 6.2 粒子投影

每个存活粒子使用当前相机矩阵计算：

```text
Clip = WorldToClip(Position)
Valid = Clip.W > 0
UV = Clip.xy / Clip.w × 0.5 + 0.5
```

必须拒绝：

- 相机后方粒子。
- 非有限坐标。
- `W` 太小的投影。
- 屏幕外粒子。

无效坐标必须跳过，不能 Clamp 到边缘。

### 6.3 Grid 写入

当前基线写入沿 `Particles.SSPR_ScreenDeltaUV` 拉伸的旋转椭圆高斯。轨迹连续性同时来自高粒子数/年龄分布和各向异性 Splat。

并发累积使用 Q10 整数原子加法：

```text
ContributionInt = round(GaussianWeight × DensityPerParticle × 1024)
InterlockedAdd(DensityRaster, ContributionInt)
ResolvedDensity = DensityRaster / 1024
```

不得把普通非原子 Read/Modify/Write 当作正确密度累加，也不得让 Raster Stage 为调试标记写回粒子属性。

允许增加“当前帧三维运动段”的短线 Splat：

```text
PreviousPosition -> Position
```

它只连接本帧粒子运动，不读取上一帧二维图像，因此不属于 History Ping-pong。

## 7. Grid 输出与材质绑定

UE 5.8 当前采用 Niagara 自管 RenderTarget DI 桥接方式：

1. 本 System 内的 `RasterizationGrid3D(2048×2048×1)` 保存 Q10 原子密度。
2. Resolve Simulation Stage 将需要显示的密度整理到 `User.SSPR_SimRT`。
3. `User.SSPR_SimRT` 是 `NiagaraDataInterfaceRenderTarget2D`，其内部 `RenderTarget` 由 Niagara 管理。
4. Emitter SourceMode 的 Sprite Renderer 生成显示面片。
5. Renderer 的材质参数绑定将 `User.SSPR_SimRT.RenderTarget` 传给材质 Texture Parameter。
6. 材质以 `ScreenPosition.ViewportUV` 采样，显示面片只作载体，不用其 Mesh UV 决定投影比例。

当前主线资产使用的实际绑定为：

```text
Material Parameter: TrajectoryTexture
Niagara Variable: User.SSPR_SimRT
Child Variable: RenderTarget
Material Instance: MI_SSPR_AnisotropicSplat_HQ
```

这条链没有 Content 外部 RT 资产，也没有 Blueprint RT 调度。

材质建议参数名：

```text
TrajectoryTexture
SSPR_InvTextureSize
FilamentWeight
MediumWeight
BodyWeight
MediumRadiusPx
BodyRadiusPx
DetailStrength
EdgeStrength
BlackPoint
InputGain
DensityGain
Contrast
Extinction
OpacityScale
EmissiveStrength
SmokeColor
DebugRaw
```

不再由 Blueprint 创建动态材质并给多张 RT 排序，也不再需要相机前方的独立 SmokeCard 承担主显示链路。

## 8. 单材质高品质重建

为了满足“不声明额外 RT”并降低各阶段耦合，M3 采用“父材质只编排、算法优先放材质函数”的结构。各函数只通过显式输入/输出交换数据，后续可以单独替换卷积、密度整形或着色，而不改 Niagara 数据生产链。

```text
TrajectoryTexture + ViewportUV
    -> MF_SSPR_RawDensity
    -> MF_SSPR_MipPyramidDensity（当前内部为稳定 LOD0 空间核）
         ├─ Filament / Core
         ├─ Medium Gaussian
         └─ Body Gaussian
    -> MF_SSPR_DensityShape
    -> DebugRaw 选择
    -> MF_SSPR_ScreenEdgeMask
    -> MF_SSPR_SmokeResolve
    -> MF_SSPR_DensityGradientLighting（当前 HQ 实例中性关闭）
    -> Emissive + Opacity
```

正式函数库：

`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Functions/M3_HQBaseline`

`/Game/SSPR_Validation/M2/AnisotropicSplat_V2/Functions/M3_HQFluidV2`

| 材质函数 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `MF_SSPR_RawDensity` | 原始轨迹采样与非负增益 | SourceTexture、UV、Gain | Density |
| `MF_SSPR_MipPyramidDensity` | 当前使用 LOD0 连续多尺度高斯与边界保护；名称和 MipBias 兼容接口待收口 | SourceTexture、UV、TexelSize、MediumRadiusPx、BodyRadiusPx | Filament/Medium/Body 三通道 Scales |
| `MF_SSPR_DensityShape` | 多尺度混合、真实频段细节、黑位与对比度 | Scales、三层权重、DetailStrength、EdgeStrength、BlackPoint、DensityGain、Contrast | Density |
| `MF_SSPR_ScreenEdgeMask` | 屏幕边缘安全衰减 | UV、TexelSize、FadeWidthPx | Mask |
| `MF_SSPR_SmokeResolve` | Beer–Lambert 消光、透明度和烟雾颜色 | Density、SmokeColor、Extinction、OpacityScale、EmissiveStrength | Color、Opacity |
| `MF_SSPR_DensityGradientLighting` | 可选低频密度梯度明暗 | Density Texture、UV、Light 参数 | Lighting |

父材质 `M_SSPR_AnisotropicSplat_Display` 只负责：

- 接收 Renderer 绑定的 `TrajectoryTexture`。
- 提供 `ScreenPosition.ViewportUV` 与 `SSPR_InvTextureSize`。
- 暴露参数并调用六个材质函数。
- 用 `DebugRaw` 在处理后密度与原始密度之间切换。
- 将 Resolve 的 Color/Opacity 接到材质输出。

Niagara Display Renderer 正式绑定 `MI_SSPR_AnisotropicSplat_HQ`。该实例是当前视觉调参层；函数接口和父材质编排保持稳定。当前梯度光照为排除中央暗块而临时中性化，尚不是最终受光结果。

### 8.1 高品质空间核

当前基线优先画质，不先做 separable、稀疏 taps 或低分辨率优化：

| 层 | 采样 |
| --- | --- |
| Core | 原始中心样本 |
| Medium | 连续 `7×7` 二项式 Gaussian，49 taps，当前半径 14 px |
| Body | 连续 `13×13` 二项式 Gaussian，169 taps，当前半径 48 px |

多尺度函数本身每像素执行 219 次 LOD0 纹理采样。父材质为了保留独立 Raw 调试链还会额外采样一次；性能优化统一留到 M5，不以破坏当前质量基线为代价。SimRT 自动 Mip 当前关闭，避免把动态 Mip 链当作正式质量基线。

边界策略：

- 使用 `SSPR_InvTextureSize=(1/2048, 1/2048)` 计算真实 Texel。
- 采样中心限制在半 Texel 安全范围。
- 越界 tap 的权重直接归零，不允许 Wrap，也不把越界密度累积到屏幕边缘。
- 只用有效权重归一化，避免画面边缘因核被裁剪而异常变暗。

### 8.2 密度整形

`MF_SSPR_DensityShape` 不引入与粒子无关的假屏幕噪声，而是从真实尺度差中提取细节：

```text
FineDetail = Core - Small
BroadEdge = Small - Large
Density = weighted(Core, Small, Large)
        + FineDetail × DetailStrength
        + BroadEdge × EdgeStrength
```

随后依次执行 BlackPoint、DensityGain 与 Contrast。当前默认参数：

| 参数 | 默认值 |
| --- | ---: |
| `FilamentWeight` | 0.18 |
| `MediumWeight` | 0.50 |
| `BodyWeight` | 0.32 |
| `DetailStrength` | 0.03 |
| `EdgeStrength` | 0.00 |
| `BlackPoint` | 0.00 |
| `InputGain` | 1.00 |
| `DensityGain` | 2.00 |
| `Contrast` | 0.48 |
| `RidgeStrength` | 0.25 |

### 8.3 烟雾 Resolve

透明度使用 Beer–Lambert 指数消光：

```text
Alpha = saturate((1 - exp(-Extinction × max(Density, 0))) × OpacityScale)
Color = SmokeColor × Alpha × EmissiveStrength
```

当前默认参数：

| 参数 | 默认值 |
| --- | ---: |
| `Extinction` | 2.4 |
| `OpacityScale` | 0.82 |
| `EmissiveStrength` | 1.0 |
| `SmokeColor` | (0.72, 0.78, 0.88) |
| `DebugRaw` | 0 |

当前光照验证参数：`AmbientLight=1`、`LightStrength=0`。这是为了先确认密度和透明度连续性，不代表最终体积受光已经完成。

第一阶段优先最高画质，不因性能提前减少分辨率或采样数。

### 8.4 自动化构建约束

UE 5.8 中，对同一材质函数反复“删除全部表达式后原地重建”可能残留旧 `FunctionInput` GUID，使函数调用节点反射出重名输入；材质虽然显示编译成功，实际连线却可能命中失效 Pin 并得到全黑结果。

因此正式规则是：

- 已发布的函数资产不做破坏性原地重建。
- 函数接口或图结构发生破坏性变化时，在新的版本目录创建干净资产并重新绑定父材质。
- 自动化完成后必须反射检查函数调用输入名唯一，并用已知白纹理做端到端非零 Gate。

## 9. 调参职责

### Niagara

| 参数 | 作用 |
| --- | --- |
| `SpawnRate` | 单帧轨迹采样密度 |
| `Lifetime` | 流线覆盖长度与时间范围 |
| `SourceRadius` | 初始分布范围 |
| `FlowSpeed` | 沿 Curl 场移动速度 |
| `CurlFrequency` | 卷曲尺度 |
| `CurlPan` | 流场随时间变化 |
| `FollowRate` | 速度跟随场的响应 |
| `SplatRadiusPx` | Grid 原始轨迹宽度 |
| `AgeDensityCurve` | 不同年龄粒子的密度贡献 |

### Material

| 参数 | 作用 |
| --- | --- |
| `FilamentWeight` | 保留各向异性细丝核心 |
| `MediumRadiusPx` | 连接近邻轨迹 |
| `BodyRadiusPx` | 形成柔软宽烟团 |
| `Medium/BodyWeight` | 多尺度比例 |
| `DetailStrength` | 恢复 Core-Small 高频细丝 |
| `EdgeStrength` | 使用 Small-Large 频段塑造宽边 |
| `BlackPoint` | 去除低值底噪 |
| `InputGain / DensityGain` | 原始输入与处理后密度总增益 |
| `Contrast` | 密度响应曲线 |
| `Extinction` | 透明度 |
| `OpacityScale` | 消光结果总透明度 |
| `EmissiveStrength` | Unlit 烟雾亮度 |
| `SmokeColor` | 烟雾颜色 |
| `DebugRaw` | 原始密度与处理结果 A/B |

原 Ping-pong 方案中的 `DecayRate`、`RepresentativeDepth`、`HistoryValid`、`TrailTime` 和 `MaxTrailPx` 不再是正式主线核心参数。

## 10. 相机行为

每帧从三维粒子重新投影，因此：

- 相机旋转不需要 History 重投影。
- 相机平移不需要代表深度。
- 镜头远近变化会自然改变粒子屏幕范围。
- 不应出现旧二维图像造成的水平撕裂和鬼影。

如果相机改变后仍出现横线，优先检查：

- 无效 UV 是否被 Clamp 到边缘。
- Grid 是否未在本帧正确清空。
- 粒子写入是否错误跨行。
- 材质采样是否 Wrap。

不得重新引入 History 来掩盖这些问题。

## 11. 深度与场景融合

基础版本先验证透明烟雾形态。

深度阶段优先考虑在同一个 Grid2DCollection 中增加 `FrontDepth` 属性，而不是创建独立外部 RT。

FrontDepth 需要明确的最近深度归约：

```text
FrontDepth = min(valid particle depths)
```

在没有确定性原子 Min 或等价 Rasterization 方案前，Last Writer Depth 只能作为调试数据。

最终材质使用 FrontDepth 与 SceneDepth：

- 遮挡场景物体后的烟雾。
- 在交界处软淡化。
- 通过密度/深度梯度估计轻量法线。

## 12. 不采用的主线路线

- 屏幕空间 History A/B Ping-pong 作为主要拖尾来源。
- 代表深度近似重投影。
- Current/Core/Small/Large/Density/Smoke 多张外部 RT 链。
- Blueprint 每帧 Clear、DrawMaterialToRenderTarget 和交换 RT。
- 完整 Navier-Stokes 压力求解。
- 用各向同性大模糊掩盖粒子数量不足。
- 未经验证的非原子密度累加。

Ping-pong 原型可作为对比和应急低粒子数方案保留，但不能与正式 Grid 主线混合调度。

## 13. 质量策略

当前阶段先建立最高品质基线：

- 2048×2048 Grid / Niagara 自管 RGBA16F SimRT。
- 约 25000 或更多存活 GPU 粒子。
- 高质量 Curl 运动。
- 7×7 + 13×13 连续高斯多尺度过滤。
- 高精度 Grid 格式。
- 不创建外部 RT。

画面通过后再依次评估：

1. 局部 Grid 包围范围。
2. 动态分辨率。
3. 降低采样数。
4. 降低 SpawnRate 或 Lifetime。
5. 合并或简化 Grid 属性。

## 14. 验证用例

| 测试 | 通过条件 |
| --- | --- |
| 单帧静止观察 | 可以看到由粒子年龄分布形成的连续流线，而非孤立圆点 |
| 停止 Spawn | 已存在粒子按 Lifetime/Alpha Curve 自然消失 |
| 相机左右旋转 | 无 History 横向撕裂和持续鬼影 |
| 相机平移与拉远 | Grid 结果与三维粒子范围一致 |
| 30/60/120 FPS | 流速、覆盖范围和密度基本一致 |
| Velocity Reset 对比 | 明确记录 Reset、无 Reset、目标速度场三种运动差异 |
| 屏幕外/相机后粒子 | 不写入 Grid 边缘 |
| 高粒子重叠 | Grid 输出稳定，不闪烁 |
| 长时间运行 | Grid 每帧重建，不逐渐画满 |
| Niagara 停止 | Grid 清空，画面归零 |
| 材质边缘 | 无 Wrap、Clamp 拉丝或边缘泛色 |
| 编译 | Niagara 和材质零错误、零警告 |

时间步稳定性基线：`Fixed Tick Delta=true`、`Fixed Tick Delta Time=0.01667s`。仍需分别限制渲染帧率到 30/60/120 FPS，验证低帧率补步不会产生新的性能尖峰或密度跳变。

## 15. 实施里程碑

### M0：运动方向对齐（已完成当前 V2 基线）

- 以 `NewNiagaraSystem2` 复现 Leader 给出的高密度粒子轨迹。
- 对比 Velocity Reset、强 Drag 和目标速度场。
- 当前以 Fixed Tick 60 Hz 固化正式运动步长；30/60/120 渲染帧率性能回归留在视觉封版前完成。
- 将 Emitter 切换为 GPU Compute Sim。

**验收：** 单独粒子视图已经形成相干 Curl 流线，且相机观察下范围正确。

### M1：单帧 Raster 轨迹（已完成）

- 当前实现使用 `RasterizationGrid3D(2048×2048×1)` 单层原子密度。
- 新增清 Grid Simulation Stage。
- 新增 Particle-to-Grid 写入阶段。
- 使用当前相机投影全部存活粒子。
- 先输出单属性 Density 调试图。
- 已移除 Niagara Fluids Advect、Pressure 与 Lighting 主链依赖，只保留 Clear、Rasterize 与 Resolve。

**验收：** 不依赖任何 History 或外部 RT，Grid 单帧已经出现连续轨迹；长时间运行不画满。

### M2：Niagara 内部 SimRT 绑定材质（已验收并冻结）

- 使用 Emitter SourceMode Sprite Renderer。
- 将 `User.SSPR_SimRT.RenderTarget` 绑定到材质 Texture Parameter。
- 删除正式链路对外部 RenderTarget、Orchestrator 和 SmokeCard 的依赖。
- 验证视口比例、UV、Clamp 和边缘。
- 验证 `ScreenPosition.ViewportUV -> TextureSample.UVs` 的实际连线，而不只检查节点是否存在。
- 验证场景中只有一个主系统实例参与可见渲染。

**验收：** Niagara System 单独放入场景即可显示材质结果，不需要 Blueprint RT 调度。

当前验证结果：

- Niagara 编译状态 `UpToDate`。
- `bHasErrors=false`，`bHasWarnings=false`。
- 运行时自动创建 2048×2048 RGBA16F `SimRT`。
- 256×256 材质桥回读检测到非零轨迹像素，证明粒子/Grid 数据已经进入材质所绑定的内部纹理。
- `TextureSample.UVs` 已确认连接 `MaterialExpressionScreenPosition.ViewportUV`，屏幕空间投影与显示采样使用同一套归一化坐标。
- 验证关卡中的重复主系统 Actor 已停用、隐藏并关闭 Tick，正式画面只保留 `SSPR_ParticleTrails_Main`。
- 两轮 PIE 安全退出测试均通过，UnrealEditor 进程与 MCP 服务保持存活。
- 编辑器世界可能暂时保留旧 Niagara 实例创建的同规格内部 RT，自动化验收必须按有效像素量选择当前活动输出，不能直接取第一个对象。

### M3 / G4：高品质烟雾材质（技术链已完成，视觉 Gate 进行中）

- 保留 Raw Density 调试开关，确保任何处理都能与冻结输入对照。
- 用独立材质函数实现 Raw、Core/Small/Large、Density Shape 与 Smoke Resolve。
- 使用 7×7 + 13×13 连续高斯核建立最高品质基线。
- 完成真实频段细节、黑位、对比度、指数消光和颜色。
- 在最高品质基线上调出拉丝烟雾。
- 不依赖 TSR/TAA 的历史积累消除噪点；时序抗锯齿只负责最终常规画面抗锯齿。

**验收：** 看不出独立粒子圆点，呈现连续、卷曲、有层次的 2.5D 烟雾。

当前技术 Gate：

- 当前父材质引用六个自包含 V2 函数，编译零错误。
- Display Renderer 已绑定 HQ 材质实例，且 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 子变量绑定保持不变。
- SimRT 已切为 Bilinear、无自动 Mip；多尺度函数使用 LOD0 7×7/13×13 空间核。
- 一次当前活动 2048² SimRT 原始回读为 32,030 个非零像素、R 最大约 6.77、R 总量约 23,390.58；Niagara `UpToDate`、零错误、零警告。
- HQ 当前参数为 Filament/Medium/Body=`0.18/0.50/0.32`，半径 `14/48 px`，中性光照 `Ambient=1 / LightStrength=0`。
- Fixed Tick 60 Hz 已消除可变时间步造成的整片亮度脉动。
- 旧 `SSPR_M2A_TemporalOrchestrator` 关卡实例已从正式验证关卡移除；归档 Blueprint 资产保留，PIE 不再执行旧 Ping-pong MID 调度。

尚未通过的视觉 Gate：独立粒子感、连续拉丝、柔软烟体层次、最终受光、静止/转镜头/拉远、屏幕边缘和长时间运行。

### M4：深度与场景融合

- 在同一个 Grid 中评估 FrontDepth。
- 接入 SceneDepth 遮挡和软交界。
- 增加轻量受光。

**验收：** 烟雾能正确进入场景，不明显暴露二维载体。

### M5：性能与质量档位

- 记录目标显卡、粒子数、Grid 尺寸和材质耗时。
- 实现局部范围、动态分辨率和采样档位。
- 保留最高品质档作为视觉基准。

## 16. 完成定义

功能完成必须满足：

1. 正式效果不依赖屏幕 History Ping-pong。
2. 轨迹连续性主要来自存活粒子的年龄分布。
3. 屏幕 Raster 密度每帧从三维粒子重新生成。
4. Raster Grid 通过 Niagara 自管 `User.SSPR_SimRT` 与 Renderer 参数绑定提供给材质。
5. Content 中不需要正式外部 RT 链。
6. 相机旋转、平移和缩放不产生历史撕裂。
7. 30/60/120 FPS 下运动和形态基本稳定。
8. 最终画面达到高精度拉丝烟雾目标。
9. Niagara、材质和场景运行零错误、零警告。
10. UE 引擎源码修改完成本地 Git 提交与 bundle；项目 V1/V2 资产完成可恢复快照，项目文档完成本地 Git 提交。
