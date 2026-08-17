# P0c Continuous Field Resolve V2.2 — Implementation Review Draft

> 审查状态：**REQUEST CHANGES**。方向通过，实施草案未通过；本文件保留为被审 Rev A，不是权威 spec，也不授权 UE 实施。修订稿见 `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md`。
>
> 审查通过后的顺序：先把最终决议并入 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`、`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 和当前执行计划，再开始 UE 资产修改。
>
> 当前事实：P0c Stage A/B、erf 解析核和 Raw Main/Aux 数据层保留；V2.1 的结构/编译成立，但视觉已被用户判定为白色刷毛/排线，Gate D 失败。

审查依据分工：`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 负责视觉/字段重建，`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 负责 P0 架构与性能 Gate，`ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md` 负责 Stage B erf 核与 P0c 原始矩数学。

## 0. 审查者快速背景与当前进度

**需求背景**：本项目用屏幕空间粒子重建替代高成本、低体素精度的 Niagara Fluids Grid3D 气体。形态参考 `/Game/NewNiagaraSystem.NewNiagaraSystem`：需要连续体积、大中尺度卷吸/卷曲、拉伸分裂、边缘细丝和自然耗散；不是只做圆形气团，也不是把粒子画成长线。目标是在不默认求解完整 Navier–Stokes、且完整系统 GPU 成本不高于该参考的前提下，获得更高可见精度。

**已完成的数据/性能层**：当前 P0c 候选已经完成粒子端 Stage A 有界注册、2048² 像素端 Stage B current-cell/K64 gather、erf 解析高斯核和双 RGBA16F Raw RT。Raw0/Raw1 八通道原始矩、FrontDepth、有限值/half、冷启动、Stage/DI/Renderer 连接及同机位技术性能 Gate 均已验证；现有证据中候选稳态整帧约 `14.42 ms`、SSPR Stage A/B 链约 `0.67 ms`。这些数字不包含本草案新增 Field Resolve，也不能代替与 Niagara Fluids 的干净完整系统 A/B。

**已失败的视觉层**：第一条 RawMoments Streamline 路线保留 Raw 单粒子 Core，并用低 Contrast 抬亮离散贡献，结果放大粒子感；已否决。第二条 Normalized FieldRecon V2.1 虽满足局部矩正则化、support denominator、深度约束和同场三频带的结构要求，但仍把 `8 steps × 5 lanes` 采样节奏直接显形成白色刷毛/排线，Body 不连续、Medium 支撑不足、Filament 承担主体；用户再次否决。旧 G5/GS 资产和正式 M3 均仍保留，当前 P0c 数据层没有被推翻。

**当前准确进度**：项目停在“数据层通过、视觉 Gate 失败、下一 Resolve 架构待审查”。源粒子运动已经冻结为后置备选；Stage C、Field RT、二维 scale-space stencil、residual/ridge 分频均尚未实施。本文的作用就是在改权威 spec 和 UE 资产之前，让审查者先检查这些新增判断是否成立。

## 1. 本轮拟定结论

下一候选不继续调 V2.1 的 `8 steps × 5 lanes` 材质追踪，也不修改源粒子运动。拟将 §14.3 已批准的“当前帧归一化连续场”真正物化为一个可单独读回、可分频调试的 2048² Field Resolve：

```text
当前源粒子运动（冻结）
    -> Stage A：NeighborQuery 有界注册（不改）
    -> Stage B：P0c erf gather，输出 Raw0/Raw1 原始矩（不改）
    -> Stage C：Current-frame Continuous Field Resolve（新增）
         -> 同一归一化场的 Tight / Mid / Body 三个尺度
         -> 同一场传播得到的 Mean / Sigma / Front Depth
    -> Material：由三个尺度做 Body / Medium / Filament 分频
         -> Depth Transport
         -> Smoke Resolve / Lighting
```

这里的 GS/P0c 仍负责“粒子 → 紧支撑密度与原始矩种子”；新增 Resolve 只替换失败的显示重建，不重做 Stage A/B。

## 2. 冻结项与禁止项

以下内容在本轮保持不变：

- 活动数据候选：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`。
- Stage A 粒子端 `AddParticleWithRadius` 注册、Stage B 2048² current-cell/K64 gather、P0b erf 解析核。
- Raw0/Main=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`。
- Raw1/Aux=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`。
- 2048²、RGBA16F、Bilinear、Mip Disabled、Fixed Tick `0.01667s`、P1 last-substep gate。
- 固定诊断输入 `rate=40,000`、`K=64`、`DensityPerParticle=0.03`，直到视觉变量隔离完成。
- Fountain/CurlNoise/Drag/Velocity 等源粒子运动冻结；调整源运动只保留为后置备选。
- 正式 M3、Dense/G5 视觉基线、V2.1 失败资产均不原地覆盖。

禁止项：

- 不使用 History、A/B 跨帧反馈或 Blueprint Ping-pong。
- 不恢复 Raw/isolated particle core 可见兜底。
- 不使用 `Contrast<1` 抬亮弱离散粒子。
- 不使用一个大半径各向同性 Blur 代替三频带。
- 不继续用宽 Streamline 或规则横向 lanes 生成 Body。
- 不要求 Filament 必须连接主 Body；具有局部密度、方向和深度支撑的脱离烟缕可以保留并自然衰减。
- 视觉 Gate 通过前不降低 Raw Main/Aux 的 2048² 分辨率、粒子率或 K64 预算。

## 3. 拟实现的连续场算子

### 3.1 先正则化原始矩，再归一化

对查询像素 `p` 的紧邻域先累计原始量，之后才做除法：

```text
D       = Σ Density
T       = Σ (TensorCos2Sum, TensorSin2Sum)
M1/M2   = Σ (DepthMoment1, DepthMoment2)
V       = Σ (VelocityMomentX, VelocityMomentY)
Mean    = M1 / max(D, ε)
Sigma   = sqrt(max(M2 / max(D, ε) - Mean², 0))
Tangent = 0.5 * atan2(T.y, T.x)
Velocity= V / max(D, ε)
```

低支撑区输出低置信度；零/弱张量不得生成任意屏幕 X 方向。方向、速度与深度只作为场引导，不直接成为可见密度。

### 3.2 一个连续场的三个尺度

拟用固定上限的二维、张量引导、深度约束 normalized convolution 定义同一个尺度空间 `F(p,r)`，而不是沿若干可见轨迹描线：

```text
N_r(p) = Σ[q in K_r] W(p,q,r) * Density(q)
S_r(p) = Σ[q in K_r] W(p,q,r) * Coverage(q)
F(p,r) = N_r(p) / max(S_r(p), ε) * SupportConfidence(S_r)

W = EllipticSpatialWeight(Tangent, Normal, r)
  * DepthBilateralWeight(Mean, Sigma, FrontDepth)
  * CoherenceWeight
  * ValidSupportWeight
```

- `K_r` 是固定编译上限的紧支撑二维 stencil；不能退化为规则的长线/五条 lane。
- `EllipticSpatialWeight` 随张量方向旋转；Body 的法向支撑更宽，但仍保留流向与轮廓，不能变成圆形软泡。
- `DepthBilateralWeight` 禁止跨明显前后层连接。
- `SupportConfidence` 在支撑趋零时也趋零，避免 normalized division 把单粒子重新抬成高亮。
- Tight/Mid/Body 是同一 `F(p,r)` 在三个尺度上的结果，不是三套互不相关的模糊。
- 初始总采样预算拟限制在每像素 **32～48 个共享/嵌套 tap**；精确 stencil、半径和权重在低负载 shader Gate 后冻结，不能预先冒充已验证参数。

### 3.3 分频职责

Field Resolve 先输出三个尺度，材质再做频带组合。拟定语义：

```text
Body     = F_body
Medium   = positive_band(F_mid, F_body)
Filament = ridge_or_positive_residual(F_tight, F_mid)
```

- Body 是低频体量，不等于圆团；可以是拉长、卷曲、分叉的连续气体主体，但不能由宽 Streamline 直接绘制。
- Medium 连接同深度、同方向支撑下的局部空洞和中尺度结构，不负责跨无支撑区域造桥。
- Filament 只承担连续场中的高频 ridge/residual、边缘尖丝和受支持的脱离 wisps，不承担主体密度。
- `positive_band`、ridge 判据和频带归一化是本轮新增算法选择，当前 spec 没有写死；必须由审查者确认后才能固化。
- 不使用“必须连接主 Body 的全局连通图”作为硬门槛；那会错误删除物理上合理的脱离烟缕。

### 3.4 深度传播与最终着色

Resolve 使用与密度相同的有效权重传播 DepthMoment1/2 与 FrontDepth，输出与已填充密度一致的 MeanDepth、DepthSigma、FrontDepth/DepthConfidence。禁止在新增密度像素上继续读取空的中心 Raw Depth。

只有 Body 和 Medium 通过视觉 Gate 后，才启用：

- BackDepth/Thickness 推导；
- Beer–Lambert 消光与透射；
- 低强度深度/密度梯度受光；
- SceneDepth soft intersection。

光照不得用于遮盖密度场中的孔洞、排线或粒子点。

## 4. 拟新增资源与当前争议

验证期拟保留 Raw0/Raw1 不变，并新增两张 Niagara 自管、仅当前帧、每帧完整覆盖的 2048² RGBA16F RT：

```text
FieldMain RGBA = TightScale / MidScale / BodyScale / SupportConfidence
FieldAux  RGBA = MeanDepth / DepthSigma / FrontDepth / DepthConfidence(or Coherence)
```

最终材质只消费 FieldMain/FieldAux；Raw0/Raw1 继续作为 Stage C 输入和数据层 Debug。

这是本方案与现行 spec 最大的资源差异：现行 §7/§12 只预算 Main+Aux 两张 2048² RT，而该验证结构会暂时达到 **2 Raw RT + 2 Field RT**，另含 Niagara 内部工作资源。每张 2048² RGBA16F 约 32 MiB，两张新增 RT 约 64 MiB，不含 DI/中间缓冲。

审查需要在以下两种路线中批准一种：

1. **质量隔离优先（当前建议）**：验证期允许 2 Raw + 2 Field，视觉 Gate 通过后再评估融合 Stage B/Stage C、通道打包或格式压缩；优点是 Raw 数据证据不被破坏，缺点是显存与带宽增加。
2. **资源上限优先**：从一开始就让 Stage B 写内部 Raw Grid，Stage C 最终覆盖现有 Main/Aux；优点是最终仅两张 RT，缺点是会修改已经通过 Gate 的 P0c Stage B 输出合同，必须重跑 S0/A/B/C，风险更高。

未经审查，不默认选择第二条，也不私自降低分辨率抵消额外资源。

## 5. 实施流程与 Gate

### Gate R0 — 审查与 spec 收口

- 审查本文第 3～7 节，明确批准/否决每个新增选择。
- 更新视觉 spec 的当前状态、P0c 通道、Resolve 归属、资源预算、频带定义和验收顺序。
- 更新性能 spec 中已经失败的 Gate D 状态与新的完整链路预算口径。
- 更新/取代当前计划里“8×5 不得减少”的旧约束；该约束只适用于已经失败的材质追踪候选。

### Gate R1 — 隔离、备份与空 Stage

- 对当前可运行 P0c System 做精确二进制备份；不使用已经证实可能产生空运行副本的普通 Niagara `duplicate_asset` 作为恢复点。
- 新建独立 Stage C 模块、Field RT 参数、Debug 材质/MI；正式 M3 与 V2.1 文件哈希保持不变。
- Stage C 先做 pass-through/marker，低分辨率低负载验证 Simulation Stage → HLSL → DI → Field RT 闭环、执行顺序和 P1 last-substep gate。
- 通过后恢复 2048²；0 error、0 warning、无脏包、冷启动 RT 非零。

### Gate R2 — Body-only

- 只显示 `F_body` 灰度/Alpha，不显示 Medium、Filament、Depth Lighting 或颜色调试。
- 同时输出 SupportConfidence Debug。
- 技术检查：finite、无 half saturation、无边缘 Wrap/Clamp、无跨深度连接、当前帧清空、相机移动对齐。
- 视觉检查：主体连续、有内部浓淡与柔软轮廓；允许拉长、卷曲和分叉；不能出现粒子点、平行刷毛、五通道排线、圆形软泡或均匀白板。
- 记录密度积分/覆盖变化，防止 normalized convolution 无约束增亮或削薄主体。
- **Body 未通过即停止，不进入 Medium。**

### Gate R3 — Medium

- 单独查看 `Body`、`Medium band`、`Body+Medium` 三种画面。
- Medium 只连接局部、同层、受方向/支撑约束的空洞；不得出现跨层桥、周期采样纹或规则管线。
- 动态中连接应连续变化，不得随 Top-K/低支撑方向来回抽出。
- **Body+Medium 未通过即停止，不进入 Filament。**

### Gate R4 — Filament

- 单独查看 `Filament band` 和三频段组合。
- 细丝必须来自 Tight-vs-Mid residual/ridge；禁止 Raw Core、硬胶囊头和宽 Streamline。
- 允许有局部支撑的脱离 wisps；无双侧/局部支撑的孤立亮线应随置信度衰减。
- 关闭 TAA/TSR 后仍应保留自然细丝，但不能暴露离散粒子或 stencil 图案。

### Gate R5 — Depth/Lighting

- 分别查看 MeanDepth、DepthSigma、FrontDepth/Confidence、Thickness，再接最终白烟。
- 深度先约束连接，再控制透射和低强度受光；空像素不得被解释为近景。
- 检查近景、标准距离、拉远、转镜、屏幕边缘和 SceneDepth 软交界。

### Gate R6 — 完整系统视觉与性能

- 金标准：`/Game/NewNiagaraSystem.NewNiagaraSystem` 的 Niagara Fluids/NS 气体形态。
- 候选必须具有连续体积、大中尺度卷曲/拉伸、中尺度结构与边缘细丝；不是只形成一个圆团。
- 性能比较必须为同场景、同机位、同分辨率、相近屏幕覆盖、一次只启用一个系统：
  - 参考：粒子源 + Grid3D 模拟 + Volume Renderer；
  - 候选：粒子模拟 + Stage A/B + Field Resolve + 最终 Translucent Renderer。
- 目标：候选总 GPU 成本不高于参考，同时可见精度更高。单独 Stage 时间不能替代完整链路结论。
- 若性能超预算，先优化 tap 共享、边界范围、格式与 Stage 融合；视觉 Gate 前不靠降低粒子数、Raw 分辨率或恢复大模糊过关。

### Gate R7 — 是否需要改源粒子运动

只有 R2～R6 视觉链已通过，但动态仍可复现地缺少必须由轨迹决定的大尺度卷吸、回流或涡团时，才提交源运动修改提案。未经用户再次批准，Fountain/CurlNoise/Drag/Velocity 不变，也不引入完整 NS 求解。

## 6. 与权威 spec 一致的部分

| 拟实现项 | 对应现行条款 | 判断 |
| --- | --- | --- |
| 保留当前帧紧支撑 GS/P0c 输入 | §14.3.1 | 一致 |
| 原始矩局部正则化后再归一化 | §14.3.2 | 一致 |
| Density numerator / Support denominator + 低支撑置信度 | §14.3.3 | 一致 |
| 张量/Coherence/深度限制连接 | §14.3.3、§8.3 | 一致 |
| 三频带来自同一连续场 | §14.3.4 | 一致；需确认“同一尺度空间”解释 |
| 无 Raw Core、无大半径各向同性 Blur | §14.3.4 | 一致 |
| Front/Mean/Sigma 先约束连接再驱动深度表现 | §14.3.5 | 一致 |
| 无 History、无跨帧反馈 | §4、§14.3、§12 | 一致 |
| 迁移到 current-frame Resolve Stage | §14.3.6 | 条件已经由两轮材质场一致性失败触发 |
| 2048²、RGBA16F、Bilinear、无 Mip、Fixed Tick | §14.3 末段、§12 | 一致 |
| 固定循环上限、屏幕越界贡献为零 | §8.2、§11 | 一致 |

## 7. 与现行 spec 不一致、未定义或需要改写的部分

| 编号 | 项目 | 当前 spec | 本草案 | 类型/需要的决议 |
| --- | --- | --- | --- | --- |
| D1 | 当前数据通道 | §7.2/7.3 仍写已归一化 G5 Main/Aux | 使用 P0c Raw0/Raw1 原始矩 | **直接不一致**；视觉 spec 必须对齐性能 spec 的 P0c v2 |
| D2 | 管线归属 | §4/§8 仍以 Dense Raster + 材质 RK2 为主 | P0 Stage A/B + 独立 Stage C Field Resolve | **历史管线过期**；需重写当前管线并把旧 G5 标为回退基线 |
| D3 | Resolve 迁移状态 | §14.3.6 只在材质失败后迁移 | 判定 V1/V2.1 已满足失败条件，直接迁移 | **状态推进**；需明确批准 Stage C 为当前主线 |
| D4 | Field 算子 | spec 只规定 adaptive normalized field-aligned convolution | 选择二维张量引导 compact scale-space stencil | **新增实现选择**；需审查数学与 tap 预算 |
| D5 | 分频算子 | spec 只说同场分频 | Body=`F_body`，Medium=Mid-vs-Body，Filament=Tight-vs-Mid ridge/residual | **新增实现选择**；需审查正负频带、能量和稳定性 |
| D6 | Body 生成 | 旧 §8.1 仍写 13×13 各向同性核，旧 §8.2 强调 Streamline | Body 为二维张量引导的低频连续场，不由宽 Streamline 生成 | **替换旧算法**；与 §14.3 方向一致，但需废止旧表述 |
| D7 | Filament Gate | §11 仍是 Streamline Gate | 改为连续场 ridge/residual、无 stencil 显形 Gate | **验收标准变化**；需新增 Field/Band Gate |
| D8 | 8×5 约束 | 当前纠偏计划禁止视觉前减少 8×5 | 彻底移除失败算子，改为 32～48 tap 上限的二维 stencil | **当前计划冲突**；审查通过后必须改计划，不能称为“降质优化” |
| D9 | RT 数量 | §7/§12 只预算 Main+Aux | 验证期拟 2 Raw + 2 Field | **资源冲突/最大争议**；需批准额外约 64 MiB，或选择重做 Stage B 的两 RT 路线 |
| D10 | 调试顺序 | spec 有字段/最终 Gate，但未规定先 Body 后 Medium 再 Filament | 强制 R2→R3→R4，前一项失败即停止 | **新增流程纪律**；建议写入 spec |
| D11 | 脱离烟缕 | spec 只规定低支撑抑制 | 允许局部受支持 wisps，不要求全局连接主 Body | **语义澄清**；避免误删真实气体分离结构 |
| D12 | 视觉金标准 | 视觉 spec §1 只写类似高品质流体烟雾；解析核 spec 的 D6 已写“观感 ≥ Niagara Fluid”，但未指定资产 | 明确参考 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的 NS 形态 | **目标细化**；需把三份 spec 的口径合并 |
| D13 | 性能目标 | 旧 spec 主要对 Dense/P0 单阶段 Gate | 候选完整链总 GPU ≤ 参考完整链，同时精度更高 | **新增验收合同**；需定义干净 A/B 采集流程 |
| D14 | 源粒子运动 | spec 未明确冻结 | 当前重建阶段冻结；只在最终证据下另行审批 | **新增范围边界**；建议写入 spec |
| D15 | “孤立分支必须连主体” | spec 未要求全局连通 | 本草案明确不采用该硬规则 | **撤回过严提案**；只保留局部支撑/深度置信度 |

## 8. 请审查者明确回答的问题

1. 是否同意“两次材质式 8×5 场重建失败”已经满足 §14.3.6 的迁移条件，Stage C current-frame Resolve 可成为下一主线？
2. `F(p,r)` 的三尺度结果是否可被认定为“同一连续场分频”，还是必须先生成单一 base field 再做严格频域/尺度分解？
3. 二维张量引导 compact stencil 是否足以避免 Brush/Lane 显形；建议的 32～48 tap 上限是否合理？
4. normalized convolution 的 `SupportConfidence` 与密度积分应采用什么守恒/容差 Gate，才能既不削薄主体也不放大孤立粒子？
5. Body=`F_body`、Medium/Filament 使用正残差/ridge 的定义是否合理；是否需要保留有符号 Laplacian/DoG，再在合成阶段处理？
6. 深度应随每个尺度分别传播，还是只维护一套由最终支持加权的 Mean/Sigma/Front？
7. 是否批准验证期新增 FieldMain/FieldAux 两张 2048² RGBA16F RT？若不批准，是否接受重构已经通过 Gate 的 Stage B 以保持两 RT？
8. 是否坚持所有 Field RT 首轮都为 2048²，还是允许 Body/Medium 在视觉 Gate 前用较低分辨率？本草案默认坚持 2048²以遵守现行 spec。
9. 是否同意允许“局部有支撑但未连接主 Body”的脱离 wisps，并只衰减无局部双侧/深度支撑的孤立亮线？
10. 是否同意把 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的完整系统 GPU 成本设为硬上限，并以同机位完整链路 A/B 为唯一性能结论？
11. 是否同意当前冻结源粒子运动，直到 Field Resolve 的视觉能力被独立验收？

## 9. 审查后动作

收到最终审查意见后，先形成逐条决议表，再按决议：

1. 修改 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`，将历史 G5 与当前 P0c/Field Resolve 明确分层，更新状态、通道、资源、算法和 Gate。
2. 修改 `M3-PERF-OPTIMIZATION-SPEC-20260731.md`，把 RawMoments Gate D 标记为失败，并加入 Reference-vs-Candidate 完整链预算。
3. 修改或取代 `P0C-NORMALIZED-FIELD-RECON-PLAN.md` 中只适用于失败 8×5 候选的约束。
4. 同步 `AI-BRIEF.md`、`BACKLOG.md`、`LOG.md`。
5. 重新做 spec 自洽检查；没有悬空通道、资源或 Gate 后，才进入 Gate R1 的 UE 实施。
