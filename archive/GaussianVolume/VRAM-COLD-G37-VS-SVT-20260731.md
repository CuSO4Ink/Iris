# G37 GS 与 UE SVT 冷启动显存对比（2026-07-31）

## 结论

当前冻结的 311,993 点 G37 GS 相对同源 UE SVT，在独立 `-game` 冷进程中：

- 整场景进程专用显存中位数低 `320.198 MiB`，即 `12.019%`；
- 整场景稳态采样峰值低 `298.051 MiB`，即 `11.063%`；
- 相对 Empty 的完整 RHI 净新增 working set 为 `66.476 MiB`，SVT 为
  `305.566 MiB`；GS 少 `239.090 MiB`、降低 `78.245%`，约为 SVT 的
  `1 / 4.597`。

因此，对外区分两个数字：整场景进程实际驻留节省约 `320.2 MiB / 12.0%`；
体积功能净新增 RHI working set 节省约 `239.1 MiB / 78.2%`。

## 测试条件

- GPU：NVIDIA GeForce RTX 5060，8 GiB，驱动 `32.0.15.9636`；
- Unreal Development `-game` 独立冷进程，D3D12，离屏 `1920×1080`；
- 每个方案 3 次独立进程；每次地图完成加载后预热 10 秒，采 20 个稳态点；
- 相机位置 `(1677.07570194, 4953.87681787, 577.09876377)`；
- 相机旋转 `(-7.09999697, -91.77999607, 0)`；
- 三张基准地图均从当前 TechLab 复制，只分别保留 0/1 个目标体积 Actor；
- Windows `GPU Process Memory / Local Usage` 记录进程专用显存；
- 第 300 帧读取 `rhi.DumpResourceMemory ... Transient=all` 与 UE 原生 SVT 内存统计。

## 整场景进程专用显存

| 方案 | 三次进程中位数的中位数 | 稳态采样峰值 | 相对 Empty 中位数 |
|---|---:|---:|---:|
| Empty | `2337.764 MiB` | `2465.488 MiB` | `0` |
| UE SVT | `2664.178 MiB` | `2694.094 MiB` | `+326.414 MiB` |
| G37 GS | `2343.980 MiB` | `2396.043 MiB` | `+6.216 MiB` |

逐冷进程中位数：

| 方案 | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| Empty | `2376.434` | `2337.764` | `2298.080` |
| UE SVT | `2664.178` | `2674.008` | `2649.451` |
| G37 GS | `2318.086` | `2350.068` | `2343.980` |

GS 的 `+6.216 MiB` 落在 D3D12 堆保留的冷进程波动内，不能单独当成 GS
真实资源体积。SVT 与 GS 的整进程中位数差 `320.198 MiB`，三次观察范围按
最保守/最宽组合为 `299.383–355.922 MiB`，方向稳定。

## 完整 RHI working set

第 300 帧、三次冷进程取中位数：

| 方案 | RHI 总量 | Non-Transient | Transient | 净新增 vs Empty |
|---|---:|---:|---:|---:|
| Empty | `2328.946 MiB` | `1657.460 MiB` | `671.485 MiB` | `0` |
| UE SVT | `2634.512 MiB` | `1963.027 MiB` | `671.485 MiB` | `305.566 MiB` |
| G37 GS | `2395.422 MiB` | `1676.523 MiB` | `718.899 MiB` | `66.476 MiB` |

GS 净新增可拆为：

- 常驻：`19.063 MiB`；
- 瞬态净增：`47.414 MiB`；
- 合计：`66.476 MiB`。

SVT 原生统计稳定为 `305.566 MiB`，其中 Tile Data `303.250 MiB`、Page Table
`2.316 MiB`。它的渲染瞬态在该场景中复用了 Empty 已存在的 transient pool，
所以净新增主要表现为常驻 SVT 数据。

## 资源名直接归因

- `GS7DRGS.*`：17 个资源，共 `74.223 MiB`；其中 `GS7DRGS.Raw`
  `19.063 MiB`，其余命名瞬态 `55.161 MiB`；
- `SparseVolumeTexture.*` 首帧：9 个资源，共 `306.379 MiB`；稳定后 UE 原生
  统计为 `305.566 MiB`，首帧多出的约 `0.813 MiB` 为上传缓冲。

命名资源总和与相对 Empty 的 RHI 净增不是同一口径：前者计算资源自身，后者会
扣除 RDG alias/公共 transient pool 的复用。两者都显示 GS 明显低于 SVT；命名口径
降低 `75.774%`，净新增 RHI 口径降低 `78.245%`。

## 有效性检查

- 3/3 GS 进程均实际加载 `311,993 compact static transport gaussians`；
- 3/3 SVT 进程均输出 `305.566 MiB` 原生 GPU Memory；
- 9/9 进程均完成目标地图加载；
- 0 次 GPU crash、D3D device removed、shader fatal。

原始结果位于 `evidence/memory-20260731-g37-cold-3x/`：`results.csv`、
`summary.csv`、`rhi_totals.json`、`rhi_summary.csv`、逐进程样本及完整 UE 日志。

这里对比的是 UE 实际使用的同源 U8 SVT，不把原始 `378 MiB` VDB 文件大小当成
运行显存。测试为 Development standalone `-game`，不是 Shipping build。
