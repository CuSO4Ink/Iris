# M3 近景性能优化 Spec（2026-07-31）

> 状态（2026-08-09）：P1 与 P0 RawMoments 的 Gate S0/A/A2/B/C 已通过，Stage A/B 数据证据继续有效；Raw Streamline 与 FieldRecon V2.1 视觉失败。Rev B current-frame Stage C 已通过 R0/R1/R1.5/R1.6，但 R2 Body-only 的 V1～V6 均因固定 stencil 显形而失败；R3～R7 未开始，正式 M3 不替换。当前只允许 Niagara asset-level multipass；native RDG、C++、USF、插件和源码修改被用户明确禁止。
>
> **当前执行纪律**：不得从失败候选继续复制；不得把 sidecar、`UpToDate`、Emitter Active 或孤立 HLSL 片段当成 Stage 已正确执行的证据。必须独立证明 `Simulation Stage → 调用模块 → HLSL → DI → Main/Aux RT` 闭环，随后才允许低负载运行。
>
> **修订 v3（2026-08-06）**：保留 NeighborQuery counting-sort 选型；删除“完整列表可直接无界遍历”的隐含前提。Stage B 改为当前 cell 单次查询，并强制候选预算、overflow 观测与补偿；这是 StageB V1 卡死事故后的硬约束。
>
> **修订 v4（2026-08-06）**：并入 P0c——gather 内核只写线性原始矩（Raw0/Raw1 布局 v2），归一化后移到 Resolve/材质端；回收原 Aux.B 恒 0 通道装有符号速度矩，使 RK2 沿真流向积分并支持先平滑后归一化。同步松绑 §2 Main/Aux 语义硬约束、更新 Stage B 输出与 Gate B 校验口径。RT 数量不变、不踩 Temporal 红线，唯一新增风险是 RGBA16F 存原始矩的精度（尤其深度二阶矩）。
>
> **修订 v5（2026-08-08）**：纠正低负载运行 Gate 的测试假阴性。屏幕空间 Gate 必须固定并回读相机、确认粒子 ScreenUV/Depth 有效；绝对 marker/计数必须使用 `read_render_target_raw(..., False)`。PIE Reinitialize 后 DI clone 代次与数字后缀均不稳定，必须从当前绑定重新解析并核验实际 RT 尺寸。以上只修正验证流程，不放宽 A2/B/C/D 标准。
>
> **修订 v6（2026-08-08）**：Gate A2/B/C 实测收口。K=8 的 Top-K 成员保留率仅 2.06%，会让 FrontDepth/方向随成员切换产生可见抽动；最终预算提升到 K=64。`FrontDepthWeightThreshold` 改为相对每个解析核自身理论峰值比较，避免把低于 0.1 的合法解析贡献全部拒绝。2048² RT 只能在 UE 内分条聚合，不得把全量像素 JSON 送入 PowerShell/MCP。
>
> **修订 v7（2026-08-09）**：记录 Gate D 失败并增加 P0d Stage C。验证期批准单实例 `2 Raw + 2 Field`（四张 2048² RGBA16F 持久 RT 下限约 128 MiB），但必须先做 R1.5 的分辨率/tap/输入输出/采样/支撑微基准。最终性能硬上限改为同 packaged build、同机位、同覆盖条件下候选完整链 GPU median/P95 不高于 `/Game/NewNiagaraSystem.NewNiagaraSystem` 完整链；单 Stage 时间只作归因。
>
> **修订 v8（2026-08-09）**：R1.5 选择 33-tap Point 基线，R1.6 干净 Stage 中位 `2.04 ms`；R2 的 41-tap/109-load V6 数值全过但视觉仍显示固定椭圆 impulse footprint。V6 spot 受后台 8 Hz 追帧污染，不作为正式性能结论，但质量/成本组合已足够停止继续堆 tap。Niagara 单 dispatch 降为 correctness carrier；下一实现只能是 Niagara asset-level multipass/transient RT。native RDG、C++、USF、插件和源码修改不在项目范围内。

## 1. 背景与问题定义

- 主线：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev`（Dense 49×11 Raster，复制自 V4 冻结源）。
- 实测（2026-07-30 `.profViz`）：近景下 Dense Raster 单步 `17.70～18.88 ms`，超过 60Hz Fixed Tick 步长，触发"帧慢→补步→更慢"追帧螺旋（单帧最多 24 substep，总 GPU 468ms）。
- 粒子规模：`SpawnRate=50,000/s`、Lifetime 5s，约 25 万稳态粒子；屏幕覆盖率仅 2～5%。
- 根因两条：
  1. **原子串行化**：稠密核心区几千粒子对同一批像素做 `InterlockedAdd`，密度早已饱和，写入无区分度（冗余写）。Dense scatter 最高约 8 亿次原子请求，热点像素排队串行化是 17.7ms 的来源。
  2. **substep 乘数**：Raster/Resolve 跟随每个 Fixed Tick substep 执行，而画面每渲染帧只消费最后一次结果。
- 历史教训：Sparse V1 短时 Gate 为假阳性（空路径）；Sparse V2 的 `24.8~27.1×` 因未记录相机姿态被撤回。性能 Gate 当前处于重开状态。
- 外部佐证：3DGS tile-based sorted rasterizer 与本方案高度同构（~30 万高斯、1080p、全管线 2-4ms），且本项目矩累加可交换、不需要深度序，比 3DGS 更简单。

## 2. 目标与硬约束

**目标**：近景（相机贴近烟雾主体）下 Raster+Resolve 合计 ≤ 3ms/渲染帧，消除追帧螺旋，视觉与 Dense 基线无可辨认退化。

**硬约束（全部优化项共同遵守）**：
- 不引入 History / Temporal 累积（项目红线，V2 时代已否决 ping-pong）。
- Main/Aux 六属性**信息量**不变（密度、方向矩、深度矩、FrontDepth、速度、Coverage 全部可派生）；自 P0c 起 RT 存**线性原始矩**、归一化后移到 Resolve/材质端，通道语义按 P0c 布局 v2（此为对旧"RT 存归一化量"表述的正式修订）。
- 质量守恒：任何丢弃/稀疏化必须有期望级补偿。
- 只改 M3；V4 冻结源、V3 快照不动。
- Fixed Tick `0.01667s` 模拟节奏不变（解耦的是渲染侧，不是模拟侧）。
- 恢复点只认 **`.uasset` 二进制同名复制**；`duplicate_asset(NiagaraSystem)` 对本系统产出空运行副本，禁止作为备份 Gate（已实锤两次）。

## 3. 优化项

### P1 — Raster 与 Fixed Tick 解耦 ★最先实施（源码实锤，一天工作量）

**原理**：模拟保持 60Hz Fixed Tick，Raster/Resolve（或 gather Stage）每**渲染帧**只执行一次。直接打掉追帧螺旋的最坏 24× 乘数（先止血再手术），且与任何核优化叠乘。对 Dense 基线立即生效。

**实现（写死，源码级依据）**：
- 引擎在 Fixed Tick 循环内每 substep 写入 `Engine.System.CurrentTimeStep` 与 `Engine.System.NumTimeSteps`（NiagaraSystemSimulation.cpp / NiagaraModule.cpp 注册）。
- GPU tick 每 substep 生成一个，Stage 的 **Enabled Binding 每 substep 求值一次**（NiagaraGPUSystemTick.cpp L239-279）——机制成立。
- 做法：EmitterUpdate（CPU VM，每 substep 执行）计算 `bLastSubstep = (Engine.System.CurrentTimeStep == Engine.System.NumTimeSteps - 1)` 存入 emitter attribute，Raster/Resolve Stage 的 Enabled Binding 绑定该 attribute。
- B 方案（UI/编译链异常时）：Stage 的 NumIterations 绑 int 参数，非末 substep 置 0（`NumIterations <= 0` 同样跳过 Stage，源码同段实锤）。
- **不推荐**外部每帧写帧号 User 参数：User 参数每 game-frame 快照一次，substep 间无法区分，且需 emitter 持久状态比对、语义变成"用上帧末状态 raster"引入一帧延迟。

**已知边界行为（非 bug，需知晓）**：帧率高于 60Hz 或 fixed 预算不足的渲染帧 `NumTimeSteps=0`，该帧 Raster 不跑、RT 保持上帧内容（保持≠累积，不违反无 History 红线）；相机快速运动时投影滞后一帧，属可感知现象。

**Gate**：最小系统连通性与 M3 Dense 主线合入均 **✅ 已通过**。2026-07-31，`M3/PerfMinTest/NS_PerfMinTest_EnabledBinding` 从 1∶1 验证到 1∶4；2026-08-03，主线新增 `P1_EmitterFrameGate`，把 bool `Emitter.P1_IsLastSubstep` 绑定到 Raster/Resolve，ProfileGPU 得到 `12 ParticleSpawnUpdate : 3 Raster : 3 Resolve = 4∶1`。Main/Aux 唯一签名、非零、无 NaN/Inf、未画满；System `UpToDate`、零错误零警告；组件 DI 仍为 `1 Raster + 2 RT + 1 Grid2D`。**资产层两个硬约束**：① binding 目标必须是 **bool** 类型；② Python 侧设置只能用 struct 的 `import_text`。本次捕获相机距离约 `939 uu`，只用于 P1 执行比验证，不冒充历史最坏近景性能对照。

### P0 — NeighborGather：scatter→gather 架构翻转 ★主候选

**原理**：粒子只注册索引（scatter 端零重活），像素端 gather 聚合，累加全程零原子。原子串行化是排队问题（最坏 O(热点深度)），gather 是吞吐问题（并行可扩展）——25 万粒子/5% 覆盖/高重叠场景下量级优势 5~10×。

**首选 DI：`NeighborQuery`（UE 5.8 新增，counting-sort 架构）**

- 写入 pass 后引擎在 PostStage 自动执行 Histogram → PrefixSum → Scatter 三个 pass，产出按 cell 分段、cell 内按距 cell 中心距离排序的完整粒子列表；写入端无竞速丢弃。
- **完整列表存在不等于允许满载无界遍历。**Stage B 必须配置读取预算 K、记录 overflow，并对被截断的加性矩做 `N/min(N,K)` 期望补偿；FrontDepth 的截断偏差必须单独 Gate，不能用密度补偿掩盖。
- 引擎注释明确该 DI 为 "asymmetric gather (P2G rasterization)" 预期用法，即 Niagara 原生的 3DGS 式 tile binning。
- 显存：约 12MB（MaxCellsPerParticle=4）～ 27MB（=9），可接受；可关 `bUsePersistentIDs` 省 2 个 buffer。
- X×Y×1 二维退化可行（继承 Grid3D 基类，无 Z≥2 假设）。

**架构**：

```
Stage A（粒子迭代，替代 SSPR Rasterize Trails）:
  - 每粒子单次 AddParticleWithRadius 注册（半径 = 轨迹半长 + 3σ 横向）
    覆盖屏幕轨迹 AABB 内所有 cell
  - 注册前 clamp 轨迹长度，保证 AABB cell 数 ≤ MaxCellsPerParticle

Stage B（Grid2D 迭代 2048²，替代原 Raster+Resolve 两个 Stage）:
  - ExecutionIndexToGridIndex 取得当前像素；只查询该像素所属 cell
    （Stage A 已把 primitive 注册到全部覆盖 cell，禁止再做 3×3 重复查询）
  - cell count 为零 → 立即 early-out
  - 遍历前 min(cellCount, MaxCandidatesPerCell) 个粒子 → ParticleRead 读属性
  - 解析线积分核求值（见 P0b，每对 pixel↔particle O(1)）
  - 寄存器内累加**线性原始矩**（见 P0c 布局 v2，不在内核内提前归一化）；截断时对加性矩做期望补偿
  - SetRenderTargetValue 直接完整覆盖 Main/Aux RT（Raw0/Raw1 原始矩）；调试期额外输出 overflow
```

**首版参数**：cell = 32px（64×64×1 格）、MaxCellsPerParticle = 4（轨迹 clamp 后最多 2×2 AABB）、`MaxCandidatesPerCell` 为 User Parameter；安全首跑从 8 开始，只用于低负载结构/RT Gate，必须根据 overflow 分布调整，不能直接宣称最终画质。

**成本模型**：Stage B 固定执行 2048² 次 cell-count 查询，候选求值上界为 `G × K`；K=8 时最坏 33,554,432 次 pixel↔particle 求值。2~4ms 仅是设计目标，不是结论；实际瓶颈、NeighborQuery sorting 开销、overflow 与最坏 cellCount 必须在 Gate A2/C 实测。

**强制安全阀**：所有运行候选都必须有确定性 K 截断、overflow 计数和 `N/min(N,K)` 加性矩补偿。只有在低负载证明 `cellCount≤K` 时，才等价于完整列表；禁止先满载、后观察是否卡死。

**实施坑 checklist（源码实锤，违反即系统性错误）**：
1. **索引约定**：基类 `UnitToFloatIndex` 带 -0.5 中心偏移，直接 `floor()` 会错半格——统一使用 `UnitToCellCornerFloatIndex`，注册端与 gather 端必须同一约定。
2. **单次 Add 限制**：NeighborQuery 每粒子 slot 段固定（`ExecIndex() × MaxCellsPerParticle`），Add 系函数**只能调用一次**，第二次覆盖同段；AABB 超出 MaxCellsPerParticle 时循环**静默截断**——注册前必须 clamp。
3. **ParticleRead 无"上一帧"坑**：Grid2D 迭代 stage 不写粒子，self-read 读到的是本 tick 粒子 Update 后的数据，当帧 spawn 粒子也可读（NiagaraGpuComputeDispatch.cpp L927-938 实锤）。仅两条约束：gather Stage 排在粒子 Update/注册 Stage 之后；**读取的属性必须有消费者保活**（防编译器裁剪后返回默认值，坑手册 §7）。
4. gather Stage 不得开 partial particle update（self-read 硬约束，本来也不写粒子）。

**Fallback：NeighborGrid3D + cap（仅 NeighborQuery 排序 pass 实测超预算时启用）**

- 计数器语义（源码 L399-431 实锤）：`InterlockedAdd` 无条件执行、仅索引写入受 cap 保护，`GetParticleNeighborCount` 返回**真实尝试总数**（可 > cap）——无需独立计数通道，补偿系数 = `N / min(N, cap)`，零额外成本。
- 显存 ~1.05MB（64×64×1 × cap64 × 4B + 计数）。自动清空（`ClearBeforeNonIterationStage`）无需手动 pass。
- **已定量的画质风险（选它就要认）**：cap=64 竞速子采样在近景稠密 cell（N≈1000）产生 ~12%×cv 逐帧独立密度噪声；方向矩在涡旋/剪切区（带符号均值近零）相对方差爆炸；FrontDepth 期望偏移 ~R/65 且同量级逐帧抖动。无 Temporal 红线下均直接可见。缓解：cap 提 128/256（噪声 ∝1/√K，治标）+ FrontDepth 独立 scatter 原子 min pass。

### P0b — 解析线积分核（并入 P0，必须实施在 gather 内核）

Dense 的 `49×11=539` 枚举是 scatter 架构强加的；gather 中 pixel↔particle 一对一，直接解析求值。**注意：P0b 单独套在 scatter 上只省 ALU 不省原子次数，收益有限——它的正确位置在 gather 内核。**

**闭式**（粒子质量 m 沿屏幕线段 P0→P1 均匀展布，横向 σ 高斯；像素分解 `p−P0 = s·d̂ + w·n̂`）：

```
ρ(p) = m/(2πσ²L) · exp(−w²/2σ²) · σ√(π/2) · [erf(s/(√2σ)) − erf((s−L)/(√2σ))]
```

- **归一化天然精确**：∫ρ = m 严格成立，比离散核的样本权重和归一化更强地满足质量守恒红线；顺带消灭 Sparse V2 为守恒额外做的 `49+11+33+7` 次权重求和包袱。
- **L→0 退化连续**：`L < 0.25px` 时切各向同性点高斯分支，两支在阈值处差 O(ε²/σ²)，无奇异。
- **erf 选型**：HLSL 无内建 erf，用 **Winitzki / tanh 型近似**（~5 ALU，最大误差 ~1.3e-4）；gather 累加在寄存器 float 进行（不过 65535 定点），误差远低于 RGBA16F 量化（~5e-4）。每像素每粒子仅 2 次 erf + 1 次 exp。
- **一阶矩闭式**（仅当现行核对深度/属性做沿轨迹插值时才需要；若粒子级常数则矩 = 属性 × ρ(p)，勿加复杂度——实施前先确认现行离散核行为）：`I1 = s·I0 + σ²·[g(s) − g(s−L)]`，DepthSigma 二阶矩同样有闭式。
- **预期画质差异（Gate 对比时不算回归）**：离散核端点有半样本宽度系统偏移，解析核端点更"软"；σ 小于纵向步长时离散核的欠采样条纹被解析核消除。
- **屏幕边缘检查项**：解析核对出屏部分照常计入归一化，与现行核的出屏样本处理可能不同——Gate 用例必须含屏幕边缘。

### P0c — 原始矩输出布局 v2 + 归一化后移（并入 P0，随 gather 内核一起落地）

**动机**：现行设计在 Stage B 内核里就把矩除以密度、算出 MeanDepth/DepthSigma/Coherence 再写 RT。归一化量**不是线性可加的**——P2 半分辨率或任何双边模糊/上采样若作用在归一化后的角度、平均深度、深度方差上，结果在数学上就是错的（模糊比值 ≠ 比值的模糊）。修正方向：**gather 内核只累加线性可加的原始矩，归一化后移到 Resolve/材质端**。

**RT 布局 v2（仍是 2 张 RGBA16F，数量不增加）**：

```
Raw0 (SSPR_SimRT) RGBA:
  R = Density            (Σ ρ)
  G = TensorCos2Sum      (Σ ρ·cos2θ)
  B = TensorSin2Sum      (Σ ρ·sin2θ)
  A = DepthMoment1       (Σ ρ·depthNorm)

Raw1 (SSPR_AuxRT) RGBA:
  R = DepthMoment2       (Σ ρ·depthNorm²)
  G = FrontDepth         (min depthNorm，超阈值贡献者)
  B = VelocityMomentX    (Σ ρ·vX，屏幕空间 ScreenDeltaUV 语义)
  A = VelocityMomentY    (Σ ρ·vY，屏幕空间 ScreenDeltaUV 语义)
```

**Resolve/材质端派生（不占额外通道）**：

```
MeanDepth   = DepthMoment1 / max(Density, ε)
DepthSigma  = sqrt(max(0, DepthMoment2 / max(Density, ε) − MeanDepth²))
Coherence   = sqrt(TensorCos2Sum² + TensorSin2Sum²) / max(Density, ε)
Velocity    = (VelocityMomentX, VelocityMomentY) / max(Density, ε)
Coverage    = (Density > ε) ? 1 : 0        // 由 Density 推得，不占通道
```

**收益**：
- **回收原 Aux.B 恒 0 的 Reserved 浪费通道**，改装速度矩——零新增 RT。
- **获得有符号速度场**：方向张量 `cos2θ/sin2θ` 天生 180° 对称、无法分正反向；速度矩恢复真实有符号流向，**材质端 RK2 Streamline 得以沿真流向积分**，直接对着"连续长丝 / 去粒子感"目标。
- **先平滑后归一化**：P2 半分辨率、双边上采样都作用在线性矩上，结果数学正确。
- 与 P0b 天然一致：erf 核输出的本就是 `Σ contribution·attr` 形态的矩，此布局只是不在内核里提前除。

**实施约束（RGBA16F 精度红线）**：
- 深度矩必须用**归一化深度 depthNorm∈[0,1]** 累加（P0b 核内已 saturate），禁止用原始 UU 深度，否则 `DepthMoment2` 动态范围爆 half 精度。
- `DepthSigma` 是两相近大数相减开方，half 下易出负/噪声；`max(0,·)` 必留，且深度矩尽量走归一化域。
- Velocity 存**屏幕空间**（对齐 `SSPR_ScreenDeltaUV`），不得混世界速度；材质端 RK2 在屏幕空间积分。
- 近景稠密像素 Density 可达数百上千，Gate B 需检查 half 是否溢出/丢精度，必要时给密度或深度矩加固定尺度缩放（Resolve 端对称还原）。
- 归一化后移会让材质/Resolve 每像素多几次除法+sqrt，覆盖像素仅 2~5%、可忽略，但记入成本模型。

### P2 — 半分辨率矩场 + 全分辨率材质重建（可选滑杆，P0 达标则不必做）

**原理**：密度/方向/深度矩均为低频场；高频流丝是材质端 Streamline 重建产物。矩场降至 1024²：gather 像素量与 RT 带宽砍 4×。

**修订后的设计要点**：
- **σ clamp**：`WidthPx=1.25` 在 1024² 为 0.6px、低于 Nyquist。生成 1024² 矩场时横向 σ clamp ≥1px@1024（=2px@2048），**等比降峰值保持 ∫ρ 不变**（守恒红线 OK）；已知取舍：细丝下限变粗一档，材质端金字塔部分找回锐度。
- **上采样加权**：烟雾无硬深度边缘，FrontDepth 引导基本退化为双线性（无害但别指望它）；真正要防的是轮廓 halo——空像素 FrontDepth 无效，**改用 Coverage/valid-mask 主加权**（有效像素才参与、权重乘 coverage），FrontDepth 差仅作次级权重。
- `SSPR_InvTextureSize` 等 MI 参数同步。**不与 P0 混在同一候选**，独立 Gate；画质对比必须含快速细丝用例。

### Plan C — 止损线（P0 gather 路线全灭时启用）

解析核 + 半分辨率直接套在**现有 Dense scatter** 上（1024² + 每粒子解析求值缩减样本面积）——纯参数/内核级修改，1 天可验证，预期 17.7ms → 4~6ms。不达 3ms 目标，但作为架构翻转失败时的止损。

### F — Dense 原地救急项（仅 Plan C 也不够时叠加）

- **Wave 内预聚合**：同 warp 落同像素的贡献先 `WaveActiveSum` 再原子写一次，只改 HLSL 内部。前置：确认 Niagara 编译目标下 SM6 wave intrinsics 可用。
- **随机稀疏化**：稠密区按局部密度概率 p 跳过 splat、贡献乘 1/p，期望守恒。

### S — 源头减产（独立立项，不进本轮）

`SpawnRate` 按密度需求重标定 + `DensityPerParticle` 补偿。改变输入分布，必须独立过视觉 Gate，禁止与架构改动混在同一候选。

**近景 LOD 保险丝（新增，极端贴脸场景）**：按屏幕覆盖率动态降 SpawnRate 并等比放大粒子 mass（期望级质量守恒，不踩红线）。仅作为最终保险丝立项，不进本轮候选。

### 否决项

- Temporal / checkerboard 分摊：违反无 History 红线。
- Async compute：不减绝对时间，编辑器态收益微弱。
- 粒子按 tile 排序后 coherent scatter：Niagara 无粒子排序原语，NeighborQuery 已是其等价物。
- 自定义 indirect dispatch / LDS tile 分类：Niagara sim stage 不暴露，引擎层面做不了。软替代：gather 内按邻域计数分支快/慢路径（可后补）。

## 4. 执行顺序与 Gate 流程（v2 调整：P1 最先）

```
0. 前置：M3 Dense .uasset 二进制备份（Saved/CodexBackups/）
1. P1：最小系统验证 Enabled Binding 资产层连通性 → 合入 M3 Dense 基线
   → 同机位复测（这一步已消灭 substep 乘数，Dense 可用性立即改善）
2. P0 干净候选：从 _RecordPoint_12ms 新建独立资产；不得复制任何失败候选
   Gate S0：结构闭环——无旧 V1/Safe V2 默认对象或依赖；无粒子端 gather；
            Stage A/B 调用模块、HLSL、DI、RT 连线逐项回读；
            Gather Stage bDisablePartialParticleUpdate=true；sidecar 不作为 Stage 证据
   Gate A：低粒子/低分辨率 NeighborQuery 连通性（一次 AddParticleWithRadius +
           当前 cell GetParticleNeighborCount/GetParticleNeighbor + ParticleRead 可读）
   Gate A2：counting-sort 三 pass 开销实测（250k × MaxCellsPerParticle slots）
            + cellCount/overflow 分布；未过 Gate 前禁止满载
   Gate B：RT 原始 Gate（按 P0c 布局 v2 校验 Raw0/Raw1 原始矩通道语义、签名唯一、非零、
           无 NaN/Inf、未画满、含屏幕边缘用例；抽验 half 精度无溢出/丢精度，
           Resolve 端派生的 MeanDepth/DepthSigma/Coherence/Velocity 数值合理）
   Gate C：同机位 A/B ProfileGPU —— 必须记录相机姿态；用户保持视口前台；
           Dense(+P1) 与候选在完全相同近景机位各抓一次
   Gate D：❌ 已失败；P0c Raw 数据层保留，旧显示 Resolve 作废
   P0d Stage C：按执行合同依次执行 R0/R1/R1.5/R1.6/R2～R6b
3. 降级链：Gate A/A2 失败 → NeighborGrid3D fallback（重新评估画质风险）
           → 仍失败 → Plan C 止损线 → 仍不够 → F 救急项叠加
4. P2 评估：仅在 Stage C 视觉与完整性能 Gate 后仍需余量时开独立候选
5. 收口：胜出候选替换 M3 主线资产（干净组件替换，不原地 Rebind），LOG.md 记录
```

**Gate C 纪律（对 2026-07-30 撤回事故的直接回应）**：
- ProfileGPU 前必须读回并记录视口相机 Location/Rotation 与到粒子系统距离；
- Dense 基线与候选必须同会话、同机位、视口前台条件下采集；
- 任何"候选 RT 为空但性能变好"的组合直接判假阳性。

**必须实测验证的未知项**：
1. NeighborQuery counting-sort 三 pass 在 250k×4 slots 的开销（Gate A2，决定首选 vs fallback）；
2. Stage B 实际毫秒数、近景最坏 cellCount、K 截断率与补偿后的质量误差；
3. ~~Enabled Binding 绑 emitter attribute 的资产/UI 层连通性~~ → **已验证通过（2026-07-31，见 §3-P1 Gate）**；
4. 解析核 vs 离散核画质对比（端点软化、屏幕边缘为预期差异点，不算回归）。

## 5. 当前基线数据（供 Gate C 对照）

| 项 | 值 |
|---|---|
| Dense Raster 单步（近景，2026-07-30） | 17.70～18.88 ms |
| Resolve 单步 | 0.19～0.20 ms |
| Grid Clear | ~0.325 ms |
| 稳态粒子数 | ~25 万（Dispatch 25.1~25.4 万） |
| 屏幕覆盖率 | 2～5%（8.2万～22.3万 / 4,194,304 非零） |
| P0 RawMoments 低负载 Gate A（2026-08-08） | 256²、644 粒子；CellCount `0..54`；生产 Main/Aux 八通道非零、无 NaN/Inf；仅连通性通过 |
| P0 RawMoments Gate A2（2026-08-08） | 80k 粒子：nonzero cells=1047，cellCount p50/p95/p99/max=`35/1485/3930/4785`；K8/K64 保留率=`2.06%/11.46%`；251,678 粒子样本 Stage A/sort=`0.67/0.52 ms` |
| P0 RawMoments Gate B（2026-08-08） | 2048²、K64：覆盖 716,764（17.09%）；Main/Aux 八通道 finite、half saturation=0；FrontDepth nonzero=643,843；密度>1e-3 时无矩丢失或严重负方差 |
| P0 RawMoments Gate C（2026-08-08） | 固定机位 `(-592.975,299.746,3052.565)` / `(-38.105,164.537,0)`；候选稳态整帧 14.42ms、链路 0.67ms；保守 100,671 粒子链路 1.72ms；Dense 66k～75.5k 单次 Raster 中位 10.76ms |
| 止血 CVar | `fx.Niagara.SystemSimulation.MaxTickSubsteps=4`（会话级，编辑器重启即失效，开工必查） |
| 远机位编辑器态 GPU（2026-07-31） | 7.07 ms（Dense 未被喂满，不作为对照） |

## 6. 状态跟踪

| 项 | 状态 |
|---|---|
| P1 Enabled Binding 连通性验证 | **✅ 已通过**（2026-07-31：语义验证 + 最小系统资产层判定 1∶1→1∶4 实测） |
| P1 合入 M3 Dense 主线 | **✅ 已通过**（2026-08-03：双 Stage binding、主线 4∶1、有效 Main/Aux、零编译错误） |
| P0 `NeighborGather_StageB_V1` | **❌ 失败**：3×3 × 无界 cellCount，满载卡死；已删除，禁止复用 |
| P0 `NeighborGather_StageB_Safe_V2` | **❌ 失败**：旧 DI/孤儿节点残留、partial particle update 未禁用、Stage 挂载未证明；已删除，禁止复用 |
| P0 RawMoments V1 数据层 | **✅ Gate S0/A/A2/B/C**：rate=40,000、K=64 已落盘；Raw 证据继续有效，显示 Gate D 见下一行 |
| P0 RawMoments V1 视觉 | **❌ Gate D 失败**：Raw Streamline 与 V2.1 FieldRecon 均被用户否决；数据层不回滚 |
| P0d Continuous Field Resolve | **❌ R2 视觉失败 / Request Changes**：R0/R1/R1.5/R1.6 已通过；33-tap 基线保留，41-tap V6 不升级生产。下一步仅 Niagara multipass；禁止 RDG/源码路线 |
| P0c 原始矩布局 v2 + 归一化后移 | **✅ 完整 Gate B 已通过**：2048² 八通道语义、有限值、half、边缘与派生量均已实测；低密度尾部负方差按材质端 `max(0,·)` 处理 |
| P0 fallback（NeighborGrid3D + cap） | 封存（Gate A/A2 失败才启用） |
| Sparse V2 `33×7` | 有效 RT Gate 通过；性能 Gate 无同机位证据，非当前主线 |
| Plan C 止损线 | 封存 |
| P2 半分辨率矩场 | 可选滑杆，未评估 |
| F 救急项 | 封存 |
| S 源头减产 / 近景 LOD 保险丝 | 未立项 |
