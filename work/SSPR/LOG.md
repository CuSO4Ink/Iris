# Screen Space Particle Reconstruction · LOG

> **当前真相（2026-08-08）**：P1 已通过；P0 仍是主线。三个历史候选 `NeighborGather_StageB_V1`、`NeighborGather_StageB_Safe_V2`、`BoundedGather_Clean_V3` 均已废弃删除，禁止复用。当前活动诊断候选 `P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1` 已完成 Gate S0 的结构/编译核验，但 K=8、256²、约 644 粒子的 Main/Aux 运行读回全零，Gate A 未通过。下一步为可回滚 Gather dispatch marker；有效 RT、overflow、视觉与正式 GPU 时间均尚未验收。当前规格只认 `AI-BRIEF.md`、`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 与 `ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md`。
>
> **阅读规则**：本文件是追加式历史记录。带“历史原型”“失败候选”“已撤回”的条目只用于事故追溯，不得作为当前实现或验收依据；后写的撤回条目覆盖更早结论。

### 2026-07-28 — [根因修复] RT 与粒子比例错位：ScreenPosition 节点存在但 UV 连线实际失败

用户观察到内部 SimRT 已经显示，但轨迹相对真实粒子同比例放大，体感像 Niagara 面片被推向摄像机。现场读取材质图确认 `MaterialExpressionScreenPosition` 节点存在，但 `TrajectoryTexture` Texture Sample 的 Connected Inputs 为空。创建脚本错误使用输入名 `Coordinates`；UE 5.8 的真实输入名是 `UVs`，而 `ConnectMaterialExpressions` 的失败此前未检查。已改为强校验连接 `ScreenPosition.ViewportUV -> TextureSample.UVs`，重编译并保存材质，运行时回读确认 Texture Sample 的输入源为 `MaterialExpressionScreenPosition`。因此显示采样与 Niagara `View.WorldToClip` 投影统一使用 Viewport UV，比例不再依赖面片世界深度和尺寸。

同次排查发现验证关卡同时运行两个不同位置的 `NS_SSPR_ParticleTrails_Main` Actor；激活脚本现优先保留 `SSPR_ParticleTrails_Main`，将重复实例设为不可见、关闭 Tick 和 Auto Activate，不删除资产。另修复 PIE 自动化的 Python 生命周期：所有验证脚本改为 `main()` 局部作用域，请求执行器改用独立 globals 并在 `finally` 中 clear + Python GC。连续两轮“进入 PIE -> 非零 RT 回读 -> 退出 PIE”均通过，UnrealEditor 与 MCP 保持存活，未再触发 `PlayLevel.cpp:553` 的旧 PIE Package 引用断言。

> 决策流水。追加式，新条目加在**文件末尾**。只记录决策、否决方案和重要发现。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

### 2026-07-22 16:47 — [决策] 先搭可插拔架构，不锁定密度算法
项目主干固定为粒子投影/分桶、场处理、Particle G-buffer、材质解析四层；KDE、各向异性 splat、MLS/RBF、深度平滑等都作为可替换 Field Operator。

### 2026-07-22 16:47 — [决策] 材质与场重建解耦
场处理层只产出标准化深度、厚度/密度、法线相关量和粒子属性；水、烟、能量、卡通等外观由 Resolve Material 组合，避免每种效果重写前端粒子管线。

### 2026-07-22 16:47 — [发现] 参考文档用于算法候选而非架构前提
RBF/各向异性 MLS 可用于特定线状点云边缘，但不应绑死基础设施；有序线链、无序点云和液体粒子的几何前提不同，应允许选择不同 Field Operator。

### 2026-07-22 16:47 — [决策] 保留每像素深度重建能力
相机朝向广告牌只作为材质载体，不把"跟随相机旋转"当作三维信息；需要立体感时由 RT 深度与逆视投影矩阵恢复视图/世界位置。

### 2026-07-22 17:00 — [发现] Niagara Fluids 有同构分层，但不是同一坐标域
Niagara Fluids 已有源粒子 scatter 到 Grid2D/Grid3D、Simulation Stages 处理、Renderer/Material 消费的分层；Grid3D Gas 和 FLIP 保留模拟域数据，公开资料未证明其通用模板采用每帧屏幕空间前后深度 G-buffer。
来源：Epic `fluid-simulation-in-unreal-engine---overview`、`niagara-fluids-reference`；80 Level 对 Epic TA Asher Zhu 的 Niagara Fluids 拆解。

### 2026-07-22 17:00 — [发现] Niagara 3D Liquid 是最近的表面重建参照
公开拆解包含 PIC/FLIP、粒子球 rasterizer、SDF/Jump Flood 与水材质路径，本质同样是"粒子 → 连续表面表示 → 材质"，但其目标是液体表面，不是通用的可插拔 Particle G-buffer。
来源：https://80.lv/articles/working-with-niagara-fluids-to-create-water-simulations

### 2026-07-22 17:00 — [发现] FluidNinja LIVE 更接近场缓冲与表现解耦
Fab 公开功能确认 LIVE 可把 Density、Velocity、Pressure 暴露到 Render Targets，支持 Niagara 双向数据流并驱动 Niagara/Volume 组件；其接口思想可直接参考，但公开资料不足以把它等同于"3D 粒子经相机矩阵投影为前后深度"。
来源：https://www.fab.com/ja/listings/80fcf53e-49f7-4635-a71c-ba81280c6618

### 2026-07-22 17:00 — [决策] 借鉴接口，不复制求解器
从 Niagara Fluids 借鉴 Grid/Simulation Stage/scatter/debug slice，从 FluidNinja 借鉴 RT 暴露、组件化和 Niagara 双向数据；项目仍保留独立 Projection 与 Field Operator 接口，不绑定 FLIP、2D Navier-Stokes 或某个商业插件的数据布局。

### 2026-07-23 11:34 — [发现] 与官方 Niagara 水渲染是同构而非一模一样
官方文档明确：3D FLIP 把粒子 splat 到模拟空间三维网格，再把网格作为表面 ray march；本项目则投影到当前视图的二维网格/RT，再用深度和密度解析 2.5D 表面。两者同为"粒子 → 连续场 → 材质"，但坐标域、信息保真度和多视图成本不同。

### 2026-07-23 11:34 — [发现] 单平面广告牌对应 Niagara 的另一条官方路径
Epic 文档明确 2D Gas 可始终朝向摄像机并模拟 3D 感，2D FLIP 的域通常也与摄像机对齐；这支持单层二维场作为实时特效方案，但它主要提供视角相关的 3D 感，不等价于带每像素深度重建的液体表面。

### 2026-07-23 14:40 — [决策] 用 UEAgent MCP 在 precisefluid 工程内做投影层活体验证
验证工程 `D:\Work\Company\Advance\Fluid\precisefluid`（UE 5.8 源码引擎 `C:\Work\UEEngine\UnrealEngine-5.8.0-release`）。经 UEAgent MCP（端点 127.0.0.1:8000）新建干净系统 `/Game/SSPR_Validation/NS_SSPR_ProjTest`（模板 DefaultSystem + Minimal 发射器 ProjParticles），隔离验证投影层，不混入 NiagaraFluids 模拟逻辑。已独立验真发射器切换为 GPUComputeSim。清理方式：整目录 `/Game/SSPR_Validation/` 可删。

### 2026-07-23 14:40 — [发现] 投影层不必自研 HLSL，UE 5.8 已内置 GPU 相机/投影函数
Niagara 内容库自带 `/Niagara/Functions/GBuffer/WorldPositionToScreenUV` 与 `ScreenUVToWorldPosition`（世界↔屏幕 UV 双向映射），以及 `/Niagara/Functions/Camera/` 下 GetClipSpaceTransformsGPU、ProjectionMatrix、GetViewPropertiesGPU、GetViewSpaceTransformsGPU。Projection layer 第一版可先用官方函数验证正确性，Custom HLSL 只在自定义分桶/场处理时再上，实现风险大幅下降。

### 2026-07-23 14:40 — [发现] 第一版投影用 Niagara 内置渲染 View 矩阵，多视图后置
Niagara GPU sim 取到的是当前渲染视图矩阵，编辑器单视口验证够用；多视图/VR 需显式传入指定相机 VP，列为后续 BACKLOG，不阻塞正确性基线。

### 2026-07-23 16:10 — [发现] Niagara Custom HLSL 里 `View.WorldToClip` 可用，投影管线编译通过
在 `NS_SSPR_ProjTest` 的 `ProjParticles` 发射器 ParticleUpdate 阶段建 scratch 模块 `SSPR_Projection`：MapGet 读 `Particles.Position` → Custom HLSL 做 `mul(float4(wp,1), View.WorldToClip)` → 透视除法得 NDC → `uv = ndc*(0.5,-0.5)+0.5`、`depth = clip.w` → MapSet 写回 `Particles.SSPR_ScreenUV`(vec2)/`Particles.SSPR_ViewDepth`(float)。ApplyChanges 返回 true，GetCompileMessages 为空。证实 Niagara HLSL dialect 直接暴露引擎 `View` uniform 的 `WorldToClip`，投影层第一版无需依赖官方 Function Script 节点即可编译通过。

### 2026-07-23 16:10 — [决策] 投影结果编码进 `Particles.Color` 做可视验证，绕开渲染器绑定缺口
VibeUE `NiagaraEmitterService` 的 renderer/module-input binding action 未 bound（issue #462），无法把自定义粒子属性直接绑到 Sprite 渲染器。因此在同一 scratch 模块内让 HLSL 追加输出 `OutColor`（R=U, G=V, B=depth ramp/5000, 屏幕外降亮 0.25），写回 `Particles.Color`，Sprite 默认消费该属性即出可视效果。整条"投影+可视化"图零错误编译通过，等待视口截图确认。

### 2026-07-23 16:10 — [发现] gateway 正确用法与全限定 toolset 名
`mcp_gateway.ps1` 用 `-Action {ping|tools.list|toolsets.list|toolset.describe|tool.call|script.execute|level.current}`；`tool.call` 传 `-Tool <全限定名> -ArgumentsFile <json>`。AssetTools 裸名会 not found，须用 `editor_toolset.toolsets.asset.AssetTools.*`；VibeUE 服务用 `VibeUE.NiagaraScratchPadService.*`。参数一律走 `-ArgumentsFile` 避免 PowerShell JSON 转义坑。

### 2026-07-23 后续 — [回滚] 推翻上面两条"编译通过=投影跑通/出效果"的结论
上面 16:10 两条把 `ApplyChanges=true`+`GetCompileMessages` 空当成"投影管线跑通、出效果"，是错的。真相：那个资产保存后**一打开编辑器就 Assert 崩溃**（Array.h:1339 数组越界，栈全在 NiagaraEditor），从未有任何可见效果，且反复保存成了"打开即崩"的坏档。教训见 E1——绝不能拿"自报/编译成功"当验收，验收只认"人能打开+能看到预期"。

### 2026-07-23 后续 — [否决] 用 MCP `NiagaraScratchPadService` 动态拼 scratch 图这条路
二分法坐实：空 scratch 模块、只加游离 Custom HLSL 节点都不崩；一旦执行 `AddPin`+`ConnectPins`（哪怕最保守的单输入 `WorldPos`+单输出 `OutDepth`+逐个加 pin），`ApplyChanges` 编译阶段即崩（资产全程关闭，排除 UI 因素，同一 Array.h:1339，栈底含 UnrealEditor-Niagara 编译帧）。即 MCP 这套动态拼 pin 会稳定产出让 Niagara 编译越界的畸形图，非操作顺序问题。→ 弃用此路（详见坑册 K11）。投影 scratch 的图/HLSL 改由**编辑器内手动搭建**，MCP 退回"只读核对+给 HLSL 代码"角色。骨架系统 `NS_SSPR_ProjTest`（Fountain+ProjParticles，Sprite renderer，已验证能打开、有粒子）保留为干净起点。

### 2026-07-23 后续 — [根因] VibeUE 崩溃三重根因（源码级坐实）
读 UE5.8 引擎源码坐实崩溃机制。崩点 = `UNiagaraNodeCustomHlsl::BuildParameterMapHistory`（编译期）用 `Signature.Inputs[i]/Outputs[i]` 按 pin 循环下标索引，守卫 `InputPins.Num()==Signature.Inputs.Num()+1 && OutputPins.Num()==Signature.Outputs.Num()+1`（+1=每方向一个 Add pin）。VibeUE `NiagaraScratchPadService` 三处偏离引擎正规流程：①`AddCustomHlslNode` 只 `CreateNode+Finalize+SetCustomHlsl`，节点没有 Add pin；②`AddPin` 用裸 `CreatePin` 绕过 `RequestNewTypedPin`，不维护 Add pin、不做名字 sanitize/唯一化；③自写 `RebuildCustomHlslSignatureFromPins` 遍历原始混排 `Pins` 按 Direction 分流，顺序与 `GetInputPins/GetOutputPins` 不一致。三者叠加使 signature 与 pin 索引失配 → `Signature.Inputs[i]` 越界（Array.h RangeCheck）。打开时 UI 用同一失配画面板同样越界，故"打开即崩"与"编译即崩"同源。

### 2026-07-23 后续 — [修复完成] 路 A：改引擎导出宏 + VibeUE 走引擎正规 API，已编译通过
引擎侧（UE5.8 源码，3 头）：`NiagaraNodeWithDynamicPins.h` 给 `RequestNewTypedPin`×2、`IsAddPin` 加 `NIAGARAEDITOR_API`；`NiagaraNodeCustomHlsl.h` 给 `InitAsCustomHlslDynamicInput` 加 `NIAGARAEDITOR_API`；`NiagaraNode.h` 把 `ReallocatePins`（原 protected，本已带导出宏）提为 public。VibeUE 侧（`UNiagaraScratchPadService.cpp`）：`AddCustomHlslNode` 建节点后调 `N->ReallocatePins()` 确保 Add pin 就位；`AddPin` 的 CustomHlsl 分支改走 `HlslDyn->RequestNewTypedPin(Dir,Type,Name)`（引擎内部维护 Add pin/唯一名/按 GetInputPins/GetOutputPins 顺序重建签名）；删除死代码 `RebuildCustomHlslSignatureFromPins`。`Build.bat precisefluidEditor Win64 Development` 增量编译 30 actions 全过，NiagaraEditor.dll + VibeUE.dll 链接成功，Result: Succeeded（~168s）。待重启编辑器后用 MCP 重跑投影 scratch 验证不再崩。踩坑：第一版用 `N->ReallocatePins()` 但它在 UNiagaraNode 是 protected → C2248，遂把声明提到 public。

### 2026-07-23 后续 — [验证通过] 路 A 修复经活体复现确认：越界崩溃根治
重启新编译的编辑器后，用 MCP 完整复现上次必崩序列（`AddCustomHlslNode` → `AddPin` WorldPos 输入 + OutDepth 输出（走新 `RequestNewTypedPin` 路径）→ MapGet/MapSet 通道 → `ConnectPins`×2 → `ApplyChanges`）。结果：`ApplyChanges` **正常返回、MCP 连接未断、编辑器进程存活**（端口 8000 通、UnrealEditor 进程 1）；上次此步直接 Assert 崩溃、连接强制关闭。判定修复成功——pin↔`Signature` 索引失配的越界（Array.h RangeCheck）已根治。`ApplyChanges` 返回 `false` 是因为进入了正常的 shader 编译并报错（不再是崩溃）。

### 2026-07-23 后续 — [发现] 占位投影 HLSL 在 CPUSim 下编译报错：`View`/`PrimaryView` 不可用
`GetSystemCompileState` 显示 ProjParticles 两个脚本 `Error`：`NiagaraEmitterInstance.ush(319/488): 'PrimaryView' undeclared` + `mul(vec4, )` 无匹配。根因：`ProjParticles` 是 CPUSim，Niagara VectorVM 环境不暴露渲染 `View` uniform（`View.WorldToClip`），只有 GPU sim shader 环境才有。这是与崩溃无关的、可预期的逻辑错误，证明链路已打通到 shader 生成阶段。下一步：把 ProjParticles 切 GPUComputeSim（此前已独立验证可切），或改用 `/Niagara/Functions/Camera/` 官方相机/投影函数，再重编投影段。

### 2026-07-23 后续 — [里程碑] 切 GPU sim 后投影 HLSL 零错误编译 + 编辑器可正常打开/scratch 可编辑
用 `NiagaraToolset_System.SetEmitterData`（`propertyValues:{"SimTarget":"GPUComputeSim"}`）把 ProjParticles 切 GPU，`GetEmitterSummary` 验真 `simTarget:GPUComputeSim`；再用 `SetSystemData` 启用系统级 Fixed Bounds（±5000，GPU sim 渲染前提）。`ApplyChanges` 返回 `true`（CPU sim 时为 false），`GetSystemCompileState`：`aggregateStatus:UpToDate`、`bHasErrors:false`，ProjParticles 新增 `ParticleGPUComputeScript` 且 UpToDate，之前 `'PrimaryView' undeclared`/`mul(vec4,)` 错误全消失——证实 `View.WorldToClip` 在 GPU sim 下可用。已保存。**用户实机确认**：资产正常打开不崩、粒子正常、且 scratch 模块**能双击进去、能看到 MapGet→HLSL→MapSet 连线**——即"崩溃"与"点不进去"两大痛点经路 A 修复同时根治，MCP 现在产出结构健康、可编辑的标准 scratch。下一步：把 depth/UV 编码进 `Particles.Color` 做可见验证。

### 2026-07-23 后续 — [发现] 颜色可视化做在错误的发射器上——系统是双发射器
在 `ProjParticles` 的 `SSPR_Projection` 里把投影结果编码进颜色：HLSL 追加输出 `OutColor`（R=屏幕U、G=屏幕V、B=归一化深度 clip.w/5000、屏幕外×0.25 压暗），加 `OutColor`(LinearColor) pin + MapSet 加 `Particles.Color` 写通道 + 连线，`ApplyChanges` 返回 true、`GetSystemCompileState` 全绿（新增连线共 6 条），已保存。但**用户打开后粒子仍是白色/无变化**。用户点破根因：系统里有 **两个发射器**——`Fountain`（视口里看到的喷泉粒子）和 `ProjParticles`（投影+颜色改动所在）。改的和看的不是同一批粒子，故喷泉不变色。教训：动手前先确认系统的发射器构成，别默认单发射器。

### 2026-07-23 后续 — [决策] 走 C-2：合并为单发射器（留 ProjParticles，删 Fountain，补 spawn）
用户在 C-1（把投影搬到 Fountain）/C-2（留 ProjParticles 补喷发模块，删 Fountain）/C-3 中选 **C-2**——因 ProjParticles 上 GPU sim+投影+颜色链路已就绪且验证不崩，改动最小。已完成：用 `NiagaraToolset_System.RemoveEmitter` 删除 `Fountain`，`GetSystemSummary` 验真系统现只剩 `ProjParticles`（GPU sim + Sprite renderer）。

### 2026-07-23 后续 — [进行中] 给 ProjParticles 补 SpawnRate，让其喷出可见粒子
`GetEmitterTopology` 查得 ProjParticles 模块栈：EmitterUpdate 仅 `EmitterState`（无 SpawnRate/Burst）、ParticleSpawn 仅 `InitializeParticle`、ParticleUpdate 为 `ParticleState`+`SSPR_Projection`——缺"生成粒子"模块，故粒子不显眼。`AddModule` 参数 = `moduleLocationRef`(emitter/scriptName)+`moduleAsset`(refPath)。已确认 SpawnRate 模块 asset 路径 `/Niagara/Modules/Emitter/SpawnRate.SpawnRate` 存在（`exists` 参数名是 `path` 不是 `assetPath`）。**待办**：AddModule 把 SpawnRate 加到 EmitterUpdateScript → 视需要调 InitializeParticle 的位置分布/大小/生命周期让粒子铺开 → ApplyChanges 编译 → 保存 → 用户打开验证粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度，转相机时颜色实时变=投影正确工作）。

### 2026-07-23 后续 — [里程碑] C-2 落地：ProjParticles 补齐 spawn+分布，单发射器投影链路编译级完整
按 C-2 给单发射器 `ProjParticles`（GPUComputeSim + Sprite renderer）补齐生成/分布：`AddModule` 加 `SpawnRate`（`/Niagara/Modules/Emitter/SpawnRate.SpawnRate`）到 `EmitterUpdateScript`、`SetStackInputData` 设 `SpawnRate=200`；`AddModule` 加 `ShapeLocation`（真实路径 `/Niagara/Modules/Spawn/Location/V2/ShapeLocation`，非旧 `.../Location/ShapeLocation`）到 `ParticleSpawnScript`、设 `Sphere Radius=300`（默认 Position Mode 是 `Simulation Position` 单点，故必须靠 ShapeLocation 铺开）；`InitializeParticle` `Lifetime=5`（稳态 ~1000 粒子）。最终模块栈：EmitterUpdate=`EmitterState`+`SpawnRate`、ParticleSpawn=`InitializeParticle`+`ShapeLocation`、ParticleUpdate=`ParticleState`+`SSPR_Projection`。`GetSystemCompileState` 全绿（aggregate UpToDate、无错无警、`ParticleGPUComputeScript` UpToDate），已 `save_assets`。**待用户视觉验收**：打开 `NS_SSPR_ProjTest` 确认①能打开不崩②球状粒子团喷出③粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度）④转动相机颜色实时变=投影正确。

### 2026-07-23 后续 — [发现] gateway 需 `-ExecutionPolicy Bypass`；AddModule/find_assets 参数名坑
本机 PowerShell 默认禁用脚本，调 `mcp_gateway.ps1` 必须加 `powershell -ExecutionPolicy Bypass -File ...`。`AddModule` 入参是 `moduleLocationRef`(system+emitterName+scriptName，其余 moduleName=""/rendererIndex=-1/inputNameStack=[] 占位)+`moduleAsset.refPath`；`GetEmitterTopology` 必填参数名是 `emitterRef`。AssetTools 查资产工具是 `.exists`(参数 `path`) 与 `.find_assets`(参数 `folder_path`+`name`+`recursive`，非 `path`/`name_pattern`)。

### 2026-07-24 — [里程碑·效果级通过] 基础投影验证经用户实机视觉确认
用户打开 `NS_SSPR_ProjTest` 确认四点全对：①能打开不崩 ②球状粒子团正常喷出 ③粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度）④**转动相机颜色实时变化**。第④点是关键判据——证明每帧取当前渲染 View 矩阵、`View.WorldToClip` 世界→裁剪空间投影链路真实工作，非静态贴图。项目首个经视觉验收的里程碑达成：投影层（Projection layer）从"编译级"正式升级"效果级通过"。下一步进 Field Operator A（最简各向同性粒子 splat 到 RT，作为正确性基线）。

### 2026-07-24 — [澄清·免改插件] VibeUE scratch 本就支持 DI 类型输入，先前"要改插件"判断错误
排查粒子写 RT 通路时先误判为"VibeUE 不支持 DI 类型 module input 需改插件"，根因是 `AddModuleInput` 传了全类名 `NiagaraDataInterfaceRenderTarget2D` 报 `Unknown TypeName`。读源码 `Plugins/VibeUE/Source/VibeUE/Private/PythonAPI/UNiagaraScratchPadService.cpp` 的 `ResolveType`（约 141 行）坐实：其类型白名单**已支持** DI 短名 `RenderTarget2D`/`DynamicRT`/`Grid2D`/`Grid2DCollection` 及各 `ArrayFloat*` DI，只是要用短名不用全类名。故**无需改插件**，改传 `RenderTarget2D` 即成功。教训：报"未知类型"先读 ResolveType 白名单，别急着下改插件结论。

### 2026-07-24 — [里程碑·MVP scatter 编译通] 粒子按 SSPR_ScreenUV 写入 RT 的通路搭通，全 MCP 落地不崩
建 `RT_SSPR_Occupancy`（256×256，Python `TextureRenderTargetFactoryNew`）。在 ProjParticles/ParticleUpdate 建 scratch 模块 `SSPR_WriteOccupancy`：`AddModuleInput` OccupancyRT(RenderTarget2D DI) → MapGet 读出 `Module.OccupancyRT`+`Particles.SSPR_ScreenUV` → `AddCustomHlslNode`（`GetRenderTargetSize`→`clamp(int2(UV*size))`→`SetRenderTargetValue(true,px.x,px.y,float4(1,0,0,1))`，`OutDummy=1`）→ AddPin 手动加 OccupancyRT/ScreenUV 输入+OutDummy 输出（`AddCustomHlslNode` 不自动解析变量成 pin，须手动 AddPin，走已修复的 RequestNewTypedPin）→ 连线 3 条 → MapSet 加写 `Particles.SSPR_WriteMark` 承接 OutDummy 维持执行链。`ApplyChanges` 返 true **未崩**（路 A 稳定复用），`GetCompileMessages` 空、`GetSystemCompileState` 全绿（含 ParticleGPUComputeScript），已保存。**RT DI 写入函数签名（UE5.8 源码坐实）**：`SetRenderTargetValue(bool Enabled,int IndexX,int IndexY,LinearColor Value)`（GPU only、bRequiresExecPin）、`GetRenderTargetSize()->(int W,int H)`。**待收尾**：把 OccupancyRT DI 绑定到 `RT_SSPR_Occupancy` 资产（经 `render_target_user_parameter` User Parameter 绑定，或直接开 DI 的 Preview Render Target），才能看到写入结果并做视觉验收。

### 2026-07-24 — [卡点·需UI收尾] DI-type User Parameter 绑定资产，MCP 与 Python 两路均不可自动化
用户选"规范绑定"（DI 落到真实 `RT_SSPR_Occupancy` 资产，供后续 Field Operator/材质采样，而非临时 Preview RT）。尝试两条自动化路均失败：①`NiagaraToolset_System.AddUserVariables` 传 RT2D DI 类型 user param（defaultValue 用 `NiagaraExt_VariableValue_DataInterface` + `Default__NiagaraDataInterfaceRenderTarget2D` 实例引用）返回 null，`GetUserVariables` 复查为空——MCP 对 DI 类型 user param 静默失败；②UE Python 侧 `NiagaraSystem` 不暴露任何 exposed/user parameter 编辑方法（`dir` 过滤 expose/parameter/user 全空、无 Niagara 编辑 subsystem、`find_all_objects_of_class` 不存在），拿不到 module 内 DI 实例。结论：**DI-type user parameter 绑定是当前 UEAgent 工具链硬边界，必须编辑器 UI 手动做**（属助手能力外的 UI 拖拽类操作）。scatter 写入图本身已编译通、已保存，仅差此绑定即可视觉验收。手动清单已交付用户。

### 2026-07-24 — [根因·坐实] scratch 模块"点不进去/Details空/无图标"= System 资产模式下脚本放错了 scratch 列表
彻底重启编辑器后 `SSPR_WriteOccupancy` 仍点不进、Details 空、无 scratch 图标——排除 UI 缓存。读引擎 `NiagaraScratchPadViewModel.cpp::GetOuterAndTargetScripts` 坐实根因：Niagara 编辑器按资产 edit mode 选 scratch 脚本列表——**SystemAsset 模式只扫 `UNiagaraSystem::ScratchPadScripts`（系统级）**，EmitterAsset 模式才用 `EmitterData->ScratchPads->Scripts`（发射器级）。`NS_SSPR_ProjTest` 是 System 资产，编辑器只认系统级列表。而 VibeUE `CreateScratchModule` 一律把脚本塞进 emitter 容器 → 脚本能编译、stack 有节点、`ListScratchModules` 能列出（底层数据在），但编辑器 ViewModel 扫不到 → 无 ScriptViewModel → UI 点不进。对照：能编辑的 `SSPR_Projection` 路径在系统级（`NS_SSPR_ProjTest:SSPR_Projection`），正是引擎正规流程产物。

### 2026-07-24 — [修复完成] 路B：改 VibeUE 让 System 资产模式下 scratch 脚本进系统级列表（免改引擎）
`UNiagaraSystem::ScratchPadScripts` 是 public 字段（`NiagaraSystem.h` 约 518 行，无 EDITORONLY/无需导出宏），故修复**纯在 VibeUE 内完成，未动引擎**。改 [`UNiagaraScratchPadService.cpp`](D:/Work/Company/Advance/Fluid/precisefluid/Plugins/VibeUE/Source/VibeUE/Private/PythonAPI/UNiagaraScratchPadService.cpp) 三处：①`CreateScratchModule` 增 `bSystemAssetMode = System->GetEmitterHandles().Num()!=1`，该模式下脚本 outer 用 `System`、加入 `System->ScratchPadScripts`（否则仍用 emitter 容器）；②`ListScratchModules` 查找集合并入 `System->ScratchPadScripts`，去掉"emitter 容器空即返回"限制；③`ApplyChanges` 对系统级 scratch 脚本也 `NotifyGraphChanged`+`MarkPackageDirty`。编辑函数走 `FindModuleNodeOnEmitter`（按 graph 节点名查，与脚本容器归属无关），不受影响。防崩校验 `ValidateScratchGraphsForCompile` 暂只校验 emitter 容器（少一层保护、不引错，保持最小改动）。`Build.bat precisefluidEditor Win64 Development` 增量编译 4 actions 全过，`UnrealEditor-VibeUE.dll` 链接成功，Result: Succeeded（~20s）。**待验证**：重启编辑器后删旧 `SSPR_WriteOccupancy`（emitter 容器里的坏模块）、用新逻辑重建，确认新模块在编辑器里有图标、可双击进图、Details 有 OccupancyRT 输入，再绑 RT 资产做视觉验收。

### 2026-07-24 — [修正] bSystemAssetMode 判据错误 → 改为无条件系统级
第一版补丁用 `bSystemAssetMode = System->GetEmitterHandles().Num()!=1` 判据是错的：误把引擎 `GetOuterAndTargetScripts` 里"EmitterAsset 模式内部按 emitter 数量选"抄成了顶层判据。`NS_SSPR_ProjTest` 只有 1 个 emitter → `!=1` 为 false → 又走回 emitter 容器，重建的 `SSPR_WriteOccupancy_1` 路径仍在 `NiagaraScratchPadContainer_0`、编辑器里仍无图标/点不进（但 Details 已有参数，说明系统级并入的 List/Apply 改动部分生效）。真相：edit mode 才是决定因素，emitter 数量只在 EmitterAsset 分支内部用；VibeUE 经 `LoadSystem` 编辑的恒为 System 资产 = SystemAsset 模式。故改 `const bool bSystemAssetMode = true;`（无条件系统级）。`ListScratchModules`/`ApplyChanges` 两处是"并入两个列表"，不受影响、无需再改。已删 `SSPR_WriteOccupancy` 与误建的 `SSPR_WriteOccupancy_1`，系统回到 `ParticleState`+`SSPR_Projection` 干净态。**待重编 VibeUE + 重启后重建验证**。

### 2026-07-24 — [约定] VibeUE 插件改动用 git 分支管理，基线固定 commit 保持可回滚
VibeUE 仓库（`Plugins/VibeUE`）由 bootstrap 固定在 detached HEAD `271f487`（Merge #520，5-8 分支）。为使插件改动可追溯/可回滚，新建分支 **`sspr-scratchpad-fixes`** 承载本项目所有 VibeUE 补丁，基于 `271f487`。首个提交 `8b43efa`（scratchpad 系统级归属修复，1 file +72/-67）。约定：后续每次改 VibeUE 源码，都在此分支按"改动本体"单独 commit（message 记根因+改动点），不直接在 detached HEAD 提交（会游离丢失）。回滚基线：`git checkout 271f487`。

### 2026-07-24 — [里程碑·插件修复验证通过] MCP 建的 scratch 模块现可在编辑器正常编辑
修正判据（`bSystemAssetMode=true` 无条件系统级）重编 `VibeUE.dll` 并重启后，用新逻辑重建 `SSPR_WriteOccupancy`：scriptPath 为系统级 `NS_SSPR_ProjTest:SSPR_WriteOccupancy`（不再带 `NiagaraScratchPadContainer`），完整重搭写入图（DI 输入 OccupancyRT + MapGet 读 SSPR_ScreenUV + Custom HLSL 写 RT + MapSet SSPR_WriteMark + 连线），`GetSystemCompileState` 全绿。**用户实机确认**：编辑器里 `SSPR_WriteOccupancy` ①有 scratch 图标 ②能双击进图（可见 InputMap→MapGet→HLSL→MapSet→Output 连线）③Details 有 OccupancyRT 输入——三点全对。插件补丁彻底修好"MCP 建可编辑 scratch"能力，后续所有场算子写入模块可全 MCP 自动搭建。git commit `8b43efa` 即为此正确版本。

### 2026-07-24 — [边界·确认] DI 输入绑定 RT 资产仍需 UI 手动，自动化不可达
插件补丁修的是"模块可编辑"，非"DI 输入可绑资产"。复查：①`GetStackInputData` 仍报 `Input 'OccupancyRT' not found`（官方 toolset 扫不到 scratch module 的 DI 输入命名空间）；②Python 虽能 `load_object` 拿到系统级 scratch script（`NiagaraScript`），但它不暴露 DI/rapid-iteration 编辑方法。故 OccupancyRT→RT_SSPR_Occupancy 绑定确定为 UI 手动步骤（但模块已可编辑，绑定入口正常出现）。绑定方式：System Overview 建 RenderTarget2D User Parameter 默认值设 RT_SSPR_Occupancy → 模块 OccupancyRT 输入 Link 到该 user param → 编译保存 → 打开 RT 看亮斑。

### 2026-07-24 — [修复] read-before-set 编译错误 = Interpolated Spawning 惹的祸，关掉即解
绑定前编译报错：`Particles.SSPR_ScreenUV was read before being set`（默认模式 Fail If Previously Not Set），报错点在 SpawnScript/UpdateScript/GPUComputeScript。根因：`SSPR_WriteOccupancy`（ParticleUpdate）读 `SSPR_ScreenUV`，而 GPU sim 的 **Interpolated Spawning** 会让 spawn 帧也插值执行 update 逻辑，此时投影尚未算出 → 读到未初始化属性。先试的 spawn 阶段初始化模块 `SSPR_InitAttrs`（MapSet 三属性 + 常量 HLSL 写 0）只消掉了 GPUComputeScript 报错（6→4 条），CPU 校验脚本仍报（MapGet 默认模式仍 Fail）。真正正解：`GetEmitterData` 读到 `InterpolatedSpawnMode: Interpolation`，用 `SetEmitterData`（propertyValues 须包在 `emitterData` 对象里）改为 **`NoInterpolation`** → spawn 帧不再跑 update 逻辑 → `GetCompileMessages` 空、`GetSystemCompileState` 全绿（UpToDate 无错无警）。全 MCP 自动完成，未动 UI。`SSPR_InitAttrs` 保留作双保险无害。已保存。**下一步**：UI 绑定 OccupancyRT→RT_SSPR_Occupancy 看亮斑，完成 MVP 视觉验收。

### 2026-07-24 — [根因·全黑] RT DI 绑定方式错：要绑 DI 的 Render Target User Parameter 字段，非 Link module input
首次绑定后打开 RT 全黑。`get_all_user_parameters` 查得用户建了 `OccupancyRTParam`（类型 TextureRenderTarget 引用，正确载体），但 `NiagaraDataInterfaceRenderTarget2D` 的 `render_target_user_parameter` 绑定为空 `{}`——即 DI 不知道写哪张 RT，写进了匿名临时 RT，故打开资产全黑。根因：用户上次做的"Link Inputs→User→OccupancyRTParam"绑的是 module input，而 RenderTarget2D DI 需要绑的是 **DI 内部的 `Render Target User Parameter` 字段** → 设为 OccupancyRTParam，再让该 user param 默认值指向 `RT_SSPR_Occupancy` 资产。诊断法：临时把写入 HLSL 改为"每粒子无条件在中心写 32×32 红块"（不依赖 UV），隔离绑定问题 vs UV 问题。

### 2026-07-24 — [里程碑·MVP scatter 效果通] RT DI 绑定正确后中心红块可见 = 粒子→屏幕空间 buffer 通路打通
用户按"绑 DI 的 Render Target User Parameter 字段=OccupancyRTParam"重绑后，打开 `RT_SSPR_Occupancy` **看到中心红块**——证明粒子经 scratch HLSL 的 `SetRenderTargetValue` 真实写入了目标 RT 资产，scatter 通路（粒子 → 屏幕空间 buffer）端到端打通。随即把测试 HLSL 恢复为正式按 UV 写入（`clamp(int2(ScreenUV*size))` → `SetRenderTargetValue`），编译无错、已保存。**待用户最终验收**：打开 RT 应见粒子按屏幕投影 UV 分布的红色散点，移动/转视角散点分布随之变化。此为 SSPR buffer 层首个效果级里程碑，此后可进 Field Operator A（各向同性 splat）。

### 2026-07-26 — [根因修复] RT 近似全黑 = 投影模块丢失 ScreenUV 写回
活体检查确认系统有效、ProjParticles 已启用且为 GPUComputeSim、SpawnRate=200、Lifetime=5，故排除无粒子/未激活。真正断点是 `SSPR_InitAttrs` 每粒子把 `SSPR_ScreenUV` 初始化为 `(0,0)`，而当时的 `SSPR_Projection` Custom HLSL 仅保留 `OutDepth`/`OutColor`，既没有 `OutUV` pin，也没有写回 `Particles.SSPR_ScreenUV`。于是 `SSPR_WriteOccupancy` 的所有粒子都算出像素 `(0,0)`；512×512 预览只有左上角一个像素，视觉上等同全黑。

### 2026-07-26 — [修复完成] 恢复 UV 数据链、拒绝非法写入并统一 RT/DI
已给 `SSPR_Projection` 恢复 `OutUV`(vec2)，连接到 MapSet 的 `Particles.SSPR_ScreenUV`；投影 HLSL 对相机后方和屏外粒子输出 `(-1,-1)`。`SSPR_WriteOccupancy` 重写为先检查 RT 尺寸与 `[0,1)` UV，再以 `shouldWrite` 控制 `SetRenderTargetValue`，避免旧版 `clamp` 把非法粒子堆到边缘。旧 MapGet 含两个同名 `None` 默认输入，触发 VibeUE 防崩校验，故将该 MapGet 精确重建为仅含 `Module.OccupancyRT` 与 `Particles.SSPR_ScreenUV` 的干净节点并恢复全部连线。`RT_SSPR_Occupancy` 与 RT2D DI 统一为 256×256、RTF_R16f，RT 开启 UAV、最近点过滤，DI 开启继承用户 RT 设置。Niagara 原生编译最终 5 个脚本全部 UpToDate，零错误零警告、无在途编译；System 与 RT 包均保存为非脏。VibeUE `ApplyChanges` 仍会扫描 emitter 容器里的旧孤立 scratch 副本并误报旧 GUID，但活动堆栈使用新节点，Niagara 原生编译和保存均已通过；后续应单独清理该 legacy 容器副本或收紧 VibeUE 校验范围。

### 2026-07-26 — [里程碑·效果级通过] 正式 UV Occupancy scatter 获视觉确认
用户提供的 RT 截图显示黑底上已出现大量按二维投影位置离散分布的红色像素点，不再是全黑或全部挤在 `(0,0)`；这直接证明 `SSPR_Projection.OutUV → Particles.SSPR_ScreenUV → SSPR_WriteOccupancy → RT_SSPR_Occupancy` 的正式数据链在 GPU 运行时真实生效。结合此前相机转动时投影颜色实时变化的验证，Projection 与首个 Occupancy buffer 现均达到效果级通过，可以进入 Field Operator A（各向同性 splat，把稀疏点扩成连续密度场）。

### 2026-07-26 — [M1·技术完成，视觉待验] Curl 运动 + 屏幕速度 + 二值方向胶囊已落盘
按 `WISPY-FLUID-SPEC.md` 将首个生产候选从“各向同性点模糊”收敛为“粒子速度驱动的方向性胶囊”。`ProjParticles/ParticleUpdate` 的活动顺序现为 `ParticleState → CurlNoiseForce → SolveForcesAndVelocity → SSPR_Projection → SSPR_WriteOccupancy`；Curl 验证参数为 Strength=250、Frequency=20。`SSPR_InitAttrs` 初始化 `Particles.SSPR_ScreenVelocityUV=(0,0)`；Projection 用固定 `ReferenceDt=1/60s` 投影 `Position` 与 `Position+Velocity*ReferenceDt`，输出 UV/秒；Writer 乘实时 RT 尺寸得到像素速度，以 `TrailTime=0.04s`、`MaxTrailPx=12`、`RadiusPx=1.5` 的固定上限循环写入向后拖尾的二值胶囊。重叠像素全部写相同的 1，避免把非原子 RT 写误当密度累加。独立读回确认新增 8 个 Pin、4 条连线和三段 HLSL 均正确；原生 Niagara 5 个脚本全部 UpToDate、零错误零警告，最近 LogNiagara 仅有正常编译记录；RT DI 仍绑定 `User.Render Target 2D`，系统保存成功且 Dirty=false。**尚未取得用户画面确认，因此 M1 仅技术完成，未标效果级通过。**

### 2026-07-27 — [根因] 方向轨迹最终画满 = 外部 RT2D 只有写入、没有帧清理
用户截图已确认 Curl 方向轨迹真实存在，同时连续运行后 RT 接近铺满。旧 Writer 对持久化外部 RT 只执行二值 `SetRenderTargetValue(..., 1)`，既不清屏也不衰减；因此每帧轨迹会永久并集，画满是必然结果，与粒子 Lifetime 无关。RT2D DI 的 ClearColor 只参与纹理创建/重建，不能作为逐帧清理机制。

### 2026-07-27 — [修复] 用 Grid2D 粒子稀疏写入 + Stage 前清理覆盖外部 RT
`SSPR_WriteOccupancy` 的 Custom HLSL 已从 RT2D 原地写改为 `Grid2DCollection.GetNumCells` + `SetFloatValue<Attribute=Occupancy>`；系统新增 `User.SSPR_OccupancyGrid`，实际 DI 为 256×256、`ClearBeforeNonIterationStage=true`、`SetGridFromMaxAxis=false`，其 `RenderTargetUserParameter` 绑定 `User.OccupancyRTParam`，由 Grid 的 PostSimulate 覆盖输出 `RT_SSPR_Occupancy`。活动 MapGet 直接读取 `User.SSPR_OccupancyGrid`，旧 `OccupancyRT → User.Render Target 2D` 绑定保留为未使用备用路径。Particle Update 顺序仍为 `ParticleState → CurlNoiseForce → SolveForcesAndVelocity → SSPR_Projection → SSPR_WriteOccupancy`；5 个脚本 UpToDate、零错零警、System 保存成功且 Dirty=false。执行前磁盘备份位于 `Saved/CodexBackups/NS_SSPR_ProjTest_before_grid_clear_20260727-1138.uasset`。

### 2026-07-27 — [边界] 当前是每帧清零，不是渐隐消散
本次修复只保证上一帧轨迹不会继续累积，RT 每帧只保留当前粒子胶囊。若要烟雾式逐渐变淡，必须在 M2 增加 History/Current ping-pong，在独立 Grid/Simulation Stage 或材质历史通路中执行 `History * Decay + Current`；不能在同一粒子 scatter Stage 对同一纹理安全地边读边写伪造衰减。

### 2026-07-27 — [根因修复] Grid 版全红不动 = 外部 RT 只显示重建清屏色，运行 DI/通道未同步
用户截图中的纯红不是粒子写满。UE 5.8 `NiagaraDataInterfaceGrid2DCollection.cpp::UpdateTargetTexture` 在重建外部 RT 时会把 `ClearColor` 设为 `(0.5,0,0,0)`；截图正是这层初始化色，说明 Grid 已重建 RT，但当前帧数据没有可靠复制出来。活体读回又发现两个运行实例状态分裂：关卡 NiagaraComponent 的用户变量列表缺少新增 `SSPR_OccupancyGrid`，编辑器预览实例虽有 Grid，但其克隆仍是 `NumAttributes=0`。普通 `ReinitializeSystem` 与同资产 `SetAsset` 不会补齐旧组件参数存储；官方 `SetVariable` 对 DI 也触发 `SetParameter_InternalUseOnly` 不支持错误。

### 2026-07-27 — [修复完成，视觉待验] 固定匿名通道 0，并重建两个运行组件的参数存储
为消除命名 Attribute 的运行时映射与组件克隆差异，Writer 从 `SetFloatValue<Attribute=Occupancy>` 改为 `SetValueAtIndex(x,y,0,1)`，源 Grid 明确设为 `NumAttributes=1`；256×256、`ClearBeforeNonIterationStage=true`、`RenderTargetUserParameter=User.OccupancyRTParam` 保持不变。关卡组件通过“临时卸载同资产 → 以 Reset Overrides 重新挂载 → 激活”重建参数存储，补齐 Grid DI；预览组件同步重建并把其当前克隆通道设为 1。最终两个运行 Grid 均独立读回 `256×256 / 1 channel / clear=true / User.OccupancyRTParam`；Writer 不再含命名 Attribute 或旧 RT2D 写入；5 个 Niagara 脚本 UpToDate、零错零警，资产保存成功且 Dirty=false。随后将外部 RT 中残留的红色初始化内容一次性清为黑色，System 与 RT 包仍均为非脏。修复前备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_anonymous_grid_fix_20260727.uasset`。尚需用户目视确认 RT 已恢复动态并且长期不画满。

### 2026-07-27 — [根因修复] Grid 版纯黑 = 重建 Writer MapGet 时漏接屏幕 UV 与屏幕速度
活体读回 `SSPR_WriteOccupancy` 内部图后确认：Grid2D 改造时删除了旧 MapGet 并创建 `BFD8FBC24B2DA1BEE89AF2889F618A0A`，但只重新连接了 `Module.OccupancyRT` 与 `User.SSPR_OccupancyGrid`；Custom HLSL 的 `ScreenUV` 和 `ScreenVelocityUV` 两个输入 Pin 都处于未连接状态。编译器会给 vec2 默认值，因此代码和 Grid DI 均可正常编译，却没有按粒子投影位置产生有效散点。现已在新 MapGet 上补回 `Particles.SSPR_ScreenUV`、`Particles.SSPR_ScreenVelocityUV` 两个 vec2 输出并连接至 HLSL；`ApplyChanges=true`，两条连线独立读回存在，5 个脚本全部 UpToDate、零错误零警告，System 保存成功。修复前备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_writer_uv_reconnect_20260727.uasset`。崩溃重启后原未保存关卡 Actor 未恢复，当前只打开 Niagara System 与 RT，并将唯一预览组件绑定 RT、设为 Active/Tick/ForceSolo，避免多个实例争抢同一张外部 RT；仍需用户目视确认动态画面。

### 2026-07-27 — [源码根因] VibeUE 的 DI module input 未按 Niagara 动态 Pin 正规流程注册
进一步读回活动 scratch 图与 GPU 编译产物后确认：旧 `UNiagaraScratchPadService::AddModuleInput`/通用 `AddPin` 对 `UNiagaraNodeParameterMapGet` 使用裸 `CreatePin`，绕过了 `UNiagaraNodeWithDynamicPins::RequestNewTypedPin`。可见 DI 输出虽然存在，但对应隐藏默认 Pin、模块签名和 stack input 拓扑没有完整登记；运行时因此克隆出 Grid `3×3/0 attributes` 或 RT `0×0/无 User Parameter` 的匿名 DI，造成“图和编译都正常，RT 仍黑”的假象。VibeUE 已改为动态节点统一走 `RequestNewTypedPin`，并规范 MapGet/MapSet 命名空间；离线 `Build.bat precisefluidEditor Win64 Development` 编译成功。修复已提交到插件分支 `sspr-scratchpad-fixes`：`44d9f72 Fix Niagara dynamic input registration`。

### 2026-07-27 — [技术决策] M1 最终采用 Direct RT writer，Grid2D 输出路线暂时退出关键路径
修复动态 Pin 后，Grid 与 RT module-local DI 均能在 GPU 编译产物中正确读回 256×256 和 `User.OccupancyRTParam`；但 Grid2DCollection 的外部 RT 输出在当前 Niagara 预览运行条件下仍持续黑屏，继续投入不利于验证核心视觉假设。M1 最终回到已被证明可靠的 RenderTarget2D DI 直接写入：每个存活粒子每帧按哈希分散选择 64 个像素，读取旧值并乘 `DecayMultiplier=0.90` 后写回，形成近似全屏的分布式渐隐；随后按 `ScreenUV` 与 `ScreenVelocityUV` 写入半径 1.5 px、最长 12 px 的速度方向胶囊。该做法避免旧版“只写 1 永不清除”永久画满，同时不用全屏 Simulation Stage。正式安装脚本保存在 `_black3_install_direct_rt_writer.py`，执行后 `ApplyChanges=true`、编译消息为空、系统资产保存成功。

### 2026-07-27 — [里程碑·M1 效果级通过] Curl 拉丝轨迹、动态写入与消散经用户确认
Niagara 资产编辑器 PreviewScene 产生真实 GPU 渲染帧后，`RT_SSPR_Occupancy` 显示随粒子运动变化的细小方向性轨迹；普通 EditorWorld Actor 在没有真实渲染帧时可能保持黑色，不能作为此 GPU DI 的离屏验收环境。用户最终确认“结果已经是对的了”。至此 M1 的投影、Curl 运动、屏幕速度、方向性胶囊、RT 动态更新与非永久累积全部达到效果级通过。下一阶段进入 M2：在材质/独立场处理层做多尺度卷积、密度重映射和烟雾 Resolve，而不是继续修改已通过的 M1 写入链路。

### 2026-07-27 — [回归·相机运动] 左右晃视角出现横向撕裂状残影
用户进一步做相机运动测试后发现，左右转动视角会在 RT 中留下远长于 12 px 胶囊上限的水平红线。Projection 的 `ScreenVelocityUV` 是用同一个当前 `View.WorldToClip` 投影 `Position` 与 `Position+Velocity*dt`，只包含粒子自身速度，不含相机速度；真正原因是 Direct RT 保存了上一帧的屏幕空间历史，视角改变后旧图没有重投影，新投影横向错位叠加。同时旧衰减代码从随机起点处理 64 个连续 linear address；在 row-major 的二维 RT 上正好形成水平条带，使残影呈现“撕裂”形态。

### 2026-07-27 — [修复完成，运动视觉待验] 衰减改为逐帧旋转的无方向置换
Writer 不再连续处理 64 个线性像素，改为以 `ExecIndex × 64 + decayIndex + View.FrameNumber × 7919` 生成序号，再乘奇数 `40503` 后对 RT 总像素数取模。对当前 256×256 RT，这是一种逐帧旋转、近似无重复且无水平/垂直偏置的覆盖；稳态约 1000 个粒子时每帧可触达约 64000/65536 个像素。`DecayMultiplier` 从 0.90 收紧到 0.78，使未重投影的屏幕历史约 3 帧内显著消退。修改已 `ApplyChanges=true`、compile messages 空、资产保存成功；Niagara 5 个脚本全部 UpToDate、零错误零警告。旧 RT 已清黑并重新激活唯一 PreviewScene writer。备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_isotropic_decay_20260727.uasset`。待用户左右晃动视角确认横线消失；若仍需更长尾迹且完全相机稳定，M2 必须改用 History/Current ping-pong + 相机重投影，不能继续依赖单 RT 原地历史。

### 2026-07-27 — [规格待审批] WISPY-FLUID-SPEC v0.2：M2 改为 Niagara + Material + Orchestrator 混合架构
用户复验无方向衰减后反馈相机横移伪影“好多了”，并要求先更新 Spec、审批后再执行。`WISPY-FLUID-SPEC.md` 已升为 v0.2/待审批：Niagara 只写每帧 `CurrentRT`；材质 Render Pass 用 `HistoryA/B` 做按秒衰减、代表深度相机重投影、Clamp、双尺度卷积和 Resolve；Blueprint/C++ Component 负责 Clear、GPU Pass 排序、Reset 与 A/B 交换。单 RT 粒子级 Read/Modify/Write 正式降级为 M1 调试实现。M2 拆为 A（Current+History 时序基础）、B（多尺度场处理）、C（烟雾 Resolve）；M3 再用 FrontDepth/HistoryDepth 升级逐像素重投影。当前只请求审批 M2 架构，未修改任何 M2 UE 资产。

### 2026-07-27 — [M2-A 技术完成，视觉待验] Current + History 双缓冲与显式相机重投影
M2-A 获批后新建 `/Game/SSPR_Validation/M2/RT_SSPR_Current`、`RT_SSPR_HistoryA/B`（256×256 R16F）、`M_SSPR_TemporalCombine` 和 `BP_SSPR_TemporalOrchestrator`。`SSPR_WriteOccupancy` 的正式代码已改为只写 Current 的方向胶囊，删除 `LoadRenderTargetValue`、粒子级衰减与帧号散列；修改前备份为 `Saved/CodexBackups/NS_SSPR_ProjTest_before_m2a_current_writer_20260727.uasset`。Blueprint 每帧设置 MID、只读一张 History/只写另一张、合成后清空 Current 并交换 A/B；BeginPlay 与 `ResetTemporalHistory` 会清空三张 RT、复位 History/Camera Valid 并重置 Niagara。

首版 Temporal 材质直接使用 `View.ClipToPrevClip`，静止相机的 History 保持测试却会把 A/B 全部清黑。根因不是 Ping-pong，而是 `DrawMaterialToRenderTarget` 的离屏 Canvas View 不携带游戏主相机的上一帧矩阵。现已改为 Blueprint 每帧从 PlayerCameraManager 显式传入当前/上一帧 Position、Forward、Right、Up；材质在 `RepresentativeDepth=1000` 的平面上重建世界点并投回上一帧 UV。相机平移超过 2000 uu 或 Forward 夹角余弦低于 0.5 时拒绝旧 History，避免 Cut 后旧图回流。按秒衰减使用 `exp(-DecayRate × DeltaSeconds)`，默认 `DecayRate=6`，首帧 Camera/History Valid 为 0。

验证结果：材质 22 个表达式、2 个纹理对象、10 个标量、8 个向量参数，PCD3D_SM6 诊断编译通过；Blueprint 99 个节点、154 条连线、45 个默认值，零编译错误/警告。关闭衰减并停掉 Niagara 后，History A/B 保持同图；开启显式重投影后静止相机仍保持；平移相机 100 uu 后 A/B 继续一致；恢复正式衰减并停掉 Niagara 后两张 History 都归零。调度器实例与验证场景已保存为 `/Game/SSPR_Validation/L_SSPR_M2_Validation`；从该地图重启标准 PIE 后，MID、HistoryValid、CameraDataValid、Niagara Active 与正式参数均为有效状态。M2-B/M2-C 未开始，M2-A 左右绕转和最终观感仍待用户视觉 Gate。

### 2026-07-28 — [回归修复] M2 Current-only Writer 污染 M1 独立预览，导致 RT 再次不消散
当前编辑器实际运行的是 `Untitled_1` 中单独放置的 `NS_SSPR_ProjTest`，没有 `BP_SSPR_TemporalOrchestrator`。M2-A 实现时直接把原 M1 System 的 Writer 改成了无状态 Current-only 版本；该 Writer 假定外部调度器每帧清空 Current，但独立 Niagara Actor 仍把它写入持久的 `RT_SSPR_Occupancy`。结果是所有历帧胶囊永久并集，表现为“RT 又不会 clear”。这不是 History 材质或粒子 Lifetime 失效，而是同一 Niagara 资产承担了互斥的 M1/M2 生命周期语义。

现已把系统拆开：`/Game/SSPR_Validation/NS_SSPR_ProjTest` 恢复 M1 分布式渐隐 Writer（含 `LoadRenderTargetValue`，`DecayMultiplier=0.78`）；复制并新增 `/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2`，保留不读历史的 Current-only Writer；`BP_SSPR_TemporalOrchestrator.SSPRNiagara` 已改为引用 M2 专用系统。两套 Niagara 均 `ApplyChanges=true`、compile messages 为空、资产保存成功，Orchestrator Blueprint 为 `BS_UP_TO_DATE`。

运行回归结果：M1 清黑后启动独立 Niagara，早期与长时间导出的 `RT_SSPR_Occupancy` 都保持稀疏动态胶囊，没有随运行时间铺满；M2 临时实例中 MID、HistoryValid、CameraDataValid、DecayRate=6 和 Niagara Active 均有效，活动 History 输出正常；停掉 M2 Niagara 后再次导出，History 已归零。临时 Orchestrator Actor 随后移除，编辑器恢复到原独立 Niagara 场景并保持 PIE 运行。

### 2026-07-28 — [M2-B 技术完成，视觉待验] Core/Small/Large/Density 多尺度场接入
用户要求继续沿 Spec 推进后，新增 `RT_SSPR_Core`、`RT_SSPR_BlurSmall`、`RT_SSPR_BlurLarge`、`RT_SSPR_Density`（256×256 R16F）以及对应 `M_SSPR_CoreExtract`、`M_SSPR_BlurSmall`、`M_SSPR_BlurLarge`、`M_SSPR_DensityCombine`。第一轮让 Large 直接读取稀疏 History，导出出现明显离散采样点阵；已改为 `History → 9-tap Small → 13-tap Large`，Large 半径收敛到 7 px，消除点阵并形成平滑低频场。Density 当前权重为 Core 0.60、Small 1.00、Large 0.65，重映射阈值 0.002/0.18，边缘破碎 0.04。

Orchestrator 已扩展为每条 A/B 分支执行 `Temporal → Core → Small → Large → Density`，并在 BeginPlay/Reset 清理全部字段 RT。材质诊断全部编译通过；最终 Blueprint 构图继续扩展至 M2-C 后为 165 个节点、270 条连接、71 个默认 Pin，零失败、零编译错误/警告。

### 2026-07-28 — [M2-C 技术完成，用户视觉 Gate 待验] 指数消光烟雾 Resolve
新增 `M_SSPR_SmokeResolve`、`MI_SSPR_Smoke_Default`、`MI_SSPR_Smoke_DensityDebug` 和 `RT_SSPR_Smoke`（256×256 RGBA8）。Resolve 使用 `1-exp(-Extinction×Density)`，默认蓝灰烟色，并暴露 Extinction、DensityScale、OpacityScale、BlackPoint、SmokeColor 和 EmissiveStrength；Orchestrator 默认使用正式实例，白色实例用于纯密度检查。Smoke 材质为 Unlit Translucent；因透明材质画入持久 RT 会累积，Orchestrator 在每次 Smoke Draw 前显式清透明黑，避免重现“RT 不 clear”。

首轮 Smoke 输出仍偏软粒子团，根因是 M2 专用方向胶囊仍使用 0.04s/12px 的 M1 验证值；现只对 `M2/NS_SSPR_ProjTest_M2` 调整为 `TrailTime=0.075s`、`MaxTrailPx=20px`、`MaxTrailSteps=20`，M1 独立预览不受影响。调参后 Smoke 输出已保留更明显的方向延伸和柔软外围。运行时六个 MID（Temporal/Core/Small/Large/Density/Smoke）均有效；持续运行不铺满，停止 Niagara 后 History、Density 与 Smoke 全部归黑。当前 M2-B/C 达到技术 Gate，是否达到“拉丝烟雾而非模糊粒子”的效果 Gate 仍需用户观察动态 RT 后确认。

### 2026-07-28 — [M2-C 显示链路完成，视觉待验] Density RT 通过相机跟随面片进入场景

用户确认当前 RT “确实有感觉了”并要求跑通面片渲染。`BP_SSPR_TemporalOrchestrator` 新增 `SmokeCardPivot`（SceneComponent）和 `SmokeCard`（StaticMeshComponent）；SmokeCard 使用 `/Engine/BasicShapes/Plane`、相对旋转 Pitch=90°、缩放 2.05×1.15，BeginPlay 把 `MI_SSPR_Smoke_Default` 绑定到材质槽 0。Tick 从 PlayerCameraManager 获取位置和旋转，把 Pivot 设置到 `CameraLocation + CameraForward × SmokeCardDistance`，默认距离 100 uu，并在进入 A/B History 分支前更新。

重构后的 Blueprint 为 172 个节点、281 条连接、74 个默认 Pin，零构图失败、零编译错误/警告。标准 PIE 运行态读回确认：SmokeCard 绑定正式 Smoke Material Instance 与 Engine Plane，Visible=true、RecentlyRendered=true；Pivot 到相机距离精确为 100 uu，与 Camera Forward 的归一化点积为 1.0。当前正式场景链路为 `Density RT → M_SSPR_SmokeResolve/MI_SSPR_Smoke_Default → Camera-facing Plane`，`RT_SSPR_Smoke` 仍作为调试导出；场景深度遮挡留给 M3 FrontDepth/SceneDepth。

### 2026-07-28 — [回归修复] 面片 X/Y 轴、固定宽高比与 Mesh UV 导致错位和截断

用户在 PIE 截图中指出面片歪斜、比例不对且中间被截断。根因是 Engine Plane 在相对 Pitch=90° 后，局部 X 映射到屏幕高度、局部 Y 映射到屏幕宽度；初版却设置 X=2.05、Y=1.15，实际得到窄宽、超高载体。同时固定 16:9 与当前 PIE 视口比例不一致，TextureCoordinate 又把整张 Density RT 拉伸到这个错误矩形上。

现新增 Card 专用 `M_SSPR_SmokeCard` 与 `MI_SSPR_SmokeCard_Default`：使用 `ScreenPosition.ViewportUV` 读取 Density RT，关闭原型阶段 Depth Test；Plane 扩大为 4×4，只负责覆盖视锥，不再决定采样比例。Orchestrator 新增独立 `SmokeCardMaterial`，RT 调试 Resolve 与场景 Card 不再共用 UV 语义。Blueprint 重构为 173 个节点、281 条连接、74 个默认 Pin，零失败、零编译错误/警告；PIE 读回确认 Card 专用实例已绑定、面片近期已渲染、相机对齐点积 1.0。

截图顶部 `NS_SSPR_ProjTest` 的 “RenderTarget is read and wrote in the same stage” 来自当前 Untitled 测试关卡里仍存在的 M1 独立 Niagara Actor，而非 M2 Current-only Writer。已把该 M1 组件在当前场景设为 AutoActivate=false、Active=false、Tick=false；PIE 中只保留 `NS_SSPR_ProjTest_M2` 活跃，避免双系统重叠和旧 M1 的同阶段读写警告。

### 2026-07-28 — [边缘修复] RT Clamp、Blur 越界归零与 Card 2 px 安全边

用户观察到屏幕边缘仍有少量烟色泛出。检查确认 Small/Large Blur 直接对 `UV + Offset` 采样，且各 RT 的 Address Mode 没有在资产级显式约束；单纯在最终 Card Clamp 会让边缘像素被重复拉伸，不能解决上游卷积越界。

现把 Current、History A/B、Core、Small、Large、Density、Smoke 八张 RT 的 Address X/Y 全部显式设为 `TA_Clamp`。Small 9-tap 与 Large 13-tap 的每个采样坐标先检查半像素安全范围，越界 Tap 贡献 0，合法 Tap 才执行 Clamp 后采样，避免 Wrap 和边缘重复。Card 的 Color/Opacity 两条 Resolve 再把 ViewportUV 限制到半像素中心，并在屏幕最外侧 2 px 以 Smoothstep 衰减到透明。修改后材质重编译、资产保存与运行态回归完成；Card 正在渲染、相机对齐点积 1.0，M2 Active=true、旧 M1 Active=false。

### 2026-07-28 — [调参开放与镜头尺度修复] Writer 宽度、卷积范围与动态代表深度

用户指出 RT 方向轨迹明显粗于 Niagara 粒子，并且镜头拉远后烟雾/RT 范围约为粒子范围两倍。检查确认两层原因：M2 Writer 的 `RadiusPx=1.5` 仍是 HLSL 硬编码，Small/Large 又使用固定 `3 / 7 px` 卷积；Temporal 重投影还使用固定 `RepresentativeDepth=1000`，而实际相机到特效中心距离会随镜头移动，造成历史缩放与当前投影不一致。

现为 M2 Niagara System 增加 `User.SSPR_RadiusPx`、`User.SSPR_TrailTime`、`User.SSPR_MaxTrailPx`，Scratch Writer 的 MapGet 直接读取这三个 User 参数并连接 Custom HLSL。由于 Niagara 官方 Stack API 仍无法定位 Scratch Module 新增输入，未继续依赖 Stack 绑定；User MapGet 是资产内明确、可编译且 Blueprint 可覆盖的数据链。默认 `SplatRadiusPx` 降为 `0.75 px`，当前整数写入算法下只落中心像素；Trail 保持 `0.075s / 20px`。

`BP_SSPR_TemporalOrchestrator` 新增八个实例参数：`SplatRadiusPx`、`TrailTimeSeconds`、`MaxTrailPx`、`SmallBlurRadiusPx`、`LargeBlurRadiusPx`、`CoreWeight`、`SmallBlurWeight`、`LargeBlurWeight`。八项均移除 `DisableEditOnInstance` 并归入 Actor Details 的 `SSPR Tuning` 分类。Tick 每帧把前三项写入 Niagara、其余项写入 Small/Large/Density MID，可在 PIE 中实时调整。默认卷积收窄为 `2 / 4 px`，混合权重改为 `0.60 / 0.90 / 0.45`。

固定 `RepresentativeDepth` 节点已从运行图移除，改用 `Actor::GetDistanceTo(PlayerCameraManager)` 每帧计算相机到特效中心的代表深度，并同时写入 A/B Temporal 路径。最新 Blueprint 为 190 个节点、306 条连接、82 个默认 Pin，零失败、零编译错误/警告；Niagara Scratch 编译消息为空。重启 PIE 后读回确认三个 Niagara User Float 与 Actor 值完全一致，Small/Large/Density MID 均收到新参数；Temporal MID 的代表深度为 `220.1454468 uu`，相机到 Actor 实测为 `220.1454483 uu`，误差约 `0.0000015 uu`。Card 仍近期已渲染、相机对齐点积 1.0，M2 Active=true、旧 M1 Active=false。

### 2026-07-28 — [架构重新对齐] 高密度粒子年龄分布 + Grid2D 直连材质成为正式主线

用户说明 `/Game/SSPR_Validation/M2/NewNiagaraSystem2` 是 Leader 要求对齐的方向：拉丝连续性不应主要来自二维 History Ping-pong，而应由大量、长寿命、不同年龄的三维粒子在 Curl 场中同时占据流线不同位置，再把全部存活粒子每帧重新投影到 Grid2DCollection。Grid 通过 Niagara Grid2D Collection Renderer 直接绑定最终材质参数，正式链路不声明 Current、History、Core、Blur、Density、Smoke 等外部 RenderTarget 资产。

MCP 读回参考资产当前为单个 CPU `Fountain` Emitter：SpawnRate=5000/s、Lifetime=5s、球体半径 50、Curl Strength=5000、Frequency=10、Drag=1，稳态约 25000 个粒子；Particle Update 尾部在 `Solve Forces and Velocity` 后执行 `Particles.Velocity=(0,0,0)`。该清零会保留 Solver 已经写入的本帧位置，但禁止动量传入下一帧，使粒子更紧地跟随瞬时 Curl 场。其代价是位移近似按 `Force × DeltaTime²` 计算、有效流速具有帧率依赖，Drag 作用减弱，且下游无法读取有效 Velocity。正式实现优先评估“Curl 目标速度 + 指数响应”的帧率稳定方案；若保留 Reset，必须在清零前缓存 `Particles.FlowVelocity`。

`WISPY-FLUID-SPEC.md` 已重写为 v1.0：旧 Ping-pong Orchestrator、多 RT 材质链和代表深度重投影降为实验参考；新里程碑依次为 M0 GPU 粒子运动对齐、M1 Grid2D 单帧轨迹、M2 Grid Renderer 直连材质、M3 单材质高品质烟雾、M4 深度融合、M5 性能档位。当前只完成架构与规格重新对齐，尚未修改 `NewNiagaraSystem2`。

### 2026-07-28 — [主线切换] 旧 Ping-pong 资源归档，新粒子轨迹进入 Niagara 内部 SimRT 并绑定材质

旧 M2 Ping-pong/多 RT 原型的 20 个核心资产已从 `/Game/SSPR_Validation/M2` 移动到 `/Game/SSPR_Validation/Archive/PingPong_M2_20260728`，包括 Temporal Orchestrator、Current/History A/B、Core/Small/Large/Density/Smoke RT 与全部对应材质；只保留重定向器用于旧引用兼容。`NewNiagaraSystem`、`NewNiagaraSystem1`、`NewNiagaraSystem2` 作为 Niagara Fluids 与 Leader 运动参考未归档。

新增主线资产 `/Game/SSPR_Validation/M2/GridTrails/NS_SSPR_GridTrails_Main`、`MI_SSPR_GridTrails_Display` 与 `BP_SSPR_GridTrails_Main`。SourceParticles 为 GPU Compute Sim，已设置 `SpawnRate=5000/s`、`Lifetime=5s`、发射半径 `50 uu`、Spawn Curl Strength `130`、Frequency `0.04`、Source Density `1`，并关闭 AddVelocityInCone、Gravity、Collision、Update Curl 与 Drag；当前脚手架由 Spawn Curl 生成初始速度，再由 Solve 持续推进，稳定态目标约 25000 个存活粒子。显示 Renderer 使用项目内材质实例，并保持 `Material SimGrid <- Emitter.SimRT.RenderTarget` 的 Niagara 原生子变量绑定。连续 Curl/目标速度运动留待精简后的正式粒子运动模块实现。

引擎源码核对确认：UE 5.8 材质不能直接消费 Grid2DCollection 的原始 RDG 纹理。Niagara Fluids 的正式原生桥接是 `Grid2DCollection -> Simulation Stage -> NiagaraDataInterfaceRenderTarget2D(Emitter.SimRT) -> Emitter.SimRT.RenderTarget -> Renderer Material Parameter`。其中 `Emitter.SimRT` 在 `bInheritUserParameterSettings=false` 时由 Niagara 为系统实例自动创建，不是 Content 外部 RT 资产；因此仍满足“不声明额外 RT、不用 Blueprint Clear/DrawMaterial/Ping-pong”。

编译回读为 `UpToDate`、零错误、零警告。当前 Untitled 验证场景生成了 `SSPR_GridTrails_Main` Actor；运行时自动出现 512×512 RGBA16F `SimRT`。最终自动化验收会扫描全部同规格运行时目标并排除旧实例残留纹理；当前活动目标读回 262144 像素，RGB 最大值为 `(1.0, 1.0, 0.939453125)`，三个颜色通道均有 `261121` 个非零像素，证明粒子/Grid 数据已进入材质所绑定的内部纹理。当前系统仍以 Niagara Fluids `Grid2D_Gas_Smoke` 为脚手架，包含 Advect、Pressure、Lighting 等完整 Gas Stage；它只完成了“粒子轨迹→Grid→内部 SimRT→材质”的技术链验证。下一步必须将 Grid Emitter 精简为 `Clear -> Rasterize Trajectory Particles -> Pack/Copy to SimRT`，移除 Navier-Stokes/压力求解后再进入单材质高品质烟雾重建。

`WISPY-FLUID-SPEC.md` 已升级为 v1.1，修正“Grid2D 纹理直接绑定材质”的不准确描述，记录 Niagara 自管 SimRT 桥接的真实引擎行为，并标记当前脚手架状态和下一阶段的无压力求解精简目标。
### 2026-07-28 — [根因修复] 材质透明度恒 0：Renderer 绑定了空 TextureRenderTarget，而非 Niagara 内部 RT 子变量

正式 `NS_SSPR_ParticleTrails_Main` 原先把材质参数 `TrajectoryTexture` 绑定到 `User.SSPR_TrajectoryRT`；该对象参数默认值为 `None`，因此材质纹理采样恒为 0，Opacity 也恒为 0。现新增 Niagara 自管理 `User.SSPR_SimRT`（RenderTarget2D DI，2048×2048 RGBA16F、Bilinear、`bInheritUserParameterSettings=false`）与 Grid 迭代 Stage `SSPR Resolve Grid To Material`。Scratch 模块 `SSPR_ResolveGridToSimRT` 逐 Cell 读取自动清零的 `User.SSPR_TrajectoryGrid` 并覆盖写入 SimRT；Renderer 改绑 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget`。VibeUE 的 ScratchPadService 同步补充了 Grid2D Stage 迭代源配置与内部 RenderTarget2D User Parameter 创建接口。最终 PIE 验收：运行时生成 2048×2048 RGBA16F 纹理；256×256 材质桥读回 63 个非零像素，R 最大 118；Niagara UpToDate、0 错误、0 警告。修复前资产备份位于 `Saved/CodexBackups/NS_SSPR_ParticleTrails_Main_before_internal_simrt_20260728_2135.uasset`。

### 2026-07-28 — [里程碑·基线冻结] M2 粒子到材质链路完成视觉验收，正式进入 M3 图像处理

用户确认 `GPU 粒子 → View.WorldToClip → Grid2D → Niagara 自管 SimRT → Renderer 材质参数 → ScreenPosition.ViewportUV` 全流程已彻底跑通。关闭 TSR/TAA 的会话级 A/B 对照中链路和比例保持正确，当前离散亮点被认定为 M3 的原始密度输入，而非依靠时序抗锯齿修复的错误。自 v1.4 起冻结 Niagara 数据生产链；后续优先只改最终材质，依次建立 Raw/Core/Small/Large、多尺度混合、密度整形、边缘破碎、指数消光与烟雾着色。

### 2026-07-28 — [里程碑·M3 函数链跑通] 父材质只编排，四个材质函数完成高品质空间重建

正式函数库落在 `/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQBaseline`：RawDensity、MultiScaleDensity、DensityShape、SmokeResolve。MultiScale 使用连续 7×7/13×13 二项式高斯核（219 taps），DensityShape 从 `Core-Small` 与 `Small-Large` 的真实频段差恢复细丝和宽边，Resolve 使用 Beer–Lambert 指数消光；父材质只负责输入、参数、DebugRaw A/B 与最终 Color/Opacity。已知白图 Processed/Raw 均为 128² 全非零；活动 Niagara 内部 RT 的 512² 回读为 Processed 1407、Raw 1079 个非零像素，证明处理链真实扩大连续覆盖。

### 2026-07-28 — [根因与规则] 原地重建材质函数会残留 FunctionInput GUID

曾对同一函数资产反复“删除表达式并重建”，UE 5.8 仍保留旧 FunctionInput GUID，调用节点出现重名输入；自动连线命中失效 Pin 后，材质表面编译绿色但白纹理端到端输出仍全黑。正式规则改为破坏性接口变更时创建新的干净版本目录，反射检查输入名唯一，并用已知白纹理做非零 Gate；污染的原型函数只保留为未引用归档。

### 2026-07-28 — [清理] 正式验证关卡移除旧 Ping-pong Orchestrator 实例

归档 Blueprint `BP_SSPR_TemporalOrchestrator` 仍有一个 `SSPR_M2A_TemporalOrchestrator` 实例放在正式验证关卡，PIE 会执行旧 Current/History/MID 调度并产生大量 Accessed None。现只删除该关卡实例并保存，归档资产本身保留；重新进入 PIE 后没有产生新的同类运行时错误，正式链路只保留 Niagara 自管 SimRT 与函数化材质。

### 2026-07-28 — [解耦] 增加 HQ 材质实例作为独立视觉调参层

新增 `/Game/SSPR_Validation/M2/ParticleTrails/MI_SSPR_ParticleTrails_HQ_Default`，父级为函数化 `M_SSPR_ParticleTrails_Display`；Niagara Display Renderer 已改绑该实例，`TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 仍完整。函数/父材质保存算法与 HQ 默认值，实例只按需承载美术 Override。重启编辑器后 base/instance 的 Processed/Raw 四条 128² 白图 Gate 均为 16384 个非零像素。

### 2026-07-29 — [版本冻结/待审批] V1 自包含快照与 V2 各向异性高斯 Splat 工作区

当前圆形轨迹写入、Mip 多尺度重建和密度梯度光照版本冻结为 `/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729`；从该快照复制 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2`，主资产重命名为 `NS_SSPR_AnisotropicSplat_Main`、`M_SSPR_AnisotropicSplat_Display`、`MI_SSPR_AnisotropicSplat_HQ` 和 `L_SSPR_AnisotropicSplat_Validation`。UE 的目录复制不会自动重映射跨资产引用，因此又显式修正了两个目录内的材质实例 Parent、全部 Material Function Call 和 Niagara Display Renderer，使版本目录不依赖原 ParticleTrails 材质链。

新增 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` v0.1。新方案使用 Solver 前后位移缓存生成屏幕流向，每粒子写入旋转椭圆高斯，并以原子加法累积真实密度；V1 Mip 重建只保留为低频烟体层。规格当前待用户审批，尚未在 V2 工作副本安装 FlowDelta、各向异性 Splat、RasterizationGrid 或方向张量。

### 2026-07-29 — [根因修复/里程碑] V2 Raster Stage 属性裁剪修复，G0～G3 技术链通过

V2 一度表现为均匀整片、全黑或所有粒子集中到单个像素。最终确认存在两层问题：第一，Raster scratch 曾把调试 `OutMark` 写回 `Particles.SSPR_WriteMark`，导致 Stage 被编译为 `WritesParticles=True`；Partial Particle Update 下外部 UAV 写入无效，强制 Full Update 又会破坏未显式保留的粒子属性。现已把 `OutMark` 改为模块局部输出，Raster Stage 只输出到 `User.SSPR_DensityRaster`，生成元数据确认 `WritesParticles=False`。

第二，在 Raster Stage 改为纯 DI 副作用后，UE 5.8 编译器会裁掉没有被 Renderer 消费的 Position/ScreenDeltaUV。生成 HLSL 虽调用 `Context...Particles.Position`，数据集加载最初只含 Age/Lifetime/UniqueID，因此所有粒子实际读取默认零位置。正式修复是启用 Renderer 0 作为不可见的属性保活器：`RendererVisibility=1`，并将 `SpriteSizeBinding` 指向 `Particles.SSPR_ScreenDeltaUV`；Renderer 1 继续负责最终显示面片。重新编译后 Stage1 数据集明确加载 Position 与 SSPR_ScreenDeltaUV。

Stage1 正式高斯写入改为用持久化 Position 和当前 `PrimaryView.WorldToClip` 直接重投影中心，仅用缓存 ScreenDeltaUV 控制旋转椭圆长轴；密度通过 `RasterizationGrid3D(2048×2048×1)` Q10 整数原子加法累积，Stage2 Resolve 到 Niagara 自管 SimRT。当前原始 2048² 回读：41,353 个非零像素、R 最大约 4.203、R 总量约 23,532.886；Niagara 编译零错误零警告，Raster Stage 不写粒子。当前资产已恢复为正式高斯版本，不再是单点探针，下一步只需用户在视口确认形状后进入 G4 材质细丝/烟体混合。

### 2026-07-29 — [文档] 新增 Niagara Raster / MCP 独立排坑手册

用户完成 V2 G0～G3 视口验收并确认画面正常后，新增 `NIAGARA-RASTER-MCP-PITFALLS.md`。文档将本轮遇到的 Stage 粒子回写、Partial Particle Update、Custom HLSL 属性裁剪、隐藏 Renderer 保活、显式重编译、Parameter Map 主链、Raster Q10 原子累加、Clear、旧运行时 RT、原分辨率读回、MCP 分请求、Gateway 残留、PIE Python 引用泄漏、UBA 提交内存、材质 Pin 与目录复制依赖等问题整理为可复用规则，并给出固定写入→粒子单点→正式高斯→材质的最短诊断顺序。

### 2026-07-29 16:20 — [视觉诊断/调参] 中央暗块来自密度梯度光照，连续性优先使用中性光照

用户指出 V2 仍有明显粒子感且中央出现大块“阴影”。反射检查确认 Display Renderer 不投射阴影，父材质为 Unlit Translucent；暗块实际来自 `MF_SSPR_DensityGradientLighting`。旧 HQ 参数 `Ambient=0.45 / LightStrength=0.65 / GradientStrength=10` 会把高密度背光区域压到约 45% 亮度。当前 `MI_SSPR_AnisotropicSplat_HQ` 改为连续性基线：Filament/Medium/Body=`0.18/0.50/0.32`，Medium/Body 半径=`14/48 px`，DensityGain=`2`，Contrast=`0.48`，Extinction=`2.4`，OpacityScale=`0.82`，并暂用 `Ambient=1 / LightStrength=0`。该设置用于先验收密度连续性，最终体积受光仍待 G4 视觉 Gate 后单独恢复。

### 2026-07-29 16:33 — [高品质基线] SimRT 关闭自动 Mip，V2 改用确定性 LOD0 7×7/13×13 空间重建

针对整片亮度波动曾怀疑动态 SimRT Mip 链与同帧 Renderer 采样存在时序差异，因此将 V2 `User.SSPR_SimRT` 设置为 Bilinear、`MipMapGeneration=Disabled`，并在保持函数接口不变的前提下把 `MF_SSPR_MipPyramidDensity` 内部替换为 LOD0 7×7 Medium 与 13×13 Body 二项式核。材质和 Niagara 编译均通过；当前活动 2048² SimRT 一次原始回读为 32,030 个非零像素、R 最大约 6.77、R 总量约 23,390.58。修改前 System、Material 和函数已复制到 `Saved/CodexBackups/*before_stable_lod0_20260729.uasset`。

后续验证证明：LOD0 路线适合作为当前“质量优先”的确定性空间重建，但它不是整片闪烁的最终根因。函数资产名称和两个 MipBias 兼容输入已经与内部算法不一致，列为视觉 Gate 后的接口收口任务。

### 2026-07-29 16:47 — [根因修复] Fixed Tick 60 Hz 消除静止视口下整片忽明忽暗

用户发现按住右键持续调整镜头时画面稳定，松开后整张面片闪烁；开启 Niagara System Fixed Time 后立即稳定。MCP 读回确认 `fixed_tick_delta=true`、`fixed_tick_delta_time=0.01667s`。UE 5.8 `FNiagaraSystemSimulation::Tick_GameThread` 在 Fixed Tick 模式下累积引擎时间并按固定步长执行 0～N 个补步，Spawn、Solve、Lifetime 和当帧 Raster 密度不再直接使用不规则的渲染帧 DeltaTime。因此本次整片亮度脉动的主要根因是可变时间步，而非粒子数据归零或 Mip 链本身。

Fixed Tick 60 Hz 现作为 V2 高品质基线硬配置。仍需在最终封版前分别限制 30/60/120 FPS，确认低帧率补步成本和画面一致性。

### 2026-07-29 — [文档同步] V2 当前事实基线统一到主文档

`AI-BRIEF.md`、`BACKLOG.md`、`WISPY-FLUID-SPEC.md` 与 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 已统一到 V2 G4 当前状态：旧 Ping-pong 为归档；正式链路为粒子→RasterizationGrid3D 单层原子密度→Niagara 自管 SimRT→V2 材质；SimRT 无自动 Mip；材质使用 LOD0 7×7/13×13；Fixed Tick 为 60 Hz；中性光照用于当前连续性 Gate。尚未完成项明确收敛为最终视觉 Gate、冷启动回归、函数命名/接口收口、完整 V2 快照、未引用资产清理和文档 Git 提交。

### 2026-07-29 22:08 — [本地封存] UE、VibeUE、SSPR 资产与项目记录建立统一恢复点

UE NiagaraEditor 修复已保持在干净分支 `sspr-niagaraeditor-fixes`，提交 `98d86a7` 并带标签 `sspr-niagaraeditor-fixes-ue5.8.0`。VibeUE 分支 `sspr-scratchpad-fixes` 将 Simulation Stage、内部 RT2D 和 RasterizationGrid3D MCP authoring API 提交为 `af697f9`。`Content/SSPR_Validation`、两个源码分支分别生成 ZIP/Git bundle，并在 `recovery/README.md` 记录 SHA-256。本次仅做本地提交与恢复快照，没有推送远端；该快照为 G4 视觉 Gate 前检查点，不替代 Gate 通过后的最终 V2 封版。

### 2026-07-29 23:15 — [G4 候选/待人工视觉确认] 修正 7×7/13×13 未接入材质，并抑制无邻域支持的粒子核心
用户截图显示轮廓锯齿、点链与白色饱和核心仍然严重。资产只读复核发现，`MF_SSPR_MipPyramidDensity` 已包含既定 LOD0 7×7 Medium + 13×13 Body 代码，但 `M_SSPR_AnisotropicSplat_Display` 实际仍连接旧的 `MF_SSPR_MipBodyDensity -> MF_SSPR_FilamentBodyBlend` 3×3/5×5 链；此前记录的 219-tap 基线并未真正进入最终 `DensityShape`。现已在不改 Niagara 数据链和既有函数接口的前提下，把高品质函数的 `Scales` 直接接入 `MF_SSPR_DensityShape`。

`MF_SSPR_DensityShape` 保持原九输入接口，只修改内部整形：Raw Core 必须同时获得 Medium/Body 的相对与绝对邻域支持才可参与锐化，频段差值改为正值限定，避免孤立 splat 与负差分重新进入 Alpha。HQ 候选参数改为 Filament/Medium/Body=`0.06/0.58/0.36`、Medium/Body Radius=`16/52 px`、Detail=`0`、BlackPoint=`0.003`、DensityGain=`1.4`、Contrast=`1.10`、Extinction=`1.7`、OpacityScale=`0.82`；继续保持 Ambient=`1`、LightStrength=`0`、Fixed Tick=`0.01667s`、SimRT 2048² RGBA16F/Bilinear/无 Mip。

修改前函数、父材质与 MI 已备份到 `recovery/G4_density_support_20260729_230547`。修改后材质编译通过；Niagara Apply/Compile/Save 成功，系统 `UpToDate`、零错误、零警告；组件重绑后两份 Raster clone 均为 `2048×2048×1`。活动 SimRT 连续两次各推进 120 帧后的原始回读总量约 `2,403,536.68` 与 `2,405,154.29`，非零像素约 `225,574` 与 `217,915`，没有随运行单调画满。当前只完成技术 Gate，最终锯齿、粒子感、拉丝/烟体平衡及关闭 TAA/TSR 的视觉结果仍必须由用户观察确认。

### 2026-07-30 11:03 — [V2 冻结备份] G5 修改前建立完整 V2_pre_G5 恢复点

在任何 G5 资产修改前，将 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2` 整个内容目录及 `AI-BRIEF.md`、`WISPY-FLUID-SPEC.md`、`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`、`NIAGARA-RASTER-MCP-PITFALLS.md`、`LOG.md` 冻结到 `recovery/V2_pre_G5_20260730_110322`。共备份 29 个 UE 资产与 5 份设计文档；源/目标逐文件 SHA-256 对比为零缺失、零不一致。该目录是当前 G4 视觉候选进入 G5 前的正式回退点。

### 2026-07-30 — [G5.1/G5.2 技术 Gate] 当前帧方向张量与粒子深度场进入 Main/Aux RT

用户批准 v0.4 G5 方案后，第一实施步只落地方向/深度字段与 Debug，不接最终 Streamline 或纵深光照。`User.SSPR_DensityRaster` 扩展为 `2048×2048×1`、6 属性、Precision=`65535`：属性 0～4 为 Density Q10、双角度 TensorCos2/Sin2 Q10、DepthMoment1/2 Q16，属性 5 以原子最大值写入归一化 FrontInvDepth。新增 `User.SSPR_DepthNearUU=0`、`DepthFarUU=10000`、`FrontDepthWeightThreshold=0.1`。Raster 继续按当前相机重投影，保持纯 DI 副作用和 `WritesParticles=False`，未增加任何 History 读取或跨帧反馈。

Resolve 现在完整覆盖两张 Niagara 自管当前帧 RT：Main `User.SSPR_SimRT = (Density, TensorCos2, TensorSin2, MeanDepth)`；新增 Aux `User.SSPR_AuxRT = (DepthSigma, FrontDepth, Reserved, Coverage)`。Aux 为 `2048×2048 RGBA16F`、Bilinear、Mip Disabled。Renderer 新增 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`；独立新建 `Functions/G5/MF_SSPR_G5_FieldDebug`、`M_SSPR_G5_FieldDebug` 与 `MI_SSPR_G5_FieldDebug`，没有修改 G4 父材质接口。Debug MI 当前使用模式 6，一张视口四宫格同时显示方向/一致性、MeanDepth、DepthSigma、FrontDepth。

Apply/Compile/Save、Renderer 双绑定核对、组件 Rebind/Reinitialize 与关卡保存均完成。Niagara 状态为 `UpToDate`、零错误、零警告；Fixed Tick 仍为 `true / 0.01667s`；HQ 与 Debug 材质均零编译错误。完整 2048² 原始回读可唯一识别 Main/Aux：Main R 最大约 `143.375`，G/B 均含 `[-1,1]` 的有符号方向分量，A MeanDepth 最大约 `0.0885`；Aux R DepthSigma 最大约 `0.05487`，G FrontDepth 最大约 `0.0885`，B 恒零，A Coverage 非零像素 `234,656 / 4,194,304`（约 5.6%）。连续推进数百帧后未画满，所有通道无 NaN/Inf。下一 Gate 只需用户观察当前四宫格是否方向连续、深度随前后层次变化、空区无伪值；通过后再实施 G5.3/G5.4。

首次四宫格截图中方向场已呈连续彩色变化，但 MeanDepth、DepthSigma、FrontDepth 三格几乎全蓝。原始 RT 数值证明三场非空；进一步反射检查发现原型 `MF_SSPR_G5_FieldDebug` 被多次原地重建后残留两代 Custom 节点，父材质复制到了不含 `DepthDisplayGain` 的旧 HLSL。按既定“接口变化新建干净函数”规则，现新建 `MF_SSPR_G5_FieldDebugV2`、`M_SSPR_G5_FieldDebugV2`、`MI_SSPR_G5_FieldDebugV2`，新父材质只有 1 个 Custom 节点和 10 个表达式，代码明确包含 Depth/Sigma 显示增益；Renderer 已改绑 V2 MI。当前 Debug 参数为 `DepthDisplayGain=10`、`SigmaDisplayGain=32`，旧原型不再被引用，待字段视觉 Gate 后统一清理。

第二张用户四宫格截图确认字段视觉 Gate 通过：方向张量颜色沿弯曲主流连续变化；MeanDepth 与 FrontDepth 呈稳定暖色色阶且轮廓同帧对齐；DepthSigma 大部分薄区域保持低值蓝色，而中央厚重叠区出现连续青色带。Mean/Front 接近符合当前喷流较窄的前后跨度，并非场失效。

### 2026-07-30 — [G5.3/G5.4 首个生产候选] 无历史双向 RK2 Streamline 与粒子深度约束接入

字段 Gate 通过后，先把当前完整 G5 字段状态冻结到 `recovery/G5_fields_pre_streamline_20260730_124836`；35 个资产逐文件 SHA-256 对比零不一致。随后只新建独立资产，不修改 G4 生产父材质与 MI：`MF_SSPR_G5_StreamlineDensityV1`、`MF_SSPR_G5_DepthCueV1`、`M_SSPR_AnisotropicSplat_G5`、`MI_SSPR_AnisotropicSplat_G5_HQ`。

Streamline 为材质内当前帧双向 RK2：每侧编译上限 8 步、默认活动 6 步、3 px 步长；双角度张量解码后用前一步切线保持符号连续。3×3 邻域只扩展 Direction/Depth Guidance，不直接模糊密度；沿曲线 Gather 使用 Coherence、曲率、MeanDepth/DepthSigma 双边权重、渐细核、双侧支持和孤立 Core 衰减。Medium/Body 首候选收窄为 `12/40 px`，Filament/Medium/Body 权重为 `0.25/0.50/0.25`。`MF_SSPR_G5_DepthCueV1` 以低强度 Mean/FrontDepth 与 Sigma 厚度衰减提供纵深提示；仍不启用强密度梯度阴影、不写 PixelDepth、不使用 History。

新 G5 父材质共 52 个表达式并零错误编译；Renderer 已绑定 `MI_SSPR_AnisotropicSplat_G5_HQ`，Main/Aux 子变量绑定均保留。Niagara Apply/Compile/Save、组件 Rebind/Reinitialize、关卡保存完成，系统 `UpToDate`、零错误、零警告；Fixed Tick、2048² Raster/Main/Aux、Bilinear 和禁用 Mip 均未改变。当前进入用户最终烟雾视觉 Gate。

### 2026-07-30 — [G5 视觉失败复盘与 Visual V2 候选] 末端连通性门控和真实深度受光

用户的首张 G5 生产近景截图确认初版未通过视觉 Gate：稀疏末端仍能辨认独立粒子簇，主体在高消光下接近纯白，几乎没有纵深。初版实际已经写入并采样方向/深度字段，但 `MF_SSPR_G5_DepthCueV1` 只对 Emissive 做低强度绝对深度、Sigma 和前后分离乘法；当前覆盖区平均 `MeanDepth≈0.0576`、`FrontDepth≈0.0553`、`DepthSigma≈0.0048`，按初版默认参数平均只造成约 2～3% 亮度变化。与此同时 `G5_IsolatedCoreScale=0.12` 明确保留了孤立核心，Medium/Body 也没有用 Streamline 连通性门控，因此字段技术 Gate 通过并不等价于最终画面获得了纵深或消除了粒子感。

修改前将 39 个 V2 资产和 5 份文档冻结到 `recovery/G5_visual_v1_pre_fix_20260730_130435`，逐文件 SHA-256 为零差异。随后保持 G4 与 G5 初版不变，新建 `MF_SSPR_G5_StreamlineDensityV2`、`MF_SSPR_G5_DepthLightingV2`、`M_SSPR_AnisotropicSplat_G5_V2`、`MI_SSPR_AnisotropicSplat_G5_V2_HQ`。Streamline V2 使用每侧 8 步、4 px RK2，并在局部法线方向增加五通道窄带 Gather；孤立 Core 设为 0，Medium/Body 必须获得 Streamline 连通性后才可进入密度整形。DepthLighting V2 用 FrontDepth 四邻域梯度构造屏幕空间表面法线，并叠加 DepthSigma 与 Mean/Front 分离产生的当前帧自遮蔽；仍不读取 History、不写 PixelDepth。

Visual V2 材质为 52 个表达式，编译零错误；Renderer 已绑定 `MI_SSPR_AnisotropicSplat_G5_V2_HQ`，Main/Aux 绑定完整。Niagara Apply/Compile/Save、Rebind/Reinitialize 与关卡保存成功，系统 `UpToDate`、零错误、零警告。活动 2048² RT 回读可唯一识别 Main/Aux，所有通道无 NaN/Inf，Coverage 未画满；Raster、Main/Aux 的分辨率、RGBA16F、Bilinear、Mip Disabled 和 Fixed Tick 均保持原基线。当前仅完成技术 Gate，近景末端、标准距离、转镜和平移仍需用户观察。

### 2026-07-30 — [视觉结论/路线修正] Visual V2 仍保留粒子感，后续转入当前帧归一化场重建

用户近景截图确认 Visual V2 仍未通过最终视觉 Gate：稀疏末端和外围仍能逐个辨认离散粒子，主体虽然比旧版连续，但宽糊、偏白，FrontDepth/MeanDepth/DepthSigma 对最终画面的纵深贡献仍不明显。当前已使用的手段包括各向异性粒子 Raster、LOD0 7×7/13×13 多尺度重建、方向张量、双向 RK2 Streamline、五通道横向 Gather、孤立 Core 清零、Medium/Body 连通性门控、深度双边权重与 FrontDepth 梯度受光；这些技术 Gate 均有效，但组合仍属于对离散密度的后处理，不能从根上形成稳定连续场。

后续不再通过继续扩大 Blur、增加 History 或恢复 Ping-pong 处理。已批准的新顺序是：紧支撑当前帧粒子贡献 → Coverage/方向/深度矩正则化 → 自适应归一化场对齐卷积 → 同一连续场分频得到 Filament/Medium/Body → Front/Mean/Sigma 构造厚度、透射与可见纵深。Visual V2 保留为可回退资产，下一实现只在 V2 开发目录新增独立函数/材质。

### 2026-07-30 — [V3 冻结快照] G5 Visual V2 输出链整理为自包含版本

按用户要求，将当前最终出效果的相互引用闭包整理到 `/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730`，而不是简单复制整个开发目录。快照共 11 个资产：V3 Niagara System、V3 父材质、V3 HQ MI、V3 验证关卡，以及按 `Functions/RasterInput`、`Functions/Reconstruction`、`Functions/Shading`、`Functions/Utility` 分类的 7 个实际被父材质调用的函数。7 个 Material Function Call、MI Parent、Niagara Renderer 1 材质与验证关卡主 NiagaraComponent 均已重定向到 V3 内部；Renderer 继续保留 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 和 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`。闭包审计未发现对 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2` 的效果链引用。

V3 Apply/Compile/Save 成功；Niagara `UpToDate`、零错误、零警告；材质零编译错误；Fixed Tick 保持 `true / 0.01667 s`。活动组件 Rebind/Reinitialize 后，Raster clone 为 `2048×2048×1`、Precision `65535`、Clear=true；Main/Aux 为 `2048×2048 RGBA16F`、Bilinear、Mip Disabled。完整 2048² 原始回读唯一识别一张 Main 和一张 Aux，两者非空、互异、无 NaN/Inf 且远未画满。V3 现冻结不再修改，编辑器已切回 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2/L_SSPR_AnisotropicSplat_Validation` 继续开发。

### 2026-07-30 — [FieldRecon V1/待人工视觉确认] Coverage 归一化场对齐卷积与深度传输接入

V3 冻结后，在 V2 开发目录新增 `MF_SSPR_G5_NormalizedFieldReconstructionV1`、`MF_SSPR_G5_DepthTransportLightingV1`、`M_SSPR_AnisotropicSplat_FieldRecon_V1` 与 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ`。FieldRecon 不再调用旧 LOD0 7×7/13×13 `MipPyramidDensity`，也不调用 G5 Streamline V1/V2；查询点先以 3×3 Coverage/密度加权邻域正则化方向张量和深度，再以每侧 8 步、每步 5 横向通道做无历史场对齐采样。Filament/Medium/Body 各自积累密度分子、Coverage/一致性/深度置信度分母与支持包络；双侧支持负责连接间隙，单侧贡献只以分频受限比例保留尖端，Raw 单粒子不再作为可见兜底。

DepthTransport 从正则化的 FrontDepth、MeanDepth、DepthSigma 推导 BackDepth、厚度与透射，并输出带近远色调、厚度染色、方向受光和自透射的 RGB 因子。首个 HQ 候选 SmokeColor 为 `(0.52, 0.58, 0.68)`，Ambient/Directional=`0.62/0.50`，使深度变化不再被纯白高环境光完全吞没。

新材质 51 个表达式、零编译错误；实际函数闭包只有 FieldRecon、DepthTransport、DensityShape、SmokeResolve、ScreenEdgeMask，审计确认无旧 Mip/Streamline 调用和无 `History` token。Renderer 1 已绑定新 MI 且保留 Main/Aux 子变量映射；Niagara Apply/Compile/Save、组件 Rebind/Reinitialize 和关卡保存完成，系统 `UpToDate`、零错误、零警告，Fixed Tick 保持 `true / 0.01667 s`。完整 2048² 原始回读唯一识别 Main/Aux，当前覆盖 `82,158 / 4,194,304`，所有通道无 NaN/Inf、未画满。下一步必须由用户观察标准距离和稀疏末端，确认粒子感、模糊度、流丝连续性与纵深是否得到实质改善。

### 2026-07-30 — [FieldRecon V1 首轮视觉结论/Connected MI] 圆点减少，但刷毛排线与孔洞仍未过 Gate

用户提供标准距离和近景截图。相对 Visual V2，独立圆点/软泡已明显减少，离散贡献开始沿方向场形成短丝，证明 Coverage 归一化场对齐路线有效；但当前输出仍未通过最终 Gate：近景能看到大量方向一致的短刷毛和离散排线，主体透明度偏低，Medium/Body 支撑不足造成背景穿孔，纵深蓝灰变化虽已出现但被稀疏密度削弱。

保留初始 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ` 不变，新建并绑定 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`。主要调整为 StepPx `3.25→2.25`、GuideRadius `3.5→4.5`、Medium/Body Cross `4/13→2.75/8.5`、SupportGain `0.38→0.85`、OneSidedBlend `0.32→0.46`，Filament 权重/增益下调，Medium/Body 上调，Detail/Edge 设零，BlackPoint `0.006→0.001`，并提高低密度响应、消光与不透明度。目标是先消除刷毛采样节奏和孔洞，再恢复尖细 Filament 比例。

### 2026-07-30 — [运行实例修复] 重复 Rebind 累积 DI clone 导致活动 RT 全零

Connected MI 绑定后的严格 RT Gate 首次失败：System 编译、Renderer 材质和 Main/Aux 子变量绑定均正确，但活动 Main/Aux 全零。检查关卡组件发现反复执行 `set_asset(None) → set_asset(System)` 已把运行实例从预期的 `1 Raster + 2 RT` 累积为多代 DI override，最高观察到 `3 Raster + 5 RT`；重新载入关卡仍为空，说明污染已序列化到组件，而非一次冷启动延迟。

在 V3 冻结快照可恢复的前提下，记录旧 Actor Transform，在同一 `Location=(480,110,570)` 创建干净 NiagaraActor，只绑定 V2 System 一次，配置 `1×2048²×1 RasterizationGrid3D` 与 `2×2048² RGBA16F/Bilinear/Mip Disabled RT`，激活验证后删除旧污染 Actor，并以原标签保存关卡。严格原始回读随后恢复：唯一 Main/Aux、非零覆盖 `84,757 / 4,194,304`、无 NaN/Inf、未画满。旧 Actor 已删除但可由 V3 恢复。`_g5_rebind_reinitialize.py` 已修改为同一 System 资产只原地 Reinitialize；真实 DI 接口变化今后使用一次性干净组件替换，不再积累 override。

### 2026-07-30 — [近景性能 Gate] Dense Raster 追帧螺旋修复为质量守恒 Sparse Raster

解析用户提供的 `precisefluid-0-2026.07.30-12.57.57.profViz` 后确认，“RasterGrid 100+ ms”不是单次迭代：该帧总 GPU 约 `467.993 ms`，Niagara 因 Fixed Tick 在一个渲染帧内补做了 24 次模拟；每次 Raster 为 `17.70～18.88 ms`，Resolve 约 `0.19～0.20 ms`，Grid Clear 约 `0.325 ms`，粒子 Dispatch 从 `280,839` 增至 `300,010`。单次 Raster 已超过 `16.67 ms` 固定步长，构成“帧慢→补步→GPU 更慢→继续补步”的追帧螺旋。资产读回同时确认当前真实配置为 `SpawnRate=50,000/s`、Lifetime=`5s`，约 25 万稳态粒子，而不是旧规格里的约 2.5 万。

旧 Raster 每粒子固定枚举 `49×11=539` 个高斯候选，每个有效样本最多写入 5 个加法矩和 1 个前沿深度最大值。当前在不降低 `2048²`、粒子数、材质采样数，不关闭 Fixed Tick、不改变 Main/Aux 六属性语义且不引入 History 的前提下，改为质量守恒 Sparse Raster：投影/近平面/扩展屏幕边界先剔除，候选上限改为 `25×5=125`，并以 Dense 可见核的可分离权重和对 Sparse 权重和进行单粒子质量归一化。Dense HLSL SHA-256 为 `69dc67f6e9a58fa457982b6dfee3889e11e04f838b5934b56cb3891bec20598c`，Sparse HLSL SHA-256 为 `761b87f75279b469d6cd5628dffe3a4c1df04eaa351943e602438c6b438e92b4`；V3 仍是修改前自包含恢复点。

曾先在 `Performance/NS_SSPR_AnisotropicSplat_PerfSparseV1` 上做候选，但发现当前 UE 5.8 对这套含嵌入式 Scratch Simulation Stage 的 Niagara System 执行 `duplicate_asset` 后，即使复制品 `UpToDate`、图连接与常规模块输入一致，未修改的复制对照运行时 Main/Aux 仍全零；Sparse 复制品也只在单一投影中心附近产生约 15 个非零像素。由此不能把 Niagara 资产复制成功视为可运行备份 Gate。关卡已恢复原 V2 System，Sparse HLSL 在原活动资产上原地 Apply/Compile/Save，并通过运行 RT Gate。

程序化 `ProfileGPU` 在约 `251,666～253,333` 粒子下得到 Sparse Raster 首次 `0.930 ms`、随后 `0.559/0.563 ms`，稳态约 `0.56 ms`；Resolve 为 `0.153～0.158 ms`。相对旧 Dense Raster 单次降低约 `97%`，显著低于 60 Hz 固定步长。快速原始 Gate 在三块区域共抽样 `393,216` 像素：Main R 非零 `6,970`、最大 `4.2109375`，G/B 仍含正负方向值；Aux R 非零 `4,218`，G/A 非零 `6,970`、A 最大 `1.0`；无 NaN/Inf、未画满。最终系统 `UpToDate`、零错误、零警告，`SpawnRate=50,000/s`、Fixed Tick=`true / 0.01667s`、Main/Aux 2048² RGBA16F/Bilinear/Mip Disabled 均未改变。下一步只需用户在同一近景与动态转镜条件下确认 Sparse 核没有引入可见点列、缺口或密度宽度退化。

### 2026-07-30 — [性能候选失败/紧急恢复] Sparse 短时 Gate 为假阳性，回滚原始 Dense G5

用户首次视觉检查发现烟雾完全消失。跨请求推进 60 帧后，活动组件所有 Main/Aux 均为零，证明此前“性能 Gate 已通过”的结论无效。当前组件已累积为 `2 Raster + 4 RT`；恢复 Dense HLSL、重新编译和替换为干净 V2 组件后仍全零。进一步发现 V3 复制关卡的主组件已随 V2 一起改回 V2 System，说明其外部 Actor 并未形成可靠隔离；`duplicate_asset(NiagaraSystem)` 与复制关卡都不能作为本轮运行恢复点。

原 V2 `.uasset` 因编辑器进程锁定无法在线覆盖，先备份为 `Saved/CodexBackups/NS_SSPR_AnisotropicSplat_Main_broken_sparse_blank_20260730.uasset`。随后把 `recovery/G5_visual_v1_pre_fix_20260730_130435` 中 SHA-256=`E122D5266E1C10934696797DB45D39714A8B20D00862C46AD3A05AA865363E52` 的同包名原始二进制复制到 `/Game/SSPR_Validation/Recovery/DenseG5_20260730/NS_SSPR_AnisotropicSplat_Main`。恢复 System 使用原 `49×11` Dense Raster，Renderer 绑定 `MI_SSPR_AnisotropicSplat_G5_HQ`，不是最新 FieldRecon。

恢复 Gate 改为两个独立 MCP 请求：请求 A 只生成并保留严格 `1 Raster + 2 RT` 的干净候选，让异步 Niagara GPU 编译和渲染线程实际跑帧；请求 B 再推进 300 帧、回读并替换空白 Actor。最终 Main 抽样非零 `33,517`、最大 `4.4921875`，方向 G/B 含正负值；Aux R 非零 `17,742`、Coverage 非零 `33,517`、A 最大 `1`，无 NaN/Inf。恢复 System `UpToDate`、零错误零警告，关卡已保存。此前 `0.56 ms` 只代表失效/空路径的短时数据，Sparse 性能 Gate 正式判失败；下一步先由用户确认 Dense G5 重新可见，再恢复最新 FieldRecon 与重新设计性能方案。

用户确认 Dense G5 已重新可见。随后只修改恢复 System 的 Renderer 1，将材质从旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 切回 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`，Main/Aux 子变量绑定保持不变。Apply/Compile/Save 后为 `UpToDate`、零错误零警告；独立下一请求推进 60 帧后 Main/Aux 仍非零。由于 Renderer Apply 会使已存在组件热重载并累积到 `3 Raster + 6 RT`，最后再以最终已编译 System 创建一次干净候选，跨请求回读通过后替换旧组件。当前活动组件严格为 `1 RasterizationGrid3D + 2 RenderTarget2D`，另有 1 个 System 正式遗留 Grid2D；关卡已保存，不再对该恢复 System 执行 Apply/Rebind。

### 2026-07-30 — [视觉基线回退] 用户选择旧 G5 HQ，FieldRecon Connected 降为实验候选

用户对恢复后的 FieldRecon Connected 近景截图做出明确判断：旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 的表现更好。FieldRecon 的 Coverage/一致性/深度置信度归一化会在稀疏支撑处削薄 Medium/Body，较强的 DepthTransport 又进一步拉开局部亮度与色调，结果是短丝、孔洞和孤立贡献更容易被辨认，主观粒子感反而强于旧 G5。该结论不是否定 Main/Aux 深度字段，而是否定当前 FieldRecon 把深度传输与支撑归一化耦合到最终显示的方式。

修改前已备份恢复 System 到 `Saved/CodexBackups/NS_SSPR_RecoveryDense_FieldRecon_before_G5_visual_restore_20260730.uasset`。Renderer 1 已切回 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2/MI_SSPR_AnisotropicSplat_G5_HQ`，并保留 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 与 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`。Apply/Compile/Save 后 System 为 `UpToDate`、零错误零警告。材质热重载把旧活动组件累积为 `2 Raster + 4 RT`，因此再次用最终已编译 System 生成一次干净 Actor，并在下一独立请求推进 300 帧、回读 Main/Aux 后替换旧 Actor。

最终活动组件严格为 `1 RasterizationGrid3D + 2 RenderTarget2D`，另有 1 个正式遗留 `Grid2DCollection`。跨请求三块区域共抽样 `393,216` 像素：活动 Main R 非零 `41,201`、最大 `38.625`，G/B 含正负方向值；活动 Aux R 非零 `28,886`、Coverage 非零 `41,201`、A 最大 `1.0`；全部通道无 NaN/Inf、未画满。关卡已保存，当前人工视觉基线正式恢复为旧 G5 HQ；FieldRecon 资产保留但不再绑定。下一步近景性能优化必须以该基线做对照，且不得再次原地 Apply/Rebind 当前恢复 System。

### 2026-07-30 — [性能候选 V2/待视觉确认] Raw-copy 保守 Sparse 核通过有效 ProfileGPU Gate

为避免再次把 UE `duplicate_asset(NiagaraSystem)` 的空运行副本误当性能结果，从当前可运行 Dense G5 `.uasset` 直接复制同名二进制到 `/Game/SSPR_Validation/Performance/DenseG5SparseV2/NS_SSPR_AnisotropicSplat_Main`，原恢复资产不修改，备份位于 `Saved/CodexBackups/NS_SSPR_RecoveryDense_G5HQ_before_perf_v2_20260730.uasset`。候选只替换 Raster Scratch HLSL：Dense 最大 `49×11=539` 改为保守质量守恒 `33×7=231`，最大候选/原子写入位置下降 `57.14%`；纵横最大间距约 `1.49/1.57 px`，并把中心剔除改为带核扩展范围的屏幕相交测试。粒子数、2048²、Main/Aux 六属性、Fixed Tick、Renderer 双绑定和旧 G5 HQ 均未修改。

候选不是靠空路径得到性能：生成候选 Actor 前记录关卡已有 RT，下一独立请求只读取之后新增的两张 2048² RGBA16F RT。新增 Main/Aux 均非零且签名唯一，Main G/B 含正负方向值，Aux B 恒零、A 最大 1，所有通道无 NaN/Inf。随后强制重绘视口取得有效 ProfileGPU：在 `251,667～254,167` 粒子下，四个 Fixed Tick 的 Raster 分别为 `0.715/0.697/0.706/0.703 ms`，Clear 为 `0.324～0.325 ms`，Resolve 为 `0.156～0.165 ms`，Particle Update 为 `0.111～0.132 ms`；Niagara GPU Compute 四步合计 `5.242 ms`，整帧 `15.945 ms`。相对 Dense Raster `17.70～18.88 ms/步`，有效 Raster 提速约 `24.8～27.1×`。

2026-07-30 性能 Gate 纠正：用户指出当前近景仍明显卡顿后复核，确认上面的 Sparse V2 Profile 没有记录相机姿态，不能与用户提供的近景 Dense `.profViz` 直接相除，`24.8～27.1×` 结论撤回。资产/HLSL 修改本身真实存在：Sparse V2 的原子写入候选上限为 `33×7=231`，但为了精确质量守恒，每粒子仍额外执行 `49+11+33+7` 次一维高斯权重求和，并保留大量 `exp()`，所以原子候选减少 `57.14%` 不代表总 Stage 时间同幅下降。读回当前视口相机距 Niagara 约 `1194 uu` 后再次触发 ProfileGPU，只捕获到 Slate `0.09 ms`，没有 Niagara 场景事件；性能 Gate 重新打开，下一步必须由用户让关卡视口保持前台后，在完全相同相机下分别抓 Dense/Sparse V2。

同日止血措施：本地 UE 5.8 源码 `NiagaraSystemSimulation.cpp` 显示 Fixed Tick 每帧补步上限由 `fx.Niagara.SystemSimulation.MaxTickSubsteps` 控制，默认值为 `100`。当前编辑器会话已通过 MCP 将其临时设为 `4`，日志确认 `LastSetBy: Console`。这保留 Niagara System 的 Fixed Tick `0.01667s`，但单帧最多执行 4 个子步，从机制上阻止旧 `.profViz` 的 24 步追帧螺旋。该 CVar 尚未持久化，重启恢复默认；单次 Raster 仍需继续优化。

### 2026-07-30 — [原始粒子对照模式] Renderer 0 可见性修复待验证

用户需要同时观察原始粒子输入与 G5 重建结果。检查恢复 Dense/Sparse 候选 Renderer 0 后确认：它并非简单关闭，而是 `RendererVisibility=1`，且 `SpriteSizeBinding` 错绑到 `Particles.SSPR_ScreenDeltaUV`；该值是屏幕位移量，通常很小，会让原始 Sprite 看起来像透明。当前已备份 Sparse V2 二进制到 `Saved/CodexBackups/NS_SSPR_SparseV2_before_raw_particle_compare_20260730.uasset`，并提交候选设置：`bIsEnabled=true`、`RendererVisibility=0`、`SpriteSizeBinding=Particles.SpriteSize`。设置尚未完成 Apply/Compile/Save/Reinitialize，故暂不宣称原始粒子已可见；Renderer 1 的 G5 HQ 与 Main/Aux 绑定保持不变。

技术查询确认候选 `UpToDate`、零错误零警告，Renderer 仍绑定 `MI_SSPR_AnisotropicSplat_G5_HQ` 和两张 RT 子变量。资产级 User DI 严格为 `1 Raster + 2 RT + 1 Grid2D`；但 `NiagaraComponent` 在跨请求参数同步后仍生成第二套 override 子对象。运行时只创建两张新 RT，ProfileGPU 也只执行一套 Raster/Resolve，因此当前性能数据有效；该元数据重复仍需在视觉通过后收口，不能把候选直接视为最终封版。当前 User 标量及作用已整理到 `NIAGARA-USER-PARAMETERS.md`。

### 2026-08-03 — [项目维护] 项目目录改名 ScreenSpaceParticleReconstruction -> SSPR

名称过长影响日常使用，目录经 `git mv` 改名为 `work/SSPR`，git 全量识别为 rename（`R` 状态），文件历史与内容完整保留，464 个文件字节不变。同步修复 23 个文本文件中硬编码的旧绝对路径：22 个 Python/PowerShell 脚本的 `ROOT` 常量（`_perf_*`、`_v2_*`、`_v3_*`、`_g5_*`、`_parse_emitter*`、`_particlemain_add_grid_atomic.ps1`）与 `VISUAL-GATE-HANDOFF-PROMPT.md` 的 6 处路径及接入命令（现为 `/project SSPR`）。删除失效的 `__pycache__`。项目内已零残留旧路径。

刻意未改两处：`archive/MCP-Json-Archive-20260731/` 下约 330 个历史 MCP 请求/响应快照属冻结记录，改写会篡改历史证据；`.qoder/repowiki/` 下 200 处引用为可重新生成的索引缓存。UE 侧资产路径为 `/Game/SSPR_Validation/...`，与文件夹名无关，引擎工程不受影响。

### 2026-08-03 — [规范对齐] 存量 UE 项目补齐 UEAgent-first 导航块

远端 `6737ff6` 引入 UE 项目路由规范后，存量项目的 `AI-BRIEF.md` 均缺少 `<!-- iris-project-kind: ue -->` 标记，按新 `/project` 流程接入时不会走 UEAgent-first 路由。已为 8 个项目补齐标记与导航块（纯追加，+24 行、零删除）：SSPR、EffectPipeline、AIEffectFoundry、Bifrost、GasRibbon、GaussianVolume、UE-NeuralRender-Lab 使用标准块，链接指向 `../UEAgent/AGENTS.md` 与 `../UEAgent/skills/ue-mcp-workflows/HOTPATH.md`，并写明 `route.json` -> `compact_context.ps1` -> `doctor.ps1` 顺序、`CACHE_READ`/`NEEDS_DOCTOR`/`BLOCKED` 分支及离线分析例外。四个链接目标均已验证存在。

RenderDocMCP 按 AGENTS.md 允许的条件式写法处理：其主 MCP 是自有 RenderDoc stdio bridge，`.rdc` 抓帧与 Shader 反汇编属纯离线路径不需要 UEAgent 路由，仅当任务要读 live UE 状态或修改/保存 UE 工程时才强制入 gate，并明确不得另建第二套 UE MCP gate。

刻意未标记两个项目：`work/UEAgent/AI-BRIEF.md` 本身是 gate source，AGENTS.md 明文豁免 consumer 标记；`work/Portfolio` 是只做跨项目编排的枢纽，其 brief 明确不写引擎代码、不做 shader，技术执行在卫星项目完成，按 AGENTS.md 的"不得从项目名推断 UE 标记"不应标记。`recovery/` 下两份历史 AI-BRIEF 属冻结快照，仅随目录改名移动，内容未改。

### 2026-08-03 16:20 — [历史状态快照·已过期] 当时的 M3 主线与 Spec/Backlog 进度统一

这是 2026-08-03 当时的状态快照，不是当前执行入口。核对当时加载关卡、M3 V4 Dev 资源闭包、近期 Gate 记录和三份 Spec 后，主线为 `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev` 的 Dense `49×11`，Sparse V2 仅为有效 RT 已通过但无同机位性能/视觉证据的旁路候选；当时 P1 尚未合入 M3、P0 也尚未启动。当前状态以文件顶部“当前真相”和两份现行 Spec 为准。

### 2026-08-03 17:03 — [P1 主线通过] Raster/Resolve 与 Fixed Tick substep 解耦

先将 M3 Dense 主线 System 同名二进制备份到 `Saved/CodexBackups/P1_BeforeMerge_20260803/NS_SSPR_AnisotropicSplat_V4_Dev.uasset`，备份 SHA-256 为 `3124ED1CCA6C91FE1465DF94503ACFB54FD20148CE70738A5F1A4F1A2760FE68`。随后在 `Fountain` Emitter Update 新增最小 scratch 模块 `P1_EmitterFrameGate`：读取 `Engine.System.CurrentTimeStep`/`NumTimeSteps`，写 bool `Emitter.P1_IsLastSubstep`；`SSPR Rasterize Trails` 与 `SSPR Resolve Grid To Material` 的 EnabledBinding 均绑定 `Fountain.P1_IsLastSubstep`。Apply/Compile/Save 成功，System `UpToDate`、零错误零警告；保存后资产 SHA-256 为 `7849A28E4357F27DEF3796CEED07D517F64D81FE6305FAF5CC6E7C190D509C62`。

独立请求原地 Reinitialize 当前主线组件，没有 `None→System` 重绑；DI 仍严格为 `1 RasterizationGrid3D + 2 RenderTarget2D + 1 Grid2DCollection`。Main/Aux 原始 RT Gate 唯一识别成功：Main R 最大 `23.796875`、G/B 含正负方向值；Aux Coverage 最大 `1.0`、B 恒零；两者均非零、无 NaN/Inf、未画满。最后关闭资产编辑器页签并在 Level Editor 抓取 ProfileGPU：Frame 11725 内 `12 ParticleSpawnUpdate : 3 Raster : 3 Resolve = 4∶1`，证明两个昂贵 Stage 只在每组四个 Fixed Tick substep 的最后一步运行。捕获机位距离约 `939 uu`，只作为 P1 执行比证据，不冒充历史贴脸最坏机位性能对照。下一执行点正式转为 P0 NeighborQuery Gate A/A2。

### 2026-08-03 — [P0 进行中] NeighborQuery Radius 注册/排序/索引读回已接通，ParticleRead 分支仍阻塞

创建独立同名候选 `/Game/SSPR_Validation/M3/Performance/NeighborGather_V1/NS_SSPR_AnisotropicSplat_V4_Dev`，主线 SHA-256 保持 `7849A28E4357F27DEF3796CEED07D517F64D81FE6305FAF5CC6E7C190D509C62` 未变；Reader 改造前候选备份位于 `Saved/CodexBackups/P0_NeighborGather_PreReader_20260803/`，SHA-256 为 `AAE5896EF04CF5872EB86387D317A31DFB503F5771CD12F6E3DB51116C7B932A`。

候选已配置 System 级共享 `System.P0_NeighborQuery`，`64×64×1`、`MaxCellsPerParticle=4`；Writer `Fountain` 使用内置 `AddParticleToNeighborQuery`，Add Method 已实际映射并固定为 `Radius`（`NewEnumerator3`），Radius=`1/64=0.015625`，WorldToUnit 将 `±1000` 映射到 `0..1`。GPU Reader `P0_NeighborReader` 的内置 `NeighborQuery_Visualize` 链接同一 System DI，其资产内部调用 `GetParticleNeighborCount`、`GetParticleNeighbor` 和 `ParticleRead`；System 最终 `UpToDate`、零错误零警告。

用户同场景实测时间为：未优化约 `40 ms`，加入 Substep Gate 后约 `22 ms`，再加入 NeighborQuery 后约 `12 ms`。按用户要求不再重复测性能，后续只推进功能正确性。

Gate A 尚不能标记完全通过：NeighborQuery 的 Radius 注册、Histogram→PrefixSum→Scatter 与邻居计数/索引读回路径已接通，但内置 Visualize 的 `DrawParticlesFromReader` 是 StaticBool；当前 Niagara Toolset 将其误判为普通 Bool，返回“expected NiagaraBool but got NiagaraBool”，导致正式 `Particle Attribute Reader` 输入仍隐藏且保存后为 `Other/None`。曾尝试纯 cpp Live Coding 通用 StaticBool 命令，三轮均成功编译但未能从调用节点收集到该 pin，已完整回退；VibeUE 两个源文件 git diff 清零、回退热补丁成功。下一执行点是修复 Toolset 对 StaticBool 的类型/调用侧 pin 处理，或新增可按 Stage/模块设置静态开关的正式接口，再把 ParticleRead 固化为 `Other/Fountain` 并验证非默认属性读回；在此之前不得声称 Gate A 完成。

### 2026-08-04 — [铁律作废] 原 K11“MCP 拼 scratch 图必崩、改由人手搭”禁令已失效

早期结论“用 MCP `NiagaraScratchPadService` 动态拼 scratch 图会稳定触发编译越界崩溃，此路已否决，scratch 图/HLSL 改由编辑器内手动搭建、MCP 只做只读”**现予作废**。该越界崩溃（`Array.h:1339` RangeCheck，栈在 NiagaraEditor）根因是裸 `CreatePin` 导致 pin↔`Signature` 索引失配，早已由 `niagara-authoring` profile 修复：引擎导出 `RequestNewTypedPin`/`ReallocatePins`/`IsAddPin`，VibeUE 改走 `RequestNewTypedPin`（见 `work/UEAgent/notes/niagara-mcp-authoring.md`、`patches/niagara-mcp-authoring/`）。`work/UEAgent/notes/mcp-pitfalls.md` 的 `SSPR-K11` 已为 `Verified profile`；本轮 doctor 探测 `niagaraScratchPinAuthoring: PRESENT_VERIFIED`、`niagaraToolsetsExtension: VERIFIED_LIVE`。因此现在可通过 MCP 安全做动态 pin / Custom HLSL authoring，不再要求用户手搭 scratch 图。仍须遵守的硬规则：走 `RequestNewTypedPin` 不用裸 `CreatePin`；System 资产 scratch 注册进 `System->ScratchPadScripts`；不在同一 Stage 读写同一 DI；mutate 与 GPU readback 分请求。注意这修的是“崩溃”问题，与 P0 卡点 `NeighborQuery_Visualize` 的 `DrawParticlesFromReader` StaticBool 类型误判是**两个不同的问题**，后者未被此修复覆盖。

（本条纠正的背景：AI-BRIEF.md 当前版本已不含该 K11 禁令文字，早期“已写入 AI-BRIEF.md”的说法本身也已过期；此禁令仅残留于长期记忆，已于同日一并更正。）

### 2026-08-04 — [历史重建尝试·后证实仍有旧引用] 从 12ms 记录点建立 NeighborQuery 工作资产

V1 候选（`Performance/NeighborGather_V1`）诊断出 NeighborQuery DI 层矛盾：`System.P0_NeighborQuery` 与 `Emitter.P0_NeighborQuery` 重复声明同一 DI（值完全相同）→ 2 个 stack Error（`GetStackIssues` 坐实，`GetSystemCompileState` 曾误报 UpToDate/0 错误，两者口径不同），且分辨率为 3×3×3 默认值与 SetResolution 的 64×64×1 打架。用户决策走路线甲：不就地修 V1，改从干净点重建。V1 保留不动作对照。

用 `AssetTools.duplicate` 从 12ms 记录点 `_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms` 复制出工作资产 `Performance/NeighborGather_V2/NS_SSPR_V4Dev_P0_V2`（MCP 资产操作可用，无需 UI；`duplicate(NiagaraSystem)` 本次未触发 §14 坍缩因源为干净记录点）。已 save。独立验证：`numErrors=0`（对比 V1 的 2），仅 1 个 Fountain emitter（enabled，GPU sim），无 Reader、无坍缩。

隐患：V2 从 12ms 记录点继承了 Fountain Emitter Spawn `SetVariables_3016472A…` 里 `Emitter.P0_NeighborQuery`/`Emitter.P0_ParticleRead` 的 MapGet 默认值，硬引用 `NeighborGather_V1` 包的 DI 对象（跨包脏引用，暂未报错但须清）。

已探明完整 authoring 链（工具/门控/顺序全部验证）。正确执行顺序（避免任何时刻悬空引用）：
1. 建 System 级 NeighborQuery 单例 DI（`AddUserVariables`，NeighborQuery DI，64×64×1、MaxCellsPerParticle=4）；
2. 把 Writer `AddParticleToNeighborQuery`（Fountain ParticleUpdate）的 `Neighbor Query` input 与 `NeighborQuery_SetResolution` 重绑到新 System 级 DI；
3. 删 Fountain Emitter Spawn 的旧 `Emitter.P0_NeighborQuery`/`Emitter.P0_ParticleRead`（`RemoveSetParameterEntry`）；
4. 新建 Reader emitter（或在 Fountain 内）+ gather HLSL scratch（`RequestNewTypedPin`；`GetParticleNeighborCount`→`GetParticleNeighbor`→ParticleReader.GetPositionByIndex），System 级 DI 共享；
5. `ApplyChanges`/编译，独立验证 `numErrors=0` 且 DI 无跨 V1 引用；再分请求跑 GPU 帧读回邻居数据非零。
关键工具：`NiagaraToolsets.NiagaraToolset_System`（AddUserVariables/SetStackInputData/RemoveSetParameterEntry/AddEmitter/GetStackIssues/GetSystemCompileState）、`VibeUE.NiagaraScratchPadService`（scratch/HLSL）、`editor_toolset.toolsets.asset.AssetTools`（duplicate/save）。gateway：`mcp_gateway.ps1 -Action tool.call -Toolset .. -Tool ..（短名）-ArgumentsFile ..`；doctor 回执须写入 `Saved/UEAgent/doctor.json`，session 每 ~15 分钟过期需重刷。改前备份 `Saved/CodexBackups/P0_NeighborGather_BeforeGather_20260804`（V1 态，SHA CDE61DFE…）。

### 2026-08-04 — [历史 API 原型·已作废] V2 Emitter 级粒子端 gather 探针

在 V2（`NeighborGather_V2/NS_SSPR_V4Dev_P0_V2`）上完成粒子端 API 探针 `P0_Gather_1`，接入 Fountain ParticleUpdate、排在 Writer 之后并编译通过。当时“完全脱离 V1”的判断后来被 sidecar 中的旧 DI 默认对象引用推翻；该模块也从未满足 Grid2D 像素端 Stage B 架构，只能证明 NeighborQuery/ParticleRead API 可连通。

**最终架构（放弃 System 级，改 Emitter 级）**：Writer(`AddParticleToNeighborQuery`) 与 gather 同在 Fountain emitter，共享 `Emitter.P0_NeighborQuery`（Emitter 级单例）。gather HLSL：`ExecIndex()==0` 扫 64×64 → `NeighborQuery.GetParticleNeighborCount` → 循环 `GetParticleNeighbor` → `ParticleReader.GetPositionByIndex<Attribute="Position">` → 写回 `Particles.P0_*`。scratch 图 9 条连线闭合，已注册进 System。ParticleRead 源绑定用 `EmitterBinding.bindingMode=Self`（DI 所在 emitter=Fountain，不依赖名字字符串）。

**编译验证（三重证据，numErrors=0 等价坐实）**：`GetSystemCompileState`=UpToDate/bHasErrors=false（含 GPU compute script）；`GetCompileMessages` 空；编辑器 log `FNiagaraShader compiled 23 times` 零错误。注：`GetStackIssues` 因 `bIsCompiling` 标志未清（后台编译完成但无前台泵送）读不到确切数字，需在编辑器把资产切前台 tick 一次。脱 V1：`GetSystemDependencies` grep V1 零命中。

**本轮踩坑与工具链修复（教训）**：
1. **K11 铁律作废后仍需一路修工具链**：K11（scratch 崩溃）已由 niagara-authoring profile 解除，但 gather 落地又连撞两个新的引擎/插件硬边界。
2. **System 级 DI 被 UE5.8 引擎堵死**：`AddUserVariables` 给 DI 类型 user variable 设默认实例走 `SetParameter_InternalUseOnly()`，引擎报 `We do not support setting data interfaces in SetParameter_InternalUseOnly() currently`。故 System 级共享 NeighborQuery DI 不可行，改 Emitter 级（本场景 Writer/Reader 同 emitter，Emitter 级足够）。
3. **VibeUE `ResolveType()` 缺 NeighborQuery/ParticleRead 类型**：`add_module_input(typeName="NeighborQuery")` 报 `Unknown TypeName`。根因是磁盘源码（`Plugins/VibeUE/.../UNiagaraScratchPadService.cpp`）虽已含这两个分支（`NeighborQuery`→NeighborQuery DI、`ParticleRead`/`ParticleReader`→ParticleRead DI），但 8/3 20:22 加的分支从未编译进 DLL（obj/dll 都旧）。**修复=只需 rebuild，不改代码**：关编辑器→`Build.bat precisefluidEditor Win64 Development -NoUba -MaxParallelActions=4`→重启编辑器。新 DLL 2026-08-04 17:16。
4. **构建内存死循环坑**：首次 rebuild 用默认 UBA 并行，被两个吞了海量日志的 powershell 进程（各 37GB）撑爆内存（158/128GB），UBA kill-retry 死循环。教训：**构建用 `-NoUba -MaxParallelActions=4` + 输出重定向到日志文件，绝不用大 yield_time 轮询把构建日志吞进 shell**。清掉僵尸 powershell 后内存恢复、build 秒过（产物已在）。
5. **"编译永不收敛"假象**：从未被打开过的资产，`GetStackIssues`/`GetSystemCompileState` 会 120s 超时（后台编译未被泵送）。用户在编辑器手动打开该资产即泵送完成，之后 MCP 秒读 `numErrors=0`。对照实验（对健康资产同工具秒回）可定位是"资产未泵送"而非工具/资产损坏。
6. **本环境 PowerShell 内联 `$var`/`$_` 不可靠**：一律写成 .ps1 文件执行。

**未完成项**：运行态帧验证（读回 `Particles.P0_NeighborCount`/`P0_GatheredCount` 非零）——当前关卡非 V2，需把 V2 拖进关卡或 PIE 跑几帧再 readback。改前备份 `Saved/CodexBackups/NS_SSPR_V4Dev_P0_V2.20260804_174113.pre_P0gather.uasset.bak`（SHA 76A3E5C1…）。

### 2026-08-04 — [历史原型验证·不等于 P0 架构] 粒子端计数随密度变化

修掉编译错误后（`ExecIndex()` 当函数调用 → 改为无括号 `In_ExecIndex` 用输入 pin 值；根因是 worker 既建了 `ExecIndex` 输入 pin 又在 HLSL 里用 `ExecIndex()`，Niagara 生成 `In_ExecIndex()` 对 int 加括号报 `called object type 'int' is not a function`。注：该 GPU 着色器翻译错误 MCP 侧 `GetSystemCompileState`/`GetCompileMessages` 均抓不到，仅编辑器前台 tick 泵送才暴露——MCP 编译验证盲区），用户前台确认编译不再报错。此验证只覆盖粒子端 API 探针，不是 P0 像素端实现 Gate。

运行态验证（用户在编辑器减粒子后跑帧，通过 Attribute Spreadsheet 读 `P0_NeighborCount`）：**粒子 rate=300 时 `P0_NeighborCount=0`，rate=3000 时 `=526`**。计数随粒子密度单调变化，证明整条 gather 链真实工作：Writer 注册粒子进 NeighborQuery → gather 的 0 号粒子扫 64×64 网格 `GetParticleNeighborCount` 累加 → `ParticleReader.GetPositionByIndex` 取位置。rate=300 读到 0 是稀疏分布下的正常表现（非 bug）。P0 NeighborQuery gather 至此完整落地并诚实验证闭环。

**遗留优化项**（非阻塞）：当前 gather 是"0 号粒子单线程扫全网格"（`In_ExecIndex` pin 未连、默认 0 恒真让 0 号粒子执行），性能不优；后续可正确接执行索引或改 iteration stage。`AddParticleToNeighborQuery.Reader` 的良性 warning（UseReader=false static-switch 隐藏）保留不动。

### 2026-08-04 — [决策→回滚] gather 一度封存、转向精度/观感
用户判定"12ms 已够用"，决定停止性能优化、把 gather/Sparse 封存为保留路径，转向"消除粒子感 + 精度超 Niagara Fluid"。据此立 `ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md`（AGS 解析核替换 Dense 枚举，scatter 架构内改一个 HLSL 内核，17.7ms→4~6ms 预估）。该封存决策于 08-05 被推翻（见下）。

### 2026-08-05 — [回滚→决策] 重启 P0 gather 为主线
用户判定 12ms 节点不足、决定动架构，推翻 08-04 封存，正式重启 gather。关键澄清：① 那个 12ms 是含 Scalability 裁剪的糊涂账口径（40ms→22ms 是 P1 确凿，22ms→12ms 无技术解释、非同机位），重启前须关 System 编辑器/仅关卡实例满量同机位重测真实基线做 Gate C 靶子；② 打开 NS 编辑器致粒子变多/变卡/变浓是编辑器预览绕过关卡裁剪的正常机制（非 bug），用户已自行修复不一致。

### 2026-08-05 — [历史推导·已收口] AGS 解析核与 gather Stage B 的关系
当时确认 erf 线积分闭式可同时用于 scatter 与 gather；当前路线已经收口为 **只在像素端 gather Stage B 使用 P0b**，scatter-only 方案不再是主线。六属性 `cos2θ/z/z²` 为粒子级常数（`contribution = weight × densityPerParticle`，`_g5_install_fields.py` 核实），解析核不需一阶矩、公式取简单版。当前实现要求以 `ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md` v2 为准。

### 2026-08-05 — [历史维护·已被 08-06 收口覆盖] 文档首次对齐 gather 重启
当时清理了 AI-BRIEF/BACKLOG 中关于“12ms 收口”、Sparse V2 对照和旧 P0 状态的陈述，并把主线首次对齐到 gather 重启。该条仍包含“满量基线待测、Stage B/解析核待做”的阶段性口径，现已由 2026-08-06 的规格收口覆盖，不得作为当前任务清单。

### 2026-08-05 — [维护] 本地整理与远程隔离
将已完成阶段的 7 份快照、验证规格、交接和合并记录移动到 `archive/2026-08-05-cleanup/docs`；将 392 个历史探针/dump/临时脚本及 1 个临时目录移动到 `archive/2026-08-05-cleanup/scratch`。文件未删除，UE 资产、`recovery`、`patches`、`split-patches` 和 `env-backup` 未改动；归档目录已加入本地 `.gitignore`，本次不提交、不合并、不推送远程。

### 2026-08-05 — [失败候选·禁止复用] StageB V1 初次构建
> 本节是当时记录；其“完成/可运行”判断已被 2026-08-06 卡死事故推翻。
用户确认“关闭 System 编辑器、仅保留关卡实例、记录相机 Transform/粒子量/GPU、重测 Dense+P1 真实基线”已完成，故直接推进下一步。以 `_RecordPoint_12ms` 系的 V2 为来源创建隔离候选 `/Game/SSPR_Validation/M3/Performance/NeighborGather_StageB_V1/NS_SSPR_V4Dev_P0_StageB_V1`，未修改原 V2。读回发现 V2 的 `P0_Gather_1` 实际 HLSL 只是按当前 `ExecIndex()` 查询局部 cell，并非文档曾描述的“0 号粒子扫完整 64×64”；候选中将其禁用并保留作历史回退。

候选复用 Particle Update 的 `AddParticleToNeighborQuery` 作为 Stage A Writer；旧 Raster simulation stage 改为 no-op；现有 Grid2D iteration 的 `SSPR_ResolveGridToSimRT` 改为完整 Stage B。Stage B 在 2048² `ExecutionIndexToGridIndex` 上按像素映射 NeighborQuery cell，3×3 邻域 early-out/枚举粒子，使用 `ParticleReader.GetPositionByIndex<Attribute="Position">` 与 `GetVector2DByIndex<Attribute="SSPR_ScreenDeltaUV">`，做 owner-cell 去重、长度/宽度 clamp、Winitzki `a=0.147` erf 近似解析线高斯（L→0 点高斯回退），累积 Density、cos2/sin2 张量、深度矩与 FrontDepth，直接完整覆盖 Main/Aux。新增 24 个动态 pin、12 条精确连线；独立读回无自动后缀。`ApplyChanges`、保存与独立检查通过：System/GPU/两个 Simulation Stage Script 均 `UpToDate`，0 compile error、0 compile warning；保存后 asset SHA-256=`487C05E06D83A57643280FCDE84FE1D84B2D0707D8B08411B77CAE12C906A52A`，graph SHA1=`faad341f5eecee7507fac375902a2f18bf0638cc`。Stack 仅保留两个已知 UI warning（Writer 隐藏 Reader、已禁用旧 gather 的 ParticleRead）和两个版本升级 info。

运行验证不保存关卡：把候选临时放到原 NiagaraActor 同 Transform `(-2330,10,2560)/(0,0,0)/(1,1,1)`，Simulate-in-Editor 暖机后独立读回 Fountain 为 `GPUComputeSim/Active`，Age=`39.858 s`、Particles=`75,504`，证明候选能真实持续运行。PerformanceService 连续五次只得到 GPU=`16.07/50.32/60.45/15.80/50.77 ms`，但 GameThread 固定异常为 `4962.91 ms`、RenderThread=0，随后 viewport capture 超时；这些数字受 MCP/SIE 阻塞污染，不可作为与 Dense+P1 的正式对照，也不能声称 Gate C/D 通过。已停止 SIE、删除临时 Actor、把原实例恢复为 `_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`，未保存关卡，并将视口布局与相机精确恢复到本轮开始值 `Location=(-1285.381145,582.501619,3012.811786)`、`Rotation=(-12.31291694,-158.34777588,0)`。下一执行点：在用户已记录的同机位/同负载前台条件下先做 Main/Aux 原始 RT Gate 与视觉 Gate，再抓不受调用阻塞污染的 ProfileGPU。

### 2026-08-06 — [失败候选中间修复·禁止验收] StageB V1 坐标域修补
> 本节只记录空白问题的中间修复；候选随后因无界工作量与双 writer 卡死，不能作为有效里程碑。
用户实机截图确认首版候选完全没有显示；此前仅凭 GPU emitter Active/粒子数给出的“可验收”判断无效。源码与图拓扑复核定位到坐标域错配：Particle Update 内置 `AddParticleToNeighborQuery` 用世界空间 `WorldToUnit` 注册粒子，而 Stage B 按屏幕像素 `Pixel/32` 查询 NeighborQuery cell，并用屏幕 owner-cell 去重，两端不可能稳定命中同一 cell。

修复复用粒子迭代 Raster stage 的 `SSPR_RasterizeWhiteParticles`：新增 `Emitter.P0_NeighborQuery` 输入并连接 Custom HLSL；用 `View.WorldToClip` 从 `WorldPos` 计算当前 UV，按现有长度/宽度/Gaussian 参数估计 support radius，经 `UnitToCellCornerFloatIndex(float3(currentUV,0.5))` 后调用 `AddParticleWithRadius(..., ExecIndex(), ...)`。旧 Particle Update `AddParticleToNeighborQuery` 与旧 `P0_Gather_1` 均禁用，Stage B/P0b gather 保持不变。独立读回确认新 pin 只有一条精确连接，HLSL 包含四个关键调用，System/GPU/两个 Simulation Stage Script 全部 `UpToDate`、零错误零警告；`ApplyChanges=true`，保存后候选 SHA-256=`7B2E201ADB813238DBB6F9E63DFCCD4B7520D55169CEC52BDCC93568240B5E65`。

运行复测不保存关卡：同一关卡组件临时绑定修复候选，SIE 独立读回为 `GPUComputeSim/Active`、Age=`46.627 s`、Particles=`151,518`，证明修复资产实际编译并持续运行。自动 `CaptureViewport` 仍在渲染线程超时，因此**尚不能宣称画面或 Main/Aux Gate 通过**；已停止 SIE 并确认 `IsPIERunning=false`。编辑关卡实例目前保留修复候选供用户前台按 Simulate 做视觉确认，关卡未保存；若仍空白则立即恢复 `_RecordPoint_12ms`，若可见再继续原始 RT 与同机位 ProfileGPU Gate。

### 2026-08-06 — [严重失败/撤销验收] StageB V1 无上限全屏 gather 导致实机卡死
用户前台运行 `NeighborGather_StageB_V1` 后编辑器直接卡死。复核确认这不是“理论更优但常数偏大”，而是工作量模型落错：2048² 像素每个查询 3×3 NeighborQuery cell，并对每个 cell 的 `cellCount` 无上限遍历；151,518 粒子、64×64 cell 的全局均值约 36.99 粒子/cell，单次 Stage B 至少有 37,748,736 次 cell-count 查询，按每粒子注册一个 cell 粗估约 13.96 亿次候选枚举，radius registration 最多复制四格时可进一步放大。P1 只降低平均执行频率，不降低单次爆发工作量，无法阻止 GPU watchdog/编辑器假死。另一个乘法错误是旧世界空间 `AddParticleToNeighborQuery` 实际仍为 enabled，与屏幕空间 radius writer 同时写同一 NeighborQuery，进一步抬高并污染 cellCount。此前在没有画面、RT 和可控性能证据时要求用户验收，属于无效验收判断。

已停止 SIE，确认关卡实例恢复为 `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`；V1 编辑器已关闭，V1 不再绑定运行。`NeighborGather_StageB_V1` 标记为失败资产，只保留事故复盘，不再作为验收候选。

### 2026-08-06 — [已撤回] Safe V2 一度被误判为通过结构/编译 Gate
曾依据孤立 HLSL 回读、Particle Update 栈 0 命中与 `UpToDate`，把 Safe V2 判断为像素端有界 gather 已正确挂载。该结论不成立：这些信号无法覆盖 Simulation Stage，且随后发现旧 DI 默认引用、孤儿 `P0_Gather_1` 节点及 `bDisablePartialParticleUpdate=False`。具体撤回证据见下一条；本条不得作为实现依据。

### 2026-08-06 — [撤回结构通过结论] sidecar 覆盖盲区与 Safe V2 残留引用
用户转述的逐行审计引用的是清理前 sidecar：当前与 `.uasset` 同时写出的 16:11:23 sidecar 对 `P0_Gather_1`、`int myIdx = ExecIndex();`、`P0_AccumPosition` 均为 0 命中；其第 179 行已是 `Deps`，不是旧 gather 模块。与此同时，当前 sidecar 的 headings 只覆盖 Emitter/Particle 嵌入模块，完全不导出 Simulation Stage，所以“全文没有 `ExecutionIndexToGridIndex/SetRenderTargetValue`”既不能证明 Stage B 不存在，也不能证明它存在。

进一步 live 只读反射发现两个 Simulation Stage（`SSPR Rasterize Trails`、`SSPR Resolve Grid To Material`）以及指向 `SSPR_RasterizeWhiteParticles`/`SSPR_ResolveGridToSimRT` 的函数调用节点；但 Resolve Stage 的 `bDisablePartialParticleUpdate=False`，违反 P0 checklist。当前 sidecar 的 Emitter SetVariables MapGet 默认对象仍指向 `/Performance/NeighborGather_V1/NS_SSPR_AnisotropicSplat_V4_Dev`，证明此前 `GetSystemDependencies` 的 0 命中漏掉了嵌入默认对象引用；旧 `P0_Gather_1` 函数调用节点也仍作为图内孤儿存在。故上一节“彻底删除、旧 V1 依赖 0、结构 Gate 通过”的表述被本节取代：Safe V2 当前为结构审计失败、未证明正确挂载，禁止运行验收。只读 SIE 已结束，`IsPIERunning=false`。

### 2026-08-06 — [维护] 清理过期主线口径，规格与历史彻底分层
`M3-PERF-OPTIMIZATION-SPEC-20260731.md` 升为 v3 当前口径：Stage B 当前 cell 单次查询、强制 K 上限/overflow/补偿，并新增 Gate S0；两个失败候选均写入状态表且禁止复用。`ANALYTIC-GAUSSIAN-SPLAT-SPEC-20260804.md` 升为 v2，仅保留 P0b 像素端数学内核，删除 scatter-only 主线。AI-BRIEF/BACKLOG 统一到“从 `_RecordPoint_12ms` 新建干净候选”；本 LOG 顶部新增阅读规则，旧粒子端原型与失败候选标题均标记为历史/失败/撤回，不能再被当成当前规格。

### 2026-08-06 — [已废弃删除] Clean V3 有界 Gather 候选作废
曾从 `_RecordPoint_12ms` 新建候选 `BoundedGather_Clean_V3/NS_SSPR_P0_BoundedGather_Clean_V3`（Stage A 有界 radius 注册 + Stage B 2048² current-cell/K 上限 gather + P0b erf 核），并一度通过结构 Gate S0。该候选此后经用户判定废弃并已从工程删除（资产、sidecar、全部构建/验证/探针脚本一并抹除），不得复用、恢复或作为新候选起点。P0 gather 的正确落地方式仍见 `M3-PERF-OPTIMIZATION-SPEC-20260731.md`（P0/P0b/P0c）；下一候选只能从 `_RecordPoint_12ms` 干净新建。此条仅作历史追溯，不代表存在任何可用候选或已通过的运行/性能证据。

### 2026-08-08 — [历史假阴性·由下条纠正] RawMoments V1 首次低负载 RT 全零

从 `_RecordPoint_12ms` 新建自包含候选
`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`，未修改锚点；当前候选 SHA-256=`F3F6C066CFDA601B33DA52B56521CCCE4D9B39FF807BC8561C20C391C875F057`，锚点仍为 `746719BA…D4CE`。候选只保留一个 Fountain GPU emitter、一个屏幕空间 radius writer 与一个 current-cell/K=`User.P0_MaxCandidatesPerCell` gather；Main/Aux 为 P0c v2 原始矩布局，Gather Stage `bDisablePartialParticleUpdate=true`。System/GPU/两个 Stage script 全部 `UpToDate`，0 error、0 warning；拓扑与默认对象回读对三个失败候选、旧 `P0_Gather_1`、旧 Particle Update writer 均为零命中。

由于普通 Niagara sidecar 不覆盖 Simulation Stage，本轮额外解析候选 `.uasset` 的 1,354 项 NameMap 与 302×112-byte ExportMap。Stage0 内嵌 script export 177（offset `762742`/size `28536`）含 UsageId `DAB2BFB7483A9903F1084CB0F4756813`，对应图 Output0，并直连 `SSPR_RasterizeWhiteParticles`；Stage1 export 178（offset `791278`/size `42430`）含 UsageId `F5FFDA1D437E16744CB058AC82150881`，对应 Output1，并直连 `SSPR_ResolveGridToSimRT`。证据固化于 `scratch/p0_mainline_20260806/stage_usage_mount_offline_evidence.json`。因此已排除“两个 Simulation Stage 挂错图分支”。

运行 Gate 使用不保存关卡的 SIE：活动 PIE component 为 GPU/Active，约 644 粒子；把该 component 的 Grid/Main/Aux 克隆设为 256²并 reinitialize 后，两张 RGBA16F RT 均成功读回 65,536 个像素，但所有通道严格为零。Grid2D→R32F 的旧 Python readback API 返回空数组，不能据此证明 cellCount 为零；Main/Aux 全零则是有效反证。故 Gate A 明确失败，不能宣称有效 RT、视觉、overflow 或性能通过。

结束 SIE 时又暴露独立的工具生命周期事故：先前 `execute_python_code` 包装用 plain `exec` 把 runtime probe 的 Niagara DI/RT wrapper 留在持久 Python 全局；`StopPIE` 已开始 teardown，但 `FPyReferenceCollector` 仍引用旧 PIE package，UE 5.8 在 `PlayLevel.cpp:553` 断言并自行退出。候选、锚点和关卡文件哈希未变化。UEAgent Gateway 已新增隔离的 `python.execute`（private globals → `finally` clear → `gc.collect()`）并阻止 `script.execute` 接收显式 Unreal Python；8 MiB transport/memory/timeout 回归通过且无残留进程。

下一执行点已准备为一次可回滚三分流探针：使用既有候选备份，把 Gather Aux.A 临时写成 `1 + clamp(CellCount, 0, 1023)`。若 256² Aux.A 仍全 0，则根因位于 Stage B dispatch/DI/RT 绑定；若全 1，则 Stage B/RT dispatch 正常但 NeighborQuery cellCount 为零，转查 Stage A 注册/排序；若出现大于 1，则注册与计数有效，转查 ParticleRead、属性有效性或 P0b 核下游。探针脚本为 `set_gather_dispatch_marker.py` 与 `restore_gather_dispatch_marker.py`，必须在重启 UE、doctor 健康、无 PIE 时安装，运行读回后停 SIE 并恢复生产 HLSL。

### 2026-08-08 — [当前主线·Gate S0/A 通过] 固定相机与非归一化读回纠正假阴性

UE 重启、doctor `HEALTHY/LIVE_READ` 后安装可回滚 Gather marker `Aux.A=1+min(max(CellCount,0),1023)`。最初沿用任意视口相机时，marker 全 1；Niagara verbose 日志却逐帧存在 NeighborQuery `PreStage/PostStage`、有效 buffers、约 520～540 粒子和 sorting passes。检查发现视口相机没有覆盖目标组件，故“cellCount=0”只描述了错误测试视角。改用固定机位 `Location=(-2290,1460,2430)`、`Rotation=(0,0,0)` 后，SimCache 的 512 个 `SSPR_ScreenUV` 全部有限且在屏幕内，ViewDepth 全正（约 `945..1365`）。

第二个假阴性来自 `RenderingLibrary.read_render_target_raw(world,target,True)`：第三个参数会归一化结果，绝对 marker `1..55` 被压到 `0..1`，不能做 dispatch/count 分类。改为 `False` 后，Aux.A=`min 1 / max 55 / mean 1.435302734375 / sum 94064`，即真实 `CellCount=0..54`；这证明 Stage A radius 注册/NeighborQuery sorting、Stage B current-cell 查询、ParticleRead 与 Aux 写入链均执行。marker 期间 Main density R 非零 2766 像素、max `0.078247`、sum `15.1164`，Main G/B 有正负张量，Main A、Aux R/G/B 也均出现预期签名。

随后停止 SIE、恢复生产 HLSL 并独立回读：HLSL 8373 chars，SHA-256=`460bb2f108d65d3fb13f33ab059ec3529473b3579fe1b3a9b402378a91278500`，marker 0 命中、原生产表达式 1 命中、0 编译消息。正式生产复验在相同固定机位、256²、644 粒子下通过八项检查：Main R/G/B/A 与 Aux R/G/B/A 均非零，所有通道 nonfinite=0；Main R 非零 2209、max `0.116821`、sum `14.8909`，方向/速度矩保留正负符号。因此 Gate A 正式通过；低负载生产通道签名通过，但不冒充完整 Gate B。

收尾还验证了两个工具链风险。其一，World Partition SIE Reinitialize 会产生多代 component-local DI clone，绑定会从 `_0/_1` 切到 `_2/_3` 等新代；必须每次从当前 User Variables 解析绑定并以 PIE World 实际 `TextureRenderTarget2D` 尺寸为准。其二，恢复组件属性的 Python 调用把外部 Actor 包留脏后，下一次本来只恢复相机的 `execute_python_code` 在脚本执行前触发 `InternalPromptForCheckoutAndSave`，隐式保存了该外部 Actor。已停止 UE，把精确的复验前 Auto1（SHA-256 `0E679322D4543BC95199979FEF57A3C0D2BF95124074EDC41B6AAFB0AD2EF621`）恢复到唯一目标文件并重启验证：关卡 `.umap` SHA-256 仍为 `52499A2E…EF6B`，Actor 为干净 `2 RT + 1 Grid2D`、全部 2048²、`forceSolo=false`、无脏包。意外保存版本与恢复源均保存在 `Saved/CodexBackups/P0_ExternalActor_Recovery_20260808_1655/`。

当前候选资产因 marker 安装/恢复与 Niagara 重编译重新序列化，文件 SHA-256 为 `FE4134059E4DF02AC4881A113CA4C2003FDF943CBA404BF98A1453ACEB17D84F`；生产 HLSL 的独立哈希与无 marker 读回才是语义恢复证据，精确 pre-marker 文件备份仍在 `Saved/CodexBackups/P0_Gather_RawMoments_V1_PreDispatchMarker_20260808_012445/`。下一执行点是 Gate A2：低负载 `max CellCount=54` 已超过 K=8，先量化 overflow/截断/补偿和 counting-sort 三 pass 成本，再进入完整 Gate B、同机位 Gate C 与用户视觉 Gate D。

### 2026-08-08 — [当前主线·Gate A2/B/C 通过，待用户 Gate D] RawMoments V1 收口到 K64 + FrontDepth 峰值阈值

用户在 rate=40,000 的近景运行中观察到约 Draw 20ms、GPU 14ms，但画面里的粒子持续“来回抽出”。运行预算审计把原因定位到 K=8 的确定性 Top-K 成员抖动，而不是 Stage 架构错误：80k 粒子快照有 1047 个非空 cell，cellCount mean/p50/p90/p95/p99/max=`300.6/35/809/1485/3930/4785`；K=8 只保留 2.0607% 候选，截断 97.94%。K=64 保留率提高到 11.4636%，虽仍有 88.54% 截断，但密度补偿保持加性矩量级，Top-K 成员预算扩大 8 倍，实机截图由稀疏单线抽动转为持续的中心流体团。最终场景组件已把 `User.P0_MaxCandidatesPerCell=64` 与 `User.SSPR_ParticleNum=40000` 写入唯一 World Partition 外部 Actor；精确落盘回读通过。

同时修复 FrontDepth 恒零。原实现把 `FrontDepthWeightThreshold=0.1` 直接与单粒子解析贡献比较，但移动线段 erf 核的理论峰值本来就可能低于 0.1，因此合法候选被全部拒绝。正式 Gather 改成阈值相对每个解析核自身理论峰值比较，标记 `P0_FRONT_THRESHOLD_RELATIVE_TO_ANALYTIC_PEAK` 恰好 1 命中。生产 Gather HLSL SHA-256=`3e6a95c5641cf9fe7d6c7c8d8a1dc694bd2526e8188902ae767844c2202d14b7`，旧 dispatch marker 0 命中，0 编译消息；最终 System 文件 SHA-256=`06390F191B7000E4B9E516B5826E762D38DF1AE99407AE635228A1578C2679ED`。

Gate A2 已完成而非继续猜 K。80k 快照量化了 overflow/截断分布；251,678 粒子 ProfileGPU 的 Stage A/NeighborQuery sort 为 `0.67/0.52 ms`，证明 counting-sort 三 pass 在目标级负载可控。K64 在 100,671 粒子下的排序约 `0.09～0.19 ms`，Stage B 约 `0.57～1.52 ms`；相对 K8 只增加约 0.5～1.3ms，换取显著更稳定的候选成员集合。K64 是当前质量/性能折中，不解释为完整邻居列表。

终态 Gate B 用固定近景相机、2048² RGBA16F Main/Aux 和非归一化 raw read，按 8 个 2048×256 strip 在 UE 内聚合，未把像素数组传给 PowerShell。全 4,194,304 像素中 Density 覆盖 716,764（17.08899%）；Main 非零数=`716764/715796/715767/712455`，Aux 非零数=`679020/643843/632920/629626`。八通道 nonfinite=0、half saturation=0，密度/深度矩均无负值或原始矩上界违规；在 Density>1e-3 的 346,648 像素内，Depth/Tensor moment lost=0、严重负方差=0、coherence out-of-range=0，只有 70 个低幅速度矩为零。MeanDepth p50/p95/max≈`0.0664/0.0820/0.1051`，DepthSigma p95/max≈`0.00977/0.03227`，VelocityMagnitude max≈`0.01178`；屏幕边缘 64px 区域有 311 个覆盖像素。由 half 相近数相减产生的小负方差继续按材质规格 `max(0,·)` 处理，不构成 Gate 失败。

Gate C 在同一 PIE 会话、同一组件、同一固定机位 `Location=(-592.975399,299.745966,3052.564758)`、`Rotation=(-38.105162,164.537398,0)` 下临时切换 Dense 与候选。候选最稳样本为整帧 `14.42 ms`，Stage A/sort/Stage B=`0.01/0.09/0.57 ms`，100,671 粒子；另一受 fixed-tick 追帧污染的保守样本中，昂贵链仍只执行一次且为 `0.05/0.15/1.52 ms`。Dense 在 66,001～75,503 粒子下采到 40 个独立 Raster dispatch，范围 `8.22～15.55 ms`、中位 `10.76 ms`，Resolve 中位 `0.19 ms`；Dense 在慢帧中每个 fixed tick 重复 Raster/Resolve，累计帧值不拿来和候选整帧比较。以更低 Dense 粒子数对更高候选粒子数，单次 SSPR 链仍约有 6.3× 保守余量，因此技术 Gate C 通过；用户先前前台 GPU≈14ms 与候选稳态 14.42ms 相符。

最终视觉稳定参数只修改候选 MI：`G5_CoherenceMin=0.15`、`AS_Contrast=0.40`、`AS_Extinction=1.20`、`AS_OpacityScale=1.00`、`AS_EmissiveStrength=1.25`。曾对照旧创建脚本的 Contrast=0.9/Extinction=1.8，但共享 HLSL 证明 Contrast 是 `pow(density, Contrast)` 的指数，0.9 会压暗当前低密度场，故已撤销。候选 MI SHA-256=`47213AB27449756C90F00D28D0C6407AA6EA3CB45B4E97E0C50264FAF7A813AD`；源 Dense MI 参数保持不变。最终强制 reload 审计确认两条 Stage 的 P1 bool binding、Camera DI 连接、候选 Renderer/MI、fixed tick 0.01667、FrontDepth 标记、HLSL hash 与零编译消息全部一致；编辑器无脏 content/map package。

可恢复备份位于 `Saved/CodexBackups/P0_RawMoments_PreFrontPeakFix_20260808_230500/` 与 `Saved/CodexBackups/P0_RawMoments_PreVisualStability_20260808_222500/`。最终画面证据位于 `Saved/CodexEvidence/P0_RawMoments_GateB/`，主图为 `P0_RawMoments_FixedClose_K64_VisualStability.png`，时序图为 `..._Temporal1/2/3.png`。当前只剩 Gate D：保持最终候选运行，由用户前台判断原“抽出/回缩”是否消失，以及剩余脱离细丝、稀疏尾丝、端点软化和整体实体感是否可接受；在用户明确通过前不替换正式 M3 主线。

交付 Gate D 前最后一次从冷启动重开时，参数回读发现外部 Actor 仍覆盖了旧 `DensityPerParticle=0.10`，与上述验图使用的 0.03 不一致。已先把该精确二进制备份到 `Saved/CodexBackups/P0_RawMoments_PreDensity003_20260808_233500/`，再把同一外部 Actor 的 rate/K/Density 强制写为 `40000/64/0.03` 并保存；独立回读无脏包，最终外部 Actor SHA-256=`243730421645D449ADA4F5DEF36D5DA269D7ED3D8D6380D4C424612818E6920C`。重开 PIE 后运行参数再次回读为 `40000/64/0.03`，固定相机一致；最终 Gate D 截图 `P0_RawMoments_FixedClose_K64_GateD_Final.png` SHA-256=`A9362DA9A57892A1906A84E1634E8723EC3CF9C19E314E536217255DEEE27279`。PIE 保持运行，等待用户视觉结论。

### 2026-08-08 — [Gate D 否决/主线纠偏] 数据层保留，RawMoments Streamline 视觉分支作废

用户依据最终近景明确否决候选：画面没有形成气体团和气体拉丝，反而放大了粒子感。因此上一节“当前只剩 Gate D”的状态已结束，不能再解释为等待用户确认；Gate D 的结果是 **失败**。Stage A/B、P0b erf、P0c 原始矩、有效 RT 和技术性能证据继续有效，但 Resolve/Material 必须回到实现阶段。

离线代码对照发现决定性偏差：`MF_SSPR_P0c_StreamlineRawMomentsV1` 只在 3×3 原始矩正则化后沿离散 RT 做双向 RK2，最后用 `max(isolatedCore, connectedSupport)` 把中心 Raw Density 保留为可见兜底；MI 的 `Contrast=0.40` 又通过低指数幂显著抬亮弱离散像素。这直接违反 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 当前帧归一化场重建章节“不得把 Raw 单粒子 Core 作为可见兜底”的硬约束。K64/N-K 补偿是有损 gather 的稳定/质量折中，不是气体连续场算法，也不能靠材质对比度替代 Field Reconstruction。

根因是把历史 `FieldRecon V1` 的具体视觉失败错误理解为 normalized field reconstruction 路线被废弃，又把旧 G5 HQ 的临时视觉基线误当成最终算法。纠偏主线现冻结为：P0c Raw moments 局部正则化 → density numerator/support denominator → coherence/support/depth 自适应场对齐卷积 → 同场 Filament/Medium/Body 分频 → Front/Mean/Sigma Depth Transport → Smoke Resolve。失败 V1、正式 M3 与干净锚点均不原地覆盖；用隔离 V2 候选按 `P0C-NORMALIZED-FIELD-RECON-PLAN.md` 逐 Gate 实现。

### 2026-08-09 — [当前主线·结构完成/视觉待审] P0c Normalized FieldRecon V2.1

按纠偏合同创建并保存四个隔离资产：`MF_SSPR_P0c_NormalizedFieldReconstructionV2`、`MF_SSPR_P0c_DepthTransportLightingV2`、`M_SSPR_P0c_NormalizedFieldRecon_V2`、`MI_SSPR_P0c_NormalizedFieldRecon_V2_HQ`。父材质闭包仅含上述两个 P0c 函数与 V4Dev 的 DensityShape/SmokeResolve/ScreenEdgeMask；Renderer 1 已从失败 RawMoments MI 切到新 MI，两条 `TrajectoryTexture <- User.SSPR_SimRT` / `TrajectoryAuxTexture <- User.SSPR_AuxRT` 绑定、Emitter SourceMode、SortOrder=100 与 MotionVector Disable 均保持。Niagara System 7 个脚本全部 `UpToDate`，0 error/0 warning；保存后强制 reload 再审计，Stage A/B gather HLSL SHA-256 仍为 `3e6a95c5…14b7`，P1、Camera DI、fixed tick `0.01667s` 和 K64 均未变化。

初版 V2 按 P0c 合同读取 Raw0=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`、Raw1=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`；先做局部原始矩正则化，再执行每侧 8 steps、每步 5 lanes 的 density numerator/support denominator，连接受 coherence、曲率及 Front/Mean/Sigma 深度约束；Filament/Medium/Body 来自同一重建场，DepthTransport 单独推导 BackDepth、厚度和透射。结构审计无 History、MipPyramid、旧 Streamline、`isolatedCore`、`max(rawCore,...)` 或 `saturate(Aux.a)`；`Contrast=1`。父材质 0 error、保存后 reload 与 sidecar 一致，正式 M3 与失败 V1 文件哈希保持不变。

40k 固定近景首轮暴露两处动态缺陷：空/弱 midpoint 的张量和速度均为零时，`atan2(0,0)` 会落成屏幕 X 方向并错误改写追踪切线；统一的高阈值 seed confidence 又把 Medium/Body 与 Filament 一样硬切，造成亮短丝簇和外围断裂。V2.1 已改为“弱矩保留上一可靠切线并让 branch confidence 衰减，只有受支持矩才重新导向”，同时在同一 normalized field 上使用严格 Filament、渐进 Medium/Body 的三带 seed confidence。Recon HLSL 从 `8a43b7f0…7ed1` 更新为 `cfff060099a326617266f3921141dd9d6eb06d76bb5cab9aa2a9a4562eefe20c`；父材质重编译、保存后强制 reload、required/forbidden token 与 0 error Gate 均通过。

当前 Continuous-B 保持 `ActiveSteps=8`、`Contrast=1`，Guide/Medium/Body=`5/4.5/15 px`，三带权重=`0.12/0.43/0.45`，BlackPoint=`0`，以 Body/Medium 为主且不抬弱离散像素。固定近景 40k 多帧证据已从旧式粒子卡片转为连续主团、方向性尖丝和宽体，空矩导致的统一横向“抽针”明显消失；仍可见中心偏白、外围偶发分离小束，用户 Gate D 未通过。50k/s 仅在 PIE 运行态 A/B，主团更饱满但未写回；紧随 CaptureViewport 的 FrameTiming 被 GameThread 5.7s 阻塞污染，不能作为性能结论。备份位于 `Saved/CodexBackups/P0_FieldReconV2_PreContinuousTune_20260809_0014/` 与 `.../P0_FieldReconV2_PreContinuityHLSL_20260809_0019/`；视觉证据位于 `Saved/CodexEvidence/P0_FieldReconV2/`。

最终交接前再次在无脏包状态分别强制 reload 材质与 Niagara System。材质审计回读 Recon SHA-256=`cfff060099a326617266f3921141dd9d6eb06d76bb5cab9aa2a9a4562eefe20c`、Lighting SHA-256=`641f0c8c04fa2dc3a018cb0d50c290c648d0fb32598fa94788065a4af8553346`、5 个精确函数调用、`ActiveSteps=8`、`Contrast=1`、三带权重和 required/forbidden token 全部一致，0 compile error/0 脏包。System 审计回读两个 Stage 的 P1 binding、Camera DI、fixed tick、唯一启用的 V2.1 Renderer 与生产 Gather SHA-256=`3e6a95c5641cf9fe7d6c7c8d8a1dc694bd2526e8188902ae767844c2202d14b7` 均一致，0 compile message。SIE 重开后的运行参数为 `40000/64/0.03`，候选组件 active/tick，Grid2D 与 Main/Aux 两张运行 RT 均为 2048² RGBA16F。固定相机三帧为 `P0_FieldReconV2_1_ContinuousB_Final40k.png`、`..._T2.png`、`..._T3.png`，首帧 SHA-256=`4C12013AC3D9E2E7ACAD96DDC4B946DD6B8B35AFC9D63EC63DAC56251D8B7287`；SIE 保持 40k 运行，等待用户针对实时“来回抽出”、中心过白和外围分离束作 Gate D 判断。

### 2026-08-09 — [视觉 Gate 再否决/优先级冻结] 先修重建，源粒子运动仅作备选

用户依据最新截图否决 V2.1：画面仍是白色刷毛/纤维排线，未形成 Niagara Fluids/NS 式连续气体体积、自然卷曲与气体拉丝。此前“已出现连续宽体，只剩中心偏白和外围断束”的表述被本节取代；V2.1 只保留结构正确但视觉失败的快照。视觉金标准确定为 `/Game/NewNiagaraSystem.NewNiagaraSystem` 的气体形态，同时要求候选完整链路在同条件 A/B 下总 GPU 成本不高于该参考，并提高可见精度。

执行优先级已明确：当前冻结 Fountain/CurlNoise/Drag/Velocity 等源粒子运动，先纠正 SSPR 连续场重建与 Body/Medium/Filament 的职责，消除采样线直接显形。调整源粒子运动以产生更接近 NS 的大中尺度卷吸只登记为后置备选；仅当重建层达到视觉目标后仍明确缺少由轨迹决定的卷吸、回流或涡团时再评估，且实施前必须重新取得用户确认，默认不引入完整 NS 求解。

### 2026-08-09 — [外部审查 Request Changes] Stage C 方向通过，Rev A 禁止实施

外部审查同意把失败的 `8 steps × 5 lanes` 材质可见轨迹迁到独立二维 current-frame Continuous Field Resolve，也同意保留 Stage A/B、按 Body→Medium→Filament 分 Gate、禁止光照掩盖密度问题，并只承认完整链路 A/B；但 Rev A 的实施合同未通过。阻塞点包括：Raw 八通道没有 Coverage、空中心无法直接构造方向/深度引导、FrontDepth 不能按普通矩平均、positive residual 会造正能量、SupportConfidence 未定义不变量、2048² 32～48 taps/四 RT 成本未做微基准、坐标/边界/half 精度未闭合，以及 R6/R7 对源运动形成循环条件。

Rev A 已标记 `REQUEST CHANGES` 并保留为被审记录；新建 `P0C-CONTINUOUS-FIELD-RESOLVE-REVIEW-REV-B.md` 等待复审。Rev B 明确：Stage C 单 dispatch 内 9-tap Pilot + 共享 Main；Stage C 从 Density 推导 `C(D)=D/(D+D_ref)`，采用 canonical `F=V*(S/Z)=N/Z`；Pilot 选择前部 depth cluster，M1/M2 加权而 FrontDepth 取 valid-aware cluster min；分频改为 signed `B=Fbody / M=Fmid-Fbody / H=Ftight-Fmid`；FieldMain=`B/M/H/Q_BM`、FieldAux=`Mean/Sigma/Front/DepthConfidence_BM`；验证期单实例 `2 Raw+2 Field` 下限 128 MiB，并新增 R1.5 微基准、R1.6 合成输入 Gate、Primary View pixel metric、float32/half 对拍以及 R6a/R6b gap classification。`D_ref`、epsilon、Depth window 和误差容差仍须 R0-Numeric 定标并经复审；在三份权威 spec 修改前禁止进入 UE。

### 2026-08-09 — [用户批准实施/R0 PASS] Stage C 数值合同冻结，进入 R1

用户明确批准 Rev B 直接推进到落地。UEAgent 重新走 gate：route 指向 `127.0.0.1:8000/mcp`，doctor `HEALTHY/LIVE_READ`，Niagara authoring 与 advanced capability probe 均通过。live 只读审计确认候选 7 条 Niagara 脚本 `UpToDate`、0 error/0 warning，两条 Simulation Stage 仍存在；场景组件覆盖为 40k/K64/0.03，2 RT + Grid2D 均 2048²。

R0 reference `scratch/p0_mainline_20260806/p0c_r0_numeric_reference.py` 已通过 operator、half、cluster 全部自动 Gate，并用既有 2048² Gate B 实测与冻结解析核峰值定标：`D_ref=0.003`，`ε_D=2^-13`、`ε_S=2^-18`、`ε_Z=2^-20`、`ε_Tensor=2^-12`、`ε_Variance=0.002`；`PilotSupportAbort=0.01`、Pilot/Main front window=`1/128,1/64`、Sigma warn/reject=`0.01/0.03`。常量、脉冲、积分、粒子率、扩核峰值和 signed-band half 重建均通过；cluster 90 个稳定样例 0 分类错误。Density half 相对误差 p99=`0.0421%`，MeanDepth 绝对误差 p99=`0.0005245`；当前工作深度 Sigma p95 绝对误差最坏 `0.00477`。远深度 `z=0.9` 的 Sigma p95 误差达 `0.02481`，已明确登记为 RGBA16F 原始二阶矩相减限制：Sigma 只能降低 Confidence，禁止扩大连接。完整证据在 `P0C-R0-NUMERIC-REPORT-20260809.md`，三份上游 spec、brief、backlog 与 Rev B 已同步。

R0 期间按内存安全路径启动一次 SIE：2048² RT 只在 UE 内按 32 行 strip 聚合，MCP/PowerShell 不接收像素数组，进程 guard 为 1 GiB，未复现 PowerShell 内存暴涨。该会话中 80k 粒子、ViewDepth、组件 active/tick、40k/K64 与 RT 尺寸均有效，但 `SSPR_ScreenUV` 全为 `(-1,-1)`，两张 Raw RT 全零；候选源相机外也尝试了只读 framing，现象不变。SIE 已停止并恢复执行前视口。该问题不推翻历史 Gate B，但成为 R1 的前置 current-frame 闭环：必须先定位本次会话 PrimaryView/Projection 失效，再做精确二进制备份和空 Stage C，禁止用 Stage C marker、源运动或全量 RT JSON 绕过。

### 2026-08-09 — [R1 PASS] Stage C、Field RT 所有权与冷启动同帧直通闭环

按 Rev B 在隔离候选新增 `SSPR Resolve Continuous Field` 与 `SSPR_ResolveContinuousField`，Stage 顺序为 A→B→C，Stage C 迭代 `User.SSPR_TrajectoryGrid`，其 P1 EnabledBinding 与 Stage B export text 完全一致，`bDisablePartialParticleUpdate=true`。新增 `User.SSPR_FieldMainRT`/`User.SSPR_FieldAuxRT`，均为系统自管 2048² RGBA16F；三条 Simulation Stage 脚本均 `UpToDate`，整套 Niagara 0 error/0 warning。正式 M3 和金标准未改。

R1 marker 只做当前帧 Raw Main/Aux point-load→Field Main/Aux，不含 History。fresh SIE 中四个用户变量解析到四个不同 DI，活动世界恰有四张对应 2048² RGBA16F RT。首个聚合脚本错误地把 TextureRT 数字后缀当成 DI 角色后缀，打印了假 `pass:false`；其原始统计已经呈现两组精确配对。纠正对象映射后的中心 1024² probe 对 Main/Aux 两组共比较 2,097,152 像素、8,388,608 通道值，逐通道最大绝对差为 0、mismatch 全 0，且均 finite/non-empty，因此该假失败已被正式取代。

Pre-R1 备份为 `Saved/CodexBackups/P0_StageC_PreR1_20260809-145211/`，SHA-256=`A2436A9B…E2CB4C0`；R1-pass 备份为 `Saved/CodexBackups/P0_StageC_R1_Pass_20260809-153000/`，1,322,287 bytes，SHA-256=`6517FDA40CE6715AC587A0B0F79578ACA8EE2041365B2485A0FD2E945E2CB4C0`。一帧 ProfileGPU 仅作归因：A/sort/B/C 约 `0.05/0.19/1.01/0.51 ms`；整帧受长 Python 调用后的 fixed-tick 追帧和金标准系统共同运行污染，不作为性能 Gate。完整报告见 `P0C-R1-STAGEC-CLOSURE-REPORT-20260809.md`。当前进入 R1.5；临时微基准 HLSL 必须在 R1.5 后被生产 Pilot+Main 实现取代。

### 2026-08-09 — [R1.5 PASS] Resolve 微基准冻结首版 33-tap 预算

用可逆 synthetic carrier 对 Stage C 执行 resolution/tap/input/sampling/output/support 矩阵，运行态逐档证明候选实际使用 `512²/1024²/2048²` 的四张私有 RT 与一张 Grid；金标准和其他 PIE Niagara 均停用。2048² Point/2 Raw/2 UAV 的 Stage C 为：16 taps `0.84 ms`、24 taps `1.03 ms`、32 taps 重复 `1.42–1.47 ms`、48 taps `2.74 ms`。1 Raw/2 UAV/32 taps 为 `0.88 ms`；2 Raw/1 UAV 为 `1.50 ms`，说明输出 UAV 数不是主瓶颈。手工 Bilinear 等价 256 physical loads 达 `30.87 ms`，明确淘汰；25% checkerboard 仍为 `1.36 ms`，真实 density early-out 降至 `1.04 ms`。

首版冻结为 `9-tap isotropic Pilot + 24-tap shared Main = 33 total taps`、Point/Load、2 Raw、2 Field 与 Pilot support early-out；48 taps/Bilinear 不进入首版。编辑器被后台限制为 8 Hz，整帧包含 fixed-tick 追帧且有 `95–96 ms` 污染离群，故只把隔离 Stage event 用于本 Gate，完整帧仍须最终前台固定窗口 median/P95 A/B。Generated assembly 未由现有 Niagara authoring API 暴露，不伪造结论；不自动扩展到 RDG。完整矩阵和每个 Custom-HLSL SHA 见 `P0C-R15-RESOLVE-MICROBENCH-REPORT-20260809.md`。临时 carrier 已移除并恢复四 RT/一 Grid 为 2048²；生产 9+24 HLSL 已安装且静态回读 0 error/0 warning，下一步是真实 Raw→Field 数值闭环与 R1.6。

### 2026-08-09 — [R1.6 PASS] 生产连续场、对称 stencil 与 Synthetic Gate 闭环

生产 Stage C 已完成：2048² 单 dispatch 内使用 9-tap Pilot、24-tap Main、2 Raw Point/Load、2 Field UAV；核权重改为编译期常量，Pilot 失败时整个 Main gather/guide/depth/bands 分支不执行。初版非对称 stencil 的单脉冲质心漂移 `0.59 px`、镜像误差 `41.8%`，根因是 Point/floor 把 `±1.5` 量化成 `-1/+2` 且外环缺少反向配对；现已部署中心+`±2` Pilot、双半权中心、近/中对称环与六向外环。最终 HLSL SHA-256=`c87f1ca81c432ea21ac3090efc55bd26323432da2c49c759a77ee2dfa8682b8a`，Niagara `0 error/0 warning`。

live 映射独立证明 Managed Texture 数字后缀不等于 DI 后缀：RawAux=`DI0/Texture0`、RawMain=`DI1/Texture3`、FieldMain=`DI2/Texture2`、FieldAux=`DI3/Texture1`；后续禁止按后缀猜角色。四张 2048² RGBA16F RT 的 UE 内标量聚合通过 finite/non-empty/half/front-order/signed-reconstruction/SigmaReject 全部 Gate。对称 Synthetic 强制项全部通过，典型 blob 积分误差 `0.52%`、冲激质心/镜像误差均为 `0`、亚像素 `0.25 px` 位移测得 `0.24148 px`。生产优化把 Stage 从 `6.07/6.33/6.09 ms` 降至最终对称核干净样本 `3.14/1.94/2.04 ms`（中位数 `2.04 ms`）；`5.42 ms @ 101.36 ms frame` 是后台 8 Hz 追帧污染样本。完整证据和备份清单见 `P0C-R16-PRODUCTION-AND-SYNTHETIC-REPORT-20260809.md`。SIE 已停止；主线进入 R2 Body-only 材质 Gate，源运动继续冻结。

### 2026-08-09 — [R2 FAIL / Request Changes] V1～V6 坐实单次 Point compact-stencil 质量上限

按 Rev B 的 Body-only Gate 新建隔离 `R2_BodyDebug` 父材质/MI，Renderer 只消费 FieldMain/FieldAux 并显示 `B/F_body`；Medium、Filament、Depth lighting、Raw core 与 History 均关闭。先后执行六轮 current-frame closure：V1 扩 Pilot/Body 支撑并收紧 depth core；V2 把 9 个 Pilot 寄存器样本复用于 Main 累计；V3 明确 `5/11/24 px` 三尺度；V4 加像素交错 0°/22.5° dual-phase Point quadrature；V5 仅对 Pilot RawMain 做 valid-aware 手工 2×2 bilinear、Front/Main 保持 Point；V6 改为 4 个 D4 八点环的 `9 Pilot + 32 Main`。增益 8/14/20 与默认 sampler 的 Bilinear/Clamp/NoMip/non-streaming/linear-data 也分别排除。

V6 当前保存在隔离候选中：41 logical taps，RawMain/RawAux 物理读取=`68/41`，合计 `109`；Tight/Mid/Body 的非零 Main 权重为 `8/16/32`。HLSL SHA-256=`5bdb675e7646a818da807a0af8aae1692bb969635a3090e85fd6caaa289b65fc`、`173,546` chars，强制 reload 精确回读一致，Niagara 0 error/0 warning。System 文件 SHA-256=`48F9C1E9698667796062051D7A7727536CC0641B2DEB055AC49399BF40991F23`；MI 最终 BodyGain=14。33-tap R1.6 HLSL `c87f1ca8…b8a` 仍是批准的生产正确性/性能基线，V6 不升级为生产预算。

V6 synthetic schema `sspr-p0c-r2-body-closure-v6-dualphase-d4-41tap` 的全部强制项通过：常量误差 `4.0668e-05`、交叉转置误差 `0.0096749`、signed reconstruction `0.00039115`、典型 blob 积分误差 `0.0040427`、亚像素 L1 `0.074454`、双团空洞 Body/peak=`0.93194`；单/双层中心 confidence=`0.85010/0.048065`，全部 finite。live 2048² 聚合也通过 finite/non-empty/half/front-order/Sigma/signed density Gate，Body 正值像素约 `212,092`。运行 RT 数字后缀在 force reload 后再次变化，因此 `p0c_r16_live_field_stats.py` 已改为按通道合同动态识别四个角色，禁止按后缀猜映射。

画面 Gate 仍失败：V5 更平滑但 Body 偏薄；V6 Gain20 只把局部重复椭圆印章过曝成白膜，Gain14 去饱和后相同印章仍存在。无候选背景截图证明 `CaptureViewport` 会在整个天空产生全局点/条纹伪影；R2 的失败只依据 Body 内局部、随 Body 形状出现的重复椭圆 stencil，不把 capture 工具伪影混入结论。证据在 `Saved/CodexEvidence/P0_R2_Body/`，报告为 `P0C-R2-BODY-GATE-REPORT-20260809.md`。

性能上，33-tap 可比较基线中位仍为 `2.04 ms`；V6 spot 为 `2.89/6.90/9.00 ms`、中位 `6.90 ms`，但 `deltaSeconds=0.125`，受后台 8 Hz/fixed-tick 追帧污染，不能宣称正式性能失败。它只说明 109 loads 的成本方向上升；结合 R1.5 手工 Bilinear 256 loads=`30.87 ms` 与 V6 视觉仍失败，继续堆 tap/全面 bilinear 已无依据。

根因定性为执行后端而非参数：稀疏 Raw 经每像素独立的有限 Point compact stencil 后，其离散 impulse footprint 必然显形；扩大半径、相位交错和增益只改变印章尺度/相位/亮度。下一步在现有 Niagara 资产内使用 current-frame multipass + Niagara 自管 TempMain/TempAux，让 X/Y 连续逐 texel累计替代稀疏环形 tap。用户随后明确纠正执行边界：**禁止 native RDG、C++、USF、插件、引擎源码和项目源码修改**；此前把 RDG 提升为推荐生产方向属于越权判断，现已撤回并从当前 spec/brief/backlog 删除。R3～R7 与源运动保持冻结。

收尾已完成：SIE 独立确认 `running=false`、无脏 Content/Map；编辑器相机恢复并读回为 Location=`(-287.36989082890921,986.84100779236428,2579.6384621685947)`、Rotation=`(-4.7051612883806282,-156.46260058879855,7.8654392118147245e-7)`。V5 恢复点位于 `Saved/CodexBackups/P0_R2_BodyClosureV5_20260809-184100/`，其余 V1～V4、Gain 与 sampler 前恢复点均保留。正式 M3 与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 未改。

### 2026-08-10 — [R2.1/R3 通过，R4 结构通过但视觉 Request Changes，R5 Partial] Niagara-only 14-stage HQ

用户冻结了新的执行优先级：既有架构优化已经抬高性能下限，后续永远先以画面表现为主，只有画面达到气体标准而完整性能预算不足时才讨论降成本；当前禁止以降分辨率、减频带或删支撑换速度。实现边界继续是 Niagara/UE 资产内的同帧顺序 Simulation Stage 与 Niagara 自管 RT；未使用 RDG、C++、USF、插件、引擎源码或项目源码，Fountain/CurlNoise/Drag/Velocity 等源粒子运动保持冻结。

从失败 V6 复制到隔离活动候选 `/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1/NS_SSPR_V4Dev_P0_Multipass_HQ_V1` 后，先完成 R2.1 multipass Body：Body seed/Y 与 d2/d4/d8/d16 X/Y 连续逐 texel support-normalized 累计，替代有限 Point 椭圆 stencil。随后增加两段 `SSPR Medium Tensor Diffuse A/B`，按原始方向张量、深度和双侧支撑连接局部空洞并衰减孤立能量；最后保存 d4 TightBand、计算 `H=SupportedTight-(Body+Medium)`，把 `FieldMain` 固定为 `B/M/H/Q_BM`。当前系统精确为 14 段：Rasterize、Raw Resolve、Continuous Field seed、Body Y、d2/d4/d8/d16 X/Y、Medium A/B；Niagara 脚本均 UpToDate，0 error/0 warning。

运行数值 Gate 通过：Body sum=`1889.8359`，`|M|` sum=`337.374`，`|H|` sum=`459.048`，High 正/负像素=`81,985/126,515`，unsupported High nonzero=`0`，Tight carry error=`0`，canonical final 最大绝对误差=`3.0517578125e-05`，无 NaN/half saturation。R3 因 signed Medium 与两次扩散真实生效而结构/数值通过；R4 的 signed High、支撑/深度 Gate 与 canonical reconstruction 通过。通用 Hessian ridge 因形成闭环“脑纹/细胞边”被拒绝；只保留张量主轴 line ridge，90° 旋转对照近空，证明方向性成立，但世界图中的 ridge 仍偏短、偏弱，故 R4 视觉不能通过。

活动 HQ 资源为 2 Raw + 2 Field + 2 Temp + 1 TightBand，共七张 2048² RGBA16F，持久 RT 下限约 `224 MiB/单实例`，不含 NeighborQuery/Grid/UAV 临时与渲染开销。该成本只做诚实账本，不是当前降质理由。材质已隔离为 `R2_BodyDebug_HQ/M_SSPR_P0c_HQ_BandDebug` 与 `MI_SSPR_P0c_HQ_FieldBodyDebug`，Renderer 新增 `SSPR_RawMainTexture <- User.SSPR_SimRT`，提供 Mode 0～7 的 Body、signed Medium、B+M、Q、DepthConfidence、signed High、Tensor Ridge、Final 调试。v14 修复非预乘透明；v15 使用 `MeanDepth-FrontDepth` 与 FinalDensity 自遮蔽，Ridge 只调颜色、不扩大 Opacity。当前 Custom HLSL SHA-256=`b874173b88fcec8162a2d4452fe2091c10d420af850c2b5935c2cd13f50ef2ef`；保存参数为 Mode 7、`kM=1.0`、`kH=0.35`、FinalGain=`12`、Opacity=`0.85`、RidgeLightBoost=`0.55`、FinalColor=`(0.72,0.80,0.92,1)`，独立 reload/readback 通过。v16 烟灰高 Ridge 只得到稀疏亮点，已拒绝并恢复 v15。

当前最佳世界图为 `Saved/CodexEvidence/P0_HQ_FinalV15/P0_HQ_V15_Final_BalancedHigh_DepthVolumeLit_Mode7_40k_FixedCamera.png`。诚实视觉结论：Body 已连续且不再是粒子章、宽 Streamline 或规则椭圆印章，Medium/High 也已从连续场分频；但最终仍偏软团，张量细丝短且不连续，尚未达到 Niagara Fluids 参考的自然气体拉丝和体积层次。R4/R5 用户视觉 Gate 仍为 Request Changes；SceneDepth soft intersection、动态稳定与完整同机位性能 Gate 尚未完成。直接分带证据位于 `Saved/CodexEvidence/P0_HQ_BodyMediumV11/DirectBands/`、`Saved/CodexEvidence/P0_HQ_FilamentV12/DirectBands/` 与 `Saved/CodexEvidence/P0_HQ_FilamentV12/TensorLineRidges/`；精确资产备份位于 `Saved/CodexBackups/P0_HQ_FilamentV12_PreMaterialV13_20260810-004628/`。正式 M3、失败 RawMoments V6 与 `/Game/NewNiagaraSystem.NewNiagaraSystem` 均未修改。

最终收尾走 UEAgent 路由修复并显式使用 `ProcessGuardMaxPrivateMemoryMB=1024`；doctor 返回 `HEALTHY`。独立 live 读回先确认 SIE/PIE=`false`、Content/Map 脏包均为空，审核相机为固定机位 `(-592.975399,299.745966,3052.564758)`；随后只恢复编辑器视口相机，第二个独立请求精确读回 Location=`(-287.3698908289092,986.8410077923643,2579.6384621685947)`、Rotation=`(-4.705161094665527,-156.4626007080078,7.865439215493097e-7)`，并再次确认无脏包、SIE 停止。该相机操作没有保存关卡或资产。

### 2026-08-10 — [用户近景否决] 性能无问题，v15 粒子感未解决

按正确视觉 Gate 临时启动 SIE，在 PIE 世界把保存关卡中的 RawMoments 组件切换为 HQ v15、40k/K64；参考 Niagara Fluids 组件临时隐藏，审核相机推至候选 250 units，独立读回确认 HQ active/tick、参考 hidden、无脏包。用户明确结论是“粒子感根本没有被解决，性能倒是没有任何问题了”。因此此前“R2.1 Body 视觉通过、只剩拉丝与体积层次”的口径撤回；只能保留结构/数值与旧椭圆章消失的证据。

分带证据重新审计定位了重新显粒子的路径：`Direct_Body` 是较软的低频团；`Direct_SignedMedium` 出现块状局部正峰；`Direct_SignedHigh` 呈密集细胞状正负亮岛；`Direct_Final` 已把中心峰饱和成颗粒团。v15 保存参数 `kM=1.0/kH=0.35/FinalGain=12` 又让 M/H 进入 FinalDensity，而 Opacity 与自遮蔽均消费该 FinalDensity。即使 RidgeMask 本身只调颜色，raw H 仍通过密度路径贡献不透明度；这违反“Filament 不承担主体密度”的执行意图。根因不是性能不足，而是分带职责在最终集成时被破坏。

主线退回 R2.2：先以 Body-only 近景动态重新验收；Opacity 只允许 Body 与经过连接/低频 Gate 的 Medium，raw H 从 Opacity 完全移除，高频只有形成连续张量 line ridge 后才能调光。若 Body-only 仍可辨认粒子落点，则使用现有性能余量增加守恒扩散/低频迭代，不以 Stage/RT/采样预算阻止质量修复。之后按 Body→Medium→Ridge→Depth/Lighting 逐层重开，任何一层重新引入粒子感都立即判失败。审核 SIE 已停止，用户审核前相机 `(-32.030530582671055,539.4037055409782,2693.3892667059513)` / `(-20.57593321800232,225.5912970751524,0)` 已恢复并独立读回；Content/Map 无脏包，未保存关卡。

### 2026-08-10 — [R2.2 v33～v40 checkpoint / 视觉 FAIL] 离散章消失，但薄片与源轨迹条纹仍不是气体

live 结构审计发现，旧 18-stage 草案的执行顺序实际是 Medium A/B 位于 Body Closure 之前；后续 d32 Body 修改会在 Medium 之后重新注入未扩散 residual，违反“先形成完整 Body，再从同一连续场分频”的合同。由于现有服务没有 Stage reorder API，v33 通过重命名物理 Stage 槽位并交换模块 HLSL 职责完成等价纠正。当前精确顺序为：Rasterize、Raw Resolve、Continuous seed、Body Y、d2/d4/d8/d16 X/Y、Body Closure d32 X/Y、Medium A/B、两段 strict identity pass-through。六个相关模块精确回读一致，Niagara 全部 UpToDate、0 error/0 warning；7 张 2048² RGBA16F 持久 RT 账本不变。正式 M3、金标准、参考资产与源粒子运动均未改。

v34～v37 逐层纠正最终集成职责：soft supported-volume gate 清掉全卡 haze 和近零支撑尾部；Body 继续承担主体密度；Medium 先做连接/局部调制；raw High 从 Opacity 移除；连续 Ridge/Filament 只允许调光。结果证明单颗粒点、旧椭圆章和卡片背景可以去掉，且不会因 Ridge 重新出现；但主体退化为平滑二维薄片，内部仍沿输入轨迹出现重复条纹，缺少 Niagara Fluids 参考中的大中尺度卷吸、回流、涡团与自然耗散。

为排除“只是参数太弱”，v38 以 Medium-only/MediumGain=200 做 signed 诊断：有效 M 仍只集中在很小的中心区域，证明绝对 Medium 相对 Body 低一个量级。v39 改为 Body-relative normalized Medium 后，中频终于覆盖主体，却把密度挖成 Swiss-cheese/泡沫孔洞，直接判废。v40 将 normalized Medium 限制在 `[-0.35,+0.25] * BodyEnvelope`，对密度只做有限修正，主要通过深度矩、低频梯度和 signed Medium ratio 形成内部明暗；HighMix 保持 0，Filament/Ridge 只调光。父材质 HLSL SHA-256=`dbc0897d81e637b16fe1534cbb8435fa69fe2e6c46b62d05ee21d72e4a929127`，Mode 7 保存参数为 MediumGain=24、MediumMix=1.25、FinalGain=130、RidgeGain=0.4、RidgeLightBoost=0.2、OpacityScale=0.68、FinalColor=`(0.50,0.53,0.58,1)`；精确 readback、0 编译错误和无脏包均通过。

v40 证据为 `Saved/CodexEvidence/P0_HQ_R40_MediumShadingV40/P0_HQ_R40_MediumShading_Mode7_Close250_40k_Mature_v40.png`。孔洞比 v39 少，离散点/章和全卡 haze 未回归，但诚实 Gate 仍是 FAIL：它是带重复轨迹条纹的浅色薄片，不是有体积、有卷吸和自然拉伸/耗散的气体。用户所说“粒子感根本没有解决”应按整体视觉理解，不能用“离散点消失”替代验收。

从 v34～v40 的对照可见，重建端继续调参会在“过平/薄片”和“条纹/泡沫孔洞”之间摆动；当前输入轨迹没有提供可供连续场保留的大中尺度相干运动，后处理不能凭空发明 NS-like 涡团。按照此前登记的后置备选，下一项有证据的视觉实验应只在隔离 HQ 候选上调整源粒子运动，增加低频相干 curl/卷吸与尺度分离，不引入完整 NS，也不触碰 RDG、C++、USF、插件、引擎源码或项目源码。该范围尚需用户明确批准；批准前 Fountain/CurlNoise/Drag/Velocity 继续冻结。SIE 已停止，审核前相机已恢复为 `(-32.030530582671055,539.4037055409782,2693.3892667059513)` / `(-20.57593321800232,225.5912970751524,0)`。

### 2026-08-12 — [Gather-only 重启基线 PASS] 冻结 HQ，清空后处理

按用户要求先对当前 HQ 产物做逐文件备份，再另起独立 Content 文件夹，只保留粒子 Gather 架构。HQ 原目录 `/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1` 的 6 个文件已备份到 `Saved/CodexBackups/P0_Multipass_HQ_V1_PreGatherOnlyFork_20260812-152102/`；源与备份总计 `4,293,204` bytes，逐文件 SHA-256 mismatch=`0`。全部操作结束后再次比对，现行 HQ 与备份仍 mismatch=`0`，旧 HQ 未被删改。

新的唯一活动重启基线为 `/Game/SSPR_Validation/M3/Performance/P0_GatherOnly_Clean_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`。为避开 UE 5.8 `duplicate_asset(NiagaraSystem)` 导致 Scratch/Simulation Stage 运行时全零的已知陷阱，资产从 Stage-C-before 精确二进制恢复点注册到新包路径；保留旧 basename 以避免再次搬迁。系统精确只有两个 Simulation Stage：`SSPR Rasterize Trails`（粒子迭代/注册）与 `SSPR Resolve Grid To Material`（Grid2D 迭代/gather）。Scratch 模块只剩 InitAttrs、Projection、ResetVelocityAfterSolve、DisplayCardSetup、RasterizeWhiteParticles、ResolveGridToSimRT 与 P1_EmitterFrameGate；不存在 Continuous Field、Atrous、Closure、Tensor Diffuse、Pass Through、Streamline 或其他 Stage C。

Stage A/B HLSL 与冻结 HQ 中对应生产核逐字符一致，长度分别为 `1,981` 与 `9,359` chars；合同包含 `AddParticleWithRadius`、有界 `MaxRegistrationRadiusPx`、`ExecutionIndexToGridIndex`、`GetParticleNeighborCount/GetParticleNeighbor`、`ErfA=0.147`，以及 P0c Main=`Density/TensorCos2Sum/TensorSin2Sum/DepthMoment1`、Aux=`DepthMoment2/FrontDepth/VelocityMomentX/VelocityMomentY`。资源账本回到 1 个 2048² Grid2DCollection + 2 张 2048² RGBA16F Raw RT；旧 `DensityRaster`、`TrajectoryRT`、禁用 Sprite Renderer 与旧 HQ 外部材质依赖均已移除。

新建本地最小调试材质 `/Game/SSPR_Validation/M3/Performance/P0_GatherOnly_Clean_V1/M_SSPR_GatherRawDensity_Debug`，只执行 RawMain.R → DensityGain → Saturate → Emissive/Opacity，并绑定 `SSPR_RawMainTexture <- User.SSPR_SimRT.RenderTarget`。该画面只用于证明 Gather 连通，不能作为 Body、气体或最终视觉验收。系统 7 个脚本均 UpToDate、0 error/0 warning；材质 0 编译错误。40k/K64 的 SIE 独立运行抽样覆盖每张 RT 的 262,144 个像素：Raw0 非零 `69,352`、Raw1 非零 `65,459`，八通道全有限、nonfinite=`0`，证明新包不是“编译绿色但运行全零”。SIE 随后停止，系统/材质与 Content/Map 均无脏包。

本 checkpoint 没有修改正式数学 spec、插件、C++、USF、引擎源码、项目源码、正式 M3 或 `/Game/NewNiagaraSystem.NewNiagaraSystem`。后续从该 Gather-only 基线重新讨论和实现 Body-only，Body 视觉通过后才允许 Medium，随后才允许 Filament 与 Depth/Lighting；源粒子运动调整降为确有必要时的后置备选。

### 2026-08-12 — [GatherCompat BinarySafe 静态 PASS / 真实 SIE 待验] RecordPoint G5 后端接 Gather 前端

按用户确认的“保留当前最佳 RecordPoint 效果合同、只替换粒子采集前端”方向建立隔离候选 `/Game/SSPR_Validation/M3/Performance/P0_GatherCompat_RecordPoint_Binary_V1/NS_SSPR_V4Dev_RecordPoint_12ms`。先发现普通 `duplicate_asset` 原型存在 UE 5.8 已知的“编译绿色但 Scratch/Simulation Stage 运行全零”风险，故最终候选从 RecordPoint 文件 SHA-256=`746719ba4e72041f3be83be40674c5b9fd873389d33b37e0d53f839bee72d4ce` 做同 basename 原始二进制复制并经 Asset Registry 注册；原始二进制备份位于 `Saved/CodexBackups/GatherCompat_RecordPoint_Binary_V1_PreInstall_20260812_2150/`，哈希逐字一致。普通复制版只保留为结构原型，不具备运行认证。

候选保留 RecordPoint 的两段 Simulation Stage、2048² Grid2D/Main/Aux、G5 HQ Renderer/材质与所有后端字段语义，只替换前端：Stage A 使用保守全 footprint `AddParticleWithRadius`，`NeighborQuery_SetResolution.MaxCellsPerParticle=9`；Stage B 对 64×64 current cell 做 `K<=128` 的逐像素有界分层采样，直接计算各向异性 Gaussian，并输出 Main=`Density/Tensor.x/Tensor.y/MeanDepth`、Aux=`DepthSigma/FrontDepth/0/Coverage`。新增 `User.P0_MaxCandidatesPerCell=128`，旧 ParticleUpdate `AddParticleToNeighborQuery` 已停用，Resolve Stage 开启完整像素更新；旧 RasterizationGrid user DI 暂时保留为未引用回滚资产，不计入当前执行核。

最终 Stage A/B HLSL 长度分别为 `1,764`/`7,432` chars，SHA-256=`d64fa816230161ef71c6beb045eae344c5218e93fd7cd1c4fd369d8b709f08ad` 与 `12ea0dad48d47e191da110a63a694d6c0e180da5983d804999fbe10741f12238`。7 个 Niagara 脚本全部 `UpToDate`，aggregate 无 error/warning，Scratch compile messages 为空；Stack 仍有 3 个已有 DI Object warning（Emitter NeighborQuery、ParticleRead 与已禁用旧 writer 的 Reader），无 Stack error。最终候选文件 SHA-256=`f78af35b85cd6c6417b271bffd8cd397b306033017d6366088ea391657fb5520`；RecordPoint 源和 Gather Clean donor 分别保持 `746719…d4ce` 与 `ca989d…b824`，正式验证关卡未保存，Content/Map 脏包为空，候选瞬态组件为 0。

Editor World 瞬态 smoke 创建到两张 2048² RT，但中心 density 仍为零；同一 harness 对 RecordPoint 控制组连 RT 绑定都不能稳定成立，因此该结果不能认证候选失败或成功。真实运行 Gate 必须在用户批准的真实 SIE 实例中完成：确认 Main/Aux 非零且八通道 finite、近景动态无格子/成员抖动、与 RecordPoint 同机位效果对照，并采集完整 GPU median/P95。上述 Gate 通过前，此资产只登记为 BinarySafe 静态候选，不替换运行已验证的 `P0_GatherOnly_Clean_V1` 活动基线。

### 2026-08-13 — [Content 清理 PASS] SSPR 收敛为当前 M3 + V4 冻结闭包

按用户批准的“整个 SSPR 只保留与当前进度有关资源”执行全目录闭包清理。所有 live 删除前均先查 UE Asset Registry referencer，并对关键包做全项目 Content 二进制路径扫描；World Partition 遗留和注销后仍留在磁盘的文件只在 UnrealEditor 完全退出后按精确绝对路径迁移，没有通配删除。可恢复迁移集中到 `Saved/CodexBackups/SSPR_Cleanup_20260812_BeforeRestart/`，包含五张旧地图的 ExternalActor/ExternalObject 闭包、三个失败 NeighborGather 残留、Untitled 中精确绑定 `SSPR_ParticleTrails_Main` 的 ExternalActor、PingPong 残留 RT 与已注销空目录。终审再把 7 个递归文件数为 0 的旧空目录迁入 `EmptyDirectories`；Content 物理顶层也只剩 `M3` 与 `Versions`。

已移除根旧 M2 图/HLOD/ProjTest/旧 RT，两条 Archive 与 redirector，M2 Anisotropic/ParticleTrails/根 NS，Versions V1/V3，顶层旧 Performance/Recovery，以及 M3 PerfMinTest、三个错误 NeighborGather 候选、普通复制的 GatherCompat DenseG5 原型和旧 Multipass HQ。StarterMap 中唯一 Niagara Actor `NiagaraActor_3` 经组件 Asset 精确读回确认指向旧 HQ 后删除；只保存 StarterMap，随后 HQ referencer=0、资产 `exists=false`。旧 HQ sidecar 由 ReflectCache 隔离到 `Saved/UEAgent/cache-orphans`，没有当作 Content 资产保留。

最终 `/Game/SSPR_Validation` 从 192 个可见资产、851 个 External Actor、35 个 External Object、约 `223.96 MiB` 收敛为 40/154/10、`44,938,091` bytes（`42.86 MiB`）。Asset Registry 只剩 `M3` 29 个与 `Versions/V4` 11 个。RawMoments 整夹暂留不是视觉路线回退：GatherOnly 的 Camera/NeighborQuery/ParticleRead 内嵌默认对象仍指向其旧 NS 包。NeighborGather_V1 暂留不是候选复活：RecordPoint、ReaderWrapped 和 BinarySafe 三个保留系统的包内私有 DI 路径仍指向它。Versions V4 仍被当前 M3 验证图 ExternalActor 直接引用。这些嵌入依赖不会可靠出现在 Asset Registry referencer 中，后续必须先本地化 DI、验证 compile/runtime，再讨论删除。

重启后 UEAgent Doctor=`HEALTHY`；当前关卡是正式 M3 验证图且 `dirty=false`，MapCheck 0 error/0 warning。RecordPoint 与 GatherOnly 的 live compile state 均为 7/7 `UpToDate`、0 error、0 warning。正式 M3、ReaderWrapped、BinarySafe 的首次 `GetSystemCompileState` 在包加载处超时或返回 MCP 500，因此本轮不把它们登记为 live compile PASS/FAIL；三者源哈希匹配的 sidecar 均为 `FRESH`，且没有保存态路径指向已删除 SSPR 包，冷启动 live compile 仍留作后续独立 Gate。缓存终态 orphan=0；仅 RawMoments R2 BodyDebug 的材质/MI 两个 sidecar 为 stale，不用于当前状态判断。本轮未修改插件、C++、USF、引擎源码、项目源码或 `/Game/NewNiagaraSystem.NewNiagaraSystem`。完成终审后 UE 通过正常窗口关闭请求干净退出，没有强杀进程或留下后台内存占用。

### 2026-08-17 — [NeighborQuery_V1 静态结构 PASS / 真实运行待验] RecordPoint 只换 gather 前端

按用户要求先保护当前最佳 `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`，再在它的资源文件夹下建立隔离候选 `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NeighborQuery_V1/NS_SSPR_V4Dev_RecordPoint_12ms`。修改前备份位于 `Saved/CodexBackups/RecordPoint_PreNeighborQuery_20260817_1635/`；源与备份文件均为 `1,112,656` bytes、SHA-256=`746719ba4e72041f3be83be40674c5b9fd873389d33b37e0d53f839bee72d4ce`，原资产没有被覆盖。候选使用已经审计的 BinarySafe donor 做同 basename 二进制安装，最终文件为 `1,076,607` bytes、SHA-256=`f78af35b85cd6c6417b271bffd8cd397b306033017d6366088ea391657fb5520`；安装后 live load 成功，包内 self path 已正确重定位到新目录。

live 对照证明原 RecordPoint 的主 gather 实际使用 `RasterizationGrid3D`：Stage A 有 5 次 `InterlockedAddIntGridValue` 与 1 次 max，Stage B 有 6 次 `GetIntGridValue`；原栈里的 NeighborQuery writer 没有对应读取，只是死路径。新候选只替换这一前端：Stage A 精确回读含 `NeighborQuery.AddParticleWithRadius`，Stage B 含 `ExecutionIndexToGridIndex`、`GetParticleNeighborCount/GetParticleNeighbor`、ParticleRead 与 Main/Aux 写出，且两段均不再含任何 Raster 原子或读取调用。Stage A/B HLSL 长度为 `1,764`/`7,432` chars，SHA-256 分别为 `d64fa816230161ef71c6beb045eae344c5218e93fd7cd1c4fd369d8b709f08ad` 与 `12ea0dad48d47e191da110a63a694d6c0e180da5983d804999fbe10741f12238`；输出合同继续是 Main=`Density/Tensor.x/Tensor.y/MeanDepth`、Aux=`DepthSigma/FrontDepth/0/Coverage`。

源与候选仍是同一个 GPU Fountain emitter、同一 Emitter/Particle Spawn/Update 模块顺序、两段同名 Simulation Stage 和两只 Sprite Renderer；启用的 G5 Renderer 仍绑定 `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/MI_SSPR_AnisotropicSplat_G5_HQ_V4_Dev`，Main/Aux 仍绑定 `User.SSPR_SimRT`/`User.SSPR_AuxRT`，尺寸和格式仍为 2048² RGBA16F。17 个公共 User 参数的类型与默认值逐项相同。必要差异只有：旧 ParticleUpdate `AddParticleToNeighborQuery` 停用（避免重复注册）、`MaxCellsPerParticle 4→9`（覆盖半径 footprint）、新增 `User.P0_MaxCandidatesPerCell=128`。旧 `User.SSPR_DensityRaster` 作为未引用回滚字段保留；没有删除或改写后端。Scratch compile messages 为空，Content/Map 无脏包，未保存关卡，也未修改插件、C++、USF、引擎源码或项目源码。

当前 Gate 必须诚实停在“静态结构通过”。UE 日志会报告 `NiagaraDataInterfaceNeighborQuery - AddParticle should be in a particle-writing stage. Use at your own risk.`：当前 Stage A 虽按粒子迭代，仍是 side-effect-only Simulation Stage，尚不能仅凭编译与 HLSL 判定它在真实运行中注册正确。`GetSystemCompileState` 又会在该类内嵌 Simulation Stage System 上超时；同一接口对新鲜、未修改的 RecordPoint 副本也超时，故这是读端点问题，不作为候选损坏证据。下一 Gate 必须由真实场景/SIE 实例完成：两张 RT 非零且 finite、画面持续不清零、无成员抖动/格子断裂、与原 RecordPoint 同机位视觉对照，再采 GPU median/P95。通过前候选不替换原 RecordPoint。

### 2026-08-17 — [NeighborQuery_V1 运行数据 PASS / 用户动态视觉与性能待验] 4k/40k 同机位闭环

首次瞬态 PIE 启动候选时，组件虽然 active，但日志明确报告 `Source emitter 'None' not found` 与 `GPU particle read could not find GPU context for '...None'`。typed StackInput 读回定位到 `Emitter.P0_ParticleRead={bindingMode:Other, emitterName:None}`：该无效绑定继承自原 RecordPoint，在旧 RasterizationGrid3D 路径中从未真正读取粒子，所以此前没有阻断输出；NeighborQuery Stage B 开始调用 ParticleRead 后才成为真实运行故障。停 PIE 后只在隔离候选上把该 DI 改为 `Self`，typed 独立读回确认，保存后候选文件为 `1,120,421` bytes、SHA-256=`f6e93193ed219c5a11b420823863c12dd8305d830284e44c9a0b7bd5409196ed`。原 RecordPoint 与修改前备份继续逐字一致：`1,112,656` bytes、SHA-256=`746719ba4e72041f3be83be40674c5b9fd873389d33b37e0d53f839bee72d4ce`。

运行 harness 先暴露并修正了另一个假阴性：同一 PIE 同时存在 `/Memory/UEDPIE_...` 与 `/Game/.../UEDPIE_0_...` World，且初始玩家相机没有覆盖原点；在错误世界或错误相机下，候选和原版都会合法输出全零。最终固定实际 `/Game/` PIE World、相机 `(0,-2000,1000)` / `Pitch=-15,Yaw=90` 做 4k 连通性控制，再用 `(0,-900,600)` / `Pitch=-20,Yaw=90` 做 40k 同机位对照。原版控制组必须先得到非零 RT，之后才允许解释候选结果；RT 读回按四个 512² tile 覆盖中央 1024²，每张最多 1,048,576 pixels，避免 PowerShell/网关内存再次失控。

4k 候选两次跨帧读回均通过：首次两张 RT 的覆盖像素分别为 `51,316/51,316`，第二次为 `41,017/41,017`，所有通道 `nonfinite=0`，方向张量通道同时具有正负值，证明注册、ParticleRead gather、Main/Aux 写出和后续材质链真实执行且不是单帧残留。40k 对照中，原版两张 RT 的覆盖均为 `92,523` pixels，候选首次为 `131,756`、稍后为 `139,185`，三次读回均 `nonfinite=0`；候选 Main density 最大值为 `46.40625→38.25`，说明 half 范围内有限但与原版 `3.126953125` 的密度标定并不等价。证据为 `Saved/UEAgent/nq_runtime_40k_source_read.json`、`nq_runtime_40k_candidate_read.json`、`nq_runtime_40k_candidate_read_2.json`。

同一 40k 测试相机截图为 `Saved/CodexEvidence/NeighborQuery_V1_Runtime/RecordPoint_40k_source.png` 与 `RecordPoint_40k_candidate.png`。它们只证明两套前端都有可见输出：NeighborQuery 版在该独立时刻覆盖更宽、主体更亮；由于两套系统不是同一粒子时刻的 SimCache 重放，不能把形状差异当成逐像素等价结论，也不能据此通过动态视觉 Gate。引擎关于 side-effect-only `AddParticle` 的警告继续保留，但实际 4k/40k 跨帧输出已经证明它在此资产/配置中没有阻断注册。PIE 最终正常停止，瞬态组件移除，`dirtyContent=[]`、`dirtyMaps=[]`、PIE World=0；未保存关卡，未修改原 RecordPoint、正式 M3、材质后端、插件、C++、USF、引擎源码或项目源码。下一步仅做用户动态画面与密度标定审核；完整 GPU median/P95 仍按“视觉先行”原则后置。
