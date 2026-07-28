# Memory-Bounded Relightable Volumetric Primitives for Unreal Engine

> 云版本账本：[`CLOUD_VERSIONS.md`](CLOUD_VERSIONS.md)

> 状态：2026-07-28，解析 B2 Ultra 仍是已签字的质量 teacher；`1.112M × 320 B` H12 只保留为质量参考，H13 exact 50K／`48 B/kernel` 是唯一紧凑候选
> 当前 Gate：H13 六轴 τ 的数据、上传和 shader 消费已由 `LightTransmittance` 方向梯度验证，只待用户签字 Final 强度；H12 的 `Dual SH=false` 现场覆盖已恢复为 `true`，只待修复后视觉复核
> 当前执行顺序：H12 Final 复核 → H13 阴影强度签字 → matched-quality SVT/NanoVDB GPU time 与 working-set Gate。未完成视觉 Gate 前不启动 H14、正式 16×24 数据、新训练或裁剪
> 当前用户调定的 UE appearance defaults：Density Multiplier=`0.416`、Density Gamma=`1.515627`、Support Tau Min=`0`、Use Scene Depth/Scene Lights=`true`、Directional Light Intensity Scale=`0.5`、Sky Light Intensity Scale=`0.1`；TechLab 默认绑定 `Light Source` 与 `SkyLight`
> 版本化实现：`work/GaussianVolume/ue-plugin/GaussianVolume/` 与 `work/GaussianVolume/ue-plugin/GaussianSplattingForUnrealEngine/`；本地 UE 部署位于 `D:/Work/Personal/Project/Abyss/Plugins/`
> 目标平台：UE 5.8、RTX 5060、1920×1080

## 1. 作品集命题

为静态高细节 VDB 构建一种可被 GPU 直接渲染的紧凑 volumetric primitive 表示。在匹配 optical-depth/transmittance 误差时，相比 UE 8-bit Sparse Volume Texture 与 NanoVDB Fp8/FpN：

1. 显著降低稳态 GPU working set；
2. 峰值 transient memory 不吞掉表示收益；
3. 满足 1080p 实时帧预算。

主优势只保留 **matched-quality 下的 GPU memory**。实时是必须满足的产品约束，不单独包装成创新点。

不再以原始 `.vdb` 文件、dense float grid 或 primitive 参数大小作为胜负依据。

最终运行时表示设硬上限：`≤50K` 个 volumetric kernels，density base=`32 B/kernel`，新增 transport 摊销后总计 `≤48 B/kernel`。`1.112M` teacher、`320 B` 7DRGS 输入布局与完整 BiGS 均不得作为最终资产。

## 2. 技术底座与边界

### 2.1 解析底座与基线：DSYG volumetric primitives

- 使用 Don’t Splat Your Gaussians 的官方 tomography optimizer，将 OpenVDB 拟合为可相加的 Gaussian 或 Epanechnikov extinction kernels；
- 使用解析有限 ray-segment optical depth；
- 先在官方 Mitsuba reference 中验证，再导出 UE；
- 当前 block/adaptive converter 只保留为失败基线，不再代表项目最终拟合质量。

DSYG 提供解析 extinction kernel、ray integral、优化器和独立基线；既有 Q2/Q3 结果已经证明“直接增加固定预算 Gaussian”不保证画质改善。因此它不再被写成能够从 B2 teacher 直接压到 `50K` 的已验证主线。

### 2.2 已归档质量参考层：Gabor residual

- Gaussian base 承载低频和主要正密度；
- signed Gabor residual 承载高频细节；
- 按屏幕 Nyquist、方向和贡献，在 candidate count 之前裁剪 residual；
- 当前先以完整 Q2 base＋4K residual、固定 3σ support 与无 candidate 截断建立最高质量参考，不以帧时和 working set 拦截；画质签字后再判断 complex-erf/Faddeeva 成本能否通过频率/贡献裁剪收回。

Gabor 不是保底依赖。最终 step 1200 已完成，但用户人工画质验收失败，因此 residual 路线已关闭并归档。

### 2.3 运行时工程底座

- primitive 资产保持 local space，多 Actor 共享参数与加速数据；
- cluster-local 量化 position、log-scale、weight、extent 与方向参数；
- view/frustum/cluster/direction-LOD 选择发生在 candidate generation 之前；
- 使用 optical-depth-aware support，在不超过现有 3σ 范围的前提下缩小低贡献 Gaussian 的 tile/ray 覆盖；
- 使用 GPU `count → prefix scan → scatter` 构建固定总预算的紧凑 candidate pool；
- 当前纯吸收/统一介质通过 `T = exp(-sum(tau_i))` 无序累加，不做 depth sort；
- camera ray 使用 active field；shadow/lighting 第一版只使用 Gaussian base；
- lighting 优先使用 dirty-driven persistent per-primitive transmittance；只有中心采样画质不足时才升级为固定预算的 directional-light-space deep transmittance cache；
- temporal reprojection 与上采样只在低分辨率 lighting/deep cache 路径启用。
- 7DRGS Slice／Preprocess 必须使用 UE 原生 wrapped dispatch，并在 shader 中恢复线性 thread id；不得以单维 `DispatchThreadID.x` 限制高细节点数。

这些是生产工程基础设施，不作为第二研究赌注。

### 2.4 Optical-depth-aware Gaussian support

3DGRT 的 opacity-aware support 不能直接照搬到本项目：其 `alpha` 是无量纲粒子 opacity，而本项目存储的是有物理尺度的 peak extinction `sigma_t`。第一版使用保守的 full-ray optical-depth proxy：

```text
tau_peak = sigma_t * sqrt(2*pi) * max_scale
k = clamp(sqrt(2 * log(tau_peak / epsilon_tau)), 0, 3)
support_radius = k * max_scale
```

- `epsilon_tau = 0` 明确回退固定 3σ；
- quality-first reference 当前固定 `epsilon_tau = 0`，避免把 support 近似混入画质上限；恢复优化 Gate 后再从 `1e-5` 起步，只允许缩小、禁止超过原 3σ；
- `tau_peak <= epsilon_tau` 的 primitive 可在 GPU packing 时删除；
- 这是单 primitive/ray 的局部忽略阈值，不冒充全图严格误差上界；最终仍以 held-out `tau/T` 误差签字；
- support 的数值正确性由 held-out `tau/T` 误差验证；UE 内只报告 candidate count、candidate bytes 与 GPU time，最终画面由用户直接在编辑器中签字。

该 support 在 compact pool 前可以减少 candidate writes 与积分次数；只有 compact pool 完成后，减少的 candidate 数才计入显存收益。Generalized Gaussian 会改变拟合 kernel 和 erf 积分，不进入第一版。

support cutoff 只定义“保留到哪里”，tile coverage 还必须使用保守的 tight Particle Bounding Frustum（PBF）包围裁剪后的椭球，而不是继续用 `max_scale` 球形投影：

- PBF 必须完整包住裁剪后的 support，不允许 false-negative、破洞或视角闪烁；
- PBF 收益只用现有 telemetry 与 GPU tag 验证，避免再建固定机位截图框架；
- 同时报告 requested candidates、tile coverage、GPU time 与 held-out 数值误差；编辑器画面由用户手动检查；
- 若 PBF 没有减少 candidate 或 GPU time，直接删除，不增加第二套常驻 bounds 数据。

解析积分不得直接计算 `C - B²/A`。对远相机和小尺度 primitive，该写法会发生灾难性消减，把理论非负的垂距平方变成负数并在 `exp()` 中放大。reference 与 UE 统一改为先求 ray 上最近点，再显式计算非负的 perpendicular Mahalanobis distance；bundled PTX any-hit 在重新生成前默认关闭。

### 2.5 BiGS-inspired compact transport

BiGS 只提供分解原则，不移植完整模型。运行时固定 density geometry，将方向光响应拆成：

```text
L(x, light, view)
= rho(x) * T_direct(x, light) * Phase(light, view)
+ T_indirect(x, light)
```

- `T_direct` 表示随灯向变化的内部透射／自阴影；`T_indirect` 表示 SkyLight 与低频环境填充；
- `Phase` 第一版复用全局 dual-HG，不给每个 primitive 存双向 SH；
- 每 primitive 的 FP16 transport weights 与共享 basis/metadata 摊销合计 `≤16 B/kernel`；低阶灯向 basis 按 cluster/asset 共享；
- density、位置、尺度与旋转在 transport 训练中冻结；灯光不得改变空间 mean/covariance；
- transport 必须对未见灯向连续，并满足非负、能量有界和跨灯向平滑约束；
- 完整 BiGS 的 `1089 params/primitive`、per-primitive 高阶双向 SH、neural shader 与第二套 deferred renderer 明确禁止进入本轮。

当前 O(N²) `LightTauCS` 不再作为逐帧方案。若共享低秩 transport 通过数值验证但大核内部仍明显平坦，只允许做一次固定预算的 light-space R16F deep-transmittance cache A/B；其纹理、构建 scratch 与 history 全部计入总 working set，不能胜出即删除。

### 2.6 Moment-based transmittance 的边界

Moment-Based OIT / MB3DGS 只作为异质 albedo、emission 或高质量单散射的条件分支：

- 纯吸收/统一介质继续使用精确的 `T = exp(-sum(tau_i))`，不引入 moments；
- 当前 64-hit 数组是 shader thread-local working data，不按 `resolution × 64 hits` 计作全局显存；
- moment、quadrature、rescaling 多 Pass 及其全屏 render targets 必须证明同时改善 overflow/排序成本与总 working set；
- 在 profiler 证明 64-hit sort/overflow 是主瓶颈、且 MB3DGS 可复现实现可用之前，不进入主线。

### 2.7 32 B Gaussian primitive packing

当前 UE Gaussian base 已使用精确 `32 B/primitive` 的常驻 GPU 布局：

- world-space position 保留 FP32；scale、extinction、support 与 emission 使用 FP16；rotation 使用 SNORM8 单位四元数；albedo 使用 UNORM8；
- 当前版本没有 cluster metadata，也没有同时常驻一份 64 B 解包副本；
- shader 直接把 ray 变换到 Gaussian local space 完成解析积分，避免为每个像素重建 inverse covariance；
- shader 直接读取压缩布局，不允许同时常驻一份 64 B 解包副本；
- 与 64 B reference 使用同一资产和 support，报告 primitive bytes、metadata、decode GPU time 与离线 `tau/T` 量化误差；UE beauty 由用户手动签字；
- 通过线为 primitive 常驻字节至少下降 `45%`、matched-error Gate 不退化且完整 volume GPU time 回退不超过 `5%`；否则回退 64 B，不继续发明复杂 codec。

Q2 的 primitive buffer 已从 `636,416 B` 降到 `318,208 B`；500 帧 D3D12 中 `GPU/GaussianVolume` median 从 `1.8834 ms` 降到 `1.5344 ms`，因此字节和性能 Gate 均通过。FP32 position 是有意保留的保守项；只有多实例共享仍被 position bytes 主导时才增加 cluster-local position quantization。

该项是低风险工程优化，不是新的研究赌注。

已归档的 quality-first 分支曾为每个 primitive 增加一个 16 B `Data2`，其中 `Data2.x` 以 FP32 保存 `omega`，形成 48 B 的统一 Gaussian/Gabor 布局；`omega=0` 保持原 Gaussian。该布局只保留为 Gabor 负实验记录，不进入当前 7DRGS 训练或运行时预算。

### 2.8 Pool-free analytic transmittance raster A/B

只对纯 extinction／统一 source radiance 做一个最小架构实验，不替换现有 Compute 主线：

```text
tight Gaussian/PBF proxy raster
→ analytic per-proxy optical depth
→ low-resolution R16F sum(tau)
→ full-resolution transmittance/powder resolve
→ scene-color composite
```

该分支利用 `T = exp(-sum(tau_i))` 且统一 source radiance 下光深可交换的条件，直接删除 candidate count/scan/scatter。最初直接做逐 primitive premultiplied alpha blend；用户确认近景无格子后发现 close-up fill-rate 可超过 `50 ms`，因此改为固定预算的低分辨率 optical-depth accumulation，再只做一次全分辨率合成。限制与验收条件：

- 第一版只允许解析 ray–Gaussian extinction，不声称解决空间变化 source radiance、异质单次散射或完整体积光照；
- 使用 instanced tight ellipsoid proxy；`r.GaussianVolume.PoolFreeResolutionScale` 控制线性分辨率 `[0.25,1]`，当前默认 `0.5`；
- proxy pass 只加法累积 R16F `tau`；resolve 用总 `tau` 一次性恢复 `T`、alpha 与现有 powder，避免逐 primitive powder/alpha 的顺序误差；
- 正式 runtime 在 SceneColor 有 UAV 时原位 resolve；编辑器或不支持 UAV 的输入自动分配 copy 回退，编辑器输出显存不进入 headline；
- 大 Gaussian 的 fill-rate 风险必须与 tight support/PBF 同时测量；
- 与当前 512K compact-pool Compute 路径使用同一 Q2、分辨率、画质和 warm-frame 口径；
- 只有总 working set 和 GPU time 均不输给 Compute、并至少一项有可测收益时才保留；任一项明确更差就删除该分支。

`r.GaussianVolume.PoolFreeRaster=1` 已由用户确认真实覆盖云，且近景不再出现 candidate tile 格。1920×1080、0.5×、正式 `-game` 的命名资源只有 R16F tau=`1.1875 MiB` 与 primitive=`0.3125 MiB`，合计 `1.50 MiB`；没有 candidate pool、tile buffers、LightTau 或额外全屏输出。相对 512K Compute 的 `2.344 MiB` 低 `36.0%`，但这些资源比值没有通过 close-up matched-quality Gate，不得作为方案优势。

同一非贴脸 runtime 视角的 500 帧 A/B（最后 300 个稳态样本）中，full-res→0.5× 的 `GPU/GaussianVolumePoolFree` P50/P95 从 `1.9661/2.1377 ms` 降到 `0.5996/0.6007 ms`，完整 GPU P50/P95 从 `6.8625/7.5071 ms` 降到 `5.4609/5.5104 ms`。内部降采样确实降低该视角的 fill cost，但用户的真实 close-up 验收为：full-res 细节可接受但 `50+ ms`；0.5× 仍约 `25 ms` 且细节不通过；0.25× 预期只会继续降低画质。提高分辨率与降采样分别卡在性能和画质两端，故 pool-free Gate 正式失败，保持默认关闭且不再作为主线、matched-quality 候选或 Gabor 底座。temporal、BVH、自适应 raster 属于新架构，不在本轮收口范围。

### 2.9 原位 scene-color 合成

Compute 主线的每个 thread 只读取并写回同一个 scene-color pixel，没有跨像素依赖。`r.GaussianVolume.InPlaceComposite=1` 会在输入 SceneColor 自带 `TexCreate_UAV` 时直接绑定为 UAV，删除独立 `GaussianVolume.Output`：

- 默认请求开启；若后处理输入没有 UAV capability，或 CVar 设为 `0`，自动 copy 到带 UAV 的独立输出；
- UE 编辑器的 `PostDOFTranslucency.SceneColor` 可能只有 render-target flag，因此编辑器预览会走安全回退；正式 `-game` D3D12 已验证仍走原位路径；
- 原位路径若进入 LOD transition band，只选 alpha 更高的一档，避免两档同时改写同一 scene color；当前 Q2 Hero 已关闭 screen-size LOD；
- D3D12/RDG 已验证无 assert、resource hazard、GPU crash 或 shader error；
- 正式 `-game` 的 Gaussian 命名资源经 uniform LightTau 清理与 512K pool 后从 `17.76 MiB` 降到 `2.344 MiB`；旧 128K／错误 camera-basis 版本的性能数字已撤销，修复后的 500 帧 GPU 数据待重采；编辑器回退显存不进入 headline；
- 最终画面由用户在编辑器内直接签字；不恢复固定机位自动截图框架。

### 2.10 平移实例共享

已归档的 GaussianVolume runtime 允许一个 `UGaussianVolumeComponent` 通过 `AdditionalInstanceOffsets` 添加同一云的平移副本：

- 32 B primitive buffer 只上传一次；每个副本的逻辑描述为一个 32 B instance range/offset；
- candidate ID 以 20 bit primitive index＋12 bit instance index 编码，明确限制为 `<1,048,576` 个 unique primitives 与 `<4,096` 个 instances；
- count/scatter 对 instance×primitive 做二维 dispatch，但 candidate pool 仍保持固定 512K，不因副本数自动扩容；
- 该最小路径只对 `>4K` 且 albedo/emission 统一的高数量云开放，避免给当前 LightTau 路径制造错误光照；
- uniform fast path 不再分配 9,944 个未使用的 LightTau，只绑定 1 个 dummy float；单实例不创建独立 instance buffer；
- 512K pool 下 1/4/16 份 Q2 的 1280×720 逻辑工作集为 `2,430,108 / 2,430,236 / 2,430,620 B`；实际 RHI 中 4/16 份都会触发一次 `64 KiB` instance-buffer 最小分配，不能拿逻辑 32 B 冒充真实 allocation；
- 旧 128K 压力测试中的 4/16 overflow 数字只保留为历史证据；512K 默认值的连续相机与多实例峰值必须重采，不能宣称“16 份云仍保持同画质”。

旋转、缩放、异质外观和任意独立 Actor 的自动资产去重仍属于未来完整 local-space asset instancing，不进入当前保底承诺。

### 2.11 后置表示分支

- **Epanechnikov**：当前冻结，不因 pool-free 失败而恢复；只有未来独立证据表明有限支撑能在同误差、同 working set 下优于 Gaussian 时才重新立项；
- **Gabor residual**：step 1200 已完成但用户画质验收失败，永久作为负实验归档；当前 Gate 不恢复训练、调参、A/B 或运行时优化；
- **SplatNet／神经 primitive**：表达能力高但训练、UE shader 和泛化风险过大，本项目暂不切换；
- **moment-based 与硬件 BVH ray tracing**：只有 profiler 证明排序/关联成为主瓶颈，且新增 moment buffers 或 acceleration structure 后总 working set 仍占优时才重新评估。

### 2.12 当前 B2／7DRGS quality teacher

- WDAS cloud 因源形状底部偏平而退出当前展示 Gate；active-boundary 检查证明这不是 converter clipping。
- 当前同源资产为 CGHEVEN `Hero Congestus Cloud VDB - 50`，页面标记为 CC0。只保留可稳定读取的 `density` grid；有效分辨率=`238×264×403`、active voxels=`8,536,415`。
- 解析转换前在六个面各增加 `8 voxels` 空白，dense grid=`254×280×419`，六个外表面 density 均为 `0`。对齐按 active longest axis=`403 voxels` 归一到 `1000 cm`，padding 不改变云中心或同源 SVT 的可见尺寸。
- 最高质量档固定为 block=`2`、spatial sigma=`0.48`、angular sigma=`0.5`、density scale=`0.04`、ambient=`0`；得到 `1,112,674` 个空间样本和 `6,676,044` 个六方向 points。运行时 ambient 只由显式 SkyLight 引用提供。
- PLY 为解析代理而非论文训练结果；`2,136,336,393 B`，SHA256=`FD1E5F2B1895742611E1CD20452A76ABCB06B3BB42E8D231168BA6A3C7792A73`。
- DirectionalLight 在 editor tick 中实时刷新；SkyLight 的颜色、强度与可调 scale 进入 composite ambient fill。当前 phase=`dual HG`、`g1=0.65`、`g2=-0.2`、blend=`0.1`、phase intensity=`0.35`。
- 2026-07-26 用户确认空间细节已无问题、manual 与场景方向光均有响应；轻微色差暂不阻塞训练。训练不得以破坏当前细节或方向响应换取点数。
- `1.112M` 空间样本与六方向解析叶片只负责定义质量上限和生成监督，不参与最终资产、runtime memory 或性能 headline。

### 2.13 Compact density＋transport 训练技术方案

#### 方法边界与采用结论

- 公开 7DGS 的额外维度是时间与**观察方向**，不是灯光方向。当前 7DRGS 改编只保留为 teacher/负实验，不再承担最终压缩表示。
- BiGS 证明固定几何、分离 direct/indirect transport、约束 light/view response 的方向合理；完整 `1089 params/primitive` 不满足本项目内存目标，只采用第 2.5 节的共享低秩分解。
- Relightable Neural Gaussian、GS³ 等方法还引入 neural shader、shadow cue 或 hybrid deferred pass；这会把项目带入第二套训练/运行时架构，当前不采用。
- B2/VDB 已提供高质量 teacher；`1.112M` 只作为离线 teacher，不成为最终运行时模型，但其空间核不能在没有蒸馏证据时被 DSYG `50K` 冷启动替代。
- QIRF 只采用“局部解析 overlap＋τ-response density matrix＋广义特征分解＋participation 选核”。原论文针对表面 3DGS，平均保留约 `28.3%` primitives；它没有证明 `1.112M→50K`（仅保留 `4.5%`），也不直接生成 contracted kernels。
- QIRF 的特征模态允许 signed coefficient，而 extinction 必须非负。所有选核结果必须经过共享的 `softplus/NNLS` recovery；不得把 signed mode 直接导出为体密度。
- `τ-QIRF` 已完成 24-block discovery 与 48-block held-out smoke；相对独立贡献剪枝的收益随块类型和预算变化，不满足“类间稳定胜出”的晋升线。因此它保留为负／混合消融，不作为全局 selection 前置条件。
- 真正稳定的局部信号来自生成**新** kernels：48 个 held-out 局部块在 `3/64`（`4.6875%`）预算下，moment-contracted 同时改善 τ/T 的块数为内部 `14/16`、薄层 `13/16`、边界 `15/16`。但这不授权把每个固定网格块独立压缩；首个 hard-macroblock 50K 已证明局部指标不能预测跨块视觉连续性。
- Gabor 画质实验已失败，不恢复。

#### 15K 失败复盘

`1,112,674` 点的 step 15K PLY 已通过 finite、Mask 和 depth 检查，但用户在 UE live viewport 看到严重颗粒噪声与细节模糊，画质 Gate 明确失败。训练 `TView SH degree=1`、UE 预览曾继承为 `0`，该部署不一致已修正，但不是噪声根因。

代码和 checkpoint 审计确认：

1. `_write_init_from_b2` 只复制 xyz、scale、rotation 与 spatial Cholesky，并从六方向展开数组中选取第一组 `vertices[indices]`；没有聚合六个叶片，也没有保留 B2 opacity、`J`、`TView`、`mu_d`、lambda 或方向 covariance。因此旧“B2 warm start”实际是**丢弃五个叶片＋appearance/density 冷启动**，不是 B2 压缩或蒸馏。
2. relight stage 冻结 opacity，而初始化 opacity 统一为 `0.1`。B2 密度细节先被丢弃，再被禁止恢复，迫使 `J/TView` 与条件 covariance 代偿。
3. `lambda_sh_reg`、`lambda_sigma_reg` 虽存在于参数定义和辅助文件，却未接入主训练 loop；方向参数没有有效幅值、能量或条件数约束。
4. 当前 light direction 会进入 conditional mean/covariance，等价于让静态云的有效几何随灯光改变；时间恒为 `0`，但 temporal block 与 cross covariance 仍可训练并被模型滥用。
5. 训练集仅 `8 cameras × 6 signed-axis lights × 256`。`sh_degree=2` 有 9 个 view SH basis，却只有 8 个独立相机方向，单点实际可见方向更少；参数不可辨识，不能只靠追加迭代解决。
6. 数据生成器是简化 Beer–Lambert／single-scatter 域，UE 又叠加 dual-HG、SkyLight、曝光和 Tone Mapping；训练域与最终显示域不完全一致。

checkpoint `500→15K` 中 xyz/scale/rotation/opacity 完全不变，opacity 始终为 `0.1`；但 `J` DC std 从 `0.169→1.146`、最大系数到 `10.236`，directional/full Cholesky diagonal p99 从约 `2.081→106.747`、抽样最大值到 `4269.5`，`TView` DC std 从 `0.210→0.764`。训练视角 J PSNR=`48.10 dB`，held-out foreground J/TView 只有 `16.54/14.83 dB`。这证明是无约束过拟合和错误初始化，不是 UE 抗锯齿或显卡故障。

该 15K checkpoint 与 PLY只保留为负证据；**禁止继续训练、作为新数据 warm start 或直接进入裁剪**。

#### 目标、预算与数据

训练只承担两件事：先用少量 volumetric kernels 匹配 VDB 的 density/optical depth，再在冻结几何上拟合方向光 transport。它不承担全局调色、动画、通用多光源、多次散射或神经解码。

- 同时保留两个 teacher：VDB 线性 reference 提供 density/τ/T 物理锚点；解析 B2 提供已签字的细节、六方向响应与 UE 视觉上限。
- density 训练和验证使用 `density/τ/T/mask/depth`；transport 训练额外使用线性 `J/T_direct/T_indirect`。UE Tone Mapping 与固定截图不进入 loss。
- `τ-QIRF` 的 response 直接来自多视角 ray-kernel optical-depth contribution，不复用论文面向表面颜色的 visibility/appearance descriptor；训练灯向与 held-out 灯向完整分离。
- transport 数据目标约 `16 cameras × 24 lights × 512`，相机与灯光分别留出完整方向；先用同结构的小分辨率子集 smoke。
- 最终档固定为 `50K`。约 `300K` 的 blockwise selection/recovery 只允许作为离线桥接资产；`100K` 只允许作为一次“50K 是否纯容量不足”的诊断，二者均不得成为性能 headline。

#### 最小训练课程

1. **Stage A — local selection A/B（已完成，不晋升）**：在内部、薄层和轮廓块，以 `70%/50%/30%` 相同保留率比较 `τ-QIRF` 与独立贡献剪枝；二者使用相同非负 recovery 和 held-out rays。结果混合，QIRF 不进入全局依赖。
2. **Stage B — local contracted proof（已完成）**：用质量加权 Lloyd grouping＋Gaussian mixture moment matching 生成新 kernels，再共享 NNLS recovery。`3/64` 已在 48 个 held-out 块显示稳定相对收益。
3. **Stage C — global contracted-kernel 50K fit**：先用全局 adaptive binary partition 按质量与空间多模态残差递归拆分到 exact `50K` leaves，每个 leaf 做质量守恒 moment match；禁止固定宽度、轴对齐且彼此独立的 macroblock 输出。该 initializer 先过 UE 格纹／细节检查，再联合优化 xyz、scale、rotation 与非负 `sigma_t`，不创建 7D covariance、SH 或光照参数。
4. **Stage D — density Gate**：对齐 SVT/B2 的轮廓、薄层透射、内部 τ/T 与近中远景细节。失败即停止，不给错误 density 叠加光照。
5. **Stage E — compact transport**：冻结全部 density geometry，只训练第 2.5 节 direct/indirect shared basis 与每核最多 `16 B` weights；全局 dual-HG 继续由 UE 参数驱动。
6. **Stage F — packed export**：density 复用现有 `32 B` runtime layout，transport 与 metadata 摊销后 `≤48 B/kernel`；训练 FP32 参数、optimizer state 和 teacher 数据不得进入 UE 资产。

不把 `1.112M` teacher 逐级裁到 `900K/800K`，也不把约 `300K` selection artifact 包装成最终压缩结果；它只负责给 contracted fit 提供比随机／贡献度更好的初始化。

#### Loss、验证与健康约束

- selection A/B 固定 kernel geometry，只比较选核信息量；同预算候选共享 NNLS/softplus recovery。QIRF 消融已按 `τ` 与 `T=exp(-τ)` 同时报告，不再为追求正结果调 selector。
- contracted density loss 覆盖 VDB/B2 的 `density/τ/T/mask/depth`，并约束非负 extinction、尺度范围和总 optical-depth energy；薄层、边界和低 optical-depth rays 提高采样权重。
- transport loss 覆盖 `J/T_direct/T_indirect`，约束 `T_direct∈[0,1]`、非负间接光、跨灯向平滑、随机未见方向和总能量上限。
- 除 PSNR/SSIM 外，报告 foreground LPIPS、edge/Laplacian 高频 residual、薄层 transmittance、跨光向稳定性，以及参数 p95/p99 与 finite；每个里程碑做 held-out 检查，train/held-out gap 扩大立即停止。
- 画质必须由用户在 UE live viewport 从自由视角和多个灯光方向签字。轻微已知全局色差不阻塞，但颗粒、细节丢失或几何随灯光漂移直接失败。

#### 工程与资源边界

- 冻结参数不进入 optimizer param groups；density 与 transport 使用两个独立 checkpoint，避免恢复时误改 geometry。checkpoint 只保存恢复必需状态，完整验证只在里程碑运行。
- correctness smoke 先用 FP32；只有 8 GB 实测压力或 profiler 证明需要时才对 raster/loss 开 AMP，Cholesky 与参数主副本保持 FP32。
- 不移植 gsplat，不引入 neural shader、完整 BiGS、Gabor residual、通用数据缓存或新 stage framework。
- 不为最终 compact student 保留 7DRGS Slice input/output 双份常驻 buffer；transport 直接从 packed runtime layout 读取。

#### 验收与停止条件

- **Selection Gate（已完成）**：`τ-QIRF` 没有在内部／薄层／轮廓三类块稳定胜出，不晋升；`3/64` moment contraction 在三类块合计 `42/48` 同时改善 held-out `τ MAE` 与 foreground `T PSNR`。首个 hard-macroblock 全局化已被视觉否决，因此局部 proof 只保留 moment matching 证据，不再保留固定分块假设。
- **Density Gate**：contracted `50K` 在自由视角保持轮廓、薄层透射、内部层次和中远景细节；失败则只允许一次 `100K` 容量诊断，不训练 transport。
- **Transport Gate**：未见灯向下保持内部透射、自阴影、SkyLight fill 和自然颜色渐变；失败只允许 deep-transmittance cache A/B，不升级完整 BiGS。
- **预算 Gate**：最终 `≤50K`、`≤48 B/kernel`；packed asset 目标 `≤2.868 MiB`，当前命名 GPU 资源目标 `<4.598 MiB`，最终仍以同画质完整 working set 比较为准。
- **性能 Gate**：只对通过画质的 packed student 报 asset、resident/transient、candidate、transport、Sort/Raster/Composite 与完整 frame。
- 若 `50K` density 或 compact transport 任一失败，停止“Gaussian 优于 VDB”主张；若通过但总 working set 不优于 SVT/NanoVDB，也以负结果结项。

`50K × 48 B = 2.289 MiB`。加当前 `2 MiB` candidate pool 和约 `0.031 MiB` auxiliary 后约为 `4.320 MiB`，距离 NanoVDB FpN raw grid `4.598 MiB` 只剩约 `0.278 MiB`；任何常驻 Slice 副本或大 lighting cache 都会直接击穿目标，不能留到最后再优化。

## 3. 唯一研究赌注

**局部 Gaussian mixtures 能否被非负 moment-contracted kernels 收缩到固定小预算，再用 τ/T recovery 与共享低秩 transport 保持细节和任意方向重光照。**

研究假设：

> B2 teacher 中相邻小核组成的局部 density mixture 可以用质量守恒的一、二阶矩初始化为少量新 kernels，并通过 held-out τ/T 优化恢复；全局定额 `≤50K` 后，其低频内部光传输再由每核少量 weights 与共享灯向 basis 表示。

只回答三个问题：

1. blockwise moment contraction＋非负 recovery 能否把 `1.112M` teacher 收缩为 exact `50K`，同时保留薄层、轮廓与内部层次；
2. `≤16 B/kernel` compact transport 是否在未见灯向下保留内部透射、自阴影、SkyLight fill 与颜色渐变；
3. packed representation、candidate、transport 与 transient 的总 working set 是否低于 UE SVT 与最强可复现 NanoVDB 基线。

候选调度、tight support/PBF、packing 和 compact pool 继续作为已验证的运行时工程，不再占用第二个研究赌注。任一问题失败即保留 B2 teacher/历史 renderer 并以负结果结项，不堆完整 BiGS、神经解码或第三套表示。

## 4. 最小端到端流程

```text
Static OpenVDB
→ linear VDB reference + signed-off B2 teacher
→ local QIRF/pruning ablation (evidence only)
→ adaptive continuous partition + exact 50K moment initialization
→ visual continuity pre-Gate + non-negative τ/T recovery
→ density-only held-out + user visual Gate
→ frozen-geometry compact direct/indirect transport
→ held-out camera / light validation
→ 32 B density + ≤16 B transport packed UE asset
→ Preprocess → Sort → HW Raster → Composite
→ matched-quality SVT / NanoVDB A/B
```

第一版只支持：

- 静态、单通道 density；
- 纯吸收/统一介质起步；
- 一个 directional light + skylight；
- 中景和远景；
- 离线拟合、运行时直接渲染压缩表示。

第一版明确不做：

- 动画 VDB；
- velocity、temperature 等多属性；
- 完整 multiple scattering；
- Hero close-up 替代；
- 完整 BiGS、per-primitive 高阶双向 SH、神经解码或新 deferred renderer；
- 通用 parent-kernel merge framework；Stage C 只实现局部 moment initializer＋固定预算 differentiable contracted fit，失败即停止扩架构；
- 未获书面许可的 Zibra 同资产实测。

## 5. 必须比较的基线

所有方案使用相同源资产、相机、曝光、transfer function、灯光、输出分辨率和 warm-frame 条件。

1. **UE 5.8 density-only 8-bit SVT / Heterogeneous Volume**；
2. **NanoVDB Fp8/FpN + HDDA**，并加入能够在 UE 中独立复现的分层压缩／在线解码版本作为生产竞争基线；
3. **独立贡献剪枝＋相同非负 recovery**，作为 `τ-QIRF` 的直接同预算基线；
4. **官方 DSYG Gaussian-only fixed-budget fit**，作为解析 kernel／冷启动拟合基线，不预设 `50K` 能通过；
5. **B2 Ultra／1.112M 7DRGS**，只作质量 teacher，不进入性能排名；
6. **完整 QIRF／BiGS**，只作选核和光照分解参考，不照搬表面描述符、完整参数或运行时；
7. **当前 block/adaptive 4K/10K/30K 与 Gaussian＋Gabor residual**，只保留失败历史。

测试资产：

- `smoke2.vdb` 只保留为历史链路与失败基线；
- 当前训练与最终 A/B 使用 CC0 `Hero Congestus Cloud VDB - 50`；
- 划分训练视角、未见测试视角、近/中/远景和连续运动路径。

## 6. 测量口径

### 6.1 画质

- 多视角 optical-depth/transmittance PSNR 与 MAE；
- foreground LPIPS、FLIP、差分图、edge/Laplacian 高频 residual；
- silhouette IoU、边界距离与跨灯光方向稳定性；
- train/held-out gap 与参数 p95/p99、condition number、NaN/Inf；
- 未见视角、连续运动、LOD 切换中的结构稳定性；
- 最终画面人工签字。

不能用单张 beauty screenshot 代替 matched-error。

### 6.2 GPU memory

分别报告，不允许只报 primitive 参数：

- asset/primitive buffer；
- cluster/hierarchy；
- active list；
- candidate IDs、tile ranges 与 scan scratch；
- acceleration structure；
- lighting cache；
- temporal history 和中间纹理；
- steady resident、peak transient、总 allocated working set；
- 1/4/16 个静态实例的增量曲线。

每种方案从独立真实 `-game` 冷进程加载同一环境关卡；以无体积的 `L_GaussianVolume_EmptyBaseline` 作差。Windows `GPU Process Memory` 记录 per-process dedicated/shared memory；warm frame 的 `rhi.DumpMemory` 与 `rhi.DumpResourceMemory ... Transient=all` 负责资源归因，UE SVT 另记录原生 `SparseVolumeTexture Memory` 的 page table、tile data 与 total GPU memory。由于 UE 会保留大块 D3D12 heap，进程总 delta 必须与命名资源/子系统统计同时解释，不得单独作为结论。磁盘 `.uasset/.nvdb/.json` 大小只作补充。

### 6.3 GPU time

- selection/cull；
- candidate count/scan/scatter；
- optical-depth pass；
- lighting pass；
- temporal/upsample/composite；
- volume total 与完整 frame；
- P50/P95 active primitives、candidate-per-tile、candidate-per-pixel 和 overflow。

离线拟合和首次上传不计入 warm-frame GPU time，但必须单独报告耗时、RAM 和资产大小。

## 7. 执行顺序、Gate 与停止条件

### 7.0 当前执行队列

严格按下列顺序推进；前一项失败时先止损，不并行扩张第二套架构：

1. **已完成**：tight PBF、正确 view basis、空间公平 overflow、32 B packing、512K pool、GPU/memory telemetry、原位 scene-color 合成、1/4/16 平移实例共享；
2. **已失败并收口**：pool-free full-res 贴脸 `50+ ms`；0.5× 仍约 `25 ms` 且细节不通过；不测试画质只会更差的 0.25×，不扩 temporal、BVH 或自适应 raster；
3. **已归档**：Gabor step 1200 已完成并导出，用户人工画质验收失败；保留资产和记录，不再调参或优化；
4. **已完成**：B2 Ultra 的真实 VDB 解析 7DRGS 已通过用户细节与方向重光照验收；轻微全局色差冻结；
5. **已完成**：`τ-QIRF` selection A/B 在 discovery/held-out 块上收益不稳定，不晋升全局；不继续调 selector；
6. **当前唯一主线**：保留 moment matching，删除 hard macroblock；构建无固定网格边界的 adaptive exact `50K` initializer，并在任何训练前先做 UE 格纹／细节检查；
7. **其后**：冻结通过的 density，训练第 2.5 节 `≤16 B/kernel` shared low-rank transport；
8. **作品集签字**：与同源 SVT/NanoVDB 做完整 working-set/GPU A/B，再增加第二个结构不同的公开资产验证边界。

不启动完整 BiGS、SplatNet、通用 moment 管线、硬件 BVH 或新的 deferred 光照架构，除非当前唯一主线已经给出明确失败证据。

### Gate 0：可信基线

- 同一资产跑通 UE 8-bit SVT；
- 跑通 NanoVDB Fp8/FpN＋HDDA reference；
- 跑通至少一个能够独立复现的压缩 NanoVDB／在线解码生产基线，或明确记录其不可复现原因；
- 锁定灯光、画质和内存采样方法；画面签字由用户在编辑器中完成。

未完成前禁止发布任何“优于 VDB”的结论。

### Gate 1：Selection 与 compact density 表示成立

- 已跑通 DSYG 官方 Windows bundled smoke 与 `smoke2.vdb` Gaussian-only reference；
- Gate 1A（已完成）：`τ-QIRF` vs contribution 使用同一批 held-out rays 和相同非负 recovery；结果不稳定，QIRF 不晋升。moment-contracted `3/64` local proof 通过，允许进入全局初始化；
- Gate 1B：hard-macroblock exact `50K` 已因严重格纹和细节坍缩失败；改用全局 adaptive binary partition exact `50K`。新 initializer 若仍无细节，只允许一次 `100K` 容量诊断，不进入 contracted optimization；
- held-out `density/τ/T/mask/depth` 健康，用户在 UE 自由视角确认轮廓、薄层透射和内部层次；
- 失败时只允许一次 `100K` 容量诊断：若 100K 通过而 50K 失败，说明该资产无法满足当前内存命题；不得把 100K 偷换成最终成功。

局部 proof 只授权最小 global contracted fit；`50K` 未通过不训练 transport、不扩运行时。

### Gate 2：候选显存成立

- optical-depth-aware support 已由 held-out 数值误差约束；不把自动固定机位截图作为实现 Gate；
- tight PBF 保守包围 support，并完成 candidate/GPU telemetry 与 CPU 数值测试；
- 用紧凑全局 pool 替换固定 per-tile candidate array；
- pool 固定预算、无 CPU readback resize；
- overflow 可见，并由下一帧更粗 LOD/frequency cutoff 收敛；
- candidate 与 scan memory 进入完整统计；
- `1/4/16` 实例的常驻显存增量可解释；编辑器运动观察与最终画面由用户签字。

当前 1080p、32×32 tile 共约 2,040 tiles。现实现使用全局 `524,288 IDs` 池（`2 MiB`）；修复 view basis 后 Q2 runtime requested/granted=`142,979/142,979`、overflow=`0`、truncated tiles=`0`。uniform fast path 下 32 B primitive=`318,208 B`、candidate=`2,097,152 B`、auxiliary=`32,668 B`，逻辑合计 `2,448,028 B`（`2.335 MiB`）。旧 128K 固定机位与强制 64K 的公平降级数据只保留为历史压力测试，tight-PBF 收益需用正确 basis 重采。

用户贴脸视角明确越过该中远景预算边界：1173×957 下 requested/granted=`1,362,172/524,288`、overflow=`837,884`、max tile=`3,312`、truncated tiles=`1,110/1,110`、max dropped/tile=`2,038`。整屏 32×32 格是 `61.5%` candidates 被公平截断后的结果，当前 `GaussianVolume Max≈14 ms` 与 queue Max≈`16 ms` 不是完整画质性能。按实际 requested 计算，无截断候选至少 `5.196 MiB`，加 primitive/auxiliary 后最低逻辑 working set=`5.517 MiB`，已超过 NanoVDB FpN raw grid `4.598 MiB`；因此不扩池追求 close-up，近景由原 VDB 承担，Gaussian matched-quality Gate 只测中远景。

1/4/16 个平移副本已完成表示共享验证；删除未使用 LightTau、改为 512K pool 后的 1280×720 accounting 为：primitive 始终 `318,208 B`，外置 instance table=`0/128/512 B`，逻辑总 working set=`2,430,108/2,430,236/2,430,620 B`。D3D12 对任意非空 instance StructuredBuffer 使用 `64 KiB` 最小 allocation，因此实际 RHI 增量是 1→4 约 `64 KiB`、4→16 约 `0`，不是逻辑上的 `128/512 B`。candidate pool 固定为 512K；当前多实例 overflow 需重新取证。

### Gate 3：表示存储与架构 A/B

- 32 B packing 满足第 2.7 节的字节、误差和 GPU time 通过线；
- 64 B reference 与压缩布局不得同时常驻；
- 原位 Compute 已删除额外 full-screen output，并保留 CVar 回退；
- pool-free extinction 已确认真实覆盖云，0.5× runtime working set=`1.50 MiB`，非贴脸视角 pass P50/P95=`0.5996/0.6007 ms`；
- close-up Gate 已失败：full-res `50+ ms`，0.5× 仍约 `25 ms` 且细节不通过；该分支不得晋升默认路径，只保留为负实验。

### Gate 4：Compact relightable student

- [x] 真实 VDB 解析转换结果通过人工细节和方向重光照验收；轻微全局色差暂不阻塞；
- [x] 完成第 2.13 节六项训练器修复，并以 `500` iterations 全量短程试跑验证恢复与导出；
- [x] Stage 1 step 15,000 完成并判负：虽然空间显式块零漂移、Mask IoU=`0.951`、inverse-depth L1=`0.00319`，但 held-out foreground J/TView=`16.54/14.83 dB`、τ L1=`3.81`，用户看到严重颗粒和模糊；
- [x] 完成 `mvp/qirf_tau_ab.py`、真实相机局部投影 ray、固定预算 `5%` safeguard 与 24-block discovery／48-block held-out A/B；QIRF 收益不稳定，不晋升全局；
- [x] 完成 `mvp/contract_tau_ab.py` 与 mass-preservation self-check；48 个 held-out 块在 `3/64` 下，moment-contracted 同时改善 τ/T 的块数为内部 `14/16`、薄层 `13/16`、边界 `15/16`，median foreground T PSNR=`21.03/22.69/22.52 dB`、silhouette IoU=`0.871/0.854/0.873`；只作为 initializer 证据；
- [x] 构建 disjoint `4×4×4` macroblock exact `50K` initializer；质量守恒误差 `3.03e-16`，但 UE 人工检查显示严重格纹和细节平均，作为负结果归档，禁止续训；
- [x] 构建 global adaptive binary-partition exact `50K` moment initializer；`1.112674M→50K`，质量守恒误差 `1.52e-16`，已接入 UE 左侧且未保存关卡；
- [x] 用户确认 adaptive 50K 已出现可信体积光，hard-macroblock 格纹问题不再是主矛盾；基础版细节仍不足；
- [x] 在不改变 `50K`、质量、材质和灯光的前提下，以 `mass^0.65` priority 将名额从厚内部重分配到小尺度／薄层结构，并接入 UE；
- [x] 对 detail-weighted 50K 完成第一轮 extinction／xyz／scale／rotation 联合 τ/T recovery；6 train／2 held-out 视角下 τ MAE 下降 `44.4%`、foreground T PSNR 提升 `1.87 dB`、edge L1 未回退；
- [ ] 用户确认 H8 的 footprint／微细节收益且体积光未回退；
- [ ] Gate 1 的 contracted `50K` density student 通过数值和 UE 人工画质签字；
- [ ] 冻结 density，以小数据验证 shared direct/indirect transport 的 loss、未见灯向和参数边界；
- [ ] 全量 compact transport 通过内部透射、自阴影、SkyLight fill 与颜色渐变签字；
- [ ] 导出 `≤50K`、总摊销 `≤48 B/kernel` 的 packed asset；训练 FP32、optimizer、teacher 与 7DRGS Slice buffer 不进入 runtime；
- 与同源 SVT 使用相同机位、曝光、画面范围和 `ProfileGPU` 口径；
- 分别报告 PointCount、bytes/kernel、transport metadata、Preprocess、Sort、HW Raster、Composite、resident/transient 与完整 frame；
- 不允许以完整 BiGS、百万点 teacher、隐藏 candidate 截断或退化画质换取成功结论。
- 当前 TechLab 已部署 B2 Ultra `6,676,044` points 与默认隐藏的同源 UE SVT U8；构建、VDB import、PLY point-count readback、关卡保存和 live viewport 画质签字已完成。

### Gate 5：作品集 headline

最低通过线：

- matched quality、同源资产与同等运行条件下，稳态 GPU working set 低于 UE SVT 与 NanoVDB 中更优者；
- 最终表示 `≤50K` 且 `≤48 B/kernel`；若声称磁盘资产优势，packed asset 必须低于同源 SVT 的 `2.868 MiB`；
- RTX 5060、1080p，完整 frame `≤ 16.67 ms`；volume pass 时间必须报告，但不设独立成功阈值；
- peak transient 不抵消稳态收益；
- 1/4/16 实例时共享资产不线性复制；
- 无不可披露 candidate 截断、关闭关键 Pass 或只挑 Hero 帧。

强作品集目标：working set 至少降低 `2×`；冲刺目标为降低 `4×`。GPU time、带宽和指令数作为解释收益与代价的佐证指标，不取代显存主结论。

若只达到实时但没有 matched-quality memory 优势，删除“VDB replacement/proxy advantage”主张，仅作为 UE volumetric primitive renderer 工程案例。

## 8. 当前工程证据与债务

- 当前 UE 主线只使用 Q2 的 9,944 个 Gaussian；旧 30K heuristic 档及其约 `8.5 ms` 主 Pass 只保留为历史失败基线，不再进入当前性能结论；
- DSYG/Gabor Fields 官方链路已跑通 64/1K/4K/10K；Q2 10K 以 `220 次原训练 + 20 次无 Adam 状态的冷启动微调` 导出 9,944 primitives。此前 full-T `29.31 dB`、foreground-T `17.18 dB` 的“失败”已定位为 any-hit 中 `C-B²` 数值消减，而非拟合退化；
- Q3 使用 `24,576` 个 Gaussian、明确设置 `skip_gabor_optim=true` 跑到 120 checkpoint；同一 8-view、512×512、64-spp held-out 评估相对 Q2 的 full-T/foreground-T/τ PSNR 分别下降 `14.00/14.52/22.41 dB`，只有 IoU 提升 `0.057`。Q3 已否决并停止，不导入 UE 主线；
- Q2 使用稳定顺序积分完成 8 个未见视角、512×512、64 spp 的签字评估：full-T `48.60 dB`、foreground-T `36.93 dB`、tau `28.07 dB`、IoU `0.629`，candidate negative-tau fraction 为 `0`；该结果显著越过 Q1 4K 的 `36.11/24.22 dB` 质量下限，高保真上限正式成立；
- Q2 已保存为 TechLab 唯一的 Gaussian Actor：`Smoke2 GFields Q2 10K High Fidelity`；当前 runtime 使用 `epsilon_tau=1e-5` 的 opacity/error-aware support，`epsilon_tau=0` 保留 fixed-3σ reference，并关闭旧 screen-size LOD；UE 展示密度不进入拟合指标，前述 64 spp/PSNR 数字严格对应 `DensityMultiplier=1.0` 的原始拟合输出；Actor 的 runtime/editor Hidden 状态现已统一驱动共享渲染注册，关闭可见性不会再残留云体；
- 固定机位、自动截图和截图微调已经从当前执行链路删除；用户负责在 live viewport 中移动视角、对齐 transfer function 并签字画面，助手只负责云表示、shader、显存、性能与数值正确性；
- 同源 UE SVT U8/F16 与 NanoVDB Fp8/FpN 对照关卡已完成；PNanoVDB accessor、HDDA 与独立 GPU tag 已在 D3D12 `-game` 实跑并完成 warm-frame 内存归因。画面与 transfer function 仍待用户签字；
- Q1 4K 的 CPU coverage proxy 显示：`epsilon_tau=1e-5` 时 83.62% primitive support 缩小，平均投影球面积 proxy 为固定 3σ 的 81.49%；这只是优化潜力，不是 matched-error 或 GPU 收益证明；
- 自由转镜头暴露旧 tile culling 使用 `ViewToWorld.GetColumn(1/2)`、与主射线 `ClipToWorld` 不一致；现已统一使用 UE `GetViewRight()/GetViewUp()`。修复后默认 512K 池的 1080p runtime requested/granted=`142,979/142,979`、overflow=`0`、truncated tiles=`0`。旧 128K 固定机位 tight-PBF 收益与强制 64K 降级数字只保留为历史压力测试；
- 当前常驻布局为精确 `32 B/primitive`，Q2 primitive=`318,208 B`；candidate=`2,097,152 B`、uniform auxiliary=`32,668 B`，逻辑总计 `2,448,028 B`（`2.335 MiB`）。shader 直接在 Gaussian local space 积分，不常驻 64 B 解包副本；
- 原位 scene-color 合成删除了两个跨帧保留的 `GaussianVolume.Output` 全屏纹理；uniform fast path 又把未使用的 9,944-float LightTau 缩成 1 个 dummy float。512K pool 下 1080p RHI 命名 Gaussian 资源为 `2.344 MiB`，相对旧 `17.76 MiB` 降低约 `7.58×`；按自定义运行时资源口径，它约为 SVT U8 原生 `12.402 MiB` 的 `1/5.29`，约为 NanoVDB FpN raw grid `4.598 MiB` 的 `1/1.96`。最终仍须由用户完成 matched-quality/transfer-function 签字，才能把该比值写成作品集 headline；
- 旧 128K／错误 camera-basis 版本的 500 帧 GPU 数字不再作为最终性能结论；修复后 D3D12 运行、内存 dump 与 overflow telemetry 已通过，正式 GPU P50/P95 在用户确认自由镜头画面后重采；
- 512K Compute 的贴脸边界已取证：requested=`1,362,172`、overflow=`837,884`、全部 `1,110` tiles 截断；不以扩池或隐藏截断把中远景代理包装成 Hero close-up；
- pool-free 已完成并否决：0.5× optical-depth 路径的正式 runtime 命名资源=`1.50 MiB`，非贴脸视角 pass P50/P95=`0.5996/0.6007 ms`；但贴脸约 `25 ms` 且细节失败，full-res 则 `50+ ms`。主线保持 512K Compute；
- H9 高数量路径关闭 O(N²) `LightTauCS`，改为每核 local `±X/±Y/±Z` 六轴 FP16 光程并对灯向连续插值；标记为 Atmosphere Sun 的 Directional Light 按世界朝光方向 `Z` 做上半球门控，地平线下直射为零，地平线上约 3° 内平滑恢复；普通非太阳方向灯不受该门控。该一阶方向基底已解决固定受光方向，但不宣称等同于 SVT 的逐体素完整多次散射；
- 实现记录中的 7DRGS 数据布局、方向切片、UE compute/sort/raster/composite 已逆向落地；真实 `smoke2.vdb` 经 block-4 聚合与 6 个方向叶片生成 `388,890` 点 PLY。该解析抬升版用于验证接口与上限，不等同于论文训练器；
- 同一 TechLab 隔离 `ProfileGPU` 得到 7DRGS 整帧/自身=`9.19/1.799 ms`，SVT U8 整帧/HeterogeneousVolumes=`8.43/1.070 ms`。当前版本画面轮廓接近但细边界更颗粒，且体积范围慢约 `0.73 ms`，因此不满足“优于 SVT”结论；
- quality reference 已换为 CC0 Hero Congestus 50：density-only SVT resolution=`238×264×403`；B2 Ultra=`1,112,674` 空间样本／`6,676,044` 六方向 points。DirectionalLight editor live refresh 与 SkyLight ambient fill 已构建和部署；用户已签字细节与方向响应，轻微全局色差冻结；仍不沿用 smoke2 的 GPU 数字，也不宣称新资产性能领先；
- 1.112M 训练版 15K 已由用户画质否决。审计确认旧 warm start 只从六叶片取第一叶并只复制空间属性，opacity 固定冷启动值 `0.1`，SH/covariance 正则未进入 main loop，light condition 还能改变有效空间 covariance；checkpoint 中 appearance/directional 参数爆炸且 train/held-out 严重分离。15K 只保留为负证据，后续改用 B2 teacher distillation 与固定静态几何；
- Gabor 已从 step 720 完成到 1200，恢复优化耗时 `5 h 38 min`，最终 32 视角 clean PSNR=`31.1498 dB`，导出 14,040 primitives；用户人工画质验收失败，路线归档；
- 当前 Actor 仍将 world transform 烘入 primitive；同一组件内的平移副本已共享该 buffer，但旋转/缩放和独立 Actor 自动去重尚未实现完整 local-space asset sharing；
- 旧 30K/10K/4K cross-fade 不是新主线；新 LOD 由统一的预算化 selection 输出 active set。

这些数字只证明已有 UE 内核进展，不证明相较 SVT/NanoVDB 的优势。

## 9. 保底交付

若唯一研究赌注失败，保底仍是：

```text
OpenVDB
→ DSYG analytic Gaussian baseline
→ τ-QIRF／贡献剪枝同预算证据
→ 通过则 contracted 50K；失败则保留负结果
→ local-space shared、quantized UE asset
→ compact candidate pool
→ analytic transmittance
→ UE 原生 directional light + skylight 的最小物理光照
```

若 compact transport 失败但 compact density 通过，保底不继续堆光照参数：直接交付 density-only／最小物理光照版本，并把重光照作为明确限制。

作品集必须披露：成功与失败画面、完整显存分类、GPU breakdown、matched-error A/B、复现步骤和不适用场景。未击败基线时可以作为严谨负结果，但不得包装成 VDB 替代品。

压缩 NanoVDB 是必须保留的生产保底竞争者：若它在 matched quality 下拥有更低总 working set 或更稳的生产流程，应让它获胜，并把 Gaussian 路线作为有边界的对照或负结果，而不是为了作品集强行宣称替代。

## 10. 相关实现

- DSYG project/code：<https://arcanous98.github.io/projectPages/gaussianVolumes.html> / <https://github.com/facebookresearch/volumetric_primitives>
- QIRF paper：<https://arxiv.org/abs/2607.18067>
- BiGS project/paper：<https://desmondlzy.github.io/publications/bigs/> / <https://arxiv.org/abs/2408.13370>
- Gabor Fields project/code：<https://arcanous98.github.io/projectPages/gaborVolumes.html> / <https://github.com/Arcanous98/gabor_fields>
- UE Sparse Volume Texture：<https://dev.epicgames.com/documentation/en-us/unreal-engine/sparse-volume-textures-in-unreal-engine>
- NanoVDB/OpenVDB：<https://github.com/AcademySoftwareFoundation/openvdb>
- Compact tile-list reference：<https://github.com/graphdeco-inria/diff-gaussian-rasterization>
- Opacity-aware support / generalized Gaussian：<https://gaussiantracer.github.io/>
- Deep Shadow Maps：<https://graphics.stanford.edu/papers/deepshadows/>
- Deep Gaussian Shadow Maps：<https://arxiv.org/abs/2601.01660>
- Moment-Based OIT：<https://momentsingraphics.de/I3D2018.html>
- Moment-Based 3D Gaussian Splatting：<https://vc-bonn.github.io/mb3dgs/>

本 SPEC 是当前唯一方向依据；旧 integration plan 与 archive 只作历史记录。
