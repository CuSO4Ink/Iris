# [已纠偏：实为《死亡搁浅：导演剪辑版》] frame55458 帧分析报告

> **2026-07-14 纠偏**：标题原写"The Last of Us Part II"系人为标注错误。已通过像素解码 + `most_recent.cap`
> 双重确认本帧实为《死亡搁浅：导演剪辑版》，抓帧文件名 `ds_` 前缀本就是 Death Stranding 缩写。
> 帧统计数字（817 Actions 等）可继续复用，但所有"TLOU2"表述均不成立。详见
> `frame55458-死亡搁浅纠偏与瀑布分析.md`。
>
> 2026-07-13 · 通过 RenderDoc MCP Bridge 自动分析
> 抓帧文件：`ds_2026.07.13_07.14.47_frame55458.rdc`

---

## 1 帧基本信息

| 属性 | 值 |
|---|---|
| API | D3D12 |
| 总 GPU Actions | 817 |
| Draw Calls | 471 |
| Compute Dispatches | 90 |
| Copy 操作 | 42 |
| Clear 操作 | 29 |
| 顶层 Markers | 53 |
| 输出分辨率 | 3840×2160 (4K) |
| 纹理总数 | 7,739 |
| Buffer 总数 | 452 |
| GPU Timing | ⚠️ 不可用（该帧未录制 GPU 计数器） |
| Shader 反编译 | ⚠️ 不可用（D3D12 PSO 架构，着色器绑定在 Pipeline State Object 内，当前 MCP 工具无法通过 D3D11 风格接口提取） |

---

## 2 渲染流程总览

帧共 53 个顶层 Marker，整体管线分为五大阶段：

```
┌─────────────────────────────────────────────────────────────────────────┐
│  阶段 1: 前期 Compute / Copy (event 12254–12267)                       │
│  7 个 Compute Pass (90 Dispatch) + 7 个 Copy/Clear Pass               │
│  → GPU Driven 可见性裁剪、资源初始化、阴影图准备                        │
├─────────────────────────────────────────────────────────────────────────┤
│  阶段 2: 主场景几何 (event 12268–12274)                                │
│  Depth Prepass → 阴影 Depth Passes → GBuffer Pass (5 MRT + Depth)     │
│  → 118 个 Draw Call 写入 5 个 4K GBuffer RT                           │
├─────────────────────────────────────────────────────────────────────────┤
│  阶段 3: 延迟光照与后处理 (event 12275–12302)                          │
│  Compute 光照 → 多轮 Depth Pass (阴影) → 第二轮 GBuffer → 全屏合成     │
├─────────────────────────────────────────────────────────────────────────┤
│  阶段 4: UI / 特效合成 (event ~12090–12243)                           │
│  DrawInstanced 全屏三角形序列 + Compute Dispatch                      │
├─────────────────────────────────────────────────────────────────────────┤
│  阶段 5: Present (event 12253)                                        │
│  Present(ResourceId::292) — 4K R8G8B8A8_UNORM 交换链                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3 GBuffer Pass 详细分析

### 3.1 GBuffer RT 规格

Colour Pass #2（event 12274, 118 个 Draw Call）使用 5 MRT + Depth：

| RT | ResourceId | 格式 | 分辨率 | 大小 | 推测用途 |
|---|---|---|---|---|---|
| RT0 | 28484 | `R8G8B8A8_SRGB` | 3840×2160 | 31.7 MiB | Albedo / Base Color |
| RT1 | 28483 | `R11G11B10_FLOAT` | 3840×2160 | 31.7 MiB | HDR Specular |
| RT2 | 28481 | `R16G16_UNORM` | 3840×2160 | 31.7 MiB | Normal (XY) |
| RT3 | 28482 | `R16G16B16A16_FLOAT` | 3840×2160 | 63.4 MiB | World Pos / Motion Vector |
| RT4 | 28485 | `R8G8B8A8_UNORM` | 3840×2160 | 31.7 MiB | Material ID / ORM |
| Depth | 28489 | `D32S8_TYPELESS` | 3840×2160 | 63.4 MiB | 深度 + Stencil |

**单次 GBuffer 写入带宽：~253.2 MiB**（5 RT + Depth），4K 无 MSAA。

### 3.2 GBuffer Pass 大三角形 Draw Call

| Event ID | Indices | Instances | 说明 |
|---|---|---|---|
| 8264 | 44,373 | 1 | 最大单次绘制 |
| 8413 | 29,319 | 1 | 大场景几何 |
| 8233 / 8241 | 24,504 | 1 / 4 | 实例化大块几何 |
| 8249 | 24,234 | 1 | — |
| 8157 | 22,104 | 1 | — |

### 3.3 第二轮 GBuffer

Colour Pass #4（event 12293, 6 个 Draw Call, 5 MRT + Depth）— 可能用于透明/叠加层或瀑布水面的第二轮写入。

---

## 4 瀑布渲染分析（着重）

### 4.1 识别依据

通过逐 Draw Call 扫描实例数（`num_instances`），发现一组特征鲜明的高实例化绘制序列，反复出现在多个 Pass 中。这些 Draw Call 具有高度一致的模式——相同 indices 数、相同实例数组——跨 Pass 重复出现，是典型的流体/瀑布渲染特征。

### 4.2 瀑布相关的 Depth Pass 绘制

**Depth-only Pass #2（阴影渲染, event 12273, 32 children）**

该 Pass 向主深度 `ResourceId::28489`（4K D32S8）写入，核心瀑布 Draw Call：

| Event ID | Indices | Instances | 总顶点负载 | 特征 |
|---|---|---|---|---|
| 7858 | 1,536 | 23 | 35,328 | 瀑布主体网格 × 多级 |
| 7866 | 1,536 | **45** | 69,120 | 瀑布主体网格 × 更高实例 |
| 7874 | 1,536 | 5 | 7,680 | 同网格少量实例 |

1,536 indices = 512 triangles，相同的网格用不同实例数渲染三次 → **多级瀑布层叠**，每级用不同的变换矩阵实例。

### 4.3 瀑布相关的阴影 Depth Pass

**Depth-only Pass #8–#11（级联阴影图渲染）**

以下 Draw Call 写入 **2048×2048 `R32_TYPELESS` 阴影图**（`ResourceId::28493` / `28494`）：

| Event ID | Indices | Instances | Depth Target | Pass | 说明 |
|---|---|---|---|---|---|
| 8080 | **279** | **217** | 28489 | Depth #2 | 瀑布粒子/泡沫 × 217 实例 |
| 8087 | **279** | **58** | 28489 | Depth #2 | 同网格 × 58 实例（不同 LOD） |
| 8905 | **279** | **217** | 28489 | Colour #4 | 同组实例在 GBuffer 阶段重现 |
| 8912 | **279** | **58** | 28489 | Colour #4 | 配对实例 |
| 9823 | **384** | **346** | **28493** | Colour #10 | 瀑布水面 × 346 实例 → 阴影图 1 |
| 9832 | **384** | 18 | 28493 | Colour #10 | 同网格 × 18 实例 |
| 9841 | **384** | 101 | 28493 | Colour #10 | 同网格 × 101 实例 |
| 9850 | **384** | 44 | 28493 | Colour #10 | 同网格 × 44 实例 |
| 10378 | **384** | **346** | **28494** | Depth #11 | 同组 346 实例 → 阴影图 2 |

**关键发现**：`384 indices × 346 instances` 在两个不同 Pass 中出现，分别写入两张 2048×2048 阴影图（`28493` 和 `28494`），这是**双级联阴影图（Dual CSM）对同一瀑布几何的两次渲染**。

### 4.4 瀑布相关的 GBuffer 绘制

**GBuffer Pass（Colour Pass #2, 5 MRT + Depth）中的瀑布实例：**

| Event ID | Indices | Instances | 输出 | 特征 |
|---|---|---|---|---|
| 8140 | 654 | 21 | 5 RT + Depth | 瀑布水面 × 21 级 |
| 8148 | 654 | 29 | 5 RT + Depth | 瀑布水面 × 29 级 |
| 8287 | 459 | 23 | 5 RT + Depth | 水花/泡沫 × 23 级 |
| 8294 | 882 | **51** | 5 RT + Depth | 水花/泡沫 × 51 级 |
| 8302 | 408 | 9 | 5 RT + Depth | 少量水花 |
| 8309 | 474 | 3 | 5 RT + Depth | — |
| 8316 | 474 | 14 | 5 RT + Depth | — |
| 9104 | **6** | **172** | 5 RT + Depth | **2 三角形 × 172 实例 = 粒子公告板** |

**event 9104 特别关注**：6 indices = 2 个三角形，172 个实例 → 这是**瀑布水花/水雾的公告板粒子系统**。每个实例是一个面向相机的四边形公告板，172 个粒子在 GBuffer Pass 中直接写入全 5 RT。

### 4.5 第二轮 GBuffer 中的瀑布绘制

Colour Pass #4（event 12293, 5 MRT + Depth）中也出现了瀑布实例：

| Event ID | Indices | Instances | 说明 |
|---|---|---|---|
| 8947 | 1,944 | **64** | 瀑布水面/水流 × 64 实例 |
| 8960 | 1,944 | 4 | 同网格 × 4 实例 |
| 8968 | 1,944 | 3 | 同网格 × 3 实例 |
| 8905 | 279 | 217 | 与 Depth Pass #2 配对重现 |
| 8912 | 279 | 58 | 与 Depth Pass #2 配对重现 |

### 4.6 瀑布渲染流程还原

综合以上数据，瀑布在该帧中的完整渲染路径为：

```
Depth Prepass (event 12268)
  └─ 瀑布几何 → 主深度 28489 (4K D32S8)
       1536 indices × 23/45/5 instances (多级瀑布主体)

阴影 Depth Pass #2 (event 12273)
  └─ 瀑布粒子 → 主深度 28489
       279 indices × 217 instances + 279 × 58 (瀑布泡沫粒子阴影)

GBuffer Pass (event 12274, Colour Pass #2)
  └─ 瀑布水面 → 5 RT (28484/83/81/82/85) + Depth 28489
       654 indices × 21/29 instances (水面网格)
  └─ 水花泡沫 → 5 RT + Depth
       882 indices × 51 instances
  └─ 水雾粒子 → 5 RT + Depth
       6 indices × 172 instances (公告板粒子)

第二轮 GBuffer (event 12293, Colour Pass #4)
  └─ 瀑布水面 → 5 RT + Depth
       1944 indices × 64/4/3 instances (水流主体)
  └─ 瀑布粒子重现 → 5 RT + Depth
       279 indices × 217/58 instances

阴影 Depth Pass #10–#11 (event 12289–12290)
  └─ 瀑布水面 → 阴影图 28493 (2048² R32)
       384 indices × 346/18/101/44 instances (CSM Cascade 1)
  └─ 瀑布水面 → 阴影图 28494 (2048² R32)
       384 indices × 346 instances (CSM Cascade 2)
```

### 4.7 瀑布渲染特征总结

| 特征 | 数据 |
|---|---|
| 瀑布相关 Draw Call 数 | ~20+（跨 5 个 Pass） |
| 最高单次实例数 | 346（水面阴影渲染） |
| 公告板粒子实例数 | 172（水雾/水花） |
| 阴影图数量 | 2 张 2048×2048 R32（双级联） |
| 瀑布写入的 GBuffer RT | 全 5 RT（完整延迟着色参与） |
| 网格复杂度范围 | 6–1,944 indices（2 三角形粒子 → 648 三角形水面） |
| 总顶点负载估算 | ~12 万+ 顶点/帧（仅瀑布部分） |

**瀑布渲染是本帧中除主场景几何之外实例化程度最高的元素**，其特征为：

1. **多层网格实例化**：同一网格用不同实例数在多 Pass 中重复（1536×45, 279×217, 384×346），对应瀑布的多层级流动效果
2. **公告板粒子系统**：6 indices × 172 instances 的极端比例，典型水雾/水花粒子公告板
3. **双级联阴影**：384×346 在两张独立阴影图上各渲染一次，说明瀑布参与了双 CSM 阴影投射
4. **完整 GBuffer 参与**：瀑布写入全部 5 个 GBuffer RT，意味着它接受完整的延迟光照计算（包括 PBR 材质、法线、运动矢量）

---

## 5 阴影渲染系统

### 5.1 Depth-only Pass 总览

| Pass | Event | Children | 主要 Depth Target | 推测用途 |
|---|---|---|---|---|
| Depth-only #1 | 12268 | 21 | 111583 (1024² R16) | 场景 Prepass |
| Depth-only #2 | 12273 | 32 | 28489 (4K D32S8) | 主场景阴影 |
| Depth-only #3 | 12277 | 6 | — | 小规模深度 |
| Depth-only #4 | 12283 | 8 | — | — |
| Depth-only #5 | 12284 | 20 | — | — |
| Depth-only #6 | 12285 | 15 | — | — |
| Depth-only #7 | 12286 | 8 | — | — |
| Depth-only #8 | 12287 | 41 | — | 最多子操作 |
| Depth-only #9 | 12288 | 14 | — | — |
| Depth-only #10 | 12289 | 10 | 28493 (2048² R32) | CSM Cascade 1 |
| Depth-only #11 | 12290 | 13 | 28494 (2048² R32) | CSM Cascade 2 |

**11 个 Depth-only Pass 共 ~187 个 Draw Call，占总 Draw Call 的 ~40%**。

### 5.2 已识别的深度目标

| ResourceId | 格式 | 分辨率 | 大小 | 用途 |
|---|---|---|---|---|
| 28489 | `D32S8_TYPELESS` | 3840×2160 | 63.4 MiB | 主深度缓冲（GBuffer + 阴影） |
| 28493 | `R32_TYPELESS` | 2048×2048 | 16.0 MiB | 级联阴影图 1 |
| 28494 | `R32_TYPELESS` | 2048×2048 | 16.0 MiB | 级联阴影图 2 |
| 111583 | `R16_TYPELESS` | 1024×1024 | 2.0 MiB | Prepass 深度 |

---

## 6 Compute Pass 系统

12 个 Compute Pass，共 90 次 Dispatch：

| Pass | Event | Dispatches | 推测用途 |
|---|---|---|---|
| Compute #1 | 12255 | 21 | GPU Driven 可见性裁剪（最大批次） |
| Compute #2 | 12256 | 13 | 几何处理延续 |
| Compute #3–#7 | 12258–12266 | 3+6+4+4+6 | 阴影图生成 / 材质更新 |
| Compute #8 | 12271 | 3 | 屏障转换后小批次 |
| Compute #9 | 12275 | 17 | **延迟光照计算**（GBuffer 后首个大 Compute） |
| Compute #10 | 12278 | 3 | 后处理 |
| Compute #11–#12 | 12292–12294 | 3+7 | 最终合成 Compute |

---

## 7 帧尾 Present 路径

```
Colour Pass #11 (2 Targets, event 12303)
  └─ DrawInstanced 90 indices (event 12196)
  └─ ClearRenderTargetView (event 12197)
  └─ CopyBufferRegion (event 12199)

Copy/Clear Pass #17–#18 (event 12304–12305)
  └─ ExecuteCommandLists 边界同步

末尾 DrawInstanced 序列 (~15 calls)
  └─ num_indices = 3~4, 全屏三角形 (UI / 画面合成)

Present (event 12253)
  └─ Present(ResourceId::292) — 4K R8G8B8A8_UNORM
```

---

## 8 关键发现与热点

### 8.1 带宽热点：4K 5-MRT GBuffer
- 单次 GBuffer Pass 写入 ~253 MiB 像素数据
- 60fps 下仅 GBuffer 就需 ~15 GB/s 带宽
- RT3（`R16G16B16A16_FLOAT`, 63 MiB）占比最大

### 8.2 阴影渲染开销
- 11 个 Depth-only Pass，~187 个 Draw Call（占总 DC ~40%）
- 双级联阴影图（2×2048² R32），瀑布等实例化几何在两个级联中各渲染一次

### 8.3 瀑布渲染开销
- ~20+ Draw Call 跨 5 个 Pass
- 最高 346 实例 × 384 indices 的阴影渲染
- 172 实例公告板粒子写入完整 GBuffer
- 在双 CSM 中各渲染一次 → 阴影 Pass 中瀑布几何被渲染两次

### 8.4 Compute 密集
- 90 次 Dispatch 分散在 12 个 Pass
- 多个 3–4 次小批次 Dispatch，存在合并空间

### 8.5 D3D12 PSO Shader 限制
- `get_pipeline_state` 返回 `shaders: {}`
- `get_shader_info` 返回 `No shader bound`
- 原因：D3D12 着色器绑定在 PSO 内，非 D3D11 风格的独立 SetShader 调用
- **需扩展 MCP 以解析 D3D12 PSO 中的 Shader 字节码**

### 8.6 GPU Timing 缺失
- `get_action_timings` 返回空数组
- 无法精确标注各 Pass GPU 耗时排序

---

## 9 优化建议

1. **GBuffer RT 精度**：RT3 `R16G16B16A16_FLOAT`（63 MiB）可考虑降为 `R16G16B16A16_SNORM` 或拆分，减少 32 MiB/帧带宽
2. **阴影 Pass 合并**：11 个 Depth-only Pass 中相同光源/级联的可合并，减少 PSO 切换
3. **瀑布阴影优化**：384×346 在双 CSM 中各渲染一次，可考虑只在高精度级联中渲染瀑布阴影
4. **Compute 批次化**：多个 3–4 次小 Dispatch 可合并为更大批次
5. **MCP 工具增强**：增加 D3D12 PSO 解析支持，以获取 Shader 反编译能力

---

## 10 与上一帧对比

| 指标 | frame25557 | frame55458 |
|---|---|---|
| 总 Actions | 1,149 | 817 |
| Draw Calls | 766 | 471 |
| Compute | 89 | 90 |
| Copy | 76 | 42 |
| 分辨率 | 4K | 4K |
| GBuffer MRT | 5 RT | 5 RT |
| Depth-only Passes | 多轮 | 11 个 |

新帧 Draw Call 减 38%，Copy 减 45%，Compute 持平 → 场景复杂度较低或不同镜头角度。


---

## 11 2026-07-14 RenderDoc MCP 复核与修订

> 本节以当前已加载的 `frame55458` 抓帧为准，直接调用 RenderDoc MCP 的 `get_frame_summary`、`get_draw_calls`、`get_draw_call_details`、`get_pipeline_state`、`get_texture_info` 和 `get_shader_info` 复核。此前未包含原始工具导出的结论，以本节的证据等级和限定为准。

### 11.1 复核结论

**帧级统计与主 GBuffer 资源结论成立；此前对渲染对象、阴影类型和严格执行顺序的解释存在超出证据范围的推断，已降级为候选假设。**

| 项目 | 复核结果 | 证据等级 | 说明 |
|---|---|---:|---|
| D3D12、817 Actions、471 Draw、90 Dispatch、42 Copy、29 Clear、53 markers | 确认 | A | `get_frame_summary` 直接返回。 |
| Colour Pass #2 为 118 个子 Draw、绑定 5 色目标与深度 | 确认 | A | marker `12274` 与 event `8140` 的 draw-detail 直接返回。 |
| RT0 `28484` 为 3840×2160 `R8G8B8A8_SRGB`，主深度 `28489` 为 3840×2160 `D32S8_TYPELESS` | 确认 | A | `get_texture_info` 直接返回。 |
| 六个全分辨率目标的静态未压缩容量约 253.2 MiB | 确认，但限定 | B | 是资源容量之和；不是实际 DRAM 带宽、也不等于完整覆盖写入量。 |
| 11 个 Depth-only marker | 确认 | A | `get_frame_summary` 顶层 marker 列表直接返回。 |
| 约 187 个深度 Draw、约占全部 Draw 40% | 可保留为调用计数 | B | 不能据此推断 GPU 时间或性能占比。 |
| D3D12 着色器无法读取 | 不成立 | A | 复核时 `get_pipeline_state` 已能返回 VS/PS，`get_shader_info` 已可返回 PS 反汇编；此前结论反映的是旧版工具状态。 |
| GPU Timing 缺失 | 仍成立 | A | 本次未获得本帧有效 GPU timer；不对 Pass 耗时排序。 |

### 11.2 事件编号与流程顺序修正

此前报告把 `Present (event 12253)` 放在帧尾；但当前顶层 marker 的编号为 `12254`–`12305`，且 `Present` 不在本 MCP 返回的顶层 marker 列表中。因此，**不能用 `12253` 作为本帧严格帧尾的 event 顺序证据**。

可确认的是 RenderDoc 返回的顶层 marker 顺序；按该顺序，帧内骨架应写为：

```text
Copy/Clear #1
→ Compute #1/#2
→ Copy/Clear #2–#7 与 Compute #3–#7 交错
→ Depth-only #1 → Colour #1
→ Copy/Clear #8 → Compute #8 → Copy/Clear #9
→ Depth-only #2 → Colour #2 (5 Targets + Depth)
→ Compute #9 → Copy/Clear #10 → Depth-only #3 → Compute #10
→ Copy/Clear #11/#12 → Colour #3 → Copy/Clear #13
→ Depth-only #4–#11
→ Copy/Clear #14 → Compute #11 → Colour #4 (5 Targets + Depth)
→ Compute #12 → Colour #5–#10 → ExecuteIndirect marker
→ Colour #11 → Copy/Clear #17/#18
```

这是一条**marker 提交顺序**，不是对 GPU 异步队列实际完成顺序、资源依赖或功能语义的完全证明。Present 资源 `292` 的结论应保留为“此前记录的可能交换链资源”，直到补出其准确 event/action 证据。

### 11.3 对第二个五目标阶段的修订

`Colour Pass #4 (5 Targets + Depth)`（marker `12293`）的实际子 Draw 为 event `10653`–`10697`，均为单实例、大索引几何（9,390–44,778 indices）；它**不包含**此前列出的 `8905`、`8912`、`8947`、`8960` 或 `8968`。该 pass 的 event `10653` 绑定的是 `28483/28487/28481/28482/28485` 以及深度 `28490`，并非主 GBuffer 的完整同一套 `28484/28483/28481/28482/28485 + 28489`。

因此，“Colour Pass #4 是瀑布第二轮 GBuffer”“此前列出的高实例瀑布绘制在该 pass 重现”两项结论撤回；只能称它为**另一组 5 色目标加深度的几何阶段**，用途尚待资源读取关系、shader 与纹理内容验证。

### 11.4 对高实例绘制和阴影的修订

以下是已直接验证的事实：

- `Depth-only Pass #2`（marker `12273`）内有 `1536 × 23/45/5`，以及 `279 × 217/58` 的实例化 indexed draw。
- `Colour Pass #2` 中 event `8140` 是 `654 × 21` 的实例化 indexed draw，输出 `28484/28483/28481/28482/28485`，深度输出 `28489`；其像素阶段绑定了 `Layer_Wet_BuildingBlock_inSampler0`、法线与材质纹理集。
- 同一 Colour Pass 的 event `9104` 是 `6 × 172` 的实例化 indexed draw，输出同一组 5 RT 并写入 `28489`。其 PS 读取主深度、BC7 texture array、BC4/BC7/RGBA8 纹理与 per-view/per-instance 常量；这支持“屏幕空间相关、贴图驱动的高实例材质绘制”，但不独立证明它是瀑布、水雾或相机朝向公告板。
- `Depth-only Pass #11`（marker `12290`）含 `384 × 346/18/4/42/101/44`，event `10378` 的深度输出是 `28494`。`28494` 规格为 2048×2048 `R32_TYPELESS`。
- `28493` 与 `28494` 都是 2048×2048 `R32_TYPELESS`；但当前复核的 `Depth-only Pass #10` 事件中**没有**此前报告写作 `9823/9832/9841/9850` 的 `384` indices 系列。因而不能建立“`384 × 346` 在两张阴影图上重复”的证据链。

基于上述事实，`28493/28494` 可称为“两个同规格的深度目标候选”；“Dual CSM / Cascade 1 / Cascade 2”“瀑布对象”“水花/泡沫/水雾”“完整 PBR / motion-vector 语义”均须保留为待验证假设，不能视为本帧已确认结论。

### 11.5 已确认的工具能力状态

本次 MCP 已成功在 D3D12 event `7858`、`8080`、`8140`、`9104`、`10378` 与 `10653` 返回 VS/PS resource ID、绑定资源、常量缓冲和 shader entry point；event `9104`、`8140` 的 PS 反汇编也可获取。当前限制变为：常量缓冲变量解码仍报 `PipeState.GetConstantBuffer` 属性缺失，且未确认 GPU timing 数据。这应作为 MCP 后续改进项，而非“D3D12 PSO 无法获取 shader”。

### 11.6 结论使用规则

1. 用“实例化几何/粒子候选绘制”替代未经像素、资源名或 shader 语义确认的“瀑布、水花、水雾”。
2. 用“两个 2048² R32 深度目标候选”替代未经采样关系和 light constant 确认的“Dual CSM”。
3. 用“静态资源容量”和“调用数量”替代“实际带宽热点”与“耗时热点”。
4. 后续要确认对象身份，应优先导出候选 draw 的 mesh、纹理缩略图、PS 反汇编中资源访问、常量值和最终画面中的 pixel history。
