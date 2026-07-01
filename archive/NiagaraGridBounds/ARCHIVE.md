# NiagaraGridBounds 归档记录

归档日期：2026-06-12
状态：已完成，归档。

## 项目结论

`NiagaraGridBounds` 是一个通用 N3D / Neighbor Grid 3D 网格范围模块，用于为 Niagara 中依赖 Neighbor Grid 3D 的系统计算并设置稳定的 Grid Bounds。项目已完成，后续作为可复用技术资产和经验记录保留。

## 三个关键坑 / 卡点

### 1. Rasterization Grid 数据无法直接流通到 CPU

卡点：Rasterization Grid 里的数据不能直接顺畅回传 / 流通到 CPU 侧，导致 CPU 侧无法直接拿到需要的网格结果。

解决：额外建立一个 `Vector Array`，通过数组把需要的数据传过去，绕开 Rasterization Grid 到 CPU 的流通限制。

经验：Niagara GPU / Grid 数据结构不要默认假设能直接给 CPU 使用。需要 CPU 参与后续逻辑时，应提前设计一条明确的数据出口，比如数组、参数集合或蓝图可读的数据承载层。

### 2. R3D Reset Value 的清理时机：不是每帧一次，也不是所有 stage；是在输出 stage 的 PreStage 按条件清

卡点：一开始以为 R3D 的 `Reset Value` 是每帧清一次，于是设计为：

- `min` 初始给 `100000`
- `max` 初始给 `-100000`
- 因为自带 `Reset Value` 只能选一个值，所以尝试用一个 stage 手动刷初始值

修正后的源码结论：R3D 的自动 clear 发生在 `FNiagaraDataInterfaceProxyRasterizationGrid3D::PreStage`，不是每帧固定清一次，也不是所有 stage 都清。完整触发条件是：

```cpp
if (Context.IsOutputStage() && NumTotalCells > 0 && InstanceData.ClearBeforeNonIterationStage)
{
    const FUintVector4 ResetValue(InstanceData.ResetValue, InstanceData.ResetValue, InstanceData.ResetValue, InstanceData.ResetValue);
    AddClearUAVPass(GraphBuilder, InstanceData.RasterizationTexture.GetOrCreateUAV(GraphBuilder), ResetValue);
}
```

也就是必须同时满足：

- `Context.IsOutputStage()`：当前 stage 把该 Rasterization Grid 当作写入输出；纯读 stage 不触发。
- `NumTotalCells > 0`：grid 有效。
- `InstanceData.ClearBeforeNonIterationStage`：开启清理开关。

对应源码锚点：`C:\UE58\Engine\Plugins\FX\Niagara\Source\Niagara\Private\NiagaraDataInterfaceRasterizationGrid3D.cpp`：

- `ResetData`：约第 `1071` 行，整体 reset 路径；第 `1080~1081` 行同样用 `ResetValue` 调 `AddClearUAVPass`。
- `PreStage`：约第 `1084` 行。
- 输出 stage 条件 clear：约第 `1136~1140` 行。
- `ResetValue` 编码：约第 `991` 行，`InstData->ResetValue = FMath::FloorToInt(NewResetValue * InstData->Precision)`。

所以当手动刷完初始值后，进入下一个真正写 grid / 做原子操作的 output stage，如果 `ClearBeforeNonIterationStage` 为 true，就会在该 stage 的 `PreStage` 再执行一次 clear，导致之前写入的初始值被刷掉。问题不是“每个 stage 都 reset”，而是“每个满足条件的输出 stage 都可能在 PreStage reset”。

从函数使用上看，可以这样判断：

- `GetFloatValue`：只读 grid，不会让当前 stage 成为该 grid 的 output stage，因此不会触发这个 PreStage clear。
- `SetFloatValue`：写 grid，会让该 grid 成为 output，满足条件时会触发 PreStage clear。
- `InterlockedMin` / `InterlockedMax`：原子写 grid，同样属于写输出，满足条件时会触发 PreStage clear。

这也是这次 bug 的关键：读 stage 安全，真正危险的是后续 `SetFloatValue` 或 `InterlockedMin/Max` 这类写 stage。手动初始化如果放在前一个 stage，后一个写 stage 进入前可能又被 clear 掉。

最终方案：放弃“自己用 stage reset 出 min/max 初值”的路线，改为 reset 一个很大的值；求 min 时对值全部取反，用符号变换绕开“reset value 只能一个值”的限制。

额外注意：`ResetValue` 会乘 `Precision` 后编码成 int，设置 reset 值时要考虑 `值 × Precision` 不能溢出 `int32`。

经验：Niagara Rasterization Grid 3D 的 reset 语义要按 **output stage + PreStage 条件 clear** 理解。凡是依赖跨 stage 保留 grid 值的设计，都必须确认下一段是否会把该 grid 作为输出、`NumTotalCells` 是否有效、`ClearBeforeNonIterationStage` 是否开启，否则会出现“手动写入看似成功，但进入真正写入 stage 前又被清掉”的问题。

### 3. Neighbor Grid 3D 算 transform 时出现 float32 / LWC 精度崩塌

现象：`center`、`extent`、debug 画框都正常，偏偏算出来的 `unit pos` 崩掉，甚至出现几万级结果。

#### 为什么 center / extent / 画框都正常

这三者正常，是因为它们没有触发最危险的精度地板：

- `center`：几十万级大数本身，float32 表示绝对值没问题；ULP 约 `0.03`，画框误差几厘米看不出来。
- `extent`：虽然来自 `max - min`，但结果是几千级，相对误差肉眼无感。
- debug 画框：用 `center ± extent` 画，仍然是大数位置上的框，几厘米误差不会影响观察。

真正崩的是 `unit pos`：

```text
unit = (pos - min) / size
```

它需要得到 `0~1` 的归一化坐标。有效信息全在 `pos - min` 这个小差值里，但 `pos` 和 `min` 都是几十万级大数，float32 在这个量级已经吃掉了大量尾数。

#### float32 精度地板

float32 只有 23 bit 尾数，约 7 位十进制有效数字。

当世界坐标达到 `5×10^5` 时，已经占掉 6 位；这个量级下相邻可表示 float 的间隔约 `0.03`。

如果 extent 约 `2000`，unit 精度需要分辨 `1/extent = 0.0005` 的相对变化，对应世界坐标约 1 单位的位移。虽然 1 单位本身还大于 ULP，但 `(pos - min)` 是两个大数相减，低位有效信息会被大基数挤掉，平移项相对失效。

#### 为什么会算成几万

矩阵乘法展开类似：

```text
unit = pos * m00 + m30
m00 = 1 / size
m30 = -min / size
```

当 `m30` 因大坐标精度崩塌而失真，无法正确抵消 `pos * m00` 时，结果近似只剩：

```text
pos * (1 / size) = 几十万 / extent = 几万
```

所以这不是随机抖动。随机抖动只会让 unit 在 `0~1` 附近抖；这里是结构性的平移失配，是典型 LWC 症状。

#### 根治方案：把计算搬到以 center 为原点的局部空间

既然 GPU 已经算出了 `center`，就直接用它闭环：

1. 粒子位置先减 center：

```text
localPos = pos - center
```

这样位置量级从几十万压回 `±extent`，也就是几千级。

2. Grid 的 `WorldBBox` 不再设为世界空间 `[worldMin, worldMax]`，而是设为居中的局部空间范围：

```text
[-extent * 1.x, +extent * 1.x]
```

3. 用 `localPos` 转 unit。

此时参与矩阵 / unit 计算的值都在几千级，float32 的 23-bit 尾数可以全部用于有效信息，精度恢复正常。

经验：精度崩塌的本质是“大基数 + 小增量，基数吃光尾数”。减 center 后基数归零，只剩 `±extent` 的纯增量，精度立刻恢复。这也是 UE LWC 体系的核心思路：不要在 float32 里做“大数 - 大数”，应先把基准平移掉。

## 后续引用建议

如果未来要把这个项目转成作品集内容，不建议直接使用工作区原项目。更稳的方式是抽象出个人可公开 demo，例如：

- Adaptive Neighbor Grid Bounds for GPU Particles
- Spline-Guided Niagara Grid System
- Dynamic Bounds Toolkit for Niagara N3D

重点展示：N3D Bounds 抽象、Grid / output-stage PreStage reset 机制、LWC 精度处理、Niagara 工具化封装。


