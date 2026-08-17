# The Last of Us Part II · frame55458 高实例“瀑布”候选实现分析

> 复核日期：2026-07-14  
> 抓帧：`ds_2026.07.13_07.14.47_frame55458.rdc`  
> 方法：RenderDoc MCP 的 draw tree、draw detail、D3D12 pipeline state、texture metadata 与 pixel shader 反汇编。

---

## 1. 结论摘要

此前报告将一批高实例化 draw 命名为“瀑布、水花、泡沫与水雾”。重新对齐当前 RenderDoc MCP 后，能确认它们属于多组**实例化 indexed geometry**，其中一组进入主 5-RT 几何阶段，一组以 `6 indices × 172 instances` 进行贴图驱动的屏幕相关材质绘制，还有一组写入 2048² 的 R32 深度目标。

但目前证据**不足以确认游戏对象就是瀑布**，也不足以确认 2048² 深度目标是级联阴影图。本文保留“瀑布候选”作为场景观察假设，并把可复核事实与对象级推断严格分开。

| 层级 | 结论 |
|---|---|
| 已确认 | 多个高实例 `DrawIndexedInstanced`，跨深度和主 5-RT 几何阶段出现；管线使用 per-instance 数据、纹理资源及 D3D12 VS/PS。 |
| 强候选 | `6 × 172` 是小几何、高实例、贴图驱动效果层，形态上符合粒子、贴片或其他高频实例材质。 |
| 未确认 | 该组绘制是否为瀑布/水花；小几何是否 camera-facing；2048² R32 是否为 CSM；各 RT 的具体材质语义。 |

---

## 2. 证据标准

| 等级 | 含义 |
|---|---|
| A | RenderDoc MCP 对当前 capture 的直接返回：event、draw 参数、绑定输出、资源规格、shader 绑定。 |
| B | 基于 A 的透明计算，如索引提交量（`indices × instances`）。 |
| C | 有渲染模式支撑但尚未通过 mesh、纹理预览、pixel history、常量或 shader 语义确认的对象解释。 |

> `num_indices × num_instances` 是**索引提交量**，不是唯一顶点数，也不能直接换算 GPU 耗时。只有确认 topology 为 triangle list 后，才能将 indices/3 解释为三角形数量。

---

## 3. 帧内候选链路

### 3.1 可确认的 marker 顺序

```text
Depth-only Pass #2 (12273)
  ├─ 1536 × 23 / 45 / 5
  └─ 279 × 217 / 58

Colour Pass #2 (5 Targets + Depth, 12274)
  ├─ event 8140: 654 × 21
  └─ event 9104: 6 × 172

Depth-only Pass #11 (12290)
  └─ event 10378: 384 × 346 → depth target 28494
```

这些 marker 在 RenderDoc 返回中按上述顺序出现。它并不证明三组 draw 是同一对象：它们需要有相同/相关的 mesh、instance buffer、shader 参数、资源名或像素可见区域，才能形成对象身份链路。

### 3.2 高实例 draw 清单

| 阶段 | Event | Draw 参数 | 已知输出/绑定 | 等级 | 可以说什么 |
|---|---:|---:|---|---:|---|
| Depth-only #2 | 7858 | 1536 × 23 | 深度阶段 | A | 实例化几何 draw。 |
| Depth-only #2 | 7866 | 1536 × 45 | 深度阶段 | A | 同索引数的另一实例批次。 |
| Depth-only #2 | 7874 | 1536 × 5 | 深度阶段 | A | 同索引数的小实例批次。 |
| Depth-only #2 | 8080 | 279 × 217 | 深度阶段 | A | 高实例 indexed draw。VS 绑定 `InstanceData` 纹理及实例常量。 |
| Depth-only #2 | 8087 | 279 × 58 | 深度阶段 | A | 与 event 8080 同索引规模的另一批次。 |
| Colour #2 | 8140 | 654 × 21 | 5 RT + `28489` | A | 实例化材质几何，PS 有 wet-layer/normal/texture-set 绑定。 |
| Colour #2 | 9104 | 6 × 172 | 5 RT + `28489` | A | 小索引高实例效果候选，PS 读取深度和多张贴图。 |
| Depth-only #11 | 10378 | 384 × 346 | `28494` | A | 高实例深度 draw。 |

### 3.3 索引提交量（仅辅助规模比较）

| Event | 计算 | 索引提交量 |
|---:|---:|---:|
| 7866 | 1,536 × 45 | 69,120 |
| 8080 | 279 × 217 | 60,543 |
| 8140 | 654 × 21 | 13,734 |
| 9104 | 6 × 172 | 1,032 |
| 10378 | 384 × 346 | 132,864 |

`10378` 的索引提交量最高，但这仍不能说明它耗时最高：顶点处理、覆盖率、像素 shader、深度状态、缓存、队列和 GPU 时间均未测得。

---

## 4. 主 5-RT 几何阶段：已知事实

`Colour Pass #2 (5 Targets + Depth)` 的 marker 为 `12274`，共有 118 个子 Draw。event `8140` 与 event `9104` 都确认输出到：

```text
RT0 28484  R8G8B8A8_SRGB       3840×2160
RT1 28483  R11G11B10_FLOAT     3840×2160
RT2 28481  R16G16_UNORM        3840×2160
RT3 28482  R16G16B16A16_FLOAT  3840×2160
RT4 28485  R8G8B8A8_UNORM      3840×2160
Depth 28489 D32S8_TYPELESS     3840×2160
```

这能确认两者在同一组五色输出与主深度上执行；**不能**确认每个 RT 的语义、每个像素均被写入，或这些 draw 是延迟 PBR 路径中的何种材质。资源容量总和约为 253.2 MiB，是静态未压缩容量，不是实测写带宽。

---

## 5. 关键候选 draw 的管线证据

### 5.1 event 8140：实例化材质几何

| 项目 | 直接观察 |
|---|---|
| Draw | `DrawIndexedInstanced`, 654 indices × 21 instances |
| VS | 读取 `ScratchResource_Upload`，使用 per-frame/per-view/per-instance 常量。 |
| PS | 绑定 `Layer_Wet_BuildingBlock_inSampler0`、BC5 normal 候选、texture set（color/alpha/AO/roughness/reflectance/translucency）资源。 |
| 输出 | 主 5 RT 与 `28489` 深度。 |

“Wet BuildingBlock”是 RenderDoc 反射得到的资源名，表明该材质具备湿润层/建筑块命名线索；它不等于瀑布，也不应据此命名场景对象。较稳妥的描述是：**带湿润层材质资源的实例化表面几何**。

### 5.2 event 9104：小几何高实例效果候选

| 项目 | 直接观察 |
|---|---|
| Draw | `DrawIndexedInstanced`, 6 indices × 172 instances |
| VS | 读取 `ScratchResource_Upload`，有 per-instance 常量。 |
| PS | 读取 `28489` 主深度两次、BC7 texture array、BC4、BC7 SRGB 与 RGBA8 纹理；有 per-view/per-instance 常量。 |
| 输出 | 主 5 RT 与 `28489` 深度。 |
| Shader | D3D12 PS resource `37916`；可获取 `ps_5_1` 反汇编。 |

在常见 triangle-list 拓扑**前提**下，6 indices 对应两个三角形；再结合 172 instances，属于高度符合贴片/粒子/植被卡片等模式的候选。由于本次 MCP 返回的 draw detail 没有 topology 字段，也没有 mesh/像素验证，不能确认为公告板、更不能确认它是水雾。

### 5.3 event 10378：2048² R32 深度目标

| 项目 | 直接观察 |
|---|---|
| Draw | `DrawIndexedInstanced`, 384 indices × 346 instances |
| 输出 | 无颜色输出，深度输出 `28494` |
| `28494` | 2048×2048, `R32_TYPELESS`, 16 MiB |
| VS | `ScratchResource_Upload` + `InstanceData`（512² R16） + per-instance constants |

该模式支持“实例化对象进入独立深度渲染”的判断。`28493` 也是同规格 R32 资源，但本次复核的 `Depth-only Pass #10` 并未找到此前报告声称的同一 `384 × 346` 绘制；所以“两个级联对相同物体各渲染一次”没有得到复核支持。

---

## 6. 被撤销或降级的旧结论

| 旧表述 | 当前处理 | 原因 |
|---|---|---|
| 确认是瀑布主体、水面、泡沫与水雾 | 降为 C 级场景假设 | 缺少 marker 名、mesh、纹理预览、像素可见范围和 shader 语义。 |
| `6 × 172` 是相机朝向公告板 | 降为候选 | 索引数不保证 topology，且实例朝向未验证。 |
| `384 × 346` 在两张图重复，是 Dual CSM | 撤销 | 当前 `Depth-only #10` 清单与旧 event 编号不一致。 |
| event `8947` 等属于 Colour Pass #4 瀑布第二轮 | 撤销 | 当前 `Colour Pass #4` 实际事件为 `10653`–`10697`，且均单实例。 |
| 总顶点负载约 12 万+ | 改为索引提交量 | 缺少 topology、索引重用和实际顶点着色调用信息。 |

---

## 7. 将“瀑布候选”提升为确认对象的验证路径

1. **定位画面区域**：在 RenderDoc 中查看 event `8140`、`9104` 与 `10378` 的 mesh 输出、texture viewer 和 pixel history；确认是否覆盖瀑布区域。
2. **确认 topology 与实例朝向**：导出 mesh，查看 primitive topology、顶点位置与 instance transforms；再判断 `9104` 是否为 quad billboard。
3. **检查 shader 反汇编和常量**：搜索 PS 中对深度、UV、法线、flow/noise、alpha discard 的访问；修复 `GetConstantBuffer` 解析后读取材质常量。
4. **跟踪 `28493/28494` 的读者**：从资源使用图或后续 pipeline 中确认是否被光照 pass 以 shadow-map 方式采样，并读取 light-space 常量，才可确认 CSM。
5. **获得带 GPU counters 的重抓帧**：对上述 events 记录 GPU duration、overdraw 与像素覆盖，才可比较其真实性能开销。

---

## 8. 当前可用于技术讨论的表述

> frame55458 包含多批高实例化的 indexed geometry。至少一批在 5 个 4K 色目标和主深度上执行，另一批以 `6 × 172` 的小几何高实例模式读取深度与多张贴图，还有一批以 `384 × 346` 写入 2048² R32 深度目标。它们在渲染模式上可能与瀑布或相关效果有关，但对象身份、公告板朝向与 CSM 关系尚未通过 mesh、纹理、shader 常量和资源读取关系验证。
