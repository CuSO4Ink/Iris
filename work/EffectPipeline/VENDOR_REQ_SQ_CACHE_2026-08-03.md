# 白鹰金沙特效 Sequence 包体积整改说明

日期：2026-08-03
涉及镜头：**C30 / E20 / C60**
接收方：漫行者（BYDC 白鹰项目组）

---

## 一、问题结论

三个镜头的 Level Sequence 包体积严重超限，**无法提交入库**：

| 镜头 | Sequence 包 | 当前体积 | 超限情况 |
|------|-------------|----------|----------|
| C30 | `Fx_C30/Level/C30_Sequence.uasset` | **12809.1 MB** | 超上传上限 2.5 倍 |
| E20 | `FX_E20/Level/E20_Sequencer.uasset` | **10951.9 MB** | 超上传上限 2.1 倍 |
| C60 | `FX_C60/Level/C60_Sequence.uasset` | **5113.1 MB** | 超上传上限 |

**核心问题不是"数据量太大"，而是"数据存放位置错了"。**

体积并非来自贴图、模型或缓存数据本身过大，而是**仿真缓存被内联（inline）写进了 Sequence 包内部**。
三个 Sequence 的外部依赖资产合计都很小（见附录），说明超出的十几 GB 全部压在 Sequence 包自身。

推测成因：在 Sequencer 中直接对组件录制缓存（Record / Bake），未显式导出为独立资产，
导致缓存数据随 Sequence 一起序列化进同一个包。这属于**操作流程问题，不是制作工作量问题**。

---

## 二、整改要求

请将三个 Sequence 内联的仿真缓存**导出为独立资产**，Sequence 内只保留引用：

1. **粒子类缓存** → 导出为独立 `NiagaraSimCache` 资产
2. **顶点动画类缓存** → 导出为独立 `GeometryCache` 或 Alembic（`.abc`）资产
3. **单个资产包控制在 2 GB 以下**（如单段超过，请按时间段拆分为多个）
4. **Sequence 内不得内联缓存数据**，只保留对上述独立资产的引用

**数据一字节不少，只是换存放位置。** 预期结果：
一个十几 GB 的"死包" → 若干个 2 GB 以内的独立资产 + 一个几十 KB 的 Sequence。

---

## 三、同批镜头已验证的参照案例

同一批交付中，**D20 与 E40 采用了相同的制作方式，均已按上述形态处理完成，画面效果无任何变化**：

| 镜头 | 处理前 | 处理后 | 效果 |
|------|--------|--------|------|
| **D20** | 5206.2 MB | **40 KB** | 无变化，已验证 |
| **E40** | 5546.6 MB | 已规范化 | 无变化，已入库 |

D20/E40 之所以我方可自行处理，是因为其粒子由**独立的 PointCache 资产**驱动
（`D20_Pointcache_1/2`、`E40_Pointcache`），Sequence 内的缓存只是同一结果的第二份副本，
移除后粒子仍可从 PointCache 正常读取数据、画面完全一致。

**C30 / E20 / C60 不具备这个条件**：三个镜头的交付目录内**没有任何可再生的数据源**
（无 PointCache、无 `.abc`、无 `.hip`、无 `.vdb`），Sequence 内的缓存即为该效果的唯一数据。
我方一旦移除即丢失效果，也无法重新烘录（缺少 Houdini 工程源文件）。
因此这三个镜头必须由贵方在源头导出。

---

## 四、附带要求

### 1. 请勿交付 `Saved/Autosaves/` 目录

该目录为引擎自动保存的临时文件，无使用价值，且体积极大。当前返包中存在：

- `C10_cloud_02_v01_Auto1.uasset` — **31.8 GB**（在 A45、B20 两处重复出现）
- `daochang_fix_Auto2.uasset` — 11449.2 MB（重复出现）
- `E40_cloud_04_v01_Auto1.uasset` — 9564.3 MB（重复出现）

当前返包共 10287 个包，其中约 750 个位于 `Autosaves` 下，请在打包时排除。

### 2. 请避免同一镜头交付多个批次副本

目前同一镜头常存在新旧两份（如 `0605/baiyin_C30/.../NewLevelSequence.uasset`
与 `BYDC文件重新整理/金沙效果/C30/.../C30_Sequence.uasset`，体积完全相同），
容易造成版本混淆。请明确以一份为准。

### 3. 资产命名请与所属镜头一致

D20 交付内容中，Sequence 里的缓存轨道命名为 `E40_text3 Sim Cache`（E40 的资产名混入 D20），
同时 `BYDC/0611/BYDC-D20金沙` 目录下也混有 `E40_text3/4/5` 文件。
推测是复制 E40 资产改做 D20 时未同步改名。请确认各镜头资产归属正确。

---

## 五、后续流程

1. 贵方按第二节要求重新导出 C30 / E20 / C60 三个 Sequence 及配套缓存资产
2. 交付前请自查：Sequence 包体积应在 100 MB 以内，单个缓存资产 < 2 GB
3. 我方接收后进行导入与效果验证
4. 如对导出方式有疑问，可参照 D20 处理后的成品形态

---

## 附录：三镜头交付目录实测清单

**扫描范围**：`J:\vendors_\漫行者\Final最终归档\BYDC\BYDC文件重新整理\金沙效果\`（已排除 `Saved/`）

### C30
```
12809.1 MB  Content/Fx_C30/Level/C30_Sequence.uasset      <- 超限主体
  258.0 MB  Content/Fx_C30/Mesh/C30_zuoyi.uasset
    2.6 MB  Content/Fx_C30/Niagara/C30_niagara_1 ~ _7     (7 个，各约 2.6MB)
    ~3 MB   Content/Fx_C30/Volume/Assets/C30_vfx_test_cloud_01~04
```

### C60
```
 5113.1 MB  Content/FX_C60/Level/C60_Sequence.uasset      <- 超限主体
  672.9 MB  Content/FX_C60/Geo/C60_baiying.uasset
  140.4 MB  Content/FX_C60/Volume/C60_Cloud_1.uasset
    1.7 MB  Content/FX_C60/Niagara/C60_niagara_1 ~ _3     (3 个，各约 1.7MB)
```

### E20
```
10951.9 MB  Content/FX_E20/Level/E20_Sequencer.uasset     <- 超限主体
  150.4 MB  Content/FX_E20/Volume/Assets/E20_cloud_03_v02.uasset
   41.3 MB  Content/FX_E20/Mesh/E20_baiying.uasset
    2.6 MB  Content/FX_E20/Niagara/E20_niagara.uasset
    1.4 MB  Content/FX_E20/Mesh/E20_baiying_Anim.uasset
```

三个镜头除 Sequence 本体外，最大资产分别仅为 258 MB / 672.9 MB / 150.4 MB，
均为网格或云资产，无法解释 Sequence 包的十几 GB 体积——**可确认体积来自内联缓存**。

E20 的 `E20_baiying_Anim` 仅 1.4 MB，为骨骼动画资产，
不足以承载 10.9 GB 的顶点数据，说明顶点缓存同样内联在 Sequence 内。
