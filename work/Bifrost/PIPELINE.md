# Bifrost · PIPELINE（技术方案）

> **本文件定位**：技术实现方案（恒星 · 天象 · 铁磁流体 · MCP 量产 · 跑图规模化生产）。**周计划 / 依赖 / 交付基线全在 `ROADMAP.md`**，本文件不复述。
> **前提锁定**：D1=等离子恒星驱动天气 · D2=冷神性 · D3=A 方案·轮廓局部化 · 主机位⑤（S3 段最优截图点）· UE5.8 · FluidFlux 已复刻 · 第三人称跑图 diorama（200m 单向海滩走廊）。

---

## §1 分层架构（基底必做 · 点缀增量）

| 层 | 内容 | 交付节点 |
|---|---|---|
| 🟦 **基底** | 4 段海滩走廊全通（§5.5）+ 恒星（§2）+ FluidFlux 海面 + L1 量产（§5）+ 恒星光衍生（god-rays / 大气散射 / 体积云 §3）+ LookDev 冷神性调色 | W3 末保底成片（可跑通版） |
| 🟨 **点缀（因果链完整性）** | 铁磁流体尖刺（§4，S3 段焦点）+ 极光（§3，S3 天空） | W4 目标成片 |
| 🟨 **点缀（增量氛围）** | 分色三选一 / 沙雪 / 鸟群 | 有余力 |

> **07-07 修正**：体积云从点缀升到基底（因果链保底 2 支之一）。分色三选一的性质是"未拍板要不要做"（非"决定要做但选哪个"）。**07-07 场景重构**：跑图 diorama 硬约束——基底成片必须能第三人称跑通 200m，跑不通视觉再好也不算保底达成。

---

## §2 等离子恒星（A 方案·轮廓局部化）

材质三层堆（详情与拍板理由见 `D3-KERNEL.md` §2）：

1. **本体表面**：大球 mesh + 多层 3D 噪声（domain warp）+ 时间演化；emissive 冷白核心 → icy cyan 边缘梯度。
2. **边缘 isosurface**（A 方案核心）：仅在轮廓 / 日珥弧处叠真 marching cubes，做融合翻涌立体感。
3. **光源**：驱动方向光 + 大范围光 + 大气散射，真实照亮海岸。

**关键控制**：守 D2 冷神性——核心可过曝但保住 pale azure → icy cyan 梯度，勿糊成纯白。

**跑图机位下的注意点**：玩家在 S1-S4 移动过程中恒星始终在视野内，isosurface 局部化在不同角度下的表现需在 W3 走位测试中验证（不能只测 S3 主机位）。

---

## §3 天象体积框架

统一走一套 raymarching 体积框架（一套框架喂多种介质）：

| 天象 | 做法 | 层 | 顺序 |
|---|---|---|---|
| **体积云 / 贝母云** | raymarch + 3D 噪声密度场，恒星光穿透散射 | 🟦 基底 | W3 先做（保底） |
| **god-rays / 大气散射** | 恒星光 + 体积雾自然产出 | 🟦 基底 | 恒星成型即出 |
| **极光** | 同框架，改沿磁力线分布的发射介质 + 冷绿/冷紫，S3 上空定点 | 🟨 点缀 | W4 |

**因果链收束**：恒星光 → 云散射 · 恒星磁场 → 极光 · 恒星磁场 → 海面尖刺（§4）。

---

## §4 铁磁流体融合（点缀 · 融视觉不融物理 · S3 焦点）

**核心认知**：铁磁流体的震撼全在"尖刺阵列"视觉签名，不在磁-流耦合物理。**只偷视觉、不搬物理**，挂 FluidFlux。**S3 段落地**：铁磁流体尖刺只在 S3 主锚点区局部生效，S1/S2/S4 是普通 FluidFlux 海面。

| 层级 | 做法 | 采用 |
|---|---|---|
| ① 表面材质层 | FluidFlux 主波形 + 材质叠"磁尖刺" displacement/法线，S3 段恒星磁场影响区局部规则尖刺 | ✅ 主力 |
| ② 局部 Niagara 点缀 | S3 恒星正下方磁极点放一小片真尖刺（Niagara + 局部高度场）当奇观焦点 | ✅ 焦点 |
| ③ 全海面真磁-流耦合 | 整片海铁磁流体求解 | ❌ 已排除 |

**收益**：保住"恒星磁场牵引海面长刺"因果链，绕开 R&D ★★★ 磁-流耦合；成本从 10-15 天赌一把降到 3-5 天可控。

---

## §5 场景布置 + MCP 量产管线（L1）

**围 4 段海滩走廊布局，S3 主锚点区精修，其余段基础质量**（详见 §5.5）。

1. **路径设计先行**：T-P0.0 顶视图手绘 200m 路径线 + 4 段边界 + 4 锚点，是所有布局的锚。
2. **构图 blockout 先行**：T-P0.1 4 段低精代摆资产 blockout，先锁跑通再做资产（避免返工）。验收颗粒度见 `ROADMAP.md` §5。
3. **kitbash 巨构**：岩石母材质 + 模块化遗迹件拼装。
4. **景深分层**：前景（人物剪影+近岩）/ 中景（巨构遗迹）/ 远景（恒星+天象），远景可低模。

### MCP 量产链路（Bifrost 作跨 P1+P3 代表作的 P3 展示物）

**引擎 MCP 栈**：UE5.8 官方 ModelContextProtocol 插件（端口 8000），非旧版 UEAgent（端口 9877，已作废）。
- **母材质生成**：定义参数面板规格（冷神性色域）→ 脚本批量建材质+MI 变体 → 人 LookDev 验收
- **资产摆放**：脚本批量 spawn/transform 远景 mesh、植被散布 → 人调构图
- **规范铁律**（UE MCP 操作规范）：每批生成必设 **batch tag + semantic tags + Outliner folder + cleanup 方案**，保证可回滚可清理

### AI 参与地编的能力边界（对齐 AIEffectFoundry 10 动作集）

**AI 能做**（对齐 `work/AIEffectFoundry/AIEffectFoundry_MCPStrategy.md` 第一版 10 动作集）：
- CreateMaterial · CreateMaterialInstance · SetMaterialParameter
- CreateBlueprintActor · AddComponent · ExposeParameter
- PlaceActor · CreateTestMap · TakeScreenshot · ExportLog
- 通过 `execute_python_script` 批量 `AddInstance` / `SpawnActor` / `SetTransform` 撒点

**AI 不做**（Slate 层交互或几何创作）：
- Landscape 笔刷雕刻 / Layer Paint（Slate 交互）
- PCG Graph 节点连线（Slate 交互）
- Foliage Tool 笔刷手刷（Slate 交互，但 Python `AddInstance` 可绕过）
- Mesh 几何建模（无 API，需外部工具如 Meshy/Rodin/Blender）
- Art Direction / LookDev / 审美判断

---

## §5.5 跑图规模化生产策略（07-07 新增）

200m 海滩单人不可能全手工做完，AI 参与是**可行性前提**而不仅是提效手段。

### 分段生产矩阵

| 段 | LookDev 精力 | AI 参与度 | 人参与度 |
|---|---|---|---|
| S1 远端（0-50m） | 15% | 批量摆位、材质挂载、截图验收 | 段过渡带、远景巨构比例 |
| S2 中景（50-120m） | 15% | 遗迹 kitbash 批量 spawn、材质变体 | 段内节奏、遗迹布局 |
| S3 主锚点区（120-160m） | **60%** | 基础摆位、点缀生成 | **主机位构图精修、LookDev 定稿、铁磁流体/极光美术判断** |
| S4 回望端（160-200m） | 10% | 批量摆位、快扫质量 | 段过渡带、结尾视觉收束 |

### 资产复用矩阵

淘 3-5 个 kitbash 包 · 每包 AI 生 20-50 个 Instance 变体：

| kitbash 包 | 来源 | AI 变体维度 | 用途段 |
|---|---|---|---|
| 岩石 | Fab / Megascans | rotation、scale、material variant | S1-S4 通用 |
| 遗迹 | Fab / Megascans | rotation、破损程度 material、组合方式 | S2-S3 主线 |
| 漂流物 / 贝壳藻类 | Fab / Megascans | rotation、cluster 密度 | S2-S4 前景细节 |
| 远景巨构 | Fab 或自建 | 低模、剪影强度 | S1-S4 远景 |
| 前景苔藓 / 石缝植物 | Fab 或 Megascans Foliage | Python `AddInstance` 撒点 | S3 前景（Foliage Tool 或 Python） |

### 材质规范化

3 张母材质 + N 张 MI 全部 AI 批量生成：
- **M_Sand** 沙滩母材质 · 冷神性色域 · 参数暴露：湿度、深浅、细节颗粒
- **M_Rock** 岩石母材质 · 破损程度、苔藓覆盖、湿度、颜色 tint
- **M_Ruin_Metal** 遗迹金属母材质 · 氧化程度、破损、发光 emissive（可选）

### 分级 LookDev 精力分配（守则）

**S3 先做完再铺其余**，避免每段都追求完美导致爆时间。W4 精力分配硬约束：

- 周一至周三：S3 精修（LookDev + 铁磁流体尖刺 + 极光）
- 周四：S1/S2/S4 快扫基础 LookDev
- 周五：走位测试 + 找补塌方角落

**塌方判定**：走位测试中每段截图 3 张，任一张观感明显低于 S3 水准即视为塌方，回滚重做该段基础 LookDev。

---

## §6 人 / AI 边界

| 层 | 谁主导 | 内容 |
|---|---|---|
| L1 量产 | **AI/MCP** | 母材质、kitbash、植被、远景摆放、参数脚手架、4 段批量摆位 |
| L2 审美 | **人** | 路径设计、4 段 blockout、S3 主锚点区 LookDev、调色、比例、最终把控 |
| L3 内核 | **人** | 恒星、天象、铁磁流体融合——审美强相关，人手调 |

---

## 维护
- 技术方案变更 → 更新本文件
- 周计划 / 交付基线 / 依赖顺序 → **不在此维护**，看 `ROADMAP.md`
- 与 `CONCEPT.md`（美术定案）· `D3-KERNEL.md`（恒星实现记录）· `ROADMAP.md`（执行主图）· `BACKLOG.md`（任务指针）互引
