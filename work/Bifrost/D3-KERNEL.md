# Bifrost · D3-KERNEL（前沿内核实现记录）

> **本文件定位**：D3 内核方案已定的落地记录（**非"待填骨架"**，选型已完成）。
> **前提锁定**：D1=等离子恒星驱动天气 · D2=冷神性 · UE5.8 · 主机位⑤ · 硬约束"内核只做 1 个"已于 07-06 松绑。
> **拍板日**：2026-07-06（选型），2026-07-07（落地记录成文）。

---

## §1 拍板结论

**D3 = A 方案·轮廓局部化**：恒星主体走纯材质假体积，仅在边缘轮廓 / 日珥弧处叠 dynamic mesh（复用 NS_Slime marching cubes）做真融合翻涌立体感。

**理由**：
- **性能可控**：整球 dynamic mesh（B/C 方案的极端）在近景主机位下屏占大 × 采样密，成本失控；A 方案让主体走"便宜的假体积"、只在最需要立体感的轮廓处付真 mesh 成本。
- **breakdown 价值保住**：marching cubes 融合表面仍是可拆解、可 flex 的技术点，只是从"整球"降为"轮廓"。
- **契合美术形态**：等离子恒星的视觉签名主要在边缘（日珥、翻涌的融合"舌"），主体表面允许假体积，与 D2 冷神性的雾化边缘处理天然吻合。

**否决 B/C 的原因**：
- **B 纯 shader 假体积**：完全没有真 mesh，"marching cubes 融合"这个 breakdown 卖点消失，Part 1 前沿内核叙事站不住。
- **C 转真体积（GaussianVolume）**：R&D 最厚（换栈+驱动天气链路重接），且内核身份从 isosurface 漂移到体积渲染，等于砸 D1 定案。作品集时间盒下不合算。

---

## §2 A 方案落地：材质三层堆

（与 `PIPELINE.md` §2 完全一致，此处只做 A 方案身份的技术拆解）

| 层 | 内容 | 成本 | 是否 A 方案独占 |
|---|---|---|---|
| **层 1 · 本体表面（主力）** | 大球 mesh + 自定义材质：多层 3D 噪声（domain warp）+ 时间演化；emissive 拉出冷白过曝核心 + icy cyan 边缘梯度 | 低 | 是（B 方案也用，A/B 共享底） |
| **层 2 · 边缘 isosurface 细节（A 方案核心）** | 复用 NS_Slime marching cubes，仅在**边缘轮廓 / 日珥弧**处叠真 dynamic mesh，做融合翻涌立体感 | 中（局部而非整球） | **A 方案独占** |
| **层 3 · 光源（因果链物理落点）** | 恒星驱动方向光 + 大范围光 + 大气散射，真实照亮整个海岸 | 低 | 是（三方案共通） |

**层 2 是 A 方案的技术身份**：既保 marching cubes 的 breakdown 价值，又不让整球吃 mesh 成本。

---

## §3 UE5.8 集成路径

- **NS_Slime 现有实现**：已在个人 UE study 工程 PreComputedGodRay 之外的模块中跑通 marching cubes / metaball 融合表面。可复用面：融合逻辑核 + Niagara Emitter 结构；已知坑：整球模式下 overdraw 直线拉高（正是走轮廓局部化的动因）。
- **"驱动天气"衍生效果的连接**：恒星光源（层 3）直接驱动方向光 + Volumetric Fog + 体积云（`PIPELINE.md` §3 raymarching 框架），**不需要额外自定义 Shading Model**。
- **UE5.8 自定义渲染的接入点**：光源走标准 Directional Light + Sky Atmosphere + Volumetric Cloud（自定义 raymarch 走 Post Process Material 或自定义 volume shader）。恒星本体材质走 Emissive/Unlit + 自定义 depth。层 2 的 marching cubes mesh 走 Niagara Mesh Renderer 或直接 Static Mesh。
- **MCP/Agent 介入边界**：L3 内核**全部人手调**（材质节点图 · 时间演化 · 冷神性色彩梯度 · 层 2 的 emitter 参数）；MCP 只负责 L1 量产（`PIPELINE.md` §5）。

---

## §4 成本 / 性能校准

**基调**：性能是"可管理性 note"，唯一底线"必须实时"（≥30fps 在个人办公机 RTX 3080 上）。价值排序 = breakdown 价值 / 技术亮点 > 画面说服力 > 性能。

**A 方案实测预期**（W2 恒星本体成型后回填实测数据）：
- 层 1 纯材质：预算 <1ms（与普通天空盒同量级）
- 层 2 轮廓 marching cubes：预算 2-4ms（局部化后可控，vs 整球方案 8-15ms）
- 层 3 光源 + 大气：预算 1-2ms
- 合计目标 ≤ 8ms（留出体积云 5-8ms + 场景其他 15ms 的余量）

> [!TODO] W2 恒星成型后回填实测数据，更新本节。

---

## §5 breakdown 规划

A 方案的核心 flex 点：**"我知道整球太贵，所以只让轮廓付真 mesh 成本，主体假体积——这是取舍不是妥协"**。

素材清单（W2-W3 产出时同步留）：
- **对比截图**：整球 vs 轮廓局部化的 overdraw 热图（证明性能取舍是主动选择）
- **层剥离**：层 1（纯材质）→ 层 1+2（加轮廓 mesh）→ 层 1+2+3（加光源）三档独立截图
- **参数演示视频**：域扭曲强度 / 时间演化速度 / emissive 梯度 / marching cubes 融合阈值的滑竿 demo
- **节点图**：材质图 + Niagara emitter 图
- **性能面板**：GPU Profiler 分层截图（对应 §4 数据）

---

## §6 拍板记录

- **2026-07-06 · 决策 D3 = A 方案**：详见 `LOG.md` 07-06 相关条目 + 本文件 §1。
- **2026-07-07 · 承认 PIPELINE §2 = A 方案落地**：审阅发现 PIPELINE.md 早已按 A 方案写实现，D3 记账未跟上，本文件由"待填骨架"改为落地记录。同步更新 `AI-BRIEF.md` D3 状态、`BACKLOG.md` D3 条目、`ROADMAP.md` 前提锁定。
