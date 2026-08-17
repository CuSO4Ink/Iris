# Neural Render Lab · 训练与调参

## 当前入口：R4c World-Box Neural Volumetric Proxy

在 `work/UE-NeuralRender-Lab/` 执行：

```powershell
uv run --no-sync python train_neural_volume.py --smoke
uv run --no-sync python train_neural_volume.py
uv run --no-sync python export_neural_volume_rhi.py
```

训练默认写到 `tmp/UE-NeuralRender-Lab/neural-volume/r4c-box/`：`best.pt`、`metrics.json`、`comparison.png` 和 `relight_sweep.gif`。导出器默认在其 `rhi/` 子目录生成 `NRL_R4c_Box.fp16.bin/json`。默认配置是每个 camera/sun 组合 384 条训练射线、太阳方位 `±22.5°` 连续抖动、64 次视线步进 + 8 次太阳透射步进的盒内 Teacher，以及解析 ray/AABB 入射点和厚度、`3×32²×8` triplane + 三层宽度 64 MLP 的 Student。

当前候选在 RTX 5060 上训练 1200 steps，数据生成 `46.68 s`、训练 `6.75 s`、峰值 CUDA 分配 `184.51 MiB`。held-out PSNR `33.983 dB`、Student/analytic log-RGB RMSE 比值 `0.14754`、alpha RMSE `0.007446`；连续 sweep 平均／最差／相邻帧变化 RMSE 为 `0.005707/0.007283/0.002684`。34,372 参数导出为 `68,744 B` FP16，SHA256 为 `F416D6EF390A69D44EAC8EB5A5317740D961580EFEF968E2A3842C5F09B59225`；量化输出 RMSE `2.92e-5`、最大绝对误差 `0.001143`。

部署文件位于 Abyss 的 `Plugins/NeuralVolumeProxy/Resources/NRL_R4c_Box.fp16.bin`。UE 每帧只做推理，运行时读取相机射线、Actor Box、观察／太阳方向、厚度和可选 Scene Depth；不会根据 UE 画面在线训练。当前 DLL 已完整编译，等待重启后的 Z 向世界锚定复测和 GPU A/B。

R4a 代理球结果是历史候选，已被 R4c world-box 训练域和部署路径取代。

## 历史入口：R1 Tiny Neural Material

历史入口是 `train_neural_material.py`。它运行时合成程序化分层湿石 Teacher 与单 GGX PBR 基线，Student 只在训练方向组合上学习，最终在保留的完整 light/view 组合上评分；不需要准备图片。

## 运行

在 `work/UE-NeuralRender-Lab/` 执行：

```powershell
uv sync
uv run --no-sync python train_neural_material.py --smoke
uv run --no-sync python train_neural_material.py
```

默认结果写到 `tmp/UE-NeuralRender-Lab/neural-material/r1/`：

- `best.pt`：最佳 held-out checkpoint；
- `metrics.json`：训练曲线、误差、模型大小、训练时间和显存；
- `comparison.png`：四组 held-out 方向下的 PBR／Student／Teacher 与误差；
- `angular_sweep.gif`：连续改变光照和观察方向的响应。

## 可调参数

```powershell
uv run --no-sync python train_neural_material.py `
  --steps 1800 `
  --batch-size 32768 `
  --learning-rate 0.003 `
  --latent-resolution 64 `
  --latent-channels 8 `
  --width 64 `
  --output ..\..\tmp\UE-NeuralRender-Lab\neural-material\candidate-a
```

优先只调三项：

| 参数 | 作用 | 当前值 | 何时改 |
|---|---|---:|---|
| `--steps` | 收敛时间 | 1800 | held-out 仍持续下降时增加 |
| `--latent-resolution` | 空间细节容量 | 64 | 只有空间纹理明显糊时升高 |
| `--width` | 方向与分层响应容量 | 64 | 只有高光随角度变化拟合不足时升高 |

`--latent-channels` 先保持 8。任何容量提升都必须重新检查 FP16 总大小不超过 1 MiB；先看 held-out 指标，不按训练损失选模型。

## R1 已完成结果（2026-08-14）

- 1800 steps，batch 32768，RTX 5060；训练 `17.58 s`，峰值显存 `115.11 MiB`。
- PBR held-out log-RMSE `0.02633`；Student `0.01021`；比值 `0.3876`。
- PBR tone-mapped PSNR `27.68 dB`；Student `39.13 dB`。
- 38,723 参数；FP16 权重与 latent 共 `77,446 B`（`0.074 MiB`）。
- 数值 Gate 通过；本人允许进入 R2，视觉 Gate 已签字。

## R2 导出与结果（2026-08-14）

```powershell
uv run --no-sync python export_neural_material_ue.py `
  --shader-output D:\Work\Personal\Project\Abyss\Shaders\NeuralRenderLab\NRL_R2.ush
```

导出包含五张输入纹理和 `83,584 B` inline HLSL；shader SHA256 为 `d243b14ff6d8c011be2aa41b671d172c4ad18456000400d5a4e821ae9315525c`。8-bit latent 量化后 Student/PBR log-RMSE 比值为 `0.3720`，Student PSNR 为 `39.45 dB`。

UE 中已保存并编译 `/Game/NeuralRenderLab/R2/M_NRL_R2_PBR`、`M_NRL_R2_Student`、`M_NRL_R2_Teacher` 及五张纹理。匹配 GPU mean 分别为 `1.96 / 1.98 / 1.90 ms`；Student/Teacher 为 `1.042`，没有达到 `<= 0.60` 的 R2 Gate。当前路径到此停止，不继续增加网络或正式接入渲染管线。

旧 v00/v01 全屏训练方法只保留在 `LOG.md`，不再是当前入口。
