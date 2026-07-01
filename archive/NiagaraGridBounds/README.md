# NiagaraGridBounds — 通用 N3D 网格范围模块

一个可复用的 Niagara 模块资产，为 Neighbor Grid 3D（N3D）每帧计算并设置网格世界范围。一次搭好，任何用 N3D 做 Boids / SPH / 邻域查询的系统都能直接挂上复用。

## 文件清单

| 文件 | 作用 |
|---|---|
| `M_CalcGridBounds.spec.md` | **主规格**（单一真相源）：参数表、四路径搭法、矩阵拼法、Stage 绑定、接入清单、验收标准 |
| `Pass1_ComputeLocalAABB.hlsl` | Reduction 路径第 1 趟：分组求局部 AABB（无 atomic） |
| `Pass2_MergeAABB.hlsl` | Reduction 路径第 2 趟：归并成全局 AABB |

## 四条来源路径（BoundsSource Static Switch）

| 来源 | 数据从哪来 | 成本 | 何时用 |
|---|---|---|---|
| `Fixed` | 常量 | 零 | 范围写死的场景 |
| `SoftBounds` | 系统软边界参数 | 零 | 鸟群自约束（**默认**） |
| `SplineBounds` | 样条线 AABB（蓝图 CPU 算） | 零 | 沿样条线铺满的路径效果，美术拉路径 grid 自动跟随 |
| `Reduction` | 运动粒子 AABB（GPU） | 高+延迟 | 密度剧变逃生舱（默认不编译） |

## 快速上手

1. 读 `M_CalcGridBounds.spec.md` §0 + §8（接入清单）。
2. 在 Niagara 里照 §1 建参数、照 §3/§4 搭节点、照 §5 拼矩阵。
3. 默认走 **SoftBounds** 路径（零成本动态跟随），开 N3D debug draw 验收绿框。
4. 沿样条线铺满的效果 → 走 **SplineBounds**（§6.5 蓝图侧 CPU 算 AABB，零成本，美术拉路径所见即所得）。
5. Reduction 是逃生舱，默认不编译进 shader，密度剧变时才用 Static Switch 启用。

## 为什么 Niagara 资产以文本规格为源

Niagara Module Script 是 GUI 节点图（二进制 .uasset），无法纯文本版本控制。故以本规格文档作为设计的单一真相源——照它能 1:1 在编辑器里搭出来，改模块时同步更新规格。
