# P0c Normalized Field Reconstruction Correction

> 状态提示（2026-08-09）：本文完整记录已失败的 V2/V2.1 材质 8×5 路线，已被批准的 `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md` 取代，不再授权下一实现。本文“不得减少 8×5”的约束只解释失败候选，禁止带入 Stage C。
>
> 当前主线进度（2026-08-10）：Rev B 已推进到隔离 HQ 的 R2.2 v40；当前为 18-stage Niagara-only multipass，Body Closure 在 Medium 之前，High/Filament 不再进入 Opacity。旧离散点、椭圆章与全卡 haze 已清除，但整体视觉仍是二维薄片和重复源轨迹条纹，Niagara Fluids/NS 气体 Gate 未过。v34～v40 已提供“仅靠重建会在过平与条纹/泡沫间摆动”的证据；源运动实验成为下一候选，但在用户明确批准前仍冻结。以下旧 V2/V2.1 资产计划不得被误当成 Stage C 实施清单；native RDG、插件与源码路线禁止。当前权威状态见 `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md`。

## 状态与边界

- 2026-08-08 用户 Gate D 已否决 `MF_SSPR_P0c_StreamlineRawMomentsV1` / `M_SSPR_P0c_RawMoments_V1` 的视觉结果：没有气体团与气体拉丝，反而放大粒子感。
- P0c 数据层继续有效：Stage A 屏幕空间有界注册、Stage B 2048² current-cell/K gather、P0b erf 核和 Raw0/Raw1 原始矩不回滚。
- 正式 M3、干净性能锚点和失败 V1 均不原地覆盖；纠偏实现使用隔离的 V2 资产，先验证后切换。

## 视觉目标与源运动边界（2026-08-09）

- 形态金标准是 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的 Niagara Fluids/NS 气体：连续体积、大中尺度卷吸与回流、中尺度涡团/卷曲、边缘细丝，以及自然的拉伸、分裂和耗散；不是单一圆团，也不是沿若干采样线画出的白色纤维。
- 精度目标是在可见细节上高于该参考；性能目标是候选完整链路总 GPU 成本不高于参考完整链路。二者必须在同场景、同机位、同分辨率、相近屏幕覆盖、每次仅启用一个系统的 A/B 中验收。
- 源粒子运动在 v40 前保持冻结，且 v34～v40 已完成重建端职责、顺序、支撑与分带的排除实验；不得用改运动掩盖尚未记录的重建错误，也不得宣称需要完整 NS。
- 当前证据触发了“调整源粒子运动以产生更接近 NS 的大中尺度卷吸”备选：重建已稳定生成连续支持，但仍只得到薄片与输入轨迹条纹，缺少由轨迹本身决定的卷吸、回流或涡团。下一实验仅限隔离 HQ 候选，实施前仍须用户再次明确确认。

## 输入合同

- Raw0/Main = `Density / TensorCos2Sum / TensorSin2Sum / DepthMoment1`。
- Raw1/Aux = `DepthMoment2 / FrontDepth / VelocityMomentX / VelocityMomentY`。
- 派生字段只能在局部原始矩正则化之后归一化：`MeanDepth=M1/D`、`DepthSigma=sqrt(max(M2/D-MeanDepth²,0))`、`Tensor=(Cos2Sum,Sin2Sum)/D`、`Velocity=VelocityMoment/D`、`Coverage/Support` 由有效密度和局部支撑推导。

## 必须实现的结构

1. 3×3 或等价紧邻域对 Density、方向张量、深度矩和速度矩做 density/support 加权正则化；低支撑单粒子只能产生低置信度。
2. 使用 Density signal 作为卷积分子、Coverage/Support confidence 作为分母，执行当前帧、无 History 的双向固定上限 RK2 场对齐采样。
3. 连接半径和权重由 support gap、coherence、曲率及 Front/Mean/Sigma 深度一致性共同约束；不同深度层不得被强行连通。
4. Filament、Medium、Body 必须由同一连续重建场的核尺度/频段分离得到，而不是三个互不相关的粒子模糊。
5. Front/Mean/Sigma 推导 BackDepth、厚度、透射与深度受光；Density Shape/Smoke Resolve 只处理已经连续的场。

## 禁止项

- 禁止 Raw 单粒子 Core 作为最终可见兜底，包括 `max(rawCore, connectedField)`。
- 禁止依靠 `Contrast<1` 把极弱离散像素抬亮来伪造体量。
- 禁止用大尺度各向同性模糊掩盖空洞；禁止跨深度层连接。
- 禁止在视觉 Gate 前减少既定 8 steps/方向或 5 条横向采样通道来抢性能数字。
- 编译成功、RT 非零和 ProfileGPU 不等价于视觉完成。

## 资产计划

- `Functions/MF_SSPR_P0c_NormalizedFieldReconstructionV2`
- `Functions/MF_SSPR_P0c_DepthTransportLightingV2`
- `M_SSPR_P0c_NormalizedFieldRecon_V2`
- `MI_SSPR_P0c_NormalizedFieldRecon_V2_HQ`

历史 M2 的 `MF_SSPR_G5_NormalizedFieldReconstructionV1` 与 `MF_SSPR_G5_DepthTransportLightingV1` 只作算法参考；必须适配 P0c 原始矩合同，不能直接把旧 Aux.A Coverage/已归一化深度语义带入新材质。

## 实施状态（2026-08-09）

- 四个隔离 V2 资产均已创建、保存并由 P0c 候选 Renderer 使用；Main/Aux 两条 Niagara 材质绑定未变，正式 M3 与失败 V1 未改。
- V2 完成 P0c 原始矩局部正则化、双向 8 steps × 5 lanes 的 numerator/support denominator、Front/Mean/Sigma 深度约束、同场 Filament/Medium/Body 与 Depth Transport。
- V2.1 修正两处动态缺陷：弱/空矩不再由 `atan2(0,0)` 产生任意屏幕 X 切线，而是保留上一可靠方向并衰减；统一 seed gate 改为同场的三带支撑置信度，Filament 严格、Medium/Body 渐进延续。Recon HLSL SHA-256=`cfff060099a326617266f3921141dd9d6eb06d76bb5cab9aa2a9a4562eefe20c`。
- 当前 Continuous-B 参数保持 `ActiveSteps=8`、`Contrast=1`，三带权重 `0.12/0.43/0.45`，Guide/Medium/Body=`5/4.5/15 px`；40k 固定近景暴露白色刷毛/纤维排线、Body 不连续、Medium 连接不足和 Filament 主体化。该结果为视觉失败证据，不是合格宽体或气体拉丝。50k 仅为未持久化的运行 A/B。
- 最终保存后审计已分别强制 reload 材质闭包与 Niagara System：Recon/Lighting SHA、精确函数调用、Stage A/B、P1、Camera DI、Renderer、双 RT 绑定与生产 gather SHA 全部一致，0 error/0 脏包；运行回读为 40k/K64/0.03、组件 active/tick、Grid2D + Main/Aux 2048² RGBA16F。
- S1/S2 已通过；V1/V2 视觉均未通过，V2.1 冻结为失败快照。下一实现必须先提交独立 Body/Medium/Filament 调试画面，再提交无频带调试色的组合气体画面；V3/P 与最终用户 Gate 均未通过。

## Gate

- S1 结构：函数调用闭包正确；无 History、无 MipPyramid、无旧 Streamline、无 isolated/raw core fallback；所有 P0c 通道解码 token 存在。
- S2 编译/持久化：父材质 0 error；MI 父级与参数正确；保存后强制 reload 与 sidecar 一致；正式 M3 未改。
- V1 分频：提供 Filament/Medium/Body 独立调试，三频段都由归一化场产生；Body 连续且 Filament 无硬胶囊头。
- V2 近景：关闭 TAA/TSR 时仍无可辨认粒子点，同时存在尖丝、中尺度连接和柔软宽体；静止与运动均无来回抽出。
- V3 深度：Front/Mean/Sigma 同层约束有效，具备厚度、纵深和受光；屏幕边缘与拉远不崩。
- P 性能：视觉 Gate 通过后再按固定机位复测；若超预算，优化 FieldRecon，不回退 Raw 粒子兜底。
