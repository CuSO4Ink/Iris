<!-- iris-project-kind: ue -->
# UE Neural Render Lab

> **UEAgent first（UE live/MCP 强制前置）**：先导航到 [UEAgent 入口](../UEAgent/AGENTS.md) 和 [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md)，再处理本项目 brief。定位目标项目 `Saved/UEAgent/route.json` 并运行 `compact_context.ps1`；只有 `CACHE_READ` 才停止 MCP，否则首次 live call 前运行 `doctor.ps1`。纯离线源码、数据、训练与文档工作可跳过 MCP，但不得声称 live editor 状态。

## 一句话介绍

验证受限场景中的神经代理，能否用感知近似替代昂贵的体积光线步进，并在未见视角／太阳组合上保留可信的云体氛围与重光照响应。

## 当前状态

R4a pass / R4b allowed but not started · 旧 tiny neural material 路线已在 R2 记为性能负结果并停止；单个固定云体的 `体积步进 Teacher → 代理厚度 + learned triplane + tiny MLP Student` 已通过离线数值与本人视觉 Gate。下一阶段可进入 UE RHI 设计，但尚未执行任何 UE live 操作。

## 当前实验（R4）

- Teacher：固定程序化云密度，64 次视线步进与 8 次太阳透射步进，输出 premultiplied HDR RGB + alpha。
- Student：解析代理球给出入射点和厚度，`3 × 32² × 8` learned triplane 与三层宽度 64 的 tiny MLP 每条命中视线只求值一次。
- 条件：观察方向与太阳方向；训练太阳方位在离散方向附近连续抖动 `±22.5°`，测试仍保留精确的完整 camera/sun 组合，禁止按像素随机泄漏。
- R4a 非目标：UE 接入、动态拓扑、整片天空、在线训练、任意局部灯和生产云资产修改。
- 运行证据写入 `tmp/UE-NeuralRender-Lab/neural-volume/r4a/`。

## 已关闭实验（R1/R2）

- 单一 Teacher：程序化分层湿石材，包含粗糙基底、薄水层、灰尘和方向性微高光。
- 传统基线：同一空间参数下的标准 diffuse + 单 GGX PBR。
- Student：learned latent texture + 两层 tiny MLP；输入 UV 隐变量、切线空间入射/观察方向及物理角度特征，输出 HDR BRDF 响应。
- 数据：运行时按固定方向集合合成；保留完整 light/view 组合做 held-out 测试，禁止按像素随机泄漏。

## Gate 结果

R4a 固定 Gate：held-out tone-mapped RGB PSNR `>= 26 dB`、Student log-RGB RMSE `<= 70%` 同输入全局解析代理、alpha RMSE `<= 0.06`、FP16 表示 `<= 0.5 MiB`、同分辨率 CUDA Student median `<= 50% Teacher`，并由本人检查重光照 sweep 无明显跳变。离线 timing 只决定是否值得进入 UE，不能代替最终 RHI matched A/B。

R4a 当前候选使用每个 camera/sun 组合 384 条射线、太阳方位连续抖动 `±22.5°` 和 `32²` triplane；训练与 held-out 使用独立固定随机种子。held-out PSNR `34.44 dB`，Student/analytic log-RGB RMSE 比值 `0.1772`，alpha RMSE `0.00964`，FP16 表示 `0.0656 MiB`。连续 sweep 的相邻帧变化 RMSE 为 `0.00223`，逆光亮环已消失；`512×288` 命中视线的 PyTorch eager CUDA median 为 Student `1.194 ms`。本人已确认视觉 Gate 通过；离线 timing 不是 UE 实时性能主张，仍须 R4b 的 UE RHI matched A/B 独立证明。

R1/R2 历史结果：

R1 只回答离线表达能力，不接 UE：

- held-out log-RMSE 至少比 PBR 低 30%；
- 对比图中保留 PBR 缺失的多层/方向性高光；
- 连续角度 sweep 无明显跳变；
- 记录参数量、FP16 表示大小、训练耗时与峰值显存。

R1 结果：Student/PBR held-out log-RMSE 比值 `0.3876`，FP16 表示 `0.0739 MiB`；本人允许继续进入 R2，视觉 Gate 据此完成签字。

R2 在 RTX 5060、D3D12 SM6、`1962×1078`、相同全屏测试面与固定相机下，各取 30 帧 warmup + 120 帧样本：

| 变体 | GPU mean | p50 | p95 |
|---|---:|---:|---:|
| PBR | 1.96 ms | 1.91 ms | 2.34 ms |
| Student | 1.98 ms | 1.89 ms | 2.14 ms |
| Teacher | 1.90 ms | 1.88 ms | 2.12 ms |

Student/Teacher mean 比值为 `1.042`，高于门槛 `0.60`；三者总 GPU 时间差异也接近测量噪声，不能证明 Student 有实时成本优势。R2 失败，正式 UE shading integration 不启动。

## 技术与边界

- 当前只使用项目既有 PyTorch/CUDA/Pillow 环境，不增加依赖。
- 运行数据、checkpoint、图像与指标放在 `tmp/UE-NeuralRender-Lab/neural-material/`。
- R4a 复用相同环境，新增结果只放在 `tmp/UE-NeuralRender-Lab/neural-volume/`。
- R1 不导出 ONNX、不使用 Neural Post Processing、不修改 UE/Bifrost、不创建通用训练框架。
- R2 的 Unlit + Custom HLSL PBR／Student／Teacher 资产保留为已编译、clean 的负结果证据，不扩展为正式 shading integration。
- 运行证据在 `tmp/UE-NeuralRender-Lab/neural-material/r2-benchmark/`；临时测试 Actor 已删除，`L_Demo` 未保存。

## 文档地图

- [SPEC.md](SPEC.md)：唯一实验合同与停止条件
- [BACKLOG.md](BACKLOG.md)：任务与 Gate 裁决
- [TRAINING.md](TRAINING.md)：当前训练命令与产物
- [LOG.md](LOG.md)：历史决策、失败和已验证事实

## 文件边界

- `work/UE-NeuralRender-Lab/`：源码、锁文件与正式文档。
- `tmp/UE-NeuralRender-Lab/`：训练数据、运行结果、checkpoint、导出与一次性证据。
