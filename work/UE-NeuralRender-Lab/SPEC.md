# UE Neural Render Lab · SPEC

> 状态：R1 pass / R2 performance fail / R4a pass / R4b allowed but not started  
> 日期：2026-08-14  
> 硬件：NVIDIA GeForce RTX 5060 / 8 GB  
> 当前范围：单个固定云体的离线 neural volumetric proxy 验证

## R4a 合同：Neural Volumetric Proxy

### 研究问题

在固定云密度、受限观察／太阳范围内，能否以代理几何提供的入射点和厚度，加上 learned triplane 与每条命中视线一次 tiny MLP 求值，近似需要多次视线／太阳透射步进的体积云 Teacher？

成熟基线为 Olajos、Doggett、Goswami 的 *Environmental Volumetric Neural Shading of Clouds for Real-Time Rendering*（2026，DOI `10.1145/3820020`）。R4a 只复现最小可证伪脊柱，不复刻完整论文系统。

### 冻结对象

- Teacher：固定程序化云密度；64 次视线步进，每个有效样点 8 次太阳透射步进；输出 premultiplied HDR RGB + alpha。
- Student：解析代理球；三个 `32×32×8` learned feature plane 求和，连接入射位置、观察方向、太阳方向和厚度；三层宽度 64 ReLU MLP 输出 log-RGB + alpha。
- Analytic baseline：使用相同入射位置、厚度、观察与太阳方向的固定二次特征，以训练集 ridge least-squares 拟合单个全局响应；不含 learned spatial field。
- Split：精确的离散 camera/sun 组合完整 held out；训练射线的太阳方位在各离散方向附近连续抖动 `±22.5°`，测试不抖动。
- Benchmark：RTX 5060、CUDA、`512×288`、相同命中视线和输入；分别预热后以 CUDA event 取 median。
- Evidence：`best.pt`、`metrics.json`、`comparison.png`、`relight_sweep.gif`。

### 固定 Gate

R4a 必须同时满足：

- held-out tone-mapped RGB PSNR `>= 26 dB`；
- Student held-out log-RGB RMSE `<= 0.70 × analytic baseline`；
- held-out alpha RMSE `<= 0.06`；
- Student FP16 参数表示 `<= 0.5 MiB`；
- Student CUDA median `<= 0.50 × Teacher`；
- 本人确认 held-out 对比和连续重光照 sweep 没有破坏氛围的跳变、轮廓漂移或闪烁。

以下任一成立即停止当前候选：一次最小稳定性修正后仍有 NaN/Inf；held-out 只记忆训练视角；必须放宽代理为逐步密度查询；或 Student timing 没有至少 2× 余量。离线 CUDA timing 只筛选是否进入 R4b，最终实时主张必须由 UE RHI matched A/B 独立证明。

### 非目标

R4a 不接 UE、不修改生产云、不处理动态拓扑、整片天空、任意局部灯、在线训练、云对场景的完整阴影和通用多资产模型。

### R4a 首个候选结果

在 RTX 5060 上以冻结默认配置完成 1200 steps；训练集与 held-out 集均按完整 camera/sun 组合拆分。结果如下：

| 指标 | 结果 | Gate |
|---|---:|---:|
| held-out tone-mapped RGB PSNR | `34.44 dB` | `>= 26 dB` |
| Student/analytic log-RGB RMSE | `0.1772` | `<= 0.70` |
| held-out alpha RMSE | `0.00964` | `<= 0.06` |
| FP16 参数表示 | `0.0656 MiB` | `<= 0.5 MiB` |
| Student/Teacher CUDA median | `0.00246` | `<= 0.50` |

96 射线／组合的初版暴露出高频颗粒和轮廓膨胀；提高到 384 后静态误差下降，但离散太阳方向之间仍出现亮环。当前修订在训练集加入 `±22.5°` 连续太阳方位，并把过剩的 triplane 从 `64²` 收缩到 `32²`；训练与 held-out 生成器使用独立固定种子。模型为 34,372 参数；数据生成 `24.34 s`，训练 `3.57 s`，峰值 CUDA 分配 `137.94 MiB`。连续 sweep 的平均／最差帧 RMSE 为 `0.00387/0.00451`，相邻帧变化 RMSE 为 `0.00223`；机器检查未见明显亮环、跳变、轮廓漂移或闪烁。`512×288`、78,684 条代理命中视线下，PyTorch eager CUDA median 为 Student `1.194 ms`、Teacher `486.469 ms`；离线 eager timing 只证明有进入 R4b 的计算余量，不等价于 UE RHI 性能。

本人于 2026-08-14 确认当前静态对比与重光照 sweep 可接受，R4a 视觉 Gate 正式通过。R4b 可以启动，但其实现与 UE live 验证不属于本次签字本身。

## R1/R2 历史合同

## 研究问题

一个小型 latent texture + MLP，能否在未见的光照/观察组合上：

1. 比标准 PBR 更忠实地复现复杂空间变化、方向相关的分层材质；
2. 保持足够小，使后续 inline Shader 性能验证有意义？

R1 不证明实时收益；实时收益必须由后续 R2 的匹配 GPU A/B 独立证明。

## 固定对象

- Teacher：程序化分层湿石材；粗糙基底 + 薄水 clearcoat + 灰尘/sheeen + 方向性微高光。
- Baseline：共享相同 base color、normal、roughness 空间场的 diffuse + 单 GGX。
- Student：单个 learned latent grid，MLP 固定为两层 ReLU；首轮不搜索架构。
- Train/Test：固定 light/view 方向集合；测试保留完整方向组合，但每个单独方向仍出现在训练中。

## R1 证据

- `metrics.json`：Teacher 相对 PBR/Student 的 held-out log-RMSE、PSNR、参数量、表示大小、训练时间与峰值显存。
- `comparison.png`：多个 held-out 组合的 PBR／Student／Teacher 与误差图。
- `angular_sweep.gif`：连续光照和观察变化。
- `best.pt`：最佳验证 checkpoint。

## 通过与停止

R1 通过必须同时满足：

- Student held-out log-RMSE `<= 0.70 × PBR log-RMSE`；
- 对比图可辨认地保留至少一种 PBR 缺失的多层或方向性响应；
- sweep 没有明显离散跳变或失控亮斑；
- FP16 权重与 latent 总大小 `<= 1 MiB`。

以下任一成立即停止：

- 训练集改善但 held-out 方向无改善；
- 主要收益只是颜色拟合，方向相关材质仍丢失；
- 需要扩大到超过 1 MiB 才通过；
- 训练出现 NaN/Inf 或一次最小修正后仍不能稳定收敛。

R1 实测 Student/PBR held-out log-RMSE 比值为 `0.3876`，FP16 表示为 `0.0739 MiB`；本人允许进入 R2，数值与视觉 Gate 均记为通过。

## R2 证据与裁决

同一 Student 已写成 UE Unlit + Custom HLSL，并与 PBR、Teacher 使用相同全屏测试面。最终采用的三次稳态测量均为 `1962×1078`、D3D12 SM6、固定相机、Simulate、Game View、关闭 Cinematic Control、30 帧 warmup + 120 帧样本，性能回执均标记 `context.comparable=true` 且采样期间设置未变化。

| 变体 | GPU mean | p50 | p95 |
|---|---:|---:|---:|
| PBR | 1.96 ms | 1.91 ms | 2.34 ms |
| Student | 1.98 ms | 1.89 ms | 2.14 ms |
| Teacher | 1.90 ms | 1.88 ms | 2.12 ms |

固定门槛要求 Student GPU 时间 `<= 60% Teacher`，即按 mean 最多 `1.14 ms`。实测 Student/Teacher 为 `1.042`，没有通过；相对 PBR 的细小增量低于本次总帧 GPU 测量噪声，也不能据此改写既定门槛。R2 记为负结果，R3 与正式引擎集成停止。

原始回执、裁决摘要和捕获图位于 `tmp/UE-NeuralRender-Lab/neural-material/r2-benchmark/`。

旧 v00/v01 全屏 Neural Post Process 路线已封存，不作为 fallback。
