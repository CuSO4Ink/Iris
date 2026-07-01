# M_CalcGridBounds — 通用 N3D 网格范围模块规格

> **定位**：一个可复用的 Niagara Module Script，负责为 Neighbor Grid 3D（N3D）每帧计算并设置网格的世界范围（`SetTransformMatrix`）。一次搭好，任何用 N3D 做 Boids / SPH / 邻域查询的系统都能直接挂上复用。
>
> **本体职责**：算出 grid 的 `Center` / `Size` → 拼成变换矩阵 `M` → 调 `NeighborGrid.SetTransformMatrix(M)`。**不碰粒子注册、不碰邻域查询**（那些是 Sim Stage 的活）。
>
> **版本**：v1.1 · 引擎基线 UE5.x（N3D DI 接口名以实际版本为准）· 挂载阶段 **Emitter Update**
>
> **v1.1 变更**：新增第 4 条来源 `SplineBounds`——网格范围跟随样条线 AABB（CPU 端算，零 GPU 成本零延迟），用于"美术拉路径时 grid 自动裹住整条样条线"的工作流。

---

## 0. 一句话用法（90% 场景）

> 把模块挂到 Emitter Update，`BoundsSource` 选 **SoftBounds**，把 `BoundsCenter`/`BoundsSize` 链到系统已有的软边界参数，开 N3D debug draw 确认绿框套住粒子群——完工。Reduction 路径搭好留作 Static Switch 后面的逃生舱，默认不编译进 shader。

---

## 1. 模块输入参数（Module Inputs）

在 Module Script 的 **Module Inputs** 里按下表声明。注意区分 **Static Switch**（编译期常量，改值触发重编译）和普通输入（运行时值）。

| 参数名 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `BoundsSource` | **Static Switch (Enum `ENiagaraGridBoundsSource`)** | `SoftBounds` | 核心四选一开关，编译期决定走哪条路径 |
| `ConstCenter` | Vector | (0,0,0) | Fixed 模式：固定网格中心（世界坐标） |
| `ConstSize` | Vector | (1000,1000,1000) | Fixed 模式：固定网格全边长 |
| `BoundsCenter` | Vector | (0,0,0) | SoftBounds 模式：链到系统的软边界中心（如 `Emitter.ControlBoundsCenter`） |
| `BoundsSize` | Vector | (1000,1000,1000) | SoftBounds 模式：链到系统的软边界全边长（如 `Emitter.ControlBoundsSize`） |
| `SplineCenter` | Vector | (0,0,0) | SplineBounds 模式：链到 `User.GridCenter`（蓝图 CPU 端算好的样条线 AABB 中心） |
| `SplineSize` | Vector | (1000,1000,1000) | SplineBounds 模式：链到 `User.GridSize`（样条线 AABB 全边长） |
| `Padding` | float | 1.1 | 边界余量倍率，留 10% 防粒子贴边/快速移动溢出 |
| `NeighborGrid` | Neighbor Grid 3D (DI) | — | 链到 Emitter 上的 N3D 数据接口 |

### Enum 定义 `ENiagaraGridBoundsSource`

Content Browser → 右键 → Blueprints → **Enumeration**（或 Niagara 专用 Enum），四个值：

| 值 | 含义 | 成本 |
|---|---|---|
| `Fixed` | 用常量范围 | 零（编译后两个 Set） |
| `SoftBounds` | 复用系统已算的软边界 ×Padding | 零额外 Stage，动态跟随，当帧生效 |
| `SplineBounds` | 跟随样条线 AABB（蓝图 CPU 端算）×Padding | 零额外 Stage，运行时只读两个 User 参数，当帧生效 |
| `Reduction` | 真扫所有粒子算 AABB | 高，2 趟 Sim Stage，**慢一帧** |

---

## 2. 模块输出

模块只产出一个副作用：调用 DI 接口设置矩阵。

```
NeighborGrid.SetTransformMatrix( M )       // 唯一的 DI 写入点
// 可选：NeighborGrid.SetNumCells(Resolution) —— 一般在 Emitter Spawn 设一次即可，不参与动态
```

`M` 的语义见 §5。Reduction 路径额外读写两个 persistent Emitter 变量（见 §4）。

---

## 3. 模块图主干结构

```
[BoundsSource (Static Switch selector)]
        │
        ├── case Fixed ───────► Center = ConstCenter
        │                       Size   = ConstSize
        │
        ├── case SoftBounds ──► Center = BoundsCenter           ◄── 默认路径
        │                       Size   = BoundsSize * Padding
        │
        ├── case SplineBounds ► Center = SplineCenter           ◄── 蓝图 CPU 算好喂进来
        │                       Size   = SplineSize * Padding
        │
        └── case Reduction ──► Center = (Emitter.AABBMin+Max)*0.5   ◄── 读上一帧 Stage 存的值
                                Size   = (Emitter.AABBMax-Min)*Padding
        │
        ▼   (四路汇合，得到 Center / Size)
   M = Compose(Translate=Center, Scale=Size, Rotation=Identity)
        │
        ▼
   NeighborGrid.SetTransformMatrix(M)
```

> **关键**：主干用 **Static Switch 节点**（不是 `Select`，不是 `If`）。未选中的分支整条被剔除出最终 shader，真正做到"没必要就零成本"。

---

## 4. 四条路径的节点级搭法

### ① Fixed — 最简单

```
SetVariable  Center := ConstCenter
SetVariable  Size   := ConstSize
```

编译后只剩两个赋值。适用：范围完全可预测、写死即可的系统。

### ② SoftBounds — 默认 / 最优解

```
SetVariable  Center := BoundsCenter
SetVariable  Size   := BoundsSize * Padding
```

直接读系统已经在算的软边界参数（Boids 的 Control/Leader 软盒子本来每帧就要算）。这里只是**读它**，不加任何 Stage → 动态跟随 + 零成本 + 当帧生效（无一帧延迟）。**这是 90% 系统的最终答案。**

### ③ SplineBounds — 美术工作流路径（样条线 AABB，CPU 端算）

```
SetVariable  Center := SplineCenter        // = User.GridCenter
SetVariable  Size   := SplineSize * Padding // = User.GridSize × Padding
```

模块这一段和 SoftBounds 同样简单——只是**读两个 User 参数**，零额外 Stage、当帧生效。区别只在数据来源：这两个 User 参数是**蓝图端在 CPU 上算好喂进来的样条线 AABB**（见 §6.5 蓝图侧流程），不是 GPU 算的。

**为什么和 SoftBounds 同级零成本**：样条线是美术编辑时确定的**静态几何**，运行时几乎不变。它的 AABB 在蓝图 `OnConstruction`/`BeginPlay` 里**一次性算好**即可，根本不需要每帧 GPU reduction——因此既没有 Reduction 的扫描开销，也没有那一帧延迟。

**核心价值（这条路径存在的理由）**：美术拉样条线路径时，不用对着 N3D debug 框慢慢手调边界——想怎么拉就怎么拉，grid 自动裹住整条样条线。配合 `OnConstruction` 重算，编辑器里拖动控制点的当下绿框就实时跟随，所见即所得。

> 适用判断：鸟群**整条路径铺满**（"整条路径上都有鸟"）→ grid 必须裹住整条线 → SplineBounds 正确。若鸟群只是一小撮沿线聚集移动 → grid 跟鸟群质心更优（用 SoftBounds 那条更合适）。

### ④ Reduction — 逃生舱（仅密度剧变、SoftBounds 罩不住时启用）

模块图里这条路径只做"**读**上一帧算好的 AABB"：

```
SetVariable  Center := (Emitter.AABBMin + Emitter.AABBMax) * 0.5
SetVariable  Size   := (Emitter.AABBMax - Emitter.AABBMin) * Padding
```

真正"算 AABB"的活在两个独立的 **Simulation Stage** 里（见 §6），它们把结果存进 persistent Emitter 变量 `Emitter.AABBMin` / `Emitter.AABBMax`，供本模块下一帧读取。**结构性一帧延迟**由此而来，Padding 必须留足。

---

## 5. 矩阵 M 的拼法（最易拼反，重点）

N3D 的 `SetTransformMatrix` 期望的是 **「单位盒 → 世界盒」的正向矩阵**。你**不要**自己算逆矩阵——N3D 内部会用 `M⁻¹` 把世界坐标转回 grid 空间做 cell 映射。

```
M = Translate(Center) × Scale(Size)
```

Niagara 里用 **Make Transform / Compose Transform** 节点：
- `Location = Center`
- `Scale    = Size`
- `Rotation = Identity`（除非要斜盒子）

**两个坑**：
1. 别传成逆矩阵（N3D 自己求逆）。
2. 确认单位盒约定是 `[-0.5,0.5]³`（中心在原点，则 Scale 用全边长 Size）还是 `[0,1]³`。**验证只有一招最快**：开 N3D debug draw 看绿框，比任何纸上推导靠谱。

---

## 6. Reduction 路径的两个 Simulation Stage（树形归约，**不用 atomic**）

> 仅当 `BoundsSource == Reduction` 时这两个 Stage 才存在。把每个 Stage 的 **Enabled** 引脚绑到 `BoundsSource == Reduction`，没选中时连生成都不生成 → 彻底零成本。
>
> 设计原则：**绝不用 `InterlockedMax` 求全局最值**（那是 N 个粒子抢 1 个地址的 O(N) 极端竞争）。改用**分组归约**——每组写自己独立的槽位，零地址冲突，自然不需要原子。

### 中间 buffer

长度 `G`（组数，建议 128）的两个数组 `PartialMin[G]` / `PartialMax[G]`。可用一个 `1×G×1` 的 Rasterization Grid 3D 或自定义 Grid DI 当存储。

### Pass 1 — 分组求局部 AABB

- Stage：`Iteration Count = G`，**iteration source = G（不是 Particles）**
- 第 `g` 个 iteration 负责扫 `[g*chunk, (g+1)*chunk)` 这段粒子（`chunk = ceil(NumParticles / G)`）

```hlsl
// Pass1_ComputeLocalAABB.hlsl
int g          = ExecIndex;                 // 当前组号 0..G-1
int chunk      = (NumParticles + G - 1) / G;
int begin      = g * chunk;
int end        = min(begin + chunk, NumParticles);

float3 lo = float3( 3.402823e38,  3.402823e38,  3.402823e38);  // +FLT_MAX
float3 hi = float3(-3.402823e38, -3.402823e38, -3.402823e38);  // -FLT_MAX

for (int i = begin; i < end; ++i)
{
    float3 p = ReadParticlePosition(i);     // Particle Attribute Reader，注意 CPU/GPU sim target 要一致
    lo = min(lo, p);
    hi = max(hi, p);
}

PartialMin[g] = lo;   // 每组写自己的 g 槽位 → 零冲突 → 无需原子
PartialMax[g] = hi;
```

> ⚠️ `ReadParticlePosition` 走 Particle Attribute Reader，**读取方与被读 Emitter 的 sim target（CPU/GPU）必须一致**，否则读取失败返回默认值（这是本项目踩过的坑）。

### Pass 2 — 归并 G 个局部结果

- Stage：`Iteration Count = 1`，单线程

```hlsl
// Pass2_MergeAABB.hlsl
float3 lo = float3( 3.402823e38,  3.402823e38,  3.402823e38);
float3 hi = float3(-3.402823e38, -3.402823e38, -3.402823e38);

for (int g = 0; g < G; ++g)
{
    lo = min(lo, PartialMin[g]);
    hi = max(hi, PartialMax[g]);
}

Emitter.AABBMin = lo;   // 存 persistent Emitter 变量，供下一帧模块读取
Emitter.AABBMax = hi;
```

G=128 时单线程循环 128 次，开销可忽略。**结果隔帧生效**（Pass2 跑在 Emitter Update 之后），所以模块 §4③ 读的是上一帧的值，Padding 补偿延迟。

> 备注：若粒子数极大（百万级），可把 Pass1 再拆成层级归约（N→N/256→…）；但鸟群规模（千~万级）一趟分组就够。

---

## 6.5 SplineBounds 路径的蓝图侧流程（CPU 端算样条线 AABB）

> 这条路径**没有任何 Sim Stage、没有 HLSL**——AABB 在蓝图里用 CPU 算一次，通过两个 User 参数喂给模块。这是它和 Reduction 的本质区别。

### User 参数约定（在 Niagara System → User Parameters 新建）

| 参数名 | 类型 | 说明 |
|---|---|---|
| `User.GridCenter` | Vector | 样条线 AABB 中心，蓝图写入 |
| `User.GridSize` | Vector | 样条线 AABB 全边长，蓝图写入 |

模块的 `SplineCenter` / `SplineSize` 输入分别链到这两个 User 参数。

### 蓝图算法（`BP_CrowController` 的 `OnConstruction` + `BeginPlay`）

放 **`OnConstruction`** 是关键——美术在编辑器里拖样条线控制点的当下就重算，绿框实时跟随（所见即所得）。`BeginPlay` 再调一次兜底运行时。

```
函数 RecalcSplineGridBounds():
    Spline = 本 Actor 的 SplineComponent
    NumPoints = Spline->GetNumberOfSplinePoints()

    Min = (+大, +大, +大)
    Max = (-大, -大, -大)

    // 采样点：控制点不足以包住曲线弧段，按弧长等距多采样更准
    SampleCount = max(NumPoints * 8, 16)
    SplineLen   = Spline->GetSplineLength()
    for s in 0..SampleCount:
        dist = SplineLen * s / SampleCount
        P    = Spline->GetLocationAtDistanceAlongSpline(dist, World)
        Min  = ComponentMin(Min, P)
        Max  = ComponentMax(Max, P)

    Center = (Min + Max) * 0.5
    Size   = (Max - Min)
    // 防退化：直线/平面路径某一轴 Size≈0，给个最小厚度，避免 grid 被压扁成 0
    Size   = ComponentMax(Size, (MinThickness, MinThickness, MinThickness))

    Set Niagara Variable (Vector)  "GridCenter" := Center
    Set Niagara Variable (Vector)  "GridSize"   := Size
```

### 两个工程要点

1. **按弧长等距采样，不要只取控制点**。样条线在控制点之间是曲线，弧段可能"鼓出"控制点连线之外。只用控制点求 min/max 会漏掉鼓出部分，导致 grid 裹不住。`GetLocationAtDistanceAlongSpline` 等距采样 8×控制点数即可足够准。
2. **退化轴兜底**。一条水平/直线路径会让某一轴 `Size≈0`，`Scale` 为 0 的矩阵会让 N3D cell 映射除零崩坏。用 `MinThickness`（如 50~100）给每轴兜底。这里的 `Padding` 在模块侧统一乘，蓝图只产出裸 AABB。

### 与 §6 Reduction 的对照（同样"算 AABB"，为何一个免费一个昂贵）

| 维度 | SplineBounds（CPU） | Reduction（GPU） |
|---|---|---|
| 数据来源 | 静态样条线几何 | 运动中的粒子 |
| 算在哪 | CPU（蓝图） | GPU（Sim Stage） |
| 算几次 | 编辑时/BeginPlay 一次 | 每帧 |
| 进模块方式 | `Set Niagara Variable` 喂 User 参数 | Sim Stage 写 persistent 变量 |
| 延迟 | 零 | 一帧 |
| 共同点 | **都只产出一个 Center/Size，汇到 §5 同一出口** | |

> 这张表正是"统一接口、分流实现"的具体体现：两条路径输出契约完全一致（Center/Size → 拼 M → SetTransformMatrix），但算法、运行位置、阶段、成本全不同，所以必须各写各的来源代码，靠 Static Switch 编译期二选一，绝不强行合并成一个带运行时分支的函数。

---

## 7. 执行阶段归属（铁律）

| 操作 | 阶段 | 原因 |
|---|---|---|
| 算 Center/Size、拼 M、`SetTransformMatrix` | **Emitter Update** | grid 范围是 emitter 级全局状态，每帧一次，必须早于粒子注册 |
| `SetNumCells` / Resolution | Emitter Spawn（设一次） | cell 数固定分配，不参与动态 |
| 粒子注册写入 grid | **Simulation Stage** | per-particle 并行，用范围算各自 cell |
| 邻域查询算 Boids 力 | **Simulation Stage** | 同上，用同一套映射 |
| SplineBounds 算样条线 AABB | **蓝图 CPU**（`OnConstruction` + `BeginPlay`） | 静态几何，CPU 算一次喂 User 参数，零 GPU 成本零延迟 |
| Reduction 算 AABB（Pass1/2） | **Simulation Stage**（仅 Reduction 模式） | 需遍历全部粒子；跑在 Emitter Update 之后 → 隔帧喂回 |

**`SetTransformMatrix` 永远在 Emitter Update**，不管哪条路径。Sim Stage 只在 Reduction 模式多承担"算 AABB 存起来"。

---

## 8. 接入清单（新项目复用步骤）

1. 把 `M_CalcGridBounds` Module Script 与 `ENiagaraGridBoundsSource` Enum 拷进工程。
2. 目标 Emitter 上确保有一个 **Neighbor Grid 3D** DI，并在 Emitter Spawn 用 `SetNumCells` 设好 Resolution。
3. 在 **Emitter Update** 添加 `M_CalcGridBounds` 模块。
4. 把模块的 `NeighborGrid` 输入链到那个 DI。
5. 选 `BoundsSource`：
   - 有软边界系统 → **SoftBounds**，把 `BoundsCenter/Size` 链到软边界参数。
   - 沿样条线铺满的路径效果（美术拉路径）→ **SplineBounds**，建 `User.GridCenter/Size`，把 `SplineCenter/Size` 链上去，并在蓝图 `OnConstruction`+`BeginPlay` 调 §6.5 的 `RecalcSplineGridBounds`。
   - 范围写死 → **Fixed**，填 `ConstCenter/Size`。
   - 密度剧变 → **Reduction**，并启用 §6 两个 Stage（Enabled 绑 `==Reduction`）。
6. 设 `Padding`（默认 1.1；移动快/Reduction 模式可调到 1.2~1.3）。
7. 开 N3D debug draw，验收绿框（见 §9）。

---

## 9. 验收标准（debug draw）

| 检查 | 期望 | 不对时反推 |
|---|---|---|
| 绿框是否套住整个粒子群 | 是，且四周留约 Padding 的余量 | 框偏移 → `Center` 错；框大小不对 → `Size` 或单位盒约定（[-0.5,0.5] vs [0,1]）错 |
| 粒子群移动时绿框是否跟随 | SoftBounds/Reduction 跟随；SplineBounds 跟样条线；Fixed 不动 | 不跟随 → 检查是否误放 Particle 阶段、或参数没链对 |
| SplineBounds：编辑器拖样条线控制点 | 绿框实时重算跟随，裹住整条样条线 | 不跟随 → `RecalcSplineGridBounds` 没放 `OnConstruction`；框裹不住曲线鼓出段 → 采样数太少，只取了控制点 |
| 切 Static Switch 到 Fixed | 绿框变成固定盒，Reduction Stage 从 GPU profiler 消失 | Stage 没消失 → Enabled 没绑 `==Reduction` |
| Reduction 模式快速移动 | 绿框慢一帧但 Padding 内仍包住粒子 | 粒子溢出框 → 调大 Padding |

---

## 10. 设计决策备忘（为什么这么做）

- **动态每帧算 AABB 紧贴粒子群** → 理论省显存/省遍历，实际更慢或持平，**默认不做**。N3D 的 Resolution 是初始化时一次性分配，运行时改不了；邻居查询次数由物理密度决定，不由 cell 大小决定；空 cell 代价只是读个 0，极便宜。
- **CellSize ≈ 感知/Separation 半径** 才是 N3D 性能真开关（让 3×3×3 刚好覆盖）。`CellSize = Size / Resolution`，所以 Size 缩小时 CellSize 自动缩小——这正好覆盖"粒子群聚拢时保持效率"那个唯一有意义的动态场景。
- **求全局最值不加原子 = 丢失更新（结果错）**；加原子 = 照样 O(N) 串行（不变快）。所以 atomic 求全局 max 天生又对又慢，无优化空间 → 用**树形分组归约**换掉"全员写一个地址"的结构。
- **"自动按需启用"是伪命题**：判断要不要动态本身要算 AABB，判断成本≈执行成本。可行的只有设计时 Static Switch。
- **"动态"分两类，成本差几个数量级**：SoftBounds / SplineBounds 也是动态（grid 跟软边界/样条线实时变），但数据来源本来就在算（或 CPU 一次性算），模块只"读"不"算" → 和 Fixed 几乎一样便宜。真费的只有 Reduction（来源是运动粒子，每帧 GPU 扫一遍）。所以"动态 ≈ 免费"对本项目成立。
- **统一接口、分流实现**：四条来源（Fixed/SoftBounds/SplineBounds/Reduction）输出契约一致（Center/Size → M → SetTransformMatrix，共用尾段），但算法/运行位置/阶段/成本全不同，必须各写各的来源段，靠 Static Switch 编译期二选一，不强行合并成带运行时分支的函数。
- **SplineBounds 的真正价值是美术工作流，不是性能**：动态 grid 在运行时性能上无价值（已论证），但让美术拉样条线时不必盯着 N3D 边界手调——而且因来源是**静态样条线**而非运动粒子，AABB 在 CPU 端算一次即可，和 SoftBounds 一样零成本零延迟，根本不碰 Reduction。

---

*维护：本规格是该通用模块的设计源文件。Niagara 资产为 GUI 节点图，无法纯文本版本控制，故以本规格作为单一真相源（single source of truth）。改动模块时同步更新本文件。*
