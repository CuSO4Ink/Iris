# VDB/SVT 与 G35/G37 GS 性能对比（2026-07-31）

## 结论

在同一张 TechLab 画面中同时渲染真实 SVT 和 311,993 点 GS，并分别读取各自 GPU 事件：

| 指标（中位数） | G35 优化前 | G37 优化后 | 变化 |
|---|---:|---:|---:|
| GS total | `1.343 ms` | `1.093 ms` | `-0.250 ms / -18.6%` |
| GS HW Raster | `0.819 ms` | `0.5665 ms` | `-0.2525 ms / -30.8%` |
| GS Preprocess | `0.080 ms` | `0.081 ms` | 噪声内 |
| GS Sort | `0.230 ms` | `0.231 ms` | 噪声内 |
| SVT 主体 + 后处理 | `3.237 ms` | `3.241 ms` | 噪声内 |
| 同帧总 GPU 时间 | `8.260 ms` | `8.060 ms` | `-2.4%`，仅作旁证 |

SVT/GS 的同帧 feature-time 比值由约 `2.41×` 扩大到 `2.97×`。G37 超过 SOP 的
`0.07 ms / 5%` 收益门槛；收益来自 raster coverage，G35 的 25-tap joint bilateral 没有退化或删减。
用户已完成自由视角画质验收，G37 因而冻结为当前 runtime 基线。优化前的严格同帧样本只有 5 次，
所以 `-18.6%` 优化增量仍按工程快测报告；若需要对外发布级统计，再补 Shipping 10+10，不影响当前冻结。

## G38 冷启动完整显存结论

在同一固定机位下另建 Empty、仅 SVT、仅 GS 临时地图，使用 Development `-game`、D3D12、
1920×1080 各跑 3 个独立冷进程；每次预热 10 秒并采 20 个稳态点：

| 口径 | UE SVT | G37 GS | GS 节省 |
|---|---:|---:|---:|
| 整个 UE 进程专用显存中位数 | `2664.178 MiB` | `2343.980 MiB` | `320.198 MiB / 12.019%` |
| 整个 UE 进程稳态采样峰值 | `2694.094 MiB` | `2396.043 MiB` | `298.051 MiB / 11.063%` |
| 相对 Empty 的净新增 RHI working set | `305.566 MiB` | `66.476 MiB` | `239.090 MiB / 78.245%` |

最重要的口径说明：`2343.980 MiB` 是包含 UE 场景、Lumen、TSR、VSM 和公共渲染池的
整个 GS 测试进程，不是单个 GS。单个 GS 的净新增 RHI working set 是 `66.476 MiB`，
由常驻 `19.063 MiB` 和 transient 净增 `47.414 MiB` 组成；约为 SVT 的 `1/4.597`。

3/3 GS 进程均加载 311,993 点，3/3 SVT 均输出原生 `305.566 MiB` GPU Memory；9/9
地图加载成功且无 GPU/D3D/shader fatal。完整方法和原始结果见
`VRAM-COLD-G37-VS-SVT-20260731.md` 与 `evidence/memory-20260731-g37-cold-3x/`。

## 对齐条件

- GPU：NVIDIA GeForce RTX 5060，驱动 `32.0.15.9636`。
- Unreal Editor level viewport 快测；不是 standalone/shipping headline。
- 关卡：`/Game/GaussianVolume/Maps/L_GaussianVolume_TechLab`。
- CaptureViewport：`1990×1198`，FOV `55`。
- 相机位置：`(1677.07570194, 4953.87681787, 577.09876377)`。
- 相机旋转：`(-7.09999697, -91.77999607, 0)`。
- 同一帧同时显示：左侧真实 SVT，右侧冻结的 G35 GS。
- SVT：`DownsampleFactor=2`、`MaxStepCount=256`、shadow resolution `512`。
- GS：`311,993` 点，`AlphaCutoff=1/255`、`SubPixelRadius=0`；G35 冻结参数和 PLY 不变。
- Editor realtime 报告为 false，因此每次先发 `ProfileGPU`，紧接 `CaptureViewport` 强制真实渲染。
- 优化前 5 次同帧样本；优化后冷启动 10 次样本。使用中位数吸收 SVT lighting-cache 周期性冷样本。

这套比较的关键是“两个资源在同一帧、同一机位，各读各的 GPU tree 事件”。Editor 总帧还包含
场景、编辑器和两套资源，不能用总帧差直接宣称单资源成本。

## 资产体积对齐

| 资源 | 文件/标注体积 | 相对 GS PLY |
|---|---:|---:|
| 原始 WDAS Half VDB | `378 MiB` | `19.85×` |
| UE SVT U8 asset | `85.8 MiB` | `4.51×` |
| G35 compact PLY | `19,968,040 B = 19.043 MiB` | `1×` |

GS 的 `19.043 MiB` 是资产文件，不是完整 GPU working set。G38 已实测单个 GS 净新增 RHI
working set=`66.476 MiB`，直接命名 `GS7DRGS.*` 资源=`74.223 MiB`；前者包含公共池复用后的
净增，后者是资源名直接归因，两者都不能与磁盘 PLY 混写。SVT 净新增 RHI=`305.566 MiB`。

## G37 改动

只做 alpha-support quad crop：VS 根据 PS 已有的同一个 `AlphaCutoff` 计算仍可能贡献的高斯支撑半径，
把固定 `3σ` quad 保守缩到 `supportSigma + 0.05σ`；peak alpha 已低于 cutoff 的 quad 直接退化。
保留下来的像素仍走原 conic、opacity、J、DGSM、coverage 和 G35 composite。

当前冻结 PLY 是 `compact_shared_opacity=1`，PS 的 `GSCompactStatic==2` 分支使用的正是同一个共享
opacity，因此 VS 的 peak 公式与该分支逐项一致。`0.05σ` margin 让新 quad 边界已经落在 cutoff 以下，
吸收浮点/光栅边界漂移。

修改文件：

- `GaussianSplattingShaders.h`
- `GaussianSplattingSceneViewExtension.cpp`
- `GaussianSplattingHWRaster.usf`

`GaussianSplattingComposite.usf` SHA256 仍为 G35 的
`0C01F118173132A6BA0D39F91BD69BA291C702F95CC9DE3B8BBBB6781308C945`。

完整冷编译成功，冷启动重新编译 `FGSHWQuadVS` 并加载精确 311,993 点；当前日志没有 shader 参数
绑定错误或 fatal，关卡与内容 dirty package 均为空。公式不变量检查见
`artifacts/perf_g35_vs_svt_g37_20260731/verify_alpha_support_crop.py`。

## 已测但未晋升

- `SubPixelRadius=0.25`：GS 中位数 `1.344 ms`，相对 `1.343 ms` 无收益，恢复 `0`。
- `AlphaCutoff=1/128`：短测 GS `1.286 ms`、HW Raster `0.763 ms`，有性能收益；但历史 G28 已明确
  记录该档会产生颗粒、棉絮壳和硬暗缝，因此按视觉 Gate 否决并恢复 `1/255`。
- 不优化 G35 composite：其事件约 `0.015–0.016 ms`，不是瓶颈；退回 9 taps 只会冒画质风险。

## 当前状态与下一门

G37 已通过冷编译、公式检查、收益门和用户自由镜头复验，现为正式 runtime 冻结版。G38 又完成
Development `-game` 冷进程 working-set 闭环；当前可以对已签字的 UE SVT A/B 写出上述
feature-time 与显存结论。若对外发布 Shipping headline，仍应补 Shipping 10+10 GPU 样本；
不把当前结论扩展为近景 Hero、动画、多光源、通用 VDB 替代或已胜过 NanoVDB。

原始样本、哈希和构建状态见
`artifacts/perf_g35_vs_svt_g37_20260731/performance_manifest.json`。
