# M3 解析高斯 Splat 技术路线 SPEC — Analytic Gaussian Splat (AGS)

> 版本：v2.2（2026-08-09 对齐下游 Stage C）
> 基线来源：`_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`（用户确认为干净可用基线）
> 上游规格：`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 定义 P0 Stage A/B 架构与 P0c Raw0/Raw1 契约；`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 只作为既有字段与视觉基线参考。
> 当前角色：本文只定义 **P0b——gather Stage B 内的 pixel↔particle erf 解析核**。Stage A/B 与 P0c Raw 数学已通过；旧视觉 Gate D 失败不推翻本核。下游当前执行入口为 `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md`，本文不定义 Stage C Coverage/Depth/分频。
> 下游状态：Stage C 的 R0/R1/R1.5/R1.6 已通过，R2 Body-only 因固定 Point stencil 显形而失败；该视觉/后端结论不反向修改本文的 Stage B erf/Raw 契约。`D_ref`、epsilon、front window 与 half 容差仍以 `P0C-R0-NUMERIC-REPORT-20260809.md` 为准。

---

## 0. 一句话定义

在 P0 的 **2048² Grid2D 像素端 gather Stage B** 中，对每个候选 pixel↔particle 用一个闭式公式求各向异性高斯贡献，替代 Dense scatter 的 `49×11=539` 离散采样和原子累加；方向、深度与有符号速度的线性原始矩在寄存器内聚合后直接写 Raw0/Raw1 RT，归一化统一后移到 Resolve/材质端。

本质：这是一个**降维（2.5D）+ 沿轨迹拉伸**的各向异性高斯 splat，数学上等价于 3DGS 的 gaussian primitive splatting；累加语义是可交换的体积密度/矩聚合，不是深度排序 alpha 合成。

---

## 1. 立项动机（为什么做这条路线）

### 1.1 现状问题（事实锚点）
- 当前 Dense 主线：每粒子固定枚举 `49×11=539` 候选，每有效样本最多 `5× InterlockedAdd + 1× InterlockedMax`。近景约 28~30 万粒子时单次 Raster `17.7~18.9 ms`，且超 `16.67ms` 后触发 Fixed Tick 补步追帧螺旋（累计 >100ms）。
- 历史“12ms”含 Scalability 裁剪且不是可信的同机位/同负载对照；`_RecordPoint_12ms` 只作为干净资产锚点，不能把名称中的数字当性能基线。正式基线以用户已记录的关闭 System 编辑器、仅关卡实例、满量同机位 Dense+P1 数据为准。
- 离散 539 枚举的固有缺陷：采样条纹、半样本宽度系统偏移、粒子稀疏时的可辨认颗粒感（= 用户要消除的"粒子感"根源）。
- Sparse Raster（`125` 稀疏采样代表 `539`）已在 G5.5 **失败回滚**——减采样点不是出路。

### 1.2 为什么在 P0 gather 中使用解析核
| 目标 | Dense scatter 离散枚举 | P0b 像素端解析核 |
| --- | --- | --- |
| 性能 | 539 样本 × 多次原子/粒子 | 每个候选 pixel↔particle 约 2 erf + 1 exp，无原子；具体毫秒数只认 Gate C |
| 去粒子感 | 离散采样→条纹/偏移/颗粒 | 数学连续，无采样痕迹，粒子稀疏也平滑 |
| 精度/观感 | 近似质量守恒、边缘漏 | `∫ρ=m` 严格成立、primitive 连续；是否优于 Niagara Fluid 只由 D6 人工对照判定 |

3DGS 提供了成熟数学参考，但本项目的性能、质量和稳定性必须由自身 RT/视觉/ProfileGPU Gate 证明，不能由外部量级类比代替。

---

## 2. 范围与红线

### 2.1 只改这里
- **本文负责的唯一内容**：Stage B 内的解析贡献函数及 P0c 线性原始矩聚合公式。Stage A 注册、Grid2D Stage 配置、NeighborQuery 预算、Raw0/Raw1 契约和 Gate 顺序以 `M3-PERF-OPTIMIZATION-SPEC-20260731.md` 为准。

### 2.2 一律不改（继承基线，违反即出范围）
- P0 架构：Stage A 粒子端只注册；Stage B 为 Grid2D 2048² 像素迭代、当前 cell 有界 gather、禁止 partial particle update。
- 原始矩语义：`Density=Σρ`，方向矩为 `Σρ×cos2θ / Σρ×sin2θ`，深度矩为 `Σρ×z / Σρ×z²`，速度矩为 `Σρ×vX / Σρ×vY`；FrontDepth 为满足阈值贡献的最小归一化深度。
- P0c Raw0/Raw1 布局：Raw0/Main=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`；Raw1/Aux=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`。两张 RT 均为 2048² RGBA16F、Bilinear、无 Mip、每帧完整覆盖。
- `MeanDepth/DepthSigma/Coherence/Velocity/Coverage` 必须在 Resolve/材质端由原始矩派生；Stage B 禁止提前归一化。
- Resolve→材质 Streamline(RK2)/DepthCue 链、Renderer 双纹理绑定。
- `50000/s` SpawnRate、5s Lifetime、Fixed Tick `0.01667s`、无 History。
- 所有可调参数开放到 Niagara User Parameters / MI，不散落 HLSL 常量。

### 2.3 工作方式红线
- **不直接改 12ms 基线资产，也不复制失败候选**：只从 `_RecordPoint_12ms` 创建新的自包含 P0 候选；AssetRegistry/嵌入默认对象均不得引用历史 V1/Safe V2。
- 每步 write 后独立验证 `Stage→模块→HLSL→DI→RT`；sidecar 不导出 Simulation Stage，不能单独作为结构证据。编译通过≠Stage 执行，更不等于出效果。
- 编辑器由用户启停；MCP 编译状态有滞后/抓不全 GPU 着色器错误的盲区，最终真伪以用户前台 tick 后观察为准。

---

## 3. 核心算法：解析高斯 primitive（AGS 内核）

### 3.1 primitive 定义
每个粒子这一帧是一段屏幕空间轨迹 `P0→P1`（长 `L`，方向 `d̂`），横向高斯宽度 `σ`（`StreamlineWidthPx` 量级）。像素 `p` 相对轨迹分解：
```
p − P0 = s · d̂ + w · n̂      （s 沿轨迹，w 横向，n̂ ⟂ d̂）
```

### 3.2 密度闭式（还原 Σ w，替代 539 枚举求和）
质量 m 沿线段均匀展布、横向 σ 高斯：
```
ρ(p) = m/(2πσ²L) · exp(−w²/2σ²) · σ√(π/2) · [ erf(s/(√2σ)) − erf((s−L)/(√2σ)) ]
```
- `exp(−w²/2σ²)`：横向高斯衰减。
- `erf(s/…) − erf((s−L)/…)`：沿轨迹方向的线积分闭式（`erf` 用 Winitzki/tanh 近似，~5 ALU，最大误差 ~1.3e-4）。
- **归一化天然精确**：`∫ρ dp = m` 严格成立（质量守恒红线比离散核更强）。

### 3.3 L→0 退化
`L < 0.25px` 切各向同性点高斯分支 `ρ = m/(2πσ²)·exp(−|p−P0|²/2σ²)`；两支在阈值处差 O(ε²/σ²)，无奇异。

### 3.4 P0c 原始矩对接（关键：属性为粒子级常数，无需沿轨迹一阶矩）
已确认当前 `cos2θ / sin2θ / z / z²` 均为粒子级常数（不沿轨迹插值）。因此 Stage B 对当前像素的候选列表在寄存器内累加：
```
w := ρ(p)
Density      += w
TensorCos2   += w × cos(2θ)
TensorSin2   += w × sin(2θ)
DepthMoment1 += w × z              // z ∈ [0,1] 归一化 View Depth
DepthMoment2 += w × z²
FrontDepth    = min(FrontDepth, z) // 仅 w 高于 FrontDepthWeightThreshold 参与
VelocityMomentX += w × vX          // v = SSPR_ScreenDeltaUV，有符号屏幕速度
VelocityMomentY += w × vY
```
- 若 cellCount>K，Density/方向矩/深度矩/速度矩按上游 Spec 的 `N/min(N,K)` 做期望补偿；FrontDepth 不可用同一倍率补偿，必须单独记录截断偏差。
- 循环结束后不做除法或开方，直接按 P0c 契约写 Raw0/Raw1；`MeanDepth/DepthSigma/Coherence/Velocity/Coverage` 在 Resolve/材质端派生。
- **不需要 P0b 一阶矩闭式**（那是属性沿轨迹插值才要的）。若将来改成沿轨迹插值属性，再引入 `I1 = s·I0 + σ²·[g(s)−g(s−L)]`，本 spec 不做。

### 3.5 候选覆盖与像素求值
- Stage A 计算轨迹 support（线段半长 + 横向 `3σ`），用一次 `AddParticleWithRadius` 把粒子注册到所有覆盖 cell；注册前 clamp，禁止超过 `MaxCellsPerParticle`。
- Stage B 用 `ExecutionIndexToGridIndex` 得到当前像素中心 `p`，只查询当前 cell；逐候选投影并做 support reject，然后代入 §3.2 闭式。
- 禁止在 Stage B 再做 3×3 cell 重复查询，也禁止在粒子端枚举 AABB 像素或写 `P0_AccumPosition` 等原型属性。

---

## 4. 实施步骤（Gate 驱动，一步一验证）

- **步骤 0｜候选隔离**：从 `_RecordPoint_12ms` 新建候选；证明无任何失败候选引用、孤儿 gather 或第二 writer。
- **步骤 1｜Stage 结构 Gate**：Stage A 只做一次屏幕空间注册；Stage B 是 Grid2D 2048² 像素迭代、`bDisablePartialParticleUpdate=true`，且调用模块/DI/RT 连线完整回读。
- **步骤 2｜密度闭式**：接 §3.2/§3.3，只跑 Density；Winitzki/tanh 对拍参考 erf，误差 <2e-4。**Gate D1**：1/4/16 粒子确定性、`∫ρ` 质量守恒、与 Dense DebugRaw 无系统性错位。
- **步骤 3｜原始矩接入**：按 §3.4 接 signed 方向矩、深度矩、FrontDepth 与有符号速度矩。**Gate D2**：Tensor/Coherence 随 Curl 连续旋转；Mean/FrontDepth 随相机距离单调；Velocity 与 `SSPR_ScreenDeltaUV` 方向一致；空像素无伪深度/速度；长跑不累积（复用 G5.1 字段 Gate）。
- **步骤 4｜Raw RT 贯通**：Stage B 按 P0c 布局完整覆盖 Raw0/Raw1；MeanDepth/DepthSigma/Coherence/Velocity 由下游派生。Coverage-like certainty 不在 Raw 通道中，Stage C 按自身合同从 Density 显式推导。**Gate D3**：两 Raw RT 同帧同分辨率、非零、无 NaN/Inf、未画满、冷启动有效，且八通道签名与派生量语义正确。
- **步骤 5｜有界安全 Gate**：从低粒子量/低分辨率开始，记录 cellCount、overflow、截断率与补偿误差；逐级恢复负载，任何一级超预算立即停止。
- **步骤 6｜性能 Gate**：关闭 System 编辑器、仅关卡实例、同机位 ProfileGPU。**Gate D4**：不触发补步螺旋，且相对 Dense+P1 有真实收益；不预设毫秒结论。
- **步骤 7｜视觉/精度 Gate**：旧 Resolve 的 **Gate D5/D6 已失败**；AGS/P0c 数据层保留。新的去粒子感与参考观感由 Stage C 的 R2～R6b 重新验收。

---

## 5. 参数（全部开放到 User Parameter / MI）
| 参数 | 含义 | 首版 |
| --- | --- | --- |
| `AGS_SigmaPx` | 横向高斯宽度 σ | 承接 `StreamlineWidthPx` 1.25~2 |
| `AGS_LengthClampPx` | 轨迹长度 clamp 上限 | 待定（控 AABB 像素数） |
| `AGS_PointFallbackPx` | L→0 点高斯阈值 | 0.25 |
| `AGS_ErfMode` | erf 近似型（Winitzki/tanh） | Winitzki |
| `P0_MaxCandidatesPerCell` | 每像素候选硬上限 K | 低负载首跑 8，按 overflow Gate 调整 |
| `FrontDepthWeightThreshold` | 参与 FrontDepth 最小值的最小 ρ | 沿用基线 |
| `SSPR_DepthNearUU/FarUU` | 深度归一化范围 | 0 / 10000 |

## 6. 主要风险与对策
- **erf 近似误差污染方向/深度矩**：矩累加在寄存器 float，erf 误差 ~1.3e-4 远低于 RGBA16F 量化 ~5e-4；Gate D1 对拍守恒。
- **候选截断偏差**：加性矩做期望补偿并记录 overflow；FrontDepth 单独比较完整低负载参考，不能假设无偏。
- **注册覆盖膨胀**：`AGS_LengthClampPx` + `MaxCellsPerParticle` 双重约束；`AddParticleWithRadius` 每粒子只能调用一次。
- **Stage 挂载盲区**：孤立 scratch HLSL、函数调用节点或 `UpToDate` 都不足以证明 Simulation Stage 正在执行，必须读回 Stage 配置并以 RT 运行证据闭环。
- **深度矩溢出**：z 先归一化到 `[0,1]`，寄存器 float 聚合后写 RGBA16F。
- **MCP 编译盲区**：GPU 着色器错误 MCP 抓不全，每次 ApplyChanges 后须用户前台 tick 确认真编译状态。

## 7. 与其它路线关系
- **P0 gather**：当前主线；本文是其 Stage B 数学内核子规格。
- **P2 半分辨率矩场**：P0 正确性与视觉 Gate 通过后仍需余量时，另开候选评估。
- **Plan C scatter AGS**：仅当 P0 全路线失败时回到上游 Spec 重新立项；不与当前实现混写。
- **NeighborGrid3D**：仅在 NeighborQuery sorting Gate 失败时启用的独立 fallback。

## 8. 完成定义（DoD）
本文的 P0b/P0c 数据内核完成定义只要求干净候选通过 Stage 结构、D1～D4 数学/字段/Raw RT/性能 Gate；这些证据已经成立。最终产品完成仍要求下游 Stage C 通过 R0～R6b，并由用户确认无粒子感、参考观感与完整性能上限。任何单独的编译成功、Emitter Active 或 HLSL 关键字命中都不构成完成证据。
