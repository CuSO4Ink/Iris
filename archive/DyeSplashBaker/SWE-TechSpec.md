# DyeSplashBaker — SWE 烘焙方案技术文档

> 目标：用 **浅水方程 Level 2（带速度场的线性版）** 在 Niagara 里跑一段染料扩散，**烘焙成静态贴图序列**（核心是 Arrival Time Map），交给地面 DBuffer Decal 材质做最终视觉表现。
>
> 适用场景：坛子打破 → 染料铺地 → 在玩家眼前播放几秒扩散动画 → 稳定后留下永久痕迹。

---

## 1. 整体管线（从离线到运行时）

```
[离线烘焙阶段 / 编辑器内]                       [运行时 / 游戏中]
─────────────────────────────────────           ──────────────────────────
Niagara Emitter                                  Decal Actor
  └─ Scratch Pad (HLSL)                            └─ Material Instance
       ├─ Grid2D h  (高度 / 染料厚度)                    ├─ ArrivalTimeMap (静态)
       ├─ Grid2D vx (X 方向速度)                         ├─ FinalHeightMap (静态)
       └─ Grid2D vy (Y 方向速度)                         └─ Time 参数 (Material PSO)
            │                                            │
            ▼                                            ▼
  每 Tick 解一次 SWE Level 2                         材质里：
            │                                       float h = sample(FinalHeight)
            ▼                                              * smoothstep(t, t+fade, Time);
  收敛后导出：                                       Normal = ddx/ddy(h);
    • ArrivalTimeMap (R16f, 每像素首次到达时间)     Roughness/Color/Opacity 全部由 h 驱动
    • FinalHeightMap (R8/R16f, 稳态厚度)
    • [可选] FlowMap (RG8, 稳态时归一化的 vx/vy)
            │
            ▼
  Render Target → Static Texture（资产）
```

**关键理念**：
- **Niagara 只在编辑器跑一次**（或离线 Commandlet），不在运行时实时模拟。
- 运行时材质里**没有任何模拟**，只是用 `Time` 参数去采样烘焙出来的 `ArrivalTimeMap`，做 `smoothstep` 把扩散动画"播"出来。
- 所以最终成本 = **2~3 张静态贴图 + 1 个 Decal + 1 个材质**，性能等价普通贴花。

---

## 2. SWE Level 2 是什么

完整浅水方程（SWE）：

```
∂h/∂t  = −∇·(h·v)                               (质量守恒)
∂v/∂t  = −(v·∇)v − g·∇h − k·v + F/ρ              (动量守恒, 含对流/重力/阻尼/外力)
```

**Level 2 = 去掉非线性对流项** `(v·∇)v`，保留：
- 高度的**质量守恒**（这是流体感的主要来源，水会"流走"而不是凭空消失）
- 速度由**梯度**驱动（高的地方往低的地方流）
- **粘性阻尼** `k·v`（水会停下来）
- **外力 F**（坛子破碎瞬间给一个径向冲击）

为什么不上 Full SWE / NS：
- 对流项 `(v·∇)v` 会产生湍流和涡，染料贴花根本不需要
- 数值稳定性差很多，要 MacCormack / Semi-Lagrangian advection，HLSL 里写很重
- Level 2 已经能产生"中心隆起 → 向外铺开 → 边缘减速 → 收敛"的真实流体形态

---

## 3. Niagara 端实现细节

### 3.1 数据结构

| 资源 | 类型 | 用途 |
|---|---|---|
| `h` | Grid2D, R16f | 染料厚度 / 水位 |
| `vx` | Grid2D, R16f | X 方向速度（cell-centered） |
| `vy` | Grid2D, R16f | Y 方向速度 |
| `arrival` | Grid2D, R16f | 每像素**首次** h>阈值 时记录的 `SimulationTime` |

分辨率建议起步 **256×256**，物理域映射 1m×1m，则 `dx = 1/256 ≈ 3.9mm`。

### 3.2 单步求解（每个 Tick 在 Scratch Pad 里做）

```hlsl
// 伪代码 / 实际写在 Scratch Pad 里
float dt = DeltaTime / Substep;   // Substep 建议 4~8
for (int s = 0; s < Substep; s++)
{
    // 1) 用速度更新高度（质量守恒）
    //    ∂h/∂t = -∇·(h·v)  =>  中心差分
    float dhdt = -((h_right*vx_right - h_left*vx_left) / (2*dx)
                 + (h_up   *vy_up    - h_down*vy_down) / (2*dx));
    h_new = h + dhdt * dt;

    // 2) 用高度梯度更新速度
    //    ∂v/∂t = -g*∇h - k*v + F
    float dvxdt = -g * (h_right - h_left) / (2*dx) - k * vx + Fx;
    float dvydt = -g * (h_up    - h_down) / (2*dx) - k * vy + Fy;
    vx_new = vx + dvxdt * dt;
    vy_new = vy + dvydt * dt;

    // 3) 写回 Grid（双缓冲，Niagara Grid2D 自动支持 Previous/Current）
    h  = max(h_new, 0);   // 不能为负
    vx = vx_new;
    vy = vy_new;
}

// 4) 记录 Arrival Time
if (h > arrival_threshold && arrival[xy] < 0)
    arrival[xy] = SimulationTime;
```

### 3.3 关键参数（起步推荐值）

| 参数 | 值 | 说明 |
|---|---|---|
| `g` (重力等价系数) | 9.8 或调到 2~5 给艺术控制 | 越大扩散越快越平 |
| `k` (粘性阻尼) | 0.8~1.5 | 决定多快停下来 |
| `dt` | `1/60 / Substep` | 必须满足 CFL：`(sqrt(g*h_max) * dt / dx) < 0.5` |
| `Substep` | 4~8 | 不够会爆，过多浪费 |
| `arrival_threshold` | 0.01 | h 超过这个值视为染料"到达" |
| `Source` | 中心 1~3 个 cell 持续注入 N 帧 | 模拟坛子破碎初始"喷射" |

### 3.4 初始条件（坛子破碎瞬间）

不是直接给一个高度凸起，而是给：
- **h**：中心一个小高斯凸起（半径 3~5 cell，幅值 1.0）
- **vx, vy**：径向向外的速度场（强度 2~5 m/s，可加随机扰动）
- 持续 1~3 帧后停止源注入，让方程自己跑

这一步是流体感的灵魂——**有初速度的水才会"冲"出去再"摊"开**，纯靠重力扩散会很对称很无聊。

### 3.5 边界条件

**P0/P1 默认先用 Neumann 零梯度边界**（越界读取回退到本 cell，和 §10.2 代码一致），优点是实现最省事、便于先把 SWE 跑稳。
如果后面出现明显边缘回弹，再切到 **Dirichlet 边界**（边缘一圈 cell 强制 h=0, v=0）或加一圈 **Sponge Layer** 做吸收。

---

## 4. 烘焙导出阶段

### 4.1 触发时机

模拟跑到**收敛**（典型 3~6 秒，120~360 帧）时停止。判定收敛：
- 全图 `max(|v|) < 0.01`
- 或者固定跑 N 帧（编辑器内更可控）

### 4.2 三张产出贴图

| 贴图 | 通道 | 编码 | 用途 |
|---|---|---|---|
| **ArrivalTimeMap** | R16f | 直接存秒数（0~6.0） | 运行时驱动扩散动画 |
| **FinalHeightMap** | R16f or R8 | 归一化 0~1 | 稳态厚度，决定最终 Normal/Coverage |
| **FlowMap**（可选） | RG8 | (vx, vy) 归一化到 -1~1 后 *0.5+0.5 | 给染料表面做流向纹理 |

### 4.3 RT → Static Texture

Niagara Render Target 不能直接当资产，需要：
1. Blueprint / Editor Utility 调 `ExportRenderTarget` 或 `RenderTargetCreateStaticTexture2DEditorOnly`
2. 设置压缩格式：ArrivalTime 用 **HDR (RGBA16F)**，FinalHeight 用 **Grayscale**
3. **关闭 sRGB**、**关闭 Mip 自动生成**（高度场不要 Mip 模糊）
4. 保存为资产，Decal 材质引用

---

## 5. 运行时材质实现

### 5.1 核心节点逻辑

```hlsl
// 输入
float arrival = Texture2DSample(ArrivalTimeMap, UV).r;     // 这个像素的到达时间
float finalH  = Texture2DSample(FinalHeightMap, UV).r;     // 这个像素稳态厚度
float t       = MaterialTime - DecalSpawnTime;             // 自贴花生成以来的时间

// 1) 时间驱动的"擦除"动画
float fade   = 0.15;                                       // 边缘软度（秒）
float visible = smoothstep(arrival, arrival + fade, t);

// 2) 当前可见高度
float h = finalH * visible;

// 3) 法线 = h 的梯度（用 ddx/ddy 或者预算 NormalMap）
float3 N = normalize(float3(-ddx(h)*Strength, -ddy(h)*Strength, 1));

// 4) 视觉属性
float3 BaseColor = lerp(DryColor, WetColor, h);            // 越厚越湿
float  Roughness = lerp(GroundRough, 0.1, h);              // 染料区域反光
float  Opacity   = saturate(h * 4);                        // 软边缘
```

### 5.2 关键点

- **不需要 Material Time，需要的是"自该 Decal 出生以来的时间"**：用 `Per Instance Custom Data` 把 `SpawnTime` 写到 Decal Component，材质里 `Time - SpawnTime`。
- **`smoothstep(arrival, arrival+fade, t)` 就是动画核心**——所有像素共享一个 `t`，但每个像素的 `arrival` 不一样，所以扩散是"扫过去"而不是整张同时出现。
- 想要更柔的过渡，把 fade 加大；想要尖锐的"波前"，fade 调到 0.05。
- **法线一定从 `h` 算，不要从 `finalH` 算**，否则一开始就有完整凹凸感，看着是"贴纸瞬间出现"。

---

## 6. 实施分阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0** | Niagara 里搭好 Grid2D h/vx/vy 三通道 + 最简扩散方程，可视化 h | RT 上能看到中心凸起向外摊开，几秒后停下 |
| **P1** | 加初速度场 + 阻尼 + Source，调到"流体感" OK | 视觉上有"冲出去 → 摊开 → 停"的节奏，不再是均匀环 |
| **P2** | 加 ArrivalTimeMap 通道，模拟跑完后导出 RT 为静态贴图 | 工程里能拿到 3 张 .uasset |
| **P3** | 改造 Decal 材质，用 ArrivalTime + Time 驱动 smoothstep 播放 | 游戏运行时能看到一段流畅扩散动画，性能等价普通 Decal |
| **P4**（可选） | 加 FlowMap 让染料表面有流动纹理 / 加 Coffee Ring 边缘浓缩 | L4 视觉阶梯达成 |

---

## 7. 风险与降级方案

| 风险 | 表现 | 应对 |
|---|---|---|
| CFL 不满足 | h 出现 NaN / 棋盘格爆炸 | 降 dt 或加 Substep；加 `clamp(h, 0, 5)` |
| 收敛太慢 | 跑 10 秒还在动 | 提高 k 阻尼；或者强制 N 帧后截止 |
| 边界反射不自然 | 边缘出现回弹波 | 边界 cell 加额外阻尼层（Sponge Layer） |
| 烘焙贴图分辨率 256² 不够 | 贴在大面积地面上糊 | 提到 512²，烘焙耗时翻 4 倍但运行时无影响 |
| Niagara Grid2D Previous/Current 双缓冲写错 | 数值乱跳 | 用 `Previous Grid 2D Collection` 节点读 t-1，写 `Current` |

---

## 8. 我对方案的理解（请确认）

1. **目标**：把"几秒钟的染料扩散动画"做成可烘焙、可复用的资产，运行时零模拟成本。
2. **算法**：SWE Level 2（高度+速度，去对流），不是纯扩散方程，也不是 Full NS。
3. **核心产出**：ArrivalTimeMap（每像素到达时间）+ FinalHeightMap（稳态厚度）

> [!Q] 这个稳态厚度是做什么的？
> — v 2026-04-20

> [!A] FinalHeightMap（稳态厚度）= 染料最终停下来时每像素的厚度值，决定三件事：
> ① **覆盖范围**——h=0 的像素不画染料（`Opacity = saturate(h*4)`）
> ② **法线强度**——厚的地方凸起大，薄的地方平，靠 `ddx/ddy(h)` 算出 Normal
> ③ **视觉变化**——颜色/粗糙度随 h 渐变（越厚越深色越反光）
>
> 和 ArrivalTimeMap 的分工：
> - `ArrivalTime` → 时间维度（什么时候出现）
> - `FinalHeight` → 空间维度（出现多少、什么形状）
>
> 运行时合成：`h_now = FinalHeight * smoothstep(ArrivalTime, ArrivalTime+fade, t)`
> 翻译：这个像素最终会有多厚（FinalHeight），乘以它现在该出现多少了（smoothstep）。
> — ai 2026-04-20

4. **运行时驱动**：材质里 `smoothstep(arrival, arrival+fade, currentTime)` 当擦除遮罩。
5. **直接在 Niagara 里实现**，不做 Python 原型，你边写边改。
6. **不在运行时跑 Niagara**，只在编辑器烘焙一次。

如果哪一条理解错了或者你想调整范围（比如只做 P0~P2，不要运行时动画，只要稳态贴图），告诉我对应改方向。

---

## 9. 从 FloodStep v2 迁移到 SWE

> 原 FloodStep v2 方案全文已归档到 [[../../archive/FloodStep-v2-方案]]，本节只讲迁移策略。

### 9.1 三阶段 Scratch Pad 的映射关系

| 原方案 Stage | 新方案对应 | 动作 |
|---|---|---|
| **Stage 1 InitGrid**（种子点设 1.0） | **Stage 1 InitGrid**（种子处 h 高斯凸起 + 径向初速度 v） | 改数据：从 `GradientValue` 单通道 → `h/vx/vy` 三通道；种子从硬设 1.0 → 高斯分布；新增 v 径向速度 |
| **Stage 2 FloodStep**（max 传播 + Noise/Force 调制） | **Stage 2 SWESolve**（中心差分解 h 和 v） | 彻底替换：`max(邻居-step)` → 质量守恒 `∂h/∂t=-∇·(h·v)` + 动量方程 `∂v/∂t=-g·∇h-k·v` |
| **Stage 3 NormalizeGradient**（重映射+Gamma） | **Stage 3 Export**（写 ArrivalTime + 归一化 FinalHeight） | 保留归一化逻辑；新增 ArrivalTime 记录：`if (h > threshold && arrival<0) arrival = SimTime;` |

### 9.2 可复用的原代码片段

从 FloodStep 原码里直接搬过来的：

1. **种子 UV 距离判断**（Stage 1 开头那段）
   ```hlsl
   float2 CellUV = (float2(IndexX, IndexY) + 0.5) / float2(NumCellsX, NumCellsY);
   float Dist = length(CellUV - SeedCenter);
   ```
   SWE 里改成高斯：`h_init = exp(-Dist*Dist / (2*SeedRadius*SeedRadius))`

2. **Force 方向衰减模型**
   ```hlsl
   float ForceAttenuation = exp(-DistFromSeed * ForceDecay) * ForceStrength;
   ```
   直接用来算初速度场：`v_init = ForceDir * ForceAttenuation`

3. **8 邻域读取结构**（IndexX±1, IndexY±1 那一坨边界判断）
   SWE 的中心差分只需要 4 邻域，但边界判断套路完全一样，复制粘贴改名即可

4. **归一化 + Gamma**（Stage 3 尾部）——导出 FinalHeightMap 时完全复用

### 9.3 必须抛弃的部分

- ❌ **`max(邻居 - step)` 的 FloodStep 核心逻辑**——这是测地距离算法，和流体无关，整段删除
- ❌ **8 邻域方向 Noise 调制 `NMod_*`**——SWE 里噪声应该作用在速度场上（小扰动），不是作用在步长
- ❌ **8 邻域方向 Force 调制 `FMod_*`**——Force 改为在 Stage 1 初始化到 vx/vy，不每帧调
- ❌ **`ArcScale = 1.41421356` 对角修正**——SWE 只用正交邻居，对角距离问题不存在了

### 9.4 改造的顺序（和 §6 对齐）

- **P0 先换 Stage 2 的核心求解器**：把原 FloodStep Stage 2 整段注释掉，粘 §3.2 的 SWE 求解伪代码，编译跑通
- **P0 再改 Stage 1**：种子值从 1.0 改成高斯，加 vx/vy 初速度（复用 ForceAttenuation 模型）
- **P1 调参**：参数对齐 §3.3 表格，边调边看 RT 可视化
- **P2+ 按原 §6 阶段推进**

### 9.5 Grid2D Attribute 改动清单

原方案只有一个 Attribute：`GradientValue`。
新方案需要三个：

```
Grid2D Attributes:
  h        : float    (染料厚度 / 水位，替换原 GradientValue)
  vx       : float    (X 速度，新增)
  vy       : float    (Y 速度，新增)
  arrival  : float    (到达时间，P2 阶段加)
```

在 Niagara 的 Grid2D Collection 资产里手动加这三个 Attribute，原 `GradientValue` 可以删也可以保留（反正不再写入）。

> [!TODO] 把对应的三个阶段的 Niagara 的操作流程给我过一遍吧，包括 HLSL 的代码和输入输出参数流程
> — v 2026-04-20

> [!A] 已新增 §10《Niagara 三阶段实施手册》，完整覆盖：
> - §10.1 Stage 1 InitGrid — HLSL + Input Map + Execute Behavior
> - §10.2 Stage 2 SWESolve — HLSL + Input Map + Iteration Source
> - §10.3 Stage 3 Export — HLSL + Input Map + Arrival 写入时机
> - §10.4 Niagara Emitter 装配 checklist（Attributes / Simulation Stages / 双缓冲 / RT 输出）
>
> 每段 HLSL 均**对照老 FloodStep 代码做了"保留/改动/删除"标注**，便于边迁移边核对。
> — ai 2026-04-20

---

## 10. Niagara 三阶段实施手册

本节是 §9 迁移策略的**落地版**——给出三个 Simulation Stage 的完整 HLSL、每个 Stage 的 Input Map（User Parameter / Data Interface 连接）、以及 Stage 之间的数据流。

### 10.0 总览

```
Emitter
  ├─ User Parameters（暴露给外部调参的入口）
  │    SeedCenter, SeedRadius, InitSpeed,
  │    g, Damping, BaseDt, Substep,
  │    ArrivalThreshold, MinHeightForNormalize, Gamma
  │
  ├─ Grid2D Collection: G2D
  │    Attributes: h, vx, vy, arrival
  │
  └─ Simulation Stages（按顺序）
       Stage 1  InitGrid     (On Emitter Spawn, 只跑一次)
       Stage 2  SWESolve     (Every Frame, 带 Substep)
       Stage 3  Export       (Every Frame, 紧跟 Stage 2, 记录 arrival)

数据流：
  Stage 1 写 h/vx/vy (arrival 初始化为 -1)
     │
     ▼
  Stage 2 读 Previous h/vx/vy → 计算 → 写 Current h/vx/vy
     │
     ▼
  Stage 3 读 Current h → 若 >ArrivalThreshold 且 arrival<0 → 写 arrival = SimulationAge
     │
     ▼
  每帧 RT 输出（§10.4）：h → FinalHeight RT，arrival → ArrivalTime RT
```

**和老 FloodStep 的 Stage 映射**（详见 §9.1）：
- 老 Stage 1 InitGrid → **保留骨架**，数据从单通道改三通道
- 老 Stage 2 FloodStep → **整段替换**为 SWE 中心差分
- 老 Stage 3 NormalizeGradient → **保留归一化+Gamma**，新增 arrival 写入

---

### 10.1 Stage 1 — InitGrid（种子初始化）

**作用**：Emitter Spawn 时执行一次，在种子区域写入高斯凸起的 `h`，以及径向向外的 `vx/vy`；`arrival` 初始化为 `-1` 表示"尚未到达"。

#### Input Map（Scratch Pad 上方参数面板）

| 参数名 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `G2D` | Grid2D Collection | Data Interface | 目标网格 |
| `SeedCenter` | Vector 2D | User Parameter | 种子中心 UV，典型 `(0.5, 0.5)` |
| `SeedRadius` | Float | User Parameter | 高斯分布的 σ，典型 `0.03`（即 3% 网格宽） |
| `InitSpeed` | Float | User Parameter | 径向初速度幅值，典型 `3.0` m/s |

#### Simulation Stage 设置

| 项 | 值 |
|---|---|
| Iteration Source | `Grid2D Collection = G2D` |
| Execute Behavior | **On Emitter Spawn** |
| Iterate per Cell | ✓ |

#### HLSL

```hlsl
// ============================================================
// Stage 1 — InitGrid
// 每个 cell 执行一次。设置 h / vx / vy / arrival 初值。
// ============================================================
//
// 保留自老 FloodStep：CellUV 计算、到种子距离判断
// 改动：GradientValue(1.0/0.0) → h(高斯) + vx/vy(径向) + arrival(-1)
// 删除：硬边缘 "Dist <= Radius" 判断（改为连续高斯）

int NumCellsX, NumCellsY;
G2D.GetNumCells(NumCellsX, NumCellsY);

float2 CellUV;
CellUV.x = (float(IndexX) + 0.5) / float(NumCellsX);
CellUV.y = (float(IndexY) + 0.5) / float(NumCellsY);

float2 Offset = CellUV - SeedCenter;
float  Dist   = length(Offset);

// 1) h: 高斯凸起
//    σ = SeedRadius; h(0) = 1.0, 离中心 3σ 处约 0.01
float SigmaSq = max(SeedRadius * SeedRadius, 1e-8);
float h_init  = exp(-(Dist * Dist) / (2.0 * SigmaSq));

// 2) v: 径向向外的速度场
//    方向 = 归一化的 Offset；幅值 = InitSpeed * 同一个高斯包络
//    （离种子越远初速度越小，和 h 同步衰减）
float2 Dir    = (Dist > 1e-6) ? (Offset / Dist) : float2(0.0, 0.0);
float  VMag   = InitSpeed * h_init;
float  vx_init = Dir.x * VMag;
float  vy_init = Dir.y * VMag;

// 3) 写回 Grid2D（Stage 1 用 SetFloatValue 直接写当前帧）
G2D.SetFloatValue<Attribute="h">(IndexX,  IndexY, h_init);
G2D.SetFloatValue<Attribute="vx">(IndexX, IndexY, vx_init);
G2D.SetFloatValue<Attribute="vy">(IndexX, IndexY, vy_init);

// 4) arrival = -1，表示这个 cell 还没被染料到达
G2D.SetFloatValue<Attribute="arrival">(IndexX, IndexY, -1.0);
```

#### 输出

- `h[x,y]` 中心高、边缘低的高斯
- `vx/vy[x,y]` 径向外指，和 h 同包络
- `arrival[x,y] = -1`

> **老方案的 ForceDirection / ForceStrength / ForceDecay 模型不再需要**——初速度在这里一次性写死，Stage 2 不再每帧注入外力。

---

### 10.2 Stage 2 — SWESolve（核心求解）

**作用**：每帧读 `Previous` 的 `h/vx/vy`，用 SWE Level 2 的中心差分推进，写到 `Current`。内部循环 `Substep` 次以满足 CFL。

#### Input Map

| 参数名 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `G2D` | Grid2D Collection | Data Interface | |
| `g` | Float | User Parameter | 重力等价系数，起步 `3.0`（§3.3） |
| `Damping` | Float | User Parameter | 粘性阻尼 k，起步 `1.0` |
| `BaseDt` | Float | User Parameter | 一帧总时长，典型 `1/60 = 0.01667` |
| `Substep` | Int | User Parameter | 子步数，起步 `6` |

#### Simulation Stage 设置

| 项 | 值 |
|---|---|
| Iteration Source | `Grid2D Collection = G2D` |
| Execute Behavior | **Every Frame** |
| Iterate per Cell | ✓ |

#### HLSL

```hlsl
// ============================================================
// Stage 2 — SWESolve (浅水方程 Level 2，中心差分)
// 每个 cell 每帧执行一次。
// ============================================================
//
// 保留自老 FloodStep：4 邻域 IndexX±1/IndexY±1 的边界判断套路
// 改动：读 Previous 写 Current（双缓冲） + 解方程而非传播
// 删除：max(邻居-step) 传播、8 邻域 Noise 调制、ArcScale 对角修正、Force 调制

int NumCellsX, NumCellsY;
G2D.GetNumCells(NumCellsX, NumCellsY);
float dx = 1.0 / float(NumCellsX);    // 物理域 1m × 1m，dx = cell 宽度

// ---- 读取当前 cell 的 Previous ----
float h0, vx0, vy0;
G2D.GetPreviousFloatValue<Attribute="h"> (IndexX, IndexY, h0);
G2D.GetPreviousFloatValue<Attribute="vx">(IndexX, IndexY, vx0);
G2D.GetPreviousFloatValue<Attribute="vy">(IndexX, IndexY, vy0);

// ---- 读 4 邻域（边界外用本 cell 值，等价 Neumann 零梯度；Dirichlet 用 0 也行） ----
float h_L = h0, h_R = h0, h_D = h0, h_U = h0;
float vx_L = vx0, vx_R = vx0;
float vy_D = vy0, vy_U = vy0;

if (IndexX - 1 >= 0)           { G2D.GetPreviousFloatValue<Attribute="h"> (IndexX - 1, IndexY, h_L);
                                  G2D.GetPreviousFloatValue<Attribute="vx">(IndexX - 1, IndexY, vx_L); }
if (IndexX + 1 < NumCellsX)    { G2D.GetPreviousFloatValue<Attribute="h"> (IndexX + 1, IndexY, h_R);
                                  G2D.GetPreviousFloatValue<Attribute="vx">(IndexX + 1, IndexY, vx_R); }
if (IndexY - 1 >= 0)           { G2D.GetPreviousFloatValue<Attribute="h"> (IndexX, IndexY - 1, h_D);
                                  G2D.GetPreviousFloatValue<Attribute="vy">(IndexX, IndexY - 1, vy_D); }
if (IndexY + 1 < NumCellsY)    { G2D.GetPreviousFloatValue<Attribute="h"> (IndexX, IndexY + 1, h_U);
                                  G2D.GetPreviousFloatValue<Attribute="vy">(IndexX, IndexY + 1, vy_U); }

// ---- 局部 for-loop（注意：这不是真正的全局 Substep） ----
float h  = h0;
float vx = vx0;
float vy = vy0;

float dt = BaseDt / float(max(Substep, 1));

[loop]
for (int s = 0; s < Substep; s++)
{
    // 1) 质量守恒：∂h/∂t = -∇·(h·v)，中心差分
    //    注意：理论上应该先重构 h·v 在界面，这里简化为邻域值直接用
    float flux_x = (h_R * vx_R - h_L * vx_L) / (2.0 * dx);
    float flux_y = (h_U * vy_U - h_D * vy_D) / (2.0 * dx);
    float dhdt   = -(flux_x + flux_y);

    // 2) 动量方程：∂v/∂t = -g·∇h - k·v
    float dvxdt = -g * (h_R - h_L) / (2.0 * dx) - Damping * vx;
    float dvydt = -g * (h_U - h_D) / (2.0 * dx) - Damping * vy;

    // 3) 显式欧拉推进
    h  = max(h + dhdt * dt, 0.0);     // h 不能为负
    vx = vx + dvxdt * dt;
    vy = vy + dvydt * dt;

    // 注意：这里子步之间只演化本 cell，邻居仍保持为同一帧的 Previous 值。
    // 所以它不是严格意义上的全局 Substep，只能近似细化阻尼项；对 h 的通量推进不能等价替代多 pass。
}

// ---- 写回 Current ----
G2D.SetFloatValue<Attribute="h"> (IndexX, IndexY, h);
G2D.SetFloatValue<Attribute="vx">(IndexX, IndexY, vx);
G2D.SetFloatValue<Attribute="vy">(IndexX, IndexY, vy);
```

#### 关于 Substep 的实现约束（重要）

上面这个 `for (s < Substep)` 在 Niagara 单次 Stage 里并不是真正的全局子步：邻居仍然是同一帧的 `Previous` 值，所以它只对本 cell 的阻尼项有意义，对 `h` 的通量项不是完整 substep。换句话说，**局部 for-loop 不能替代整张 Grid 的多次推进**。

因此 P0/P1 建议两种做法二选一：
- **保守做法**：先把 `Substep = 1`，通过减小 `BaseDt` / 降 `InitSpeed` / 降 `g` 保证稳定；
- **真子步做法**：让 SWE 求解器在一帧内对整张 Grid 运行多次（多次 Stage 执行或显式多 pass），每一小步都刷新 Previous/Current。

#### CFL 自检

如果采用**真子步**，检查 `max(|v|) * (BaseDt / Substep) / dx < 0.5`。
如果还是当前这版**单 Stage + 局部 for-loop**，应按更保守的 `max(|v|) * BaseDt / dx < 0.5` 来估，不能把 `Substep` 当成等比例救命药。典型起步先按 `dx=1/256`、`|v|≈3`、`BaseDt=1/60` 控到安全，再逐步抬参数。

---

### 10.3 Stage 3 — Export（记录 ArrivalTime + 归一化）

**作用**：Stage 2 之后执行；对每个 cell 看当前 `h`，首次超过阈值时把 `SimulationAge` 写进 `arrival`。归一化 + Gamma 的活直接留给导出后的 Blueprint / 材质，本 Stage 只写 arrival。

> 若想在 HLSL 里顺便算 Normalized FinalHeight 以便运行期直接用，见下方 §10.3.1 可选片段。

#### Input Map

| 参数名 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `G2D` | Grid2D Collection | Data Interface | |
| `ArrivalThreshold` | Float | User Parameter | h 超过此值视为"到达"，典型 `0.01` |
| `SimulationAge` | Float | Emitter attribute | Niagara 内置 `Engine.Emitter.Age` 或 `Particles.NormalizedAge * Lifetime`，取秒数 |

#### Simulation Stage 设置

| 项 | 值 |
|---|---|
| Iteration Source | `Grid2D Collection = G2D` |
| Execute Behavior | **Every Frame** |
| Stage Order | **排在 Stage 2 之后** |

#### HLSL

```hlsl
// ============================================================
// Stage 3 — Export (ArrivalTime 记录)
// 每 cell 每帧执行。只在首次到达时写入 arrival。
// ============================================================
//
// 保留自老 FloodStep：Stage 3 的 "读当前值 → 条件处理 → 写回" 结构
// 改动：归一化逻辑下放给导出阶段（见 §4.2）；本 Stage 专职记录时间
// 删除：MinGradientValue 重映射、pow(Gamma) —— 改放到材质或导出 BP

float h;
G2D.GetFloatValue<Attribute="h">(IndexX, IndexY, h);

float arrival_prev;
G2D.GetFloatValue<Attribute="arrival">(IndexX, IndexY, arrival_prev);

// 只在"尚未到达"且"当前已到达"时写入
if (arrival_prev < 0.0 && h > ArrivalThreshold)
{
    G2D.SetFloatValue<Attribute="arrival">(IndexX, IndexY, SimulationAge);
}
// 否则保持 arrival_prev 不动（Niagara 不写等于保持原值）
```

#### 10.3.1（可选）顺便在 HLSL 里做归一化 FinalHeight

如果希望 Stage 3 同时产出 `[0,1]` 归一化的 h 作为一个新 Attribute `h_norm`（避免导出后再一遍 BP/材质处理），补这一段：

```hlsl
// 需要新增 Attribute: h_norm (float)
// 需要新增 Input: MinHeightForNormalize (Float, 起步 0.0), Gamma (Float, 起步 1.0)
float h_n = saturate((h - MinHeightForNormalize) / max(1.0 - MinHeightForNormalize, 1e-3));
h_n = pow(max(h_n, 1e-5), max(Gamma, 0.01));
G2D.SetFloatValue<Attribute="h_norm">(IndexX, IndexY, h_n);
```

这段**完全等价老 FloodStep Stage 3 的逻辑**，只是输入从 `GradientValue` 换成了 SWE 解出来的 `h`。P0/P1 阶段可以先不加，P2 导出前再决定。

---

### 10.4 Niagara Emitter 装配 checklist

按下列顺序在 Niagara Editor 里搭：

1. **Emitter 基础**
   - Emitter Update → `Spawn Rate = 0`，`Spawn Burst Instantaneous = 1`（只发一个粒子驱动 Stage 执行）
   - Lifetime 设够长（比如 10s，够跑到收敛）

2. **Grid2D Collection Data Interface**
   - Named Emitter Attribute → 新增 `Grid2D Collection`，取名 `G2D`
   - 打开其资产，Attributes 里添加：
     - `h` : float
     - `vx` : float
     - `vy` : float
     - `arrival` : float
     - *（可选）* `h_norm` : float
   - NumCells X/Y = 256/256（或 512 看需求）

3. **User Parameters（Emitter → User Exposed）**
   - 按 §10.1/§10.2/§10.3 的 Input Map 表暴露，统一用 `Vector 2D` / `Float` / `Int`
   - 建议起步值：`SeedCenter=(0.5,0.5)`, `SeedRadius=0.03`, `InitSpeed=3.0`, `g=3.0`, `Damping=1.0`, `BaseDt=0.01667`, `Substep=6`, `ArrivalThreshold=0.01`

4. **Simulation Stages**（严格按这个顺序，Niagara 会自上而下跑）
   - Stage 1 `InitGrid` — Execute Behavior: **On Emitter Spawn**，Iteration Source: `G2D`
   - Stage 2 `SWESolve` — Execute Behavior: **Every Frame**，Iteration Source: `G2D`
   - Stage 3 `Export`   — Execute Behavior: **Every Frame**，Iteration Source: `G2D`

5. **Scratch Pad 连线**
   - 每个 Stage 一个 Scratch Pad，HLSL 粘贴 §10.1/§10.2/§10.3 对应代码
   - Scratch Pad 顶部 Input Map 里新增对应参数（名字对齐 HLSL 里的变量名）
   - `IndexX` / `IndexY` 是 Niagara 每个 cell 迭代时自动提供的，不用连

6. **双缓冲**（关键）
   - Stage 2 用 `GetPreviousFloatValue` 读，`SetFloatValue` 写 —— Niagara Grid2D 自动维护 Previous/Current 切换
   - Stage 1 / Stage 3 只用 `GetFloatValue` / `SetFloatValue`（非双缓冲场景）
   - **千万不要在 Stage 2 里用 `GetFloatValue` 读 h 然后立刻写**，那是自反馈，会 NaN

7. **RT 输出（P2 阶段再做）**
   - Emitter 上加两个 `Render Target 2D` User Parameter：`RT_FinalHeight` / `RT_Arrival`
   - Emitter Update 里用 `Grid2D Collection → Export To Render Target` 把 `h` / `arrival` 分别导到 RT
   - Editor Utility Blueprint 里在收敛帧（§4.1）调 `RenderTargetCreateStaticTexture2DEditorOnly` 存成资产

8. **可视化调试**
   - P0 先只开 Stage 1+2，RT 输出 `h`，在 Level 里放一个 Unlit 材质贴这张 RT，实时看
   - Stage 3 等 Stage 1+2 表现正常后再接

---

### 10.5 迁移代码对照总表

| 老 FloodStep 代码片段 | 新方案处置 | 位置 |
|---|---|---|
| `CellUV = (float2(IndexX, IndexY) + 0.5) / ...` | ✅ 保留 | §10.1 |
| `Dist = length(CellUV - SeedCenter)` | ✅ 保留 | §10.1 |
| `GradientValue = (Dist <= Radius) ? 1.0 : 0.0` | 🔄 改为高斯 `exp(-d²/2σ²)` | §10.1 |
| `ForceAttenuation = exp(-Dist * Decay) * Strength` | 🔄 改为初速度幅值（一次性，不每帧） | §10.1 |
| `max(CurrentValue, 邻居 - BaseStep * Combined)` | ❌ 删除，替换为 SWE 中心差分 | §10.2 |
| 8 邻域 `N/S/W/E/NW/NE/SW/SE` 读取 | 🔄 简化为 4 邻域（L/R/D/U） | §10.2 |
| 8 邻域 Noise 采样 + `NMod_*` | ❌ 删除 | — |
| 8 邻域 Force 调制 `FMod_*` | ❌ 删除（初速度已在 Stage 1） | — |
| `ArcScale = 1.41421356` 对角修正 | ❌ 删除（不用对角邻居了） | — |
| `saturate(MaxCandidate)` 钳位 | 🔄 改为 `max(h, 0)` | §10.2 |
| `Normalized = saturate((h - Min) / (1 - Min))` | ✅ 保留（移到可选 §10.3.1 或材质） | §10.3.1 / §5 |
| `pow(Normalized, Gamma)` | ✅ 保留（同上） | §10.3.1 / §5 |
| —— 新增 —— | ➕ `arrival` 首次到达记录 | §10.3 |
| —— 新增 —— | ➕ Substep 循环 + CFL 检查 | §10.2 |
