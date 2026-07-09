# GasRibbon · 技术路线调研报告

> 2026-07-07 · 全网调研结果 + 三条候选路线评估

## 一、需求回顾

香烟烟丝式飘带气体：细长丝带、螺旋上升、湍流扭曲、边缘软扩散。写实风格，游戏内实时特效。

## 二、调研发现

### 2.1 学术参考

| 来源 | 核心方法 | 与本需求的关系 |
|---|---|---|
| **Microsoft Research — Compensated Ray Marching** (Zhou et al. 2008) | 将烟雾密度场分解为 RBF 低频近似 + 残差场，低频算散射、高频补偿细节 | 高频残差补偿思路可借鉴：用低步数算散射 + 高频噪声补视觉细节，降 GPU 成本 |
| **Horizon Zero Dawn — SIGGRAPH 2015** (Schneider) | 体积云 raymarching + 多层噪声 + Beer-Lambert | 经典实时体积渲染管线，但规模是云层而非细丝——采样策略需缩放 |
| **KillZone: Shadow Fall — SIGGRAPH 2014** (Guerilla) | Raymarching + Shadow Map 采样 + Temporal Reprojection | Temporal 抖动采样可降步数，适合实时烟雾 |

### 2.2 UE 生态现有方案

| 方案 | 情况 | 评价 |
|---|---|---|
| **Niagara Sprite + Curl Noise Force** | 最常见做法，Sprite 粒子挂烟雾贴图 + Curl Noise 扰动 + 尺寸/透明度生命周期曲线 | 快但不够"3D"——Sprite 是面片，侧面看穿帮，无法做到真体积丝带感 |
| **Niagara Ribbon Renderer** | 粒子串成连续条带，支持 Tiled UV 流动 | 形态上接近"飘带"，但默认是扁平条带面片，需要自定义材质做体积感 |
| **EmberGen → VDB → UE5** | 离线流体模拟导出 VDB，UE5 导入体积纹理 | 效果最好但非实时生成，适合离线/过场；不适合游戏内动态实时特效 |
| **Houdini 烘焙 3D 纹理** | Houdini Cloud/Volume SDF → 烘焙到 2D 纹理切片 / 3D 纹理 | 同上，离线生成静态或循环体积数据，运行时采样——灵活性最低 |
| **Niagara Render Target → 自定义材质** | Niagara GPU 模拟写入 RT，材质端 raymarching 采样 RT | 高度自定义但工程复杂，是目前最接近"真体积实时烟雾"的路线 |

### 2.3 Niagara Curl Noise 能力确认

- Niagara 内置 **Curl Noise Force** 模块，直接作用于 GPU 粒子的 `Physics.Force`
- 高级案例中使用 **Advect 模块**（本质是 Curl Noise 采样 + UV 扰动），模拟流体平流现象
- GPU Emitter 支持 Data Interface（RT 读写），可做自定义密度场计算

### 2.4 关键技术参考

- **Alan Zucconi — Volumetric Rendering 系列**：Surface Shading / 体积距离场教程，适合理解 raymarching 基础
- **知乎 UE5 Hillside 体积云移植 URP**：完整的体积云 raymarching 管线拆解，含噪声构建、光照、性能
- **知乎 MarchingCube in UnrealEngine**：对比 Raymarching vs MarchingCube，MarchingCube 静态网格更适合静态体积，Raymarching 适合动态
- **iMixBlue/Volumetric-Cloud-Raymarching (GitHub)**：开源体积云 raymarching 实现

## 三、三条候选路线评估

### 路线 A：Niagara Ribbon + Custom HLSL 体积材质 ⭐ 主方案候选

**架构**：
```
Niagara GPU Emitter (Curl Noise 驱动轨迹 + Ribbon 拓扑)
  → Ribbon Renderer (条带几何作射线步进载体)
    → Custom HLSL 材质 (密度场 + Raymarching + Beer-Lambert + HG相位 + 多次散射近似)
```

| 维度 | 评价 |
|---|---|
| 形态匹配 | Ribbon 天然丝带形态，Curl Noise 驱动螺旋上升——高度匹配 |
| 3D 体积感 | 在 Ribbon 面片上做 raymarching，步进出真体积密度——可达成 |
| 高精度 | Custom HLSL 可控制步数、噪声层数、散射精度——上限高 |
| 实时性能 | Ribbon 几何量小（少量顶点），raymarching 局限在条带范围——比全屏 raymarching 轻量 |
| 运动控制 | Niagara 粒子系统完全掌控运动轨迹——最好 |
| 工程成本 | 中高：需写 Custom HLSL + Niagara 配置 + 材质集成 |
| 风险 | Ribbon 几何有限，raymarching 步进范围受限，需验证体积感是否够"厚" |

**ms 预估**：2-5ms（1080p，单条飘带，32-64 步）

### 路线 B：纯 Shader 假体积（全屏/后处理 Raymarching）

**架构**：
```
Post Process Material 或 SceneViewExtension
  → 全屏 Raymarching (Curl Noise 密度场 + Domain Warping + Beer-Lambert)
```

| 维度 | 评价 |
|---|---|
| 形态匹配 | 纯程序化，形态完全由噪声参数控制——可匹配但调参难 |
| 3D 体积感 | 全屏 raymarching 是最"真"的体积——最高 |
| 高精度 | 无几何限制，步数可拉满——最高 |
| 实时性能 | 全屏 raymarching 很贵——最差 |
| 运动控制 | 纯 shader 运动，无粒子系统——最弱，难做复杂轨迹 |
| 工程成本 | 中：纯 shader，但调参/运动控制难 |
| 风险 | 全屏步进太贵，游戏内实时基本不可行；运动控制弱 |

**ms 预估**：8-15ms+（1080p，64 步）——实时游戏内不可接受

### 路线 C：Volume Texture 烘焙（离线 → 运行时采样）

**架构**：
```
Houdini/EmberGen 离线模拟 → 烘焙 3D Volume Texture → UE5 运行时 Niagara 采样
```

| 维度 | 评价 |
|---|---|
| 形态匹配 | 取决于离线模拟——可以很好 |
| 3D 体积感 | 3D 纹理采样有真体积——可达成 |
| 高精度 | 受纹理分辨率限制——中 |
| 实时性能 | 纹理采样便宜——最好 |
| 运动控制 | 循环播放烘焙数据——最弱，无法动态响应 |
| 工程成本 | 低中：需 Houdini/EmberGen 流程 |
| 风险 | 不动态、不响应游戏状态；循环感明显；不适合"实时特效"定位 |

**ms 预估**：<1ms——性能最好

## 四、结论与建议

| 路线 | 形态 | 3D体积 | 高精度 | 实时性能 | 运动控制 | 综合 |
|---|---|---|---|---|---|---|
| **A: Niagara Ribbon + Custom HLSL** | ★★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★★ | **推荐** |
| B: 纯 Shader 假体积 | ★★★ | ★★★★★ | ★★★★★ | ★ | ★ | 不推荐（性能+运动） |
| C: Volume Texture 烘焙 | ★★★★ | ★★★★ | ★★★ | ★★★★★ | ★ | 备选（非实时生成） |

**建议锁定路线 A 为主方案**，理由：
1. Niagara Ribbon 天然匹配"飘带"形态
2. Custom HLSL raymarching 在 Ribbon 局部范围步进，比全屏轻量
3. Curl Noise 驱动 + Niagara 粒子系统 = 完全可控的实时运动
4. 写实体积感可通过多层噪声 + 多次散射近似达成

**路线 C 作为备选**：若路线 A 的体积厚度验证不通过，可退回离线烘焙 + 运行时采样。

## 五、下一步

1. 原型验证：Ribbon 几何上做简单 raymarching，确认体积厚度是否够
2. 密度场设计：Curl Noise + Domain Warping 参数调优
3. 光照模型：Beer-Lambert + HG 相位 + 2 级散射近似
4. 性能测试：不同步数/噪声层数下的 ms 预算
