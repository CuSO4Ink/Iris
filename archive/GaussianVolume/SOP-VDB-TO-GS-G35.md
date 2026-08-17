# GaussianVolume G35：VDB → GS 生产 SOP 与性能优化顺序

日期：2026-07-31  
状态：G35 视觉与 G37 runtime 已由用户验收并冻结；G38 冷进程显存闭环完成。本文是后续生产与性能工作的唯一主入口。

## 1. 冻结目标

当前交付不是“轮廓训练候选”，而是以下组合：

```text
VDB density
  → float32 dense NPY
  → 64 视角 RGBA teacher
  → 标准 3DGS 训练
  → iteration 15000 的 311,993 点原始几何/opacity
  → 从原 VDB 沿六轴直接积分 J=exp(-tau)
  → J^0.4
  → 16×float32 compact PLY（64 B/point）
  → UE GPU sort + HW Quad + DGSM + G35 composite
```

最终 PLY 的前十列来自标准 3DGS 15K 原始结果，后六列与
`S3_F_Gamma04J.ply` 逐 bit 相同。G24～G28 的 silhouette / boundary morph
几何已从最终资产回滚；它们只保留为失败与对照分支。

### 1.1 冻结清单

| 项目 | 冻结值 |
|---|---|
| PLY | `artifacts/wdas_s3_original15k_geometry_current_transport_g31_20260731/S3_Original15KGeometry_CurrentGamma04J_AngularSigma05.ply` |
| PLY SHA256 | `AE7177BF3753E9905C34208A9D46A2647018F55A49FF13581A717BA1040EA0FB` |
| 点数 / 布局 | `311,993` / `16×float32` / `64 B/point` |
| payload | `19,967,552 B`（`19.043 MiB`，不是完整 GPU working set） |
| Shader | `GaussianSplattingComposite.usf` G35 |
| Shader SHA256 | `0C01F118173132A6BA0D39F91BD69BA291C702F95CC9DE3B8BBBB6781308C945` |
| UE 参数快照 | `artifacts/runtime_interior_joint_bilateral_g35_20260731/frozen_visual_baseline.json` |
| 稳定部署目录 | `Plugins/GaussianSplattingForUnrealEngine/Content/Data/S3Original15KG32_20260731/` |

恢复 G35 时，复制存档 Shader 与 PLY，并按参数快照恢复 Actor；不要从记忆手调。

## 2. 版本与输入门禁

### 2.1 已验收 WDAS 输入

- dense grid：`D:\Work\AI\Iris\tmp\wdas_cloud\grids\wdas_cloud_half.npy`
- dtype / shape：`float32` / `994×676×1225`
- SHA256：`7DE6A0769E2D6C79ED3E02F3ED05501A53B0608769CA72E9394989D6E8B01512`
- 最长边：`1000 cm`
- voxel：`1000/1225 = 0.8163265306122449 cm`
- density scale：`0.04`

### 2.2 代码指纹

| 文件 | SHA256 |
|---|---|
| `mvp/standard_3dgs_baseline.py` | `18EAC4195DF51EEEE525B20290C4E72E814FB0F0BB3FFFAEF4A60E8BA472465C` |
| `mvp/grid_to_7drgs.py` | `3BCD4C1AEB08751C5B2A3A4CDE91A6D9506A9A4B4B3308A8F4BF9C67DB29E17E` |
| `mvp/build_s3_transport_diagnostic.py` | `40D557C5672328E3666920C46E2FF9E5D5312C090A0D4BD144504BB22398D137` |
| upstream `train.py` | `50B47D23A5F36AE239BA66FA1B06222B5A829CB35ECCE36FC3B22476121955CC` |
| upstream `scene/dataset_readers.py` | `F71C04D6905084557DB446C88BF1305F5C5F2472C768633D3671A39F64F9EC63` |
| upstream `utils/loss_utils.py` | `11E99203FDDE95BA9EC27A974FB0B93EAB4D1A0FEC2570F926A3029E03AF7A15` |

标准 3DGS 仓库当前 HEAD 为
`54c035f7834b564019656c3e3fcc3646292f727d`，但工作树含本项目修改；仅 checkout
该 commit 不能复现结果。新生产运行前必须保留上述文件指纹，或先把本地修改形成正式 patch/commit。

### 2.3 当前缺口：VDB 解码环境

已验收运行的 `.vdb → .npy` 命令和 Python 环境没有被完整存档，因此不能把现状描述成
“从任意 VDB 一键复现”。生产 SOP 的正式输入边界暂时是已校验的 `float32 NPY`。

对新 VDB，Gate 0 必须补齐并记录：VDB 文件 hash、grid name、active bbox、voxel size、
轴顺序、dense NPY hash。`mvp/vdb_converter.py::read_vdb_grid` 可作小体积验证，但其逐 voxel
Python 循环不适合 WDAS 规模；大体积应在固定的 OpenVDB/pyopenvdb 环境中使用
`FloatGrid.copyToArray` 批量导出。该环境未验证前，不把这一步写成自动生产命令。

## 3. 每次运行的目录规则

不要覆盖 G35。每次新输入使用独立 run 目录：

```powershell
$GVRoot = 'D:\Work\AI\Iris\work\GaussianVolume'
$RunId = 'cloudname_YYYYMMDD_HHMM'
$RunRoot = Join-Path $GVRoot "runs\$RunId"
New-Item -ItemType Directory -Path $RunRoot | Out-Null
```

固定子目录：

```text
00_input/       VDB/NPY hash、bbox、单位与轴信息
10_teacher/     images、points3d.ply、transforms、prepare_report.json
20_3dgs/        标准 3DGS checkpoints、日志、cfg_args
30_compact/     compact base、六轴 J 候选与报告
40_ue/          晋升 PLY、UE 参数快照、截图、ProfileGPU
```

## 4. Stage A：生成 teacher

使用 `standard_3dgs_baseline.py prepare`。下面是已验收 WDAS 参数；新资产只允许显式修改
尺寸、相机半径或视场，不要静默继承默认值。

```powershell
$Py = '<gaussian_splatting environment python.exe>'
$Grid = 'D:\Work\AI\Iris\tmp\wdas_cloud\grids\wdas_cloud_half.npy'
$Teacher = Join-Path $RunRoot '10_teacher'

& $Py "$GVRoot\mvp\standard_3dgs_baseline.py" prepare $Grid $Teacher `
  --views 64 `
  --resolution 512 `
  --steps 256 `
  --row-chunk 8 `
  --downsample 2 `
  --seed-points 400000 `
  --seed-threshold 0.01 `
  --longest-size-cm 1000 `
  --density-scale 0.04 `
  --ambient 0.4 `
  --camera-radius-m 15 `
  --fov-degrees 42 `
  --scene-scale 0.2 `
  --test-every 8
```

Gate A：

- `prepare_report.json` 必须记录输入 hash、原始/teacher shape、voxel、scene scale；
- 64 张 RGBA，56 train / 8 test；
- points3d seed 数不超过 400K，WDAS 实际为 `379,965`；
- 任意 NaN、负 density、空 alpha 或轴向翻转，立即停止。

## 5. Stage B：标准 3DGS 训练与 checkpoint 选择

训练仓库：`D:\Work\AI\Iris\tmp\gaussian-splatting-upstream`。依赖定义见其
`environment.yml`；先运行仓库自身 smoke test，再启动生产训练。

```powershell
$GSRepo = 'D:\Work\AI\Iris\tmp\gaussian-splatting-upstream'
$Model = Join-Path $RunRoot '20_3dgs'
Set-Location $GSRepo

& $Py train.py `
  -s $Teacher `
  -m $Model `
  --eval `
  --sh_degree 3 `
  --iterations 30000 `
  --test_iterations 7000 15000 30000 `
  --save_iterations 7000 15000 30000 `
  --disable_viewer
```

WDAS 已验收选择：

| iteration | 点数 | test L1 | test PSNR |
|---:|---:|---:|---:|
| 7,000 | — | `0.00247991` | `42.9353 dB` |
| 15,000 | `311,993` | `0.00240468` | `43.5372 dB` |
| 30,000 | — | `0.00260229` | `42.9078 dB` |

因此选择 `iteration_15000`。不要把“训练更久”当作自动晋升；30K 已出现 held-out 回退。

Gate B：checkpoint finite；covariance 正定；点数、held-out L1/PSNR、训练日志和源代码指纹
全部归档。新资产只有在 15K/30K 同时比较后才决定 checkpoint。

## 6. Stage C：转为 compact 几何并从 VDB 直烘 J

当前 `grid_to_7drgs.py` 的标准 3DGS compact 转换入口要求一个 transport source。
这是转换器耦合，不是最终算法需求。对新 VDB，先生成一个临时 B8 compact source；其 J
随后会被 VDB direct bake 完全覆盖。

```powershell
$PointCloud = Join-Path $Model 'point_cloud\iteration_15000\point_cloud.ply'
$Bootstrap = Join-Path $RunRoot '30_compact\bootstrap_b8.ply'
$CompactBase = Join-Path $RunRoot '30_compact\standard15k_compact_base.ply'
$TransportDir = Join-Path $RunRoot '30_compact\direct_transport'

& $Py "$GVRoot\mvp\grid_to_7drgs.py" $Grid $Bootstrap `
  --block-size 8 `
  --longest-size-cm 1000 `
  --density-scale 0.04 `
  --spatial-sigma-ratio 0.55 `
  --angular-sigma 0.5 `
  --ambient 0.06 `
  --compact

& $Py "$GVRoot\mvp\grid_to_7drgs.py" $PointCloud $CompactBase `
  --transport-source $Bootstrap `
  --scene-scale 0.2 `
  --transport-neighbors 1

& $Py "$GVRoot\mvp\build_s3_transport_diagnostic.py" `
  $CompactBase $Grid $TransportDir `
  --density-scale 0.04 `
  --voxel-cm 0.8163265306122449 `
  --angular-sigma 0.5
```

生产选择 `$TransportDir\S3_F_Gamma04J.ply`：

- 前十列：原始 15K center、shared opacity、完整对称 covariance；
- 后六列：资产局部轴顺序 `+X/-X/+Y/-Y/+Z/-Z` 的 `pow(exp(-tau), 0.4)`；
- `compact_static_transport=1`、`compact_shared_opacity=1`、`angular_sigma=0.5`；
- 其余 A/B/C/D/E 只作 transport 诊断，不晋升。

历史 G31 最终 PLY 与 `S3_F_Gamma04J.ply` 的 16 列 payload 逐 bit 相同；G31 只是重新封装
了 header/命名。因此新生产链不必再经过 boundary-morph candidate。

Gate C：

- exactly 16 个 float property，顺序固定；
- exactly `point_count × 64 B` payload；
- 所有值 finite，opacity 在 `(0,1)`，covariance 正定，J 在 `[0,1]`；
- direct bake 报告 `inside_fraction=1`；
- geometry/opacity 与选择的标准 3DGS checkpoint 转换结果逐 bit 不变；
- 记录 PLY SHA256。

## 7. Stage D：UE 晋升

1. 将候选复制到新的插件数据目录，不覆盖 G35：

   ```powershell
   $PluginData = 'D:\Work\Personal\Project\Abyss\Plugins\GaussianSplattingForUnrealEngine\Content\Data'
   $DeployDir = Join-Path $PluginData $RunId
   New-Item -ItemType Directory -Path $DeployDir | Out-Null
   Copy-Item -LiteralPath (Join-Path $TransportDir 'S3_F_Gamma04J.ply') -Destination $DeployDir
   ```

2. 在复制完成后再切换 Actor 的 PLY 并 Reload；先回读 point count 和 compact metadata，
   不立即保存关卡。
3. 恢复 `frozen_visual_baseline.json` 的 Actor transform、光照、DGSM、phase、depth 和 appearance。
4. 固定机位比较候选与 G35，再做自由镜头检查。
5. 只有视觉、日志、ProfileGPU 都通过后才保存关卡并写新的 frozen manifest。

### 7.1 必过视觉 Gate

- 边缘不再出现蓝底贯穿空洞；
- 最外圈连续、虚化，不变亮变实；
- 内部低频体积层次不被高频斑驳打断；
- 不出现 G34 的纵向梳状/笔刷条带；
- 正面受光不出现错误黑块；
- DGSM 能拉开对比，但不整体压死；
- 多距离、自由旋转都成立，不能只看一个机位。

### 7.2 回滚

- PLY：切回 `S3Original15KG32_20260731` 的冻结文件；
- Shader：恢复 `runtime_interior_joint_bilateral_g35_20260731/GaussianSplattingComposite_G35.usf`；
- 参数：应用 `frozen_visual_baseline.json`；
- 不删除失败 run，给 manifest 标注失败原因、截图和停止条件。

## 8. G35 性能基线

采样条件：PIE Simulate、同一 TechLab 视角、`1990×1198`、`311,993` 点、单帧
`ProfileGPU`。这是 editor/PIE 快速基线，不代替 standalone/shipping 数据。

| Pass | GPU 时间 |
|---|---:|
| GaussianSplatting 7DRGS total | `1.354 ms` |
| HW Raster | `0.824 ms` |
| Sort BackToFront（固定按 311,993 项） | `0.236 ms` |
| Slice | `0.087 ms` |
| Preprocess | `0.081 ms` |
| G35 Composite | `0.016 ms` |

整帧为 `9.85 ms`。最重要的结论：G35 的 25-tap joint bilateral 不是瓶颈；把它退回
9 taps 会冒视觉回归，只可能节省零点零几毫秒，停止这条优化分支。

## 9. 性能优化顺序

### P1：先做现有 CVar 的无代码 A/B

保持 G35 文件与关卡不变，只在 PIE 会话内测试：

1. `r.GaussianSplatting.SubPixelRadius 0.25`，再测试 `0.5`；
2. `r.GaussianSplatting.AlphaCutoff 0.0078125`（`1/128`）；
3. 两项单独通过后才测试组合。

基线恢复值：

```text
r.GaussianSplatting.SubPixelRadius 0
r.GaussianSplatting.AlphaCutoff 0.0039215686
```

注意：SubPixelRadius 会减少实际 draw/raster，但当前 radix sort 仍按 CPU 已知的完整
`311,993` 长度运行，因此不会降低 `0.236 ms` 的 sort。历史 `AlphaCutoff=1/64` 已暴露明显
颗粒，不再测试该档。

### P2：按 alpha cutoff 精确收缩 quad

当前标准 3DGS quad 固定覆盖 `3σ`。低 opacity splat 在远小于 `3σ` 时已经会被 PS 的
`AlphaCutoff` 丢弃，但 quad 仍产生 raster coverage。代码级首选是根据

```text
peakAlpha = pow(saturate(opacity * multiplier), opacityPower) * footprintOpacityScale
supportSigma = sqrt(-2 * log(alphaCutoff / peakAlpha))
```

把 basis 保守收缩到 `min(3, supportSigma + epsilon)`；`peakAlpha < cutoff` 时直接 cull。
这只裁掉现有 PS 本来就 discard 的区域，不改 conic、颜色、J、coverage 或 composite。
实现时需把 opacity multiplier/power/cutoff 传入 Preprocess，属于 Shader 参数布局变化，
必须冷编译、冷启动和固定图像回归，不能用 Live Coding 热换参数结构。

### P3：减少实际 splat 数，而不是继续优化 composite

如果 P1/P2 不够，再建立距离分级资产或训练期 pruning/预算约束，使远景使用更少的有效点。
这能同时降低 HW Raster，并在改成 visible-count sort 后降低排序；代价是必须重新过全部边缘
和内部层次 Gate。不要直接把当前 312K 文件离线随机删点。

### P4：visible-only sort 只在证据足够时做

Preprocess 已在 GPU 上写出 `VisibleCount`，DrawIndirect 也只画 visible splat；但 UE 的
`SortGPUBuffers` 接口需要 CPU 标量 count，当前因此仍执行 `Sort(311993)`。每帧把
VisibleCount readback 到 CPU 会引入同步 stall，明确禁止。

只有当 sort 在目标平台稳定超过约 `0.3 ms`，或多 Actor 使其成为主瓶颈时，才值得实现
GPU-count 驱动的自定义 radix/bucket sort。当前 `0.236 ms` 排第二，但远低于 raster，暂缓。

### 9.1 性能 Gate

- 同一相机、分辨率、曝光、PIE 模式和 warmed shader；
- 每档至少 10 次 ProfileGPU，取中位数；
- 收益小于 `0.07 ms` 或 GS total 的 `5%`，视为噪声，不晋升；
- 性能通过后仍必须做固定截图差分和自由镜头人工检查；
- 禁止用 editor 总帧波动替代 pass 级证据；
- 最终 headline 必须来自 standalone/shipping，且写明完整 working set，不只写 PLY 大小。

### 9.2 G37 实测结论（2026-07-31）

- P1 `SubPixelRadius=0.25` 无收益，恢复 `0`；`AlphaCutoff=1/128` 虽有性能收益，但命中 G28 的
  颗粒/棉絮壳/硬暗缝视觉失败，恢复 `1/255`，不得重新晋升。
- P2 已实现为 HW quad VS 的保守 support crop；未新增 pass、RT 或 buffer，G35 composite 与 PLY 不变。
  冻结 shared-opacity 资产的 VS/PS peak 公式一致，并保留 `0.05σ` 浮点余量。
- 同帧 SVT/GS 固定机位：GS total `1.343 → 1.093 ms`（`-18.6%`），HW Raster
  `0.819 → 0.5665 ms`（`-30.8%`）；Preprocess/Sort 无变化。P2 通过收益门，P3/P4 暂不启动。
- 当前严格同帧 baseline 为 5 次、优化后为 10 次；幅度远高于噪声。用户自由镜头复验通过，
  G37 已晋升为当前 runtime 冻结基线；这组 GPU 时间仍标注为 editor feature-time，不冒充 Shipping。
- 完整 working set 已由下节 G38 独立冷进程补齐；`19.043 MiB` 仍只表示 PLY payload。

### 9.3 G38 冷启动显存结论（2026-07-31）

- Development `-game`、D3D12、1920×1080、固定机位；Empty/SVT/GS 各 3 个独立冷进程，
  每进程预热 10 秒、20 个稳态样本。
- 单个体积功能相对 Empty 的净新增 RHI working set：SVT=`305.566 MiB`、
  GS=`66.476 MiB`；GS 节省 `239.090 MiB / 78.245%`，约为 SVT 的 `1/4.597`。
- GS 自身口径：non-transient=`19.063 MiB`、transient 净增=`47.414 MiB`；不要把
  PLY `19.043 MiB`、命名资源 `74.223 MiB`、净增 RHI `66.476 MiB` 混成同一指标。
- 整个 UE 场景进程口径：SVT=`2664.178 MiB`、GS=`2343.980 MiB`，GS 少
  `320.198 MiB / 12.019%`。其中约 2.3 GiB 是 UE/Lumen/TSR/VSM/公共池；
  `2343.980 MiB` 绝不是单个 GS 显存。
- 完整报告：`VRAM-COLD-G37-VS-SVT-20260731.md`；原始数据：
  `evidence/memory-20260731-g37-cold-3x/`。若对外发布 Shipping headline，再补
  Shipping 10+10 GPU 样本；这不阻塞当前 Development 项目收尾。

## 10. 已终止分支

- G3/G4 jitter、density de-grid、covariance-only、split/merge、Adaptive B4、Sigma8：无法同时保留光学质量与结构；
- 7DRGS student、Gabor residual：数值或 UE visual Gate 失败；
- silhouette/internal-alpha/统一 footprint 放大：产生碎边、棉絮壳、硬暗缝或形体漂移；
- G34 稀疏大步长方向模糊：产生纵向梳状笔刷；
- 全图 RGB blur、强 AlphaCutoff、半分辨率：丢信息或暴露颗粒；
- CPU readback visible count：会用同步 stall 换掉很小的 GPU sort 成本。

详细证据与资产路径见 `summary/PROJECT-RETROSPECTIVE.md` 和
`IMPLEMENTATION-AND-OPTIMIZATION-LEDGER.md`。新实验若命中这些停止条件，直接归档，
不以换名字的方式重开。

## 11. 一次生产运行的完成定义

- 输入 VDB/NPY、代码、环境和命令均有 hash/日志；
- teacher 与 3DGS checkpoint Gate 完整；
- compact PLY 结构、数值、位一致性和 hash 通过；
- 候选在独立插件目录，不覆盖 G35；
- 固定机位、自由镜头、光照方向和距离 Gate 通过；
- ProfileGPU 及 standalone 结果归档；
- 关卡最后保存；
- 新 manifest 明确 parent、变化、收益、回滚路径和用户签字。
