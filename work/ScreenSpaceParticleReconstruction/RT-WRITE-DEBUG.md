# Grid2D / Render Target 写入调试记录

日期：2026-07-28

## M2 冻结基线与抗锯齿对照

用户已视觉确认粒子→Grid2D→内部 SimRT→材质→Niagara Billboard 全流程正确。运行时将抗锯齿从原 `r.AntiAliasingMethod=4`（TSR）临时切到 `0`，并把 `r.TemporalAA.Quality` 从 `2` 切到 `0` 后，RT 链路、比例和采样仍正常；因此离散亮点属于原始粒子密度输入，不是时序抗锯齿造成的链路错误。

M3 不应靠 TSR/TAA 隐藏颗粒感。Raw 输入必须保留为调试基线，连续烟雾形态由材质内确定性的多尺度空间滤波、密度重映射与指数消光产生。抗锯齿开关只作为 A/B 观察条件，不写入正式项目配置。

## 屏幕比例错位：先查材质 UV 是否真的连上

现场出现“RT 已有图，但像面片向摄像机移动、整体比例放大”的现象。根因不是 CameraOffset，也不是 `WorldToClip`：显示材质里虽然存在 `ScreenPosition` 节点，但自动化脚本把 Texture Sample 的输入写成了 `Coordinates`；UE 5.8 暴露的真实输入名是 `UVs`，连接调用静默失败，Texture Sample 因而回退到 Niagara Sprite 自身 0–1 UV。

正确连接是：

```text
MaterialExpressionScreenPosition.ViewportUV
    -> MaterialExpressionTextureSampleParameter2D.UVs
```

验收不能只数材质节点，必须用 `GetInputsForMaterialExpression` 确认 Texture Sample 的连接源确实是 `MaterialExpressionScreenPosition`。否则面片世界尺寸、深度或 CameraOffset 都会改变 RT 图案的屏幕比例。

同次排查还发现关卡内有两个不同位置的同一主系统实例。重复 Niagara 实例会分别生成粒子和内部 SimRT，视觉结果会叠加；正式验证必须只保留一个可见、可 Tick 的主实例。

PIE 自动化脚本必须在独立 `globals` 字典中执行，并在 `finally` 中清空该字典和执行 Python GC。不得把 PIE `NiagaraComponent`、`World`、MID 或 RT 包装对象留在 MCP Python 的持久全局命名空间，否则 `EndPlayMap` 会因旧 PIE Package 被 `FPyReferenceCollector` 引用而断言。

## 当前结论

`NS_SSPR_ParticleTrails_Main` 的写入基础链路可用：

```text
GPU 粒子
-> Particle Simulation Stage
-> User.SSPR_TrajectoryGrid
-> Grid2D 迭代 Resolve Stage
-> User.SSPR_SimRT（NiagaraDataInterfaceRenderTarget2D）
-> User.SSPR_SimRT.RenderTarget
-> Renderer 材质参数 TrajectoryTexture
```

正式链路不再依赖默认值为 `None` 的 `User.SSPR_TrajectoryRT` 对象参数。此前材质透明度恒为 0 的直接原因就是 Renderer 把 `TrajectoryTexture` 绑定到了这个空对象，而不是绑定 Niagara 内部 RT 的 `RenderTarget` 子变量。

当前正式实现为：

- `SSPR Rasterize Trails`：粒子迭代，写 `User.SSPR_TrajectoryGrid`。
- `SSPR Resolve Grid To Material`：以 `User.SSPR_TrajectoryGrid` 为 Data Interface 迭代源。
- `SSPR_ResolveGridToSimRT`：逐 Cell 读取 Grid 通道 0，覆盖写入 `User.SSPR_SimRT`。
- Renderer：`TrajectoryTexture <- User.SSPR_SimRT.RenderTarget`。
- Grid 与 SimRT 当前均为 2048×2048；SimRT 为 RGBA16F、Bilinear、Niagara 自管理。

最终 PIE 验收：256×256 调试读回中有 63 个非零像素，红通道峰值 118；Niagara Aggregate Status 为 UpToDate，错误 0、警告 0。

在隔离的 Niagara 副本上，把投影代码临时替换为“固定写中心 17×17 白块”，并在 PIE 中运行真实 GPU 帧后，得到：

- Niagara Component：Active，Tick 开启。
- 外部绑定 R32F RT：经显示材质转换到 RGBA8 后有 4 个非零像素。
- 中心像素：R=209。
- 角落像素：R=0。
- 材质桥校准：黑色 R32F 输入得到 0；白色 R32F 输入得到 R=209。

这证明 Simulation Stage、Grid2D 写入、外部 RT 绑定和材质采样四层都能工作。

调试完成后，隔离副本和临时 Actor 已删除，正式 Niagara 资产没有保留探针修改。

## 不要使用的验证方式

### 1. 不要直接 CPU 读取 RTF_R32F

当前 UE 版本中：

```text
read_render_target_raw_pixel
read_render_target_pixel
```

对 `RTF_R32F` 的读回不可信。实测清屏值为 0、0.25、1 时，R 通道都返回 1。

因此不能用它判断 Grid 是否非零。

正确方式：

```text
R32F 源 RT
-> 一个只负责显示/拷贝的材质
-> RGBA8 调试 RT
-> CPU 读取 RGBA8
```

### 2. 不要把 FillTexture2D 返回 true 当作写入成功

实测：

```text
Grid2DCollection.fill_texture2d(...) == true
```

但输出仍然全黑。

原因是系统内可能存在多个编译期 Grid2D DI 克隆，`FillTexture2D` 可能选到不是当前运行实例的克隆。它的返回值只表示调用被接受，不代表复制的是正确实例。

旧外部 RT 探针验证时可以读取绑定在 Niagara Component 上的：

```text
User.SSPR_TrajectoryRT
```

正式内部链路应扫描 PIE World 中 Niagara 自动创建的 RGBA16F RenderTarget，并通过显示材质转成 RGBA8 后读回；不要再向 `User.SSPR_TrajectoryRT` 注入临时纹理。

## 推荐调试顺序

### A. 先校准显示桥

把同一个显示材质分别输入纯黑和纯白 R32F RT，再输出到 RGBA8。

验收：

- 黑输入必须得到 0。
- 白输入必须得到明显非零。

这一步排除“材质参数没绑上”和“读回 API 失真”。

### B. 固定中心写入

临时把 Simulation Stage 改为固定写中心小白块，不使用：

- 相机矩阵；
- 粒子 World Position；
- UV 合法性判断。

验收：

- 中心非零；
- 四角为 0。

如果失败，检查 Stage 执行、Grid 用户参数和 RT 绑定。

### C. 粒子位置写入

固定中心通过后，再恢复粒子位置，并暂时取消复杂卷积。

验收：

- 非零像素随粒子运动变化；
- 停止粒子后按当前帧 Clear 归零。

### D. 最后恢复相机投影

依次开启：

1. WorldToClip；
2. `Clip.W > 0`；
3. 屏幕范围判断；
4. Splat 半径；
5. 最终烟雾材质。

每次只增加一层，出现全黑时即可定位到刚加入的判断。

## 运行环境要求

GPU Niagara 的最终判断必须在 PIE 或真实 Game World 中完成。

仅在 Editor World 中调用：

```text
component.advance_simulation(...)
```

不能作为 GPU Simulation Stage 是否执行的最终证据。实测 Editor World 探针全黑，而同一资产进入 PIE 后写入正常。

## 当前编译状态

`NS_SSPR_ParticleTrails_Main`：

- Aggregate Status：UpToDate
- Errors：0
- Warnings：0
- Particle Simulation Stage：UpToDate
- Particle GPU Compute：UpToDate

## 材质函数自动化：编译绿色不等于 Pin 绑定正确

UE 5.8 中，对同一 Material Function 资产反复删除全部表达式并原地重建，可能残留旧 `FunctionInput` GUID。调用节点会出现同名输入，自动化按名字连接时可能命中已失效的 Pin；结果是父材质编译无错误，但真实纹理输入仍为 0。

调试与发布规则：

1. 破坏性修改函数接口时创建新的干净资产/版本目录，不继续覆盖污染资产。
2. 反射读取函数调用的输入列表，要求输入名唯一且与 Spec 完全一致。
3. 用已知纯白纹理跑 Processed 与 Raw 两条端到端 Gate；两条路径都必须得到全非零输出。
4. 再接回 Niagara 内部 SimRT，按实际非零像素量选择活动目标，避免读到编辑器残留的同规格旧 RT。
