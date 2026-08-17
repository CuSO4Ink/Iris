# UE 5.8 Niagara 屏幕 Raster / MCP 实战排坑手册

- 日期：2026-07-29
- 适用工程：`precisefluid`
- 适用主线：`/Game/SSPR_Validation/M2/AnisotropicSplat_V2`
- 当前验证系统：`NS_SSPR_AnisotropicSplat_Main`
- 当前验证关卡：`L_SSPR_AnisotropicSplat_Validation`
- 当前基线：V2 G0～G3 已通过，Niagara 编译零错误、零警告

本文不是算法规格，而是本项目在“GPU 粒子 → 屏幕投影 → 原子密度场 → Niagara 自管 SimRT → Renderer 材质”落地过程中踩过的操作坑、判断误区和推荐排查顺序。

相关文档：

- 算法规格：`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`
- 主规格：`WISPY-FLUID-SPEC.md`
- 旧 Grid/RT 调试结论：已收敛到本文与 `LOG.md`
- 时间线：`LOG.md`

## 1. 当前确认可用的正式结构

```text
Particle Spawn / Update
    -> Solve 产生本帧位置变化
    -> 清零 Velocity 前缓存 ScreenDeltaUV / Flow 数据
    -> 隐藏粒子 Renderer 保活 Position 与 ScreenDeltaUV

SSPR Rasterize Trails（粒子迭代 Simulation Stage）
    -> 从 Particles.Position 用当前视图矩阵重新投影中心
    -> 用 Particles.SSPR_ScreenDeltaUV 决定高斯长轴
    -> RasterizationGrid3D(2048×2048×1) Q10 整数原子累加
    -> 只写 User.SSPR_DensityRaster，不写 Particles.*

SSPR Resolve Grid To Material（Grid2D 迭代 Simulation Stage）
    -> Grid2DCollection 只提供稳定的 2048×2048 Dispatch 域
    -> 读取 DensityRaster
    -> 覆盖写 Niagara 自管 User.SSPR_SimRT

Emitter SourceMode Sprite Renderer
    -> TrajectoryTexture <- User.SSPR_SimRT.RenderTarget
    -> 材质使用 ScreenPosition.ViewportUV 采样
```

`RasterizationGrid3D` 在这里不是三维流体求解器，只使用 Z=0 的单层，目的是复用 UE 5.8 已验证的整数原子加法。

## 2. 最重要的四条规则

### 2.1 Raster Stage 不得写任何粒子属性

错误做法：

```text
Custom HLSL.OutMark -> Particles.SSPR_WriteMark
```

这会让 Stage 生成元数据变为：

```text
WritesParticles=True
```

后果有两种：

- Partial Particle Update 开启时，外部 Raster UAV 写入可能无效。
- 强制 Full Particle Update 后，未显式保留的粒子属性可能被默认值覆盖，Position/ScreenUV 等数据被破坏。

正确做法：

```text
Custom HLSL.OutMark
    -> Output.SSPR_RasterizeWhiteParticles.OutMark
```

即写模块局部输出，只用于维持 Scratch 图数据流。正式生成元数据必须是：

```text
SSPR Rasterize Trails
WritesParticles=False
Outputs to: User.SSPR_DensityRaster
```

### 2.2 Custom HLSL 读了粒子属性，不代表编译器一定会保留它

本次最隐蔽的根因是：生成的 Stage1 HLSL 明明调用了

```text
Context.MapSimStage1...Particles.Position
```

但 `LoadUpdateVariables` 最初只从粒子数据集加载：

```text
Age
Lifetime
UniqueID
```

Position 和 ScreenDeltaUV 已被编译器裁掉，所以运行时读到全零。表现为：

- 所有粒子集中写到一个像素；
- 或投影合法性检查全部失败，RT 全黑；
- 缓存 ScreenUV 时，全部粒子落在 `(0,0)`。

当前工程的解决办法是保留 Renderer 0 作为属性保活器：

- `bIsEnabled=true`；
- `SourceMode=Particles`；
- `RendererVisibility=1`，与粒子默认 VisibilityTag 不匹配，因此不实际显示；
- `PositionBinding=Particles.Position`；
- `SpriteSizeBinding=Particles.SSPR_ScreenDeltaUV`。

Renderer 1 继续作为真正的 Emitter SourceMode 显示面片。

验收不能只看 Renderer Data，必须检查最新生成 HLSL 的 `LoadUpdateVariables`，确认 Stage1 出现：

```text
Particles.Position.x/y/z = InputDataFloat(...)
Particles.SSPR_ScreenDeltaUV.x/y = InputDataFloat(...)
```

### 2.3 改完 Renderer 后必须显式重新编译

`SetRendererData` 返回成功、再次读取属性也显示新值，不代表 GPU Compute Script 已失效并重编译。

本次曾出现：

- Renderer 0 已显示 `bIsEnabled=true`；
- 但 GPU HLSL 仍只存 Age/Lifetime/UniqueID；
- RT 仍然是单点。

必须显式执行：

```text
NiagaraScratchPadService.apply_changes(System)
检查 compile messages
保存 System 资产
重新绑定或 Reinitialize 关卡内 NiagaraComponent
```

重新编译后，原始读回才从单像素 9912 跃迁到约 8129 个分散像素。

### 2.4 GPU 修改和 GPU 读回必须拆成不同 MCP 请求

同一个 MCP `execute_python_code` 请求会长期占用编辑器线程。若在同一次请求里完成：

```text
修改资产 -> 编译 -> 激活组件 -> 立即读 RT
```

渲染线程可能没有机会执行新帧，得到的全黑是假阴性。

正确流程：

1. 请求 A：修改、Apply、编译、保存。
2. 请求 B：重新绑定组件、Reinitialize、Activate。
3. 让编辑器正常产生 GPU 帧。
4. 请求 C：读取运行时 RT。

不要用同请求内的 `advance_simulation` 作为 GPU Simulation Stage 已运行的最终证据。

## 3. Simulation Stage 与 Raster 写入坑

### 3.1 Partial Particle Update 与外部 UAV 写入冲突

当 Stage 同时被识别为粒子写入 Stage 时，`PartialParticleUpdate=True` 下 RasterizationGrid 外部写入曾完全不生效。把 `bDisablePartialParticleUpdate=true` 后，固定写入探针立即出现非零，证明冲突真实存在。

但这不是正式修复，因为 Full Update 会引入粒子属性覆盖风险。正式方案是让 Raster Stage 根本不写粒子，回到 `WritesParticles=False`。

### 3.2 Parameter Map 主链断开会让 Scratch 看似存在、实际不执行

把粒子输出改成模块局部输出时，曾删除旧 MapSet 并重建，结果 Parameter Map 主链断开：

```text
InputMap -X-> MapSet -X-> Output Module
```

随后出现异步编译错误、NiagaraComponent Inactive。

正确连接必须同时存在：

```text
Input Node.Input -> MapSet.Source
MapSet.Dest -> Output Node.OutputMap
CustomHLSL.OutMark -> MapSet.Output.<ModuleName>.OutMark
```

Scratch 图检查不能只看 Custom HLSL Pin；必须同时枚举整个模块的节点和连接。

### 3.3 不能在同一 Stage 读写同一个 RenderTarget

UE 会直接报告：

```text
RenderTarget is read and wrote in the same stage, this is not allowed,
read will be invalid
```

不应在粒子级 Writer 内对同一 RT 做 Load/Modify/Store 来实现衰减。正确办法是：

- 当前正式主线：当前帧 Raster Grid 自动清空，再 Resolve 到 SimRT；
- 若将来需要历史：使用独立 Current/History 资源和分离 Pass，不在同 Stage 原地读写。

### 3.4 Clear 的责任必须唯一、明确

“RT 不消散”通常不是粒子 Lifetime 失效，而是写入目标从未清理。

当前正式规则：

- `RasterizationGrid3D.clear_before_non_iteration_stage=True`；
- Raster Stage 每帧只累加当前存活粒子；
- Resolve Stage 对整个 2048² Dispatch 域逐像素覆盖写 SimRT；
- 不依赖材质透明混合或旧像素自然消失。

如果 Grid Clear 关闭，原子累加会快速铺满并可能溢出；如果 Resolve 没覆盖全域，SimRT 会留下旧帧残影。

### 3.5 Raster 原子值是整数，不是普通浮点密度

当前使用 Q10 固定点：

```text
ContributionInt = round(Weight * DensityPerParticle * 1024)
AtomicAdd(IntGrid, ContributionInt)
ResolveDensity = DensityInt / 1024
```

直接把高密度浮点概念塞进整数网格，会出现饱和或错误解释。诊断中出现过 `-65504`，它不是有效负密度，而是过量累加/格式解释后的饱和值信号。

正式核必须限制：

- `MaxLengthPx`；
- 高斯 Cutoff；
- 单粒子贡献；
- 最大循环边界。

## 4. 投影与属性数据坑

### 4.1 不要盲信缓存 ScreenUV

早期正式高斯使用 `Particles.SSPR_ScreenUV`，结果只有 8 个像素或全部集中在角落。合法性统计显示全部 9912 粒子都“在 0～1 范围内”，是因为默认 `(0,0)` 本身也通过合法性判断。

因此：

- “合法 UV 数量等于粒子数”不能证明投影正确；
- 必须检查 UV 分布、非零像素数量和像素坐标范围；
- 当前中心位置在 Raster Stage 内从持久化 Position 重新投影。

### 4.2 HLSL 编辑文本和最终 GPU HLSL 不是一回事

Scratch 中写：

```hlsl
mul(float4(WorldPos, 1), View.WorldToClip)
```

Niagara Translator 最终可能生成：

```hlsl
mul(float4(LWCToFloat(WorldPos), 1), transpose(PrimaryView.WorldToClip))
```

判断矩阵、LWC 转换和参数绑定时，应以 `LastHlslTranslationGPU` 为准，不以 Scratch 文本猜测。

### 4.3 屏幕中心和运动方向应分别处理

当前稳妥做法：

- 中心：Stage1 直接投影当前 `Particles.Position`；
- 长轴：读取持久化的 `Particles.SSPR_ScreenDeltaUV`；
- 不读取清零后的 `Particles.Velocity`。

参考系统在 Solver 后把 Velocity 设为 0。该操作保留本帧已经更新的位置，但下游再读 Velocity 只能得到零。因此 FlowDelta/ScreenDelta 必须在清零前缓存。

### 4.4 Camera-facing 面片与 RT 投影必须使用同一屏幕 UV 语义

材质中 Texture Sample 的真实输入名是 `UVs`，不是脚本曾使用的 `Coordinates`。错误连接会静默失败，Texture Sample 回退到 Sprite 自身 UV，表现为：

- 比例放大或缩小；
- 像面片向摄像机移动了一段距离；
- 中间截断；
- 面片旋转时图像不对齐。

正确连接：

```text
ScreenPosition.ViewportUV -> TextureSample.UVs
```

验收时用反射读取材质表达式输入连接，不要只看节点数量或“材质编译绿色”。

### 4.5 屏幕边缘不能只靠最终 Clamp

上游卷积如果直接采样 `UV + Offset`，越界 Tap 可能 Wrap 或重复边缘。正确做法：

- RT Address X/Y 明确设为 Clamp；
- 每个卷积 Tap 先判断半像素安全范围；
- 越界 Tap 贡献 0；
- 最终 Card 再增加 1～2 px 平滑安全边。

## 5. RT 与读回验证坑

### 5.1 运行时会残留多个同规格 RT，不能看到一个就当成当前输出

每次重新绑定 NiagaraComponent 都可能创建新的托管 RT；旧的 `TextureRenderTarget2D_12`、`_19` 等仍留在内存中。

典型误判：

- 旧 RT 有 8 个非零像素；
- 新 RT 全黑；
- 只读取第一个候选，就误以为最新修改仍然输出 8 个像素。

正确做法：

- 列出所有候选的对象路径、创建顺序、尺寸和统计；
- 结合当前 NiagaraComponent OverrideParameters 找到活动 DI；
- 重新绑定后优先检查新出现的 RT；
- 不把旧实例结果写入正式结论。

### 5.2 256² 缩小探针会漏掉稀疏 2048² 单像素

曾把 2048² SimRT 缩小到 256² 后读回。固定写入一个 Raster 像素时，下采样可能完全错过该点，得到全黑。

对于稀疏点验证，应直接读取原分辨率像素或原始区域。缩小图适合视觉预览，不适合证明单像素写入失败。

### 5.3 `ReadRenderTargetRawPixelArea` 的区域参数存在实现陷阱

当前 UE 5.8 的实现把 API 形态中的 `MaxX/MaxY` 传成了 Width/Height 语义。按普通 Min/Max 理解会读错区域或越界。

项目探针采用四象限读取，并按实际实现传参。复制脚本时不要自行改回常规矩形 Max 坐标语义。

### 5.4 R32F 的 CPU 读回曾不可信

旧链路实测对 `RTF_R32F` 使用普通 `read_render_target_pixel/raw_pixel` 时，清屏为 0、0.25、1 都可能读成相同结果。

旧外部 R32F 调试目标应：

```text
R32F -> 显示/拷贝材质 -> RGBA8 调试 RT -> CPU 读取
```

当前 Niagara 自管 RGBA16F SimRT 的原始读回已通过校准，但仍需先用已知黑/白输入验证读回桥。

### 5.5 `FillTexture2D == true` 不代表复制了运行实例

系统中可能存在多个编译期 Grid2D DI 克隆。`fill_texture2d()` 返回 true 只表示调用被接受，不保证选中当前运行实例。

正式验证应读取 Niagara 实际管理的 SimRT，不要把 FillTexture2D 的 bool 当成数据正确性 Gate。

## 6. MCP、Python 与编辑器生命周期坑

### 6.1 MCP Gateway 必须单实例、单请求串行

本次出现过 4 个卡死的旧 `mcp_gateway.ps1`。常见原因：

- 上一请求超时，但 PowerShell/HTTP 请求仍在等待；
- 同时启动多个 Gateway 请求；
- 编辑器主线程正被编译或长 Python 调用占用；
- 调用方终止等待，却没有终止子进程。

后果包括：

- 重复连接编辑器；
- 多个请求互相阻塞；
- 内存和句柄持续增长；
- 无法判断输出属于哪次操作。

规则：

1. 一次只运行一个 Gateway 请求。
2. `exec` 返回 running cell 时，只用 wait 继续等待，不重复启动相同命令。
3. 请求完成后检查明确的 OutFile。
4. 需要清理旧进程时，先按 PID、命令行和启动时间确认目标，不做宽泛结束。

### 6.2 MCP 返回成功不等于 UE 资产状态成功

Gateway 外层常见结果：

```json
{
  "ok": true,
  "data": {
    "success": true,
    "output": "..."
  }
}
```

它只能证明工具调用完成。正式 Gate 还必须检查：

- `apply_changes == true`；
- Compile Messages 为空；
- Aggregate Status 为 UpToDate；
- `bIsCompiling=false`、`bIsStale=false`；
- 保存成功；
- 运行时原始 RT 有合理数据；
- 用户视口视觉正确。

### 6.3 Python UObject 引用会阻止 PIE Package GC

曾触发：

```text
Object 'Package /Temp/UEDPIE_0_...' from PIE level still referenced
FPyReferenceCollector
```

根因是 MCP Python 持有 PIE World、NiagaraComponent、Actor、MID 或 RT 包装对象，结束 PIE 后旧 Package 无法 GC。

规则：

- PIE 脚本使用独立、短生命周期的局部 `globals` 字典；
- `finally` 中删除/清空 UObject 引用；
- 执行 Python GC；
- 不把 PIE UObject 放进模块全局、闭包或长期缓存；
- 不在 PIE 退出过程中继续访问旧对象。

### 6.4 不要把选择 Actor、切窗口或点按钮混进技术脚本

本项目约定：未经用户明确允许，不使用电脑控制或鼠标自动化。需要界面交互时停止并给出手动步骤。

技术脚本只做：

- 资产读写；
- 编译；
- 组件 Reinitialize/Activate；
- 属性与 RT 统计读取。

这样可以避免焦点错误、误选对象、保存错误关卡以及不可复现的 UI 状态依赖。

## 7. 编译与源码修改坑

### 7.1 UBA “Low on memory” 可能是提交内存耗尽，不是物理内存真的用了 237 GB

日志示例：

```text
UbaSessionServer - Killed process ... Low on memory (237.4gb/237.4gb)
```

这里通常指系统 Commit Charge 接近上限，可能由多个 UnrealEditor、编译器、UBA Agent、旧 Gateway 或过小页面文件共同造成。

处理顺序：

1. 确认没有重复 UnrealEditor、UBT、cl、UbaAgent、Gateway。
2. 关闭旧编辑器后再做插件全量编译。
3. 必要时扩大页面文件或降低并行编译数。
4. 不要在内存压力下不断重试同一编译，会制造更多残留进程。

### 7.2 Hot Reload patch 成功不代表正式 DLL 已更新

插件目录中可能同时存在：

```text
UnrealEditor-VibeUE.dll
UnrealEditor-VibeUE.patch_0.exe
UnrealEditor-VibeUE.patch_1.exe
```

必须核对正式 DLL 的时间戳和大小，并确认新 Python API 在重启后的反射中存在。不要只看到 patch 文件生成就认为源码改动已正式加载。

### 7.3 改 VibeUE 源码前先备份，编译后验证 API 反射

本次为 `NiagaraScratchPadService` 增加 RasterizationGrid3D User Parameter 创建接口。正确流程：

1. 引擎目录本地 Git 保存修改前基线。
2. 修改头文件与 cpp。
3. 关闭编辑器或确保不会与正式 DLL 冲突。
4. 完整编译目标模块。
5. 检查 DLL 时间戳。
6. 启动编辑器，通过 Python `hasattr`/实际调用验证反射。
7. 再开始修改 Niagara 资产。

## 8. 材质与资产自动化坑

### 8.1 材质编译绿色不代表 Texture/Function Pin 连对

自动化传错输入名时，连接可能静默失败；材质仍能用默认输入编译成功。

必须验证：

- Texture Sample `UVs` 的真实来源；
- Material Function Call 每个输入的连接源；
- Renderer Material Parameter 的 Niagara 变量和 Child Variable；
- 已知黑/白纹理的端到端输出。

### 8.2 原地重建 Material Function 会残留旧 FunctionInput GUID

反复删除表达式并在同一函数资产内重建接口，UE 5.8 可能保留旧 GUID，调用节点出现同名输入，脚本按名字连接到失效 Pin。

破坏性接口变更应：

- 新建干净版本目录或新函数资产；
- 检查输入名唯一；
- 用已知白纹理跑 Raw/Processed Gate；
- 污染原型只归档，不继续覆盖。

### 8.3 复制 UE 目录不会自动保证副本完全自包含

V1 复制为 V2 后，材质实例 Parent、Material Function Call、Niagara Renderer 材质仍可能指回旧目录。

复制后必须显式扫描依赖并修正：

- Material Instance Parent；
- Material Function Call；
- Niagara Renderer Material；
- 关卡 Actor 引用；
- Blueprint 默认资产引用。

### 8.4 函数名字、兼容输入和实际算法必须保持一致

V2 为避免重建 FunctionInput GUID，在不修改接口的前提下把 `MF_SSPR_MipPyramidDensity` 内部替换成了 LOD0 7×7/13×13 空间核。这样现有调用节点不需要重连，但产生了两个技术债：

- 函数名字仍写 Mip，实际不再读取 Mip；
- `MediumMipBias`、`BodyMipBias` 仍在接口和 MI 中，但对结果没有作用。

短期兼容改动可以保留旧接口，正式封版不能长期让名称和行为分离。正确收口方式是在新的干净函数资产中建立准确接口、重新绑定父材质、跑白图和真实 SimRT Gate，再把兼容函数移动到 Archive；不要在已发布函数中删除输入并原地重建。

本次还确认：关闭自动 Mip、改用 LOD0 是质量与确定性选择，但整片闪烁最终由 Fixed Tick 解决。排查记录必须区分“同时发生的改动”和“经 A/B 确认的根因”。

## 9. 常见现象速查

| 现象 | 最可能根因 | 第一检查项 |
| --- | --- | --- |
| RT 全黑 | GPU 尚未跑帧、当前 RT 选错、投影全部无效、Raster Stage UAV 写入失败 | 分请求执行；找最新 RT；固定中心写入 |
| RT 全红/全白 | Clear 关闭、密度尺度过大、Resolve/材质阈值饱和 | Grid Clear、Q10 Scale、Raw 数值范围 |
| 只有一个高值像素 | 所有 Position/ScreenUV 被裁剪成默认零 | Stage1 `LoadUpdateVariables` |
| 只有少量像素，如 8 个 | 读到旧 RT，或所有粒子集中少数默认坐标 | RT 对象路径和创建顺序 |
| 均匀灰色面片 | 材质采样默认值、纹理没绑定、密度被常量路径覆盖 | Renderer Child Binding 与 Texture Sample |
| 粒子正常但 RT 不消散 | 写入目标没有每帧 Clear/全域覆盖 | Raster Clear 与 Resolve Dispatch |
| 左右转相机出现横向撕裂 | 使用未重投影的历史 RT，或线性地址衰减形成水平条 | 是否仍有 History/原地衰减 |
| 图像比例比粒子大一倍 | 材质没有使用 ViewportUV，回退到面片 UV | `ScreenPosition.ViewportUV -> UVs` |
| 边缘向外泛色 | 卷积 Tap 越界 Wrap/Clamp 重复边缘 | 每 Tap 合法性与 Address Mode |
| PIE 退出断言 | Python 仍持有 PIE UObject | `FPyReferenceCollector` 引用链 |
| 编译不断被 UBA Kill | Commit Charge 到上限、并行/残留进程过多 | 进程、页面文件、并行度 |
| 修改 Renderer 后行为没变 | GPU Script 未重新编译或组件仍使用旧 DI | Apply/Compile/Save/Rebind |

## 10. 推荐的最短排查顺序

以后再遇到 RT 异常，按以下顺序，不要直接修改最终材质：

### 第 1 步：确认运行对象唯一

- 验证关卡只保留一个正式 Niagara 主实例。
- 排除旧 V1、旧 Ping-pong Actor 和 Preview Actor。
- 确认组件 Active、Tick 正常。

### 第 2 步：确认编译和 Stage 元数据

- Aggregate Status = UpToDate。
- Errors = 0，Warnings = 0。
- Raster Stage `WritesParticles=False`。
- Output Destination 只有 `User.SSPR_DensityRaster`。

### 第 3 步：确认粒子属性真的进入数据集

检查最新 GPU HLSL：

- Stage0 Store 中存在 Position/ScreenDeltaUV。
- Stage1 Load 中存在 Position/ScreenDeltaUV。
- 不只检查 Scratch Pin 或 Custom HLSL 调用文本。

### 第 4 步：固定原子写入

临时在 Grid 中心执行一次或每粒子一次 `InterlockedAdd`：

- 中心必须非零；
- Clear 开启时数值应稳定；
- Clear 关闭时数值会逐帧增长，只用于诊断。

### 第 5 步：每粒子单点写入

从 Position 直接投影，每粒子只写一个像素：

- 非零像素数应达到粒子数的同量级；
- 总原子计数应接近有效粒子数；
- 若总数正确但只有一个像素，属性被裁剪或坐标坍缩。

本次通过值：

```text
约 9917 次写入
约 8129 个非零像素
```

### 第 6 步：恢复正式高斯

恢复长短轴、高斯权重、边界判断和 Q10 累加。

本次 G0～G3 基线：

```text
2048×2048
Nonzero = 41,353
R Max ≈ 4.203125
R Sum ≈ 23,532.886
```

### 第 7 步：最后检查材质

- Raw Density Debug 先直出。
- 再接 Filament/Medium/Body。
- 最后接消光、颜色、边缘和深度融合。
- TAA/TSR 只做最终 A/B，不用来掩盖 Raw 密度错误。

## 11. 调试修改的收尾规则

每次探针结束必须完成：

1. 恢复正式 HLSL，不把固定中心/单点探针留在资产中。
2. 恢复 `clear_before_non_iteration_stage=True`。
3. 确认 Raster Stage 不写 Particles。
4. Apply、编译、保存。
5. Rebind/Reinitialize 运行组件。
6. 原始 RT Gate。
7. Compile State Gate。
8. 保存 `.uasset` 基点到 `Saved/CodexBackups`。
9. 更新 Spec 和 LOG。
10. 由用户完成视口动态视觉 Gate。

当前基点备份：

```text
Saved/CodexBackups/
NS_SSPR_AnisotropicSplat_Main_G0-G3_20260729_1552.uasset
NS_SSPR_AnisotropicSplat_Main_before_stable_lod0_20260729.uasset
M_SSPR_AnisotropicSplat_Display_before_stable_lod0_20260729.uasset
MF_SSPR_MipPyramidDensity_before_stable_lod0_20260729.uasset
MI_SSPR_AnisotropicSplat_HQ_before_continuity_tune_20260729.uasset
```

这些是修改前和阶段性备份，不是 Fixed Tick/LOD0/最新 MI 的最终封版快照。完整 V2 快照必须在 G4 视觉 Gate 通过后重新建立。

## 12. 可变时间步会让整张流体面片忽明忽暗

现象：Niagara 运行时，松开右键静止观察会整片闪烁；按住右键持续移动视角反而稳定。关闭 SimRT Mip、固定材质亮度后仍可出现。

本项目确认的根因是渲染帧间隔变化被直接送进 Niagara。粒子生成、Lifetime、位移以及当帧 Raster 密度覆盖共同依赖 `DeltaTime`；视口交互改变帧节奏后，单位帧写入 SimRT 的粒子覆盖量发生明显变化，经过大范围烟雾卷积后就表现成整片亮度脉动。

V2 高品质基线必须使用：

```text
Niagara System
Fixed Tick Delta = true
Fixed Tick Delta Time = 0.01667 s（60 Hz）
```

UE 5.8 的 `FNiagaraSystemSimulation::Tick_GameThread` 会累积引擎时间，并按固定步长补做 0～N 次模拟，而不是把不规则的渲染帧 `DeltaSeconds` 直接用于一次模拟。这能稳定 Spawn、Solve 和每帧 Raster 密度。

注意：Fixed Tick 解决的是模拟步长稳定性，不替代以下检查：

- 视口仍建议开启 Realtime；
- Niagara GPU 计算量过高时仍可能丢帧；
- RT 同帧读写、错误 Mip 或 TAA/TSR 重投影问题仍需单独排查；
- 调整固定频率时要重新检查性能，低帧率下可能触发多次补步。

## 13. 不要反复通过 `set_asset(None)` 重绑同一个 Niagara System

现象：System、Renderer 和材质均编译正常，但多次 Apply 后为了“彻底 Rebind”反复执行：

```python
component.set_asset(None)
component.set_asset(system)
```

关卡中的 NiagaraComponent 会逐代残留旧的 User DI override subobject。实际观察到同一组件从正常的 `1 RasterizationGrid3D + 2 RenderTarget2D` 累积为 `3 Raster + 5 RT`；随后最新活动 Main/Aux RT 变成全零，重新载入关卡也不能恢复。此时 System 资产仍是 `UpToDate`，所以只看 Compile State 会误判为材质或新 HLSL 导致空白。

处理规则：

1. System 资产未变、只改 Renderer/Material/MI 时，不要清空 Asset；只做 `deactivate → reinitialize_system → activate`。
2. Scratch 图改动但 User DI 接口未变时，也优先原地 Reinitialize，并检查当前组件只有预期的 DI clone 数量。
3. User DI 接口或模板确实改变时，不要在同一组件上反复制造新一代 override；创建一次干净 NiagaraActor/Component，绑定 System 一次，配置 Raster/Main/Aux，验证后再替换旧实例。
4. 定点替换前记录 Actor Transform，并确保已有版本快照；替换后保存关卡、重新检查 Renderer 绑定、Compile State 与完整原分辨率 RT。
5. 正常 G5 运行实例当前应只有 `1×RasterizationGrid3D + 2×RenderTarget2D`；额外的旧 Grid2D/RT/Raster 子对象需要先判断是否属于 System 正式接口，不能把“找到至少一份正确 DI”当作 Gate 通过。

本次污染组件已在原坐标由干净 NiagaraActor 替换；严格 2048² 回读恢复为唯一 Main/Aux，非零覆盖 `84,757 / 4,194,304`，无 NaN/Inf。后续 Rebind 脚本已改为资产不变时原地 Reinitialize。

## 14. `duplicate_asset(NiagaraSystem)` 成功且 UpToDate，不代表 Scratch Simulation Stage 能运行

现象：在 UE 5.8 中用 `EditorAssetLibrary.duplicate_asset` 复制包含多个 Scratch Pad Simulation Stage 的 Niagara System。复制返回成功，新 System 能保存、能编译，Aggregate Status 为 `UpToDate`，图连接和常规模块输入与源资产逐项对比也一致；但把复制品绑定到干净运行组件后，Main/Aux RT 可能全零。

本项目做了两个对照：

- 完全不改 HLSL 的 System 复制品运行时 Main/Aux 全零；
- 在复制品上安装 Sparse Raster 后，只在一个投影中心附近得到约 15 个非零像素，表明嵌入式 Scratch/GPU 运行状态发生了默认值坍缩，而不是 Sparse 核本身的正常输出。

因此，对这类资产不能把“复制成功 + 编译绿色”当成可恢复备份或性能候选 Gate。至少还要：

1. 把复制品绑定到一次性干净 NiagaraComponent；
2. 重新初始化并推进足够模拟帧；
3. 以原分辨率或有代表性的分区回读 Main/Aux，检查非零覆盖、方向正负、深度/覆盖签名和 NaN/Inf；
4. 用未修改的复制对照排除新 HLSL 本身；
5. 只有运行 RT Gate 通过后，才把复制品视为可执行版本。

这是当前 UE 5.8、当前 Scratch Pad/Simulation Stage System 的实测陷阱，不应无条件外推到所有 Niagara 资产。本项目最终依靠自包含 V3、Dense HLSL 恢复文本和修改前哈希作为恢复点；Sparse 优化在原活动 V2 System 上原地 Apply/Compile/Save，而不是继续信任不可运行的复制品。

## 15. Fixed Tick 的单次 GPU 阶段若超过固定步长，会形成补步追帧螺旋

`.profViz` 中看到同名 Raster Stage 在一个渲染帧内累计超过 100 ms 时，先展开事件树，不要直接把累计值当成一次 Dispatch。

本项目近景 Profile 的实际结构是：

```text
Fixed Tick Delta Time = 16.67 ms
同一渲染帧补做 24 次 Niagara 模拟
每次 Raster = 17.70～18.88 ms
Resolve ≈ 0.19～0.20 ms
Grid Clear ≈ 0.325 ms
```

单次 Raster 已经比固定步长更慢，渲染帧越慢，系统越需要补步；补步又增加 GPU 工作，形成追帧螺旋。正确处理不是关闭 Fixed Tick，因为它仍负责稳定 Spawn/Lifetime/密度；应先优化每个固定模拟步最重的阶段，使它明显低于固定步长，再复测补步次数。

本项目用投影早剔除、`49×11 → 25×5` 稀疏高斯和单粒子质量归一化，在约 25.2 万粒子下把 Raster 稳态降到约 `0.56 ms`，同时保持分辨率、粒子数、字段语义和无 History 架构。性能 Gate 必须同时报告“单次阶段耗时”和“同一渲染帧执行次数”。

## 16. GPU Niagara 的运行 Gate 必须跨请求、跨帧，不能在重编译调用内立即回读

现象：同一次 Python/MCP 调用中依次执行 `Apply/Compile/Save → Reinitialize → advance_simulation → RT 回读`，可能短时得到旧 RT 的非零数据或在新 System 尚未完成异步 GPU 编译时读到全零。工具调用返回成功、System `UpToDate` 都不能证明渲染线程已经用新脚本执行过一帧。

本项目 Sparse 候选曾在同一自动化阶段得到非零 RT 和约 `0.56 ms` Profile，用户随后却看到效果完全消失。跨请求推进后 Main/Aux 全零，日志还显示恢复 System 的 GPU 编译发生在探针脚本返回之后。正确 Gate 必须拆开：

1. 请求 A：Apply/Compile/Save 或创建候选组件，然后结束调用，不做最终判定。
2. 等编辑器/渲染线程实际运行至少数帧。
3. 请求 B：再次推进、回读活动 RT，并核对当前组件/System/DI 身份。
4. 请求 C 或用户视口：继续运行并检查画面没有随后清零。

性能 Profile 也必须建立在请求 B 已证明有效的非零 RT 上；否则“很快的空 Dispatch”会制造虚假的性能提升。

此外，复制 World Partition/外部 Actor 关卡后要检查外部 Actor 包是否真正独立。当前 V3 关卡后来与 V2 一起改变 System 引用，说明只审计 `.umap` 与表面引用不足以证明运行快照自包含。

## 17. 当前结论

这次最关键的经验不是某一行投影公式，而是分清四个相互独立的层次：

```text
Scratch 图是否正确
≠ GPU 数据集是否真的保留属性
≠ Simulation Stage 是否真的写到当前运行 DI
≠ Renderer/材质是否真的采样当前 SimRT
```

任何一层都可能编译成功却输出错误。以后必须用“生成 HLSL + 当前运行 RT 原始统计 + 视口视觉”三重证据闭环，不能只依赖编辑器节点、工具返回成功或材质绿色状态。
