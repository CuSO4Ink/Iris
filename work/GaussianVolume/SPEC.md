# GaussianVolume 下一阶段开发 Spec

> 状态：实施中（G4）  
> 日期：2026-07-12  
> 实现位置：`D:/Work/Personal/Project/Abyss/Plugins/GaussianVolume/`  
> 目标引擎：UE 5.8，目标显卡：RTX 5060

## 1. 目标

把现有 UE GaussianVolume 研究 renderer 收敛为一个可验证的 **Structured Gaussian Field FX** 原型：

- Spline 生成 `32/64/128` 个各向异性 Gaussian primitive；
- primitive 构成真实三维连续密度，而非 camera-facing ribbon；
- 支持解析 optical depth、single scattering 和场景深度遮挡；
- 同一 field 至少被 renderer 之外的一个系统消费；
- 用磁拱/等离子体管 demo 独立展示三维厚度、透射和交叉遮挡；
- 用 GPU 数据决定是否需要 half-res、排序或 tile candidate 加速。

本阶段不证明 Gaussian 普遍优于 Ribbon、VDB 或 raymarch，只验证它在三维厚度、内部观察、交叉密度、逆光透射和共享空间查询上的价值。

## 2. 非目标

本阶段不做：

- VDB import、VDB LOD 或通用云 renderer；
- Neural/ONNX/NNE decoder；
- 多次散射、复杂 phase function；
- PBF-CSF、BVH、GPU radix/bitonic sort；
- 通用 Gaussian asset format、独立编辑器窗口或 graph editor；
- ~~多 Actor renderer manager~~（2026-07-12 更正：已改为 per-world `UGaussianVolumeWorldSubsystem` 共享渲染器，聚合所有 Actor 的 primitive 到单一 pass，以支持 per-arc 参数与正确的跨 Actor 遮挡；仍不做通用资产/管线级 manager）；
- Marching Cubes、HPVolumeCloud 或 Bifrost 全场景整合。

只有本 Spec 的 benchmark 证明现有实现不达预算时，才重开相应优化。

## 3. 当前基线

已有：

- `FGaussianVolumePrimitive`：center / scale / rotation / sigma_t / albedo；
- Actor / Component / SceneViewExtension 生命周期；
- CPU → GPU `StructuredBuffer`；
- RDG Compute Shader 和后处理链输出；
- 各向异性 ray–Gaussian 解析积分；
- 简化 single scattering、ambient、powder；
- UE 5.7 中运行验证。

已知缺口：

- premultiplied volume radiance 在最终合成时被重复乘 alpha；
- shader 按数组顺序累积，不是真正 front-to-back；
- 没有 SceneDepth 截断，体积会穿透前景几何；
- primitive 使用世界坐标，正式 field 不能自然跟随 Actor transform；
- 单 primitive 会被 debug Tick 当作默认球每帧改写和上传；
- light direction 未强制归一化；
- debug mode 硬编码，缺少 tau / transmittance / candidate 可视化；
- GPU buffer 每 View 每帧重建，并有每帧日志；
- UE 5.8 尚未通过运行验收。

## 4. 用户故事

### TA 创作

作为 TA，我可以拖动一条 Spline，通过少量高层参数生成可旋转、可整体变换的三维磁拱，并在编辑器中快速调整厚度、密度、发光、断裂和数量。

### 技术验证

作为图形程序验证者，我可以切换 primitive、optical depth、transmittance、candidate count 和 final lighting，确认结果来自连续体积积分而不是后处理遮罩。

### 作品集展示

作为观众，我能从侧绕、穿越、逆光和多拱交叉画面中直接看出它与 Niagara Ribbon 的差异，并看到固定硬件上的 GPU 成本和失效边界。

## 5. Gate G0 — UE 5.8 基线

### 工作

1. 在 UE 5.8 编译并运行现有插件。
2. 创建最小 `L_GaussianVolume_TechLab`：固定相机、固定曝光、Directional Light、遮挡墙、GPU profile 机位。
3. 保留一个各向同性球和一个旋转后的各向异性椭球作为基准。
4. 删除或降为 `VeryVerbose` 的逐帧日志。

### 验收

- 编辑器启动、shader 编译和 PIE 均通过；
- 球在相机移动时不漂移、不拉伸；
- 椭球旋转方向正确；
- 固定机位可重复截图和抓取 GPU profile；
- 日志无逐帧刷屏。

### 不通过

- 只能在 UE 5.7 工作；
- 依赖手改 shader 常量才能显示；
- 相机运动仍引入形变或消失。

## 6. Gate G1 — 渲染正确性

### G1.1 合成

将 shader 体积结果视为 premultiplied radiance：

```hlsl
FinalColor = VolumeRadiance + SceneColor * Transmittance;
```

删除 shader 内固定假背景，不再次乘 `1 - T`。

### G1.2 输入保护

- 上传前归一化 `LightDirection`，零向量回退默认值；
- `Scale` 每轴限制为正 epsilon；
- `SigmaT >= 0`；
- 非有限 primitive 不上传并记录一次警告。

### G1.3 SceneDepth

- shader 读取场景深度；
- 重建该像素可见表面的 ray distance；
- 令积分上限为 `min(tExit, MaxRayDistance, SceneDistance)`；
- 增加开关用于 A/B 验证 depth composite。

### G1.4 顺序正确性

正式支持有色/发光 primitive 前，必须消除数组顺序导致的可见差异。

首选最小方案：为当前 View 生成 front-to-back index buffer，primitive buffer 保持不变。暂不实现通用 GPU sort。

若该方案在多 View 或相机运动下不适用，再单独评估 shader Top-K 或 tile list；不得预先实现。

### G1.5 最小检查

- 薄介质与低 alpha 不再异常变暗；
- 遮挡墙前后放置 Gaussian，墙后部分不可见；
- 把同一组 primitive 数组反转，固定机位最终图差异低于约定容差；
- `LightDirection` 乘任意正倍数不改变画面；
- scale 为零不会产生 NaN、整屏污染或 GPU crash。

### Gate 验收

全部检查通过后才进入 Spline authoring。若顺序尚未解决，只允许同质单色 field 原型，不宣称彩色交叉正确。

## 7. Gate G2 — Structured Field Authoring

### G2.1 坐标与更新

- primitive 数据定义在 Actor local space；
- 上传时应用 Actor transform；
- Actor 平移、旋转、缩放作用于整组 field；
- 删除 debug primitive 的常驻 Tick；
- 仅在参数、Spline 或 transform 变化时重建/上传。

### G2.2 Spline 生成

直接在现有 Actor 上增加一个 `USplineComponent` 和 `RebuildFromSpline()`，不新建生成框架。

最低参数：

| 参数 | 作用 |
|---|---|
| `PrimitiveCount` | `1–128`，默认 64 |
| `Thickness` | 截面尺度 |
| `Density` | 全局 sigma_t 倍率 |
| `Emission` | 发光/颜色强度；若当前数据布局不支持，先复用 albedo × light intensity |
| `Twist` | 截面沿 Spline 旋转 |
| `Breakup` | 确定性位置/尺度/密度扰动 |
| `Seed` | 保证可复现 |

生成规则：

1. 沿 Spline 等弧长采样；
2. primitive 主轴对齐切线；
3. 纵向尺度覆盖相邻采样间距；
4. 横向尺度由 thickness/profile 决定；
5. density、颜色和 breakup 使用确定性 seed；
6. 数量切换不改变整体路径和主要轮廓。

### G2.3 Debug View

暴露枚举：

- `Final`；
- `Primitive/Albedo`；
- `OpticalDepth`；
- `Transmittance`；
- `CandidateCount`；
- `LightTransmittance`，若已有跨 primitive 光衰减。

### Gate 验收

- 一条 Spline 可生成 `32/64/128` primitive；
- Actor transform 正确；
- thickness、density、breakup、twist 可在编辑器中产生可解释变化；
- 相机侧绕 90° 和进入 field 内部时没有 billboard 穿帮；
- 两条磁拱交叉处密度连续叠加；
- 无常驻无效 Tick 和无变化数据的重复上传。

## 8. Gate G3 — 差异性 Demo

### 场景

在 TechLab 制作两条交叉磁拱/等离子体管：

- 一面遮挡墙；
- 一个背光 Directional/局部强光；
- 一个 90° 环绕镜头；
- 一个进入 field 内部的镜头；

### 必须展示

1. 正面画面；
2. 侧绕厚度；
3. 内部观察；
4. 逆光透射；
5. 两个 field 交叉；
6. 场景几何遮挡；
7. primitive → tau → transmittance → final breakdown。

### 共享 Field

只选一个 renderer 外消费者，优先 Niagara：

- Niagara 查询局部密度/主轴/流向中的至少一个；
- 粒子运动或生成概率明显响应同一 Gaussian field；
- 不复制一套独立 Spline 数据冒充共享 field。

若 Niagara GPU 读取现有 buffer 需要大规模新架构，降级为一束光的解析 attenuation；本阶段只需证明一份 field 被第二个系统真实消费。

### Gate 验收

- 观众无需看代码即可从侧绕、内部或交叉镜头辨认三维体积特征；
- Gaussian 的优势和成本均被诚实记录；
- 如果差异不明显，停止产品化，项目以图形学研究原型结项。

## 9. Gate G4 — 按数据优化

### 基准矩阵

目标硬件 RTX 5060，固定曝光和相机：

| 分辨率 | Primitive 数 | 模式 |
|---|---:|---|
| 1920×1080 | 1 / 32 / 64 / 128 | Full resolution |
| 960×540 | 32 / 64 / 128 | Half resolution，仅在 Full 超预算时实现 |

记录：

- Gaussian render pass GPU ms；
- composite/upsample GPU ms；
- CPU upload 时间；
- primitive buffer 大小；
- 平均/最大 candidate count；
- 相机运动伪影；
- 可接受的最大 primitive 数。

### 优化决策

按以下顺序停止在第一个满足预算的方案：

1. 删除重复上传和无效工作；
2. half-resolution；
3. depth-aware upsample；
4. persistent GPU primitive buffer；
5. screen-space tile candidate list；
6. 只有 tile list 仍不够时才评估 PBF-CSF。

Temporal accumulation、N×N light tau、复杂排序均需独立数据证明，不自动进入排期。

### 建议预算

- `64` primitives、1080p 的 Gaussian 主 pass 以 `<= 2 ms` 为初始目标；
- `128` primitives 必须给出可用画质或功能收益，否则不作为默认规模；
- 预算可在 G0 首次 GPU profile 后由用户调整。

## 10. 跨 primitive 光照

当前 self-shadow 只计算 primitive 自身半程 tau，不能表现其他 primitive 对它的遮挡。

该功能不阻塞 G1/G2；在 G3 逆光画面确认缺陷明显后才实现。首选输出每个 primitive 的累计 light transmittance：

```text
Field/Light 变化时：O(N²) compute prepass
Render 时：O(1) lookup per primitive
存储：O(N)，不保留完整 N×N matrix
```

验收是交叉磁拱的前后遮挡和光照层次明显改善，且 prepass 成本有记录。

## 11. 交付物

- UE 5.8 GaussianVolume 插件源码；
- `L_GaussianVolume_TechLab`；
- 一个 Gaussian magnetic arc Actor；
- 一个共享 field 消费者（当前为 BeginPlay 解析密度 Probe）；
- 10–20 秒固定展示录屏；
- debug breakdown 截图；
- RTX 5060 性能表；
- 已知限制与停止结论。

## 12. 实施顺序

```text
G0 UE5.8 基线
  ↓
G1 合成 / 深度 / 顺序正确性
  ↓
G2 Local-space + Spline authoring + Debug
  ↓
G3 差异性 Demo + 共享 Field
  ↓
G4 只按 profile 结果优化
```

任何 Gate 未通过，不并行开启后续高成本模块。

## 13. 已确认决策

- Hero demo：交叉三维磁拱/日珥；
- 不制作 Niagara Ribbon 并排对照，差异由成片画面与口头说明承担；
- renderer 外消费者采用解析密度 Probe；
- 初始预算保留 `64 primitives / 1080p / <= 2 ms`；
- 使用 per-ray `t_star` 排序与 HDR/tonemap 前合成。
