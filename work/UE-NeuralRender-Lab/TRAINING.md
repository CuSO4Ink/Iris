# Neural Render Lab · 训练与调参

## 当前入口：R4a Neural Volumetric Proxy

在 `work/UE-NeuralRender-Lab/` 执行：

```powershell
uv run --no-sync python train_neural_volume.py --smoke
uv run --no-sync python train_neural_volume.py
```

默认结果写到 `tmp/UE-NeuralRender-Lab/neural-volume/r4a/`：`best.pt`、`metrics.json`、`comparison.png` 和 `relight_sweep.gif`。默认配置是每个 camera/sun 组合 384 条训练射线、太阳方位 `±22.5°` 连续抖动、64 次视线步进 + 8 次太阳透射步进的 Teacher，以及 `3×32²×8` triplane + 三层宽度 64 MLP 的 Student。

当前候选在 RTX 5060 上训练 1200 steps，训练与 held-out 使用独立固定随机种子：held-out PSNR `34.44 dB`、Student/analytic log-RGB RMSE 比值 `0.1772`、alpha RMSE `0.00964`、FP16 表示 `0.0656 MiB`；连续 sweep 的平均／最差帧 RMSE 为 `0.00387/0.00451`，相邻帧变化 RMSE 为 `0.00223`。机器检查中侧／逆光亮环已经消失，未见明显跳变或轮廓漂移；本人已确认视觉 Gate 通过，R4a 完成。

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
